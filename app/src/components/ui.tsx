import type { ReactNode } from "react";

import { errorText } from "../api/client";
import type { Compat, Job, Tier } from "../api/types";
import { useT, type MessageKey } from "../i18n";
import { uz } from "../i18n/uz";

/** Dinamik kalit lug'atda bormi (masalan, engine'dan kelgan bosqich nomi). */
export const isMessageKey = (k: string): k is MessageKey => k in uz;

export function ProgressBar({ value, label }: { value: number; label?: string }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="progress" role="progressbar" aria-label={label} aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div style={{ width: `${pct}%` }} />
    </div>
  );
}

export function TierBadge({ tier }: { tier: Tier }) {
  const t = useT();
  const cls = tier === "unsupported" ? "bad" : tier === "pro" ? "accent" : "good";
  return <span className={`badge ${cls}`}>{t(`tier.${tier}` as MessageKey)}</span>;
}

export function CompatBadge({ compat }: { compat: Compat | null }) {
  const t = useT();
  if (!compat) return null;
  const cls = compat === "recommended" ? "good" : compat === "slow" ? "warn" : "bad";
  return <span className={`badge ${cls}`}>{t(`compat.${compat}` as MessageKey)}</span>;
}

export function JobLine({ job, onCancel }: { job: Job; onCancel?: () => void }) {
  const t = useT();
  const stageKey = `stage.${job.stage ?? ""}`;
  const stage = job.stage ? (isMessageKey(stageKey) ? t(stageKey) : job.stage) : "";
  return (
    <div className="stack" style={{ gap: 6 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span>
          {job.status === "failed" ? (
            <span className="error" role="alert">{t("common.error", { msg: job.error ?? "" })}</span>
          ) : job.status === "cancelled" ? (
            <span className="muted">{t("job.cancelled")}</span>
          ) : job.status === "queued" ? (
            <span className="muted">{t("job.queued")}</span>
          ) : (
            stage && t("job.stage", { stage })
          )}
        </span>
        <span className="row">
          <span className="mono muted">{Math.round(job.progress * 100)}%</span>
          {onCancel && (job.status === "running" || job.status === "queued") && (
            <button className="btn small ghost" onClick={onCancel}>
              {t("job.cancel")}
            </button>
          )}
        </span>
      </div>
      <ProgressBar value={job.progress} label={stage || undefined} />
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="card muted">{children}</div>;
}

export function ErrorText({ error }: { error: unknown }) {
  const t = useT();
  if (!error) return null;
  return (
    <span className="error" role="alert">
      {t("common.error", { msg: errorText(error) })}
    </span>
  );
}

/** Server so'rovining yuklanish/xato holatlari bir xil ko'rinishda. */
export function QueryState({ query }: { query: { isLoading: boolean; error: unknown } }) {
  const t = useT();
  if (query.isLoading) return <span className="muted" role="status">{t("common.loading")}</span>;
  return <ErrorText error={query.error} />;
}

export const fmtTime = (ms: number) => {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
};


/** m:ss.d - timeline va kalit kadrlar uchun aniqroq vaqt. */
export const fmtTimePrecise = (ms: number) => {
  const s = Math.max(0, ms) / 1000;
  const m = Math.floor(s / 60);
  return `${m}:${(s % 60).toFixed(1).padStart(4, "0")}`;
};
