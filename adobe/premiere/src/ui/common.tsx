import { createContext, useContext, type ReactNode } from "react";

import type { BuildResult, BuildStep } from "../host/adapter";
import { stepText, translate, warnText, type Locale, type TFunc } from "../i18n";

export const LocaleContext = createContext<Locale>("uz");

export function useT(): TFunc {
  const locale = useContext(LocaleContext);
  return (key, vars) => translate(locale, key, vars);
}

/** Brauzer/UXP localStorage - xato bersa jim (UXP'da mavjud, lekin ehtiyot). */
export const store = {
  get(key: string): string | null {
    try {
      return window.localStorage.getItem(`lahza.${key}`);
    } catch {
      return null;
    }
  },
  set(key: string, v: string) {
    try {
      window.localStorage.setItem(`lahza.${key}`, v);
    } catch {
      /* e'tiborsiz */
    }
  },
};

export function ProgressBar({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div style={{ width: `${pct}%` }} />
    </div>
  );
}

export function ErrorLine({ error }: { error: string | null }) {
  const t = useT();
  if (!error) return null;
  return (
    <div className="error" role="alert">
      {t("common.error", { msg: error })}
    </div>
  );
}

export function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function BuildProgress({ step }: { step: BuildStep | null }) {
  const t = useT();
  if (!step) return null;
  const label = stepText(t, step.key) + (step.detail ? ` · ${step.detail}` : "");
  return (
    <div className="stack-sm">
      <div className="muted small">{t("build.progress", { step: label, i: Math.min(step.index + 1, step.total), n: step.total })}</div>
      <ProgressBar value={step.total ? step.index / step.total : 0} />
    </div>
  );
}

export function BuildResultView({ result }: { result: BuildResult | null }) {
  const t = useT();
  if (!result) return null;
  return (
    <div className="stack-sm result">
      <div className="good">{t("build.done", { name: result.sequenceName, n: result.placedClips })}</div>
      <div className="muted small">{t("build.warnings")}</div>
      {result.warnings.length === 0 ? (
        <div className="small">{t("build.no_warnings")}</div>
      ) : (
        <ul className="warn-list">
          {result.warnings.map((w, i) => (
            <li key={i}>{warnText(t, w)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));
