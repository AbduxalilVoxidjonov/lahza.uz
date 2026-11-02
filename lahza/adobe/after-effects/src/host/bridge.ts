// CEP -> ExtendScript ko'prigi: `window.__adobe_cep__.evalScript` ning promise o'rami.
// CSInterface.js ishlatilmaydi (Adobe litsenziyasi: faqat Adobe'dan olingan nusxa) — u ham ichida aynan
// `window.__adobe_cep__.evalScript(script, callback)` ni chaqiradi (CEP_12.x/CSInterface.js v12.0.0).
// Bajarilish xatosida callback "EvalScript error." satrini oladi (CSInterface: EvalScript_ErrMessage).

import type { HostPlan } from "../../../shared/src/hostplan";

export type EvalScriptFn = (script: string, callback: (result: string) => void) => void;

export const EVAL_SCRIPT_ERROR = "EvalScript error.";

export interface HostResult {
  ok: true;
  comp: string | null;
  warnings: string[];
}
export interface BuildResult extends HostResult {
  layers?: number;
  lines?: number;
}
export interface PathsResult extends HostResult {
  paths: string[];
}
export interface ProjectInfo extends HostResult {
  project_dir: string | null;
  version: string;
  host: string;
}

export class HostError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "HostError";
  }
}

interface CepGlobal {
  evalScript: EvalScriptFn;
  getSystemPath: (type: string) => string;
}

function cep(): CepGlobal | null {
  const w = globalThis as unknown as { __adobe_cep__?: CepGlobal };
  return w.__adobe_cep__ ?? null;
}

/** CEP ichida ishlayaptimi (brauzerda ochilgan panel — yo'q). */
export function inCep(): boolean {
  return cep() !== null;
}

/**
 * JS qiymatini ExtendScript (ES3) satr literaliga aylantiradi. JSON.stringify U+2028/U+2029 ni
 * qochirmaydi, ES3 da ular satr ichida qator oxiri hisoblanadi — shuning uchun qo'lda.
 */
export function jsxString(s: string): string {
  return JSON.stringify(s).replace(new RegExp("\\u2028", "g"), "\\u2028").replace(new RegExp("\\u2029", "g"), "\\u2029");
}

/** `getSystemPath("extension")` URI'sini fayl yo'liga (CSInterface.getSystemPath bilan bir xil qoida). */
export function uriToPath(uri: string): string {
  const p = decodeURI(uri);
  if (/^file:\/\/\/[A-Za-z]:/.test(p)) return p.slice("file:///".length);
  return p.replace(/^file:\/\//, "");
}

export class HostBridge {
  private loaded: Promise<void> | null = null;

  constructor(
    private evalFn: EvalScriptFn | null = cep() ? (s, cb) => cep()!.evalScript(s, cb) : null,
    private extensionPath: string | null = cep() ? uriToPath(cep()!.getSystemPath("extension")) : null,
    private timeoutMs = 120_000,
  ) {}

  get available(): boolean {
    return this.evalFn !== null;
  }

  /** Xom evalScript (natija satri). */
  eval(script: string): Promise<string> {
    const fn = this.evalFn;
    if (!fn) return Promise.reject(new HostError("After Effects topilmadi (panel CEP'dan tashqarida) / not running inside After Effects"));
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new HostError("ExtendScript javob bermadi / ExtendScript timed out")), this.timeoutMs);
      try {
        fn(script, (result) => {
          clearTimeout(timer);
          if (result === EVAL_SCRIPT_ERROR) reject(new HostError("ExtendScript xatosi / ExtendScript error"));
          else resolve(result);
        });
      } catch (e) {
        clearTimeout(timer);
        reject(new HostError(e instanceof Error ? e.message : String(e)));
      }
    });
  }

  /**
   * json2.jsx (agar JSON yo'q bo'lsa) va host.jsx yuklanganini kafolatlaydi. host.jsx manifest
   * `<ScriptPath>` orqali ham yuklanadi; bu yerda qayta yuklash — panel qayta ochilganda/dev'da xavfsiz.
   */
  ensureLoaded(): Promise<void> {
    if (!this.loaded) {
      const dir = this.extensionPath ? `${this.extensionPath.replace(/\\/g, "/")}/jsx/` : null;
      const script = dir
        ? `(function(){if(typeof JSON!=="object"||!JSON.stringify){$.evalFile(${jsxString(`${dir}json2.jsx`)});}` +
          `if(typeof lahza_buildComp!=="function"){$.evalFile(${jsxString(`${dir}host.jsx`)});}return "ok";})()`
        : `"ok"`;
      this.loaded = this.eval(script).then(
        () => undefined,
        (e: unknown) => {
          this.loaded = null;
          throw e;
        },
      );
    }
    return this.loaded;
  }

  /** `fn(arg1, ...)` ni chaqiradi; argumentlar satr literali sifatida uzatiladi; JSON javobni tekshiradi. */
  async call<T extends HostResult>(fn: string, ...args: (string | undefined)[]): Promise<T> {
    if (!/^lahza_[A-Za-z]+$/.test(fn)) throw new HostError(`noma'lum host funksiyasi: ${fn}`);
    await this.ensureLoaded();
    const argList = args.filter((a): a is string => a !== undefined).map(jsxString).join(", ");
    const raw = await this.eval(`${fn}(${argList})`);
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      throw new HostError(`host javobi JSON emas / host returned non-JSON: ${raw.slice(0, 200)}`);
    }
    const r = parsed as { ok?: unknown; error?: unknown; warnings?: unknown };
    if (r.ok !== true) throw new HostError(typeof r.error === "string" ? r.error : "host xatosi / host error");
    if (!Array.isArray(r.warnings)) (r as { warnings: string[] }).warnings = [];
    return parsed as T;
  }

  selectedFootagePaths() {
    return this.call<PathsResult>("lahza_selectedFootagePaths");
  }

  projectInfo() {
    return this.call<ProjectInfo>("lahza_projectInfo");
  }

  buildComp(plan: HostPlan) {
    return this.call<BuildResult>("lahza_buildComp", JSON.stringify(plan));
  }

  buildKaraoke(plan: HostPlan, compName?: string) {
    return this.call<BuildResult>("lahza_buildKaraoke", JSON.stringify(plan), compName);
  }
}
