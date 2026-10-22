import { useCallback, useEffect, useMemo, useState } from "react";
import type { EngineClient } from "../../../shared/src/engine";
import type { HostPlan } from "../../../shared/src/hostplan";
import type { Clip, Job, Template } from "../../../shared/src/types";
import { HostBridge, type BuildResult } from "../host/bridge";
import { homeDir } from "../host/discovery";
import { STRINGS, type Lang, type Strings } from "../i18n";
import { useEngine, type EngineState } from "./useEngine";
import { AE_PROJECT_NAME, clipDurationS, defaultOutDir, errorText, isAbsolutePath, lostItems, sortedClips } from "./workflow";

type Aspect = "9:16" | "1:1" | "16:9";
type Ortho = "official" | "ascii" | "new";

const bridge = new HostBridge();

function useLang(): [Lang, () => void] {
  const [lang, setLang] = useState<Lang>(() => {
    try {
      return localStorage.getItem("lahza.ae.lang") === "en" ? "en" : "uz";
    } catch {
      return "uz";
    }
  });
  const toggle = () =>
    setLang((l) => {
      const n = l === "uz" ? "en" : "uz";
      try {
        localStorage.setItem("lahza.ae.lang", n);
      } catch {
        /* ixtiyoriy */
      }
      return n;
    });
  return [lang, toggle];
}

export function App() {
  const [lang, toggleLang] = useLang();
  const t = STRINGS[lang];
  const { state, check, connectManual } = useEngine();
  const [tab, setTab] = useState<"reels" | "montage">("reels");
  const [outDir, setOutDir] = useState("");

  useEffect(() => {
    if (!bridge.available) {
      const h = homeDir();
      setOutDir(defaultOutDir(null, h?.home ?? null, h?.sep));
      return;
    }
    bridge
      .projectInfo()
      .then((p) => {
        const h = homeDir();
        setOutDir(defaultOutDir(p.project_dir, h?.home ?? null, h?.sep ?? (p.project_dir?.includes("\\") ? "\\" : "/")));
      })
      .catch(() => {
        const h = homeDir();
        setOutDir(defaultOutDir(null, h?.home ?? null, h?.sep));
      });
  }, []);

  return (
    <div className="app">
      <header className="row between">
        <strong>{t.title}</strong>
        <button className="link" onClick={toggleLang}>
          {t.lang}
        </button>
      </header>
      {!bridge.available && <p className="warn">{t.notInAE}</p>}
      <EnginePanel t={t} state={state} onRetry={check} onManual={connectManual} />
      {state.kind === "ok" && (
        <>
          <nav className="tabs" role="tablist">
            <button role="tab" aria-selected={tab === "reels"} onClick={() => setTab("reels")}>
              {t.tabReels}
            </button>
            <button role="tab" aria-selected={tab === "montage"} onClick={() => setTab("montage")}>
              {t.tabMontage}
            </button>
          </nav>
          <label className="field">
            <span>{t.outDir}</span>
            <input value={outDir} onChange={(e) => setOutDir(e.target.value)} spellCheck={false} />
          </label>
          {tab === "reels" ? (
            <ReelsTab t={t} client={state.client} outDir={outDir} />
          ) : (
            <MontageTab t={t} client={state.client} outDir={outDir} lang={lang} />
          )}
        </>
      )}
    </div>
  );
}

function EnginePanel(props: {
  t: Strings;
  state: EngineState;
  onRetry: () => void;
  onManual: (port: number, token: string) => void;
}) {
  const { t, state } = props;
  const [port, setPort] = useState("");
  const [token, setToken] = useState("");
  if (state.kind === "checking") return <section className="card muted">{t.engineChecking}</section>;
  if (state.kind === "ok")
    return (
      <section className="card ok">
        {t.engine}: {t.engineOk} · v{state.version}
      </section>
    );
  const msg = state.reason === "no-node" ? t.engineNoNode : state.reason === "stale" ? t.engineStale : t.engineDown;
  return (
    <section className="card bad">
      <p>
        <strong>{msg}</strong>
      </p>
      <p className="muted">{t.engineHint}</p>
      {state.detail && <p className="muted small">{state.detail}</p>}
      <button onClick={props.onRetry}>{t.retry}</button>
      <details open={state.reason === "no-node"}>
        <summary>{t.manual}</summary>
        <div className="row">
          <input placeholder={t.port} inputMode="numeric" value={port} onChange={(e) => setPort(e.target.value)} style={{ width: 80 }} />
          <input placeholder={t.token} value={token} onChange={(e) => setToken(e.target.value)} spellCheck={false} />
          <button disabled={!/^\d+$/.test(port) || !token} onClick={() => props.onManual(Number(port), token.trim())}>
            {t.connect}
          </button>
        </div>
      </details>
    </section>
  );
}

function Progress({ job, t }: { job: Job | null; t: Strings }) {
  if (!job) return null;
  return (
    <div className="progress" aria-label={t.progress}>
      <div className="bar" style={{ width: `${Math.round(job.progress * 100)}%` }} />
      <span className="small">
        {job.stage ?? job.status} · {Math.round(job.progress * 100)}%
      </span>
    </div>
  );
}

function ResultPanel({ t, plan, res }: { t: Strings; plan: HostPlan | null; res: BuildResult | null }) {
  if (!res && !plan) return null;
  const lost = lostItems(plan, res);
  return (
    <section className="card">
      <h3>{t.result}</h3>
      {res?.comp && (
        <p>
          {t.compMade}: <strong>{res.comp}</strong>
          {res.layers !== undefined && ` · ${res.layers} ${t.layers}`}
          {res.lines !== undefined && ` · ${res.lines} ${t.lines}`}
        </p>
      )}
      <h4>{t.notTranslated}</h4>
      {lost.length ? (
        <ul className="lost">
          {lost.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">{t.nothingLost}</p>
      )}
    </section>
  );
}

/** Kompozitsiya / karaoke tugmalari va natija — Reels va Montaj tablari uchun umumiy. */
function BuildActions(props: { t: Strings; getPlan: () => Promise<HostPlan>; disabled: boolean; extra?: React.ReactNode }) {
  const { t } = props;
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState<HostPlan | null>(null);
  const [res, setRes] = useState<BuildResult | null>(null);
  const [compName, setCompName] = useState<string | undefined>();
  const [err, setErr] = useState<string | null>(null);
  // Reja qaysi getPlan'dan olingan: karaoke uchun o'sha reja qayta ishlatiladi (montaj qayta yaratilmasin).
  const [planSrc, setPlanSrc] = useState<(() => Promise<HostPlan>) | null>(null);

  const run = async (karaoke: boolean) => {
    setBusy(true);
    setErr(null);
    try {
      const reuse = karaoke && plan && planSrc === props.getPlan;
      const p = reuse ? plan : await props.getPlan();
      setPlan(p);
      setPlanSrc(() => props.getPlan);
      const r = karaoke ? await bridge.buildKaraoke(p, compName) : await bridge.buildComp(p);
      if (!karaoke && r.comp) setCompName(r.comp);
      setRes(r);
    } catch (e) {
      setErr(errorText(e, t));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {props.extra}
      <div className="row">
        <button className="primary" disabled={props.disabled || busy} onClick={() => void run(false)}>
          {t.buildComp}
        </button>
        <button disabled={props.disabled || busy} onClick={() => void run(true)}>
          {t.buildKaraoke}
        </button>
      </div>
      {busy && <p className="muted">{t.working}</p>}
      {err && (
        <p className="error" role="alert">
          {t.error}: {err}
        </p>
      )}
      <ResultPanel t={t} plan={plan} res={res} />
    </>
  );
}

function useSelection(t: Strings) {
  const [paths, setPaths] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    setErr(null);
    try {
      const r = await bridge.selectedFootagePaths();
      setPaths(r.paths);
      if (!r.paths.length) setErr(t.noSelection);
      return r.paths;
    } catch (e) {
      setErr(errorText(e, t));
      return [];
    }
  }, [t]);
  return { paths, err, refresh };
}

function ReelsTab({ t, client, outDir }: { t: Strings; client: EngineClient; outDir: string }) {
  const sel = useSelection(t);
  const [job, setJob] = useState<Job | null>(null);
  const [episodeId, setEpisodeId] = useState<string | null>(null);
  const [clips, setClips] = useState<Clip[] | null>(null);
  const [clipId, setClipId] = useState<string | null>(null);
  const [aspect, setAspect] = useState<Aspect>("9:16");
  const [ortho, setOrtho] = useState<Ortho>("official");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const analyze = async () => {
    setErr(null);
    setClips(null);
    setClipId(null);
    const paths = await sel.refresh();
    const path = paths[0];
    if (!path) return;
    setBusy(true);
    try {
      const projectId = await client.ensureProject(AE_PROJECT_NAME);
      const imp = await client.importMedia(projectId, path);
      setEpisodeId(imp.episode_id);
      setJob(imp.job);
      await client.waitJob(imp.job.id, setJob);
      const cs = sortedClips(await client.clips(imp.episode_id));
      setClips(cs);
      setClipId(cs.find((c) => c.status !== "rad")?.id ?? null);
    } catch (e) {
      setErr(errorText(e, t));
    } finally {
      setBusy(false);
    }
  };

  const setStatus = async (c: Clip, status: Clip["status"]) => {
    if (!episodeId) return;
    try {
      await client.setClipStatus(episodeId, c.id, status);
      setClips((cs) => cs?.map((x) => (x.id === c.id ? { ...x, status } : x)) ?? null);
    } catch (e) {
      setErr(errorText(e, t));
    }
  };

  const getPlan = useCallback(() => {
    if (!episodeId || !clipId) return Promise.reject(new Error(t.noMoments));
    if (!isAbsolutePath(outDir)) return Promise.reject(new Error(t.outDir));
    return client.clipHostPlan(episodeId, clipId, { out_dir: outDir, aspect, orthography: ortho });
  }, [client, episodeId, clipId, outDir, aspect, ortho, t]);

  return (
    <section>
      <p className="muted small">{t.selectHint}</p>
      <button className="primary" disabled={busy} onClick={() => void analyze()}>
        {t.analyze}
      </button>
      {sel.paths[0] && (
        <p className="small">
          {t.file}: <code>{sel.paths[0]}</code>
        </p>
      )}
      {sel.err && <p className="muted">{sel.err}</p>}
      <Progress job={busy ? job : null} t={t} />
      {err && (
        <p className="error" role="alert">
          {t.error}: {err}
        </p>
      )}
      {clips && (
        <section className="card">
          <h3>{t.moments}</h3>
          {clips.length === 0 && <p className="muted">{t.noMoments}</p>}
          <ul className="clips">
            {clips.map((c) => (
              <li key={c.id} className={c.status === "rad" ? "rejected" : c.status === "qabul" ? "accepted" : ""}>
                <label className="row">
                  <input type="radio" name="clip" checked={clipId === c.id} onChange={() => setClipId(c.id)} />
                  <span className="grow">
                    <strong>{c.title || c.caption || c.id}</strong>
                    <br />
                    <span className="small muted">
                      {Math.round(c.score)} {t.score} · {clipDurationS(c).toFixed(1)} {t.seconds}
                      {c.reason ? ` · ${c.reason}` : ""}
                    </span>
                  </span>
                </label>
                <div className="row">
                  <button className="small" aria-pressed={c.status === "qabul"} onClick={() => void setStatus(c, "qabul")}>
                    {t.accept}
                  </button>
                  <button className="small" aria-pressed={c.status === "rad"} onClick={() => void setStatus(c, "rad")}>
                    {t.reject}
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <BuildActions
            t={t}
            getPlan={getPlan}
            disabled={!clipId}
            extra={
              <div className="row">
                <label className="field">
                  <span>{t.aspect}</span>
                  <select value={aspect} onChange={(e) => setAspect(e.target.value as Aspect)}>
                    <option value="9:16">9:16</option>
                    <option value="1:1">1:1</option>
                    <option value="16:9">16:9</option>
                  </select>
                </label>
                <label className="field">
                  <span>{t.orthography}</span>
                  <select value={ortho} onChange={(e) => setOrtho(e.target.value as Ortho)}>
                    <option value="official">{t.orthoOfficial}</option>
                    <option value="ascii">{t.orthoAscii}</option>
                    <option value="new">{t.orthoNew}</option>
                  </select>
                </label>
              </div>
            }
          />
        </section>
      )}
    </section>
  );
}

function MontageTab({ t, client, outDir, lang }: { t: Strings; client: EngineClient; outDir: string; lang: Lang }) {
  const sel = useSelection(t);
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [templateId, setTemplateId] = useState<string>("");
  const [name, setName] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    client
      .templates()
      .then((ts) => {
        setTemplates(ts);
        setTemplateId((id) => id || ts[0]?.id || "");
      })
      .catch((e: unknown) => setErr(errorText(e, t)));
    void sel.refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  const tpl = useMemo(() => templates?.find((x) => x.id === templateId) ?? null, [templates, templateId]);

  const getPlan = useCallback(async () => {
    if (!templateId) throw new Error(t.needTemplate);
    if (!sel.paths.length) throw new Error(t.needSources);
    if (!isAbsolutePath(outDir)) throw new Error(t.outDir);
    setErr(null);
    const m = await client.createMontage({
      name: name || undefined,
      template_id: templateId,
      sources: sel.paths.map((path) => ({ kind: "file" as const, path })),
    });
    setJob(m.job);
    try {
      await client.waitJob(m.job.id, setJob);
    } finally {
      setJob(null);
    }
    return client.montageHostPlan(m.montage_id, outDir);
  }, [client, templateId, sel.paths, outDir, name, t]);

  return (
    <section>
      <section className="card">
        <h3>{t.templates}</h3>
        {templates === null && !err && <p className="muted">{t.working}</p>}
        <ul className="templates">
          {templates?.map((x) => (
            <li key={x.id}>
              <label className="row">
                <input type="radio" name="tpl" checked={templateId === x.id} onChange={() => setTemplateId(x.id)} />
                <span className="grow">
                  {x.name[lang] ?? x.name.uz} <span className="small muted">· {x.aspect} · {Math.round(x.target_duration_ms / 1000)} s</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
        {tpl?.description && <p className="small muted">{tpl.description[lang] ?? tpl.description.uz}</p>}
      </section>
      <section className="card">
        <div className="row between">
          <h3>{t.sources}</h3>
          <button className="small" onClick={() => void sel.refresh()}>
            {t.refresh}
          </button>
        </div>
        {sel.paths.length ? (
          <ul className="small">
            {sel.paths.map((p) => (
              <li key={p}>
                <code>{p}</code>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">{sel.err ?? t.selectHint}</p>
        )}
      </section>
      <label className="field">
        <span>{t.montageName}</span>
        <input value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <Progress job={job} t={t} />
      {err && (
        <p className="error" role="alert">
          {t.error}: {err}
        </p>
      )}
      <BuildActions t={t} getPlan={getPlan} disabled={!templateId || !sel.paths.length} />
    </section>
  );
}
