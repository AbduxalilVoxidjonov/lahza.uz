import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useBundle, useHardware, useInstallBundle, useModels } from "../api/hooks";
import type { BundleItem } from "../api/types";
import { PackPanel } from "../components/settings/PackPanel";
import { CompatBadge, ErrorText, JobLine, QueryState, TierBadge } from "../components/ui";
import { LOCALE_NAMES, useT, type Locale } from "../i18n";
import { useJobs } from "../store/jobs";
import { LOCALES, useSettings } from "../store/settings";

const fmtSize = (b: number | null) => (b == null ? "—" : `${(b / 1024 ** 3).toFixed(1)} GB`);
const itemSize = (i: BundleItem) => i.entry?.files.reduce((a, f) => a + (f.size_bytes ?? 0), 0) ?? null;

/** Birinchi ishga tushirish (M2-APP-3): til, apparat, katalog to'plami, rozilik, o'rnatish. */
export function Onboarding() {
  const t = useT();
  const nav = useNavigate();
  const hw = useHardware();
  const bundle = useBundle();
  const models = useModels();
  const install = useInstallBundle();
  const job = useJobs((s) => (install.data ? s.jobs[install.data.id] : undefined));
  const { locale, setLocale } = useSettings();
  const [consent, setConsent] = useState(false);

  const items = bundle.data?.items ?? [];
  const asrReady = items.some((i) => i.task === "asr" && i.entry?.status === "approved");
  const total = items.reduce((acc, i) => acc + (itemSize(i) ?? 0), 0);
  const hasAsr = !!models.data?.defaults["asr"];
  const running = install.isPending || job?.status === "running" || job?.status === "queued";
  const failed = job?.status === "failed" || job?.status === "cancelled";

  return (
    <main className="onboarding">
      <div className="stack" style={{ maxWidth: 880, gap: 20, margin: "0 auto" }}>
        <div className="page-head">
          <div>
            <h1>{t("onb.title")}</h1>
            <p className="lead">{t("onb.lead")}</p>
          </div>
          <label className="field" style={{ width: 200 }}>
            {t("set.language")}
            <select className="select" value={locale} onChange={(e) => setLocale(e.target.value as Locale)}>
              {LOCALES.map((l) => (
                <option key={l} value={l} lang={l}>{LOCALE_NAMES[l]}</option>
              ))}
            </select>
          </label>
        </div>

        <section className="card stack" aria-labelledby="onb-hw">
          <h2 id="onb-hw">{t("onb.hardware")}</h2>
          <QueryState query={hw} />
          {hw.data && (
            <div className="stack" style={{ gap: 6 }}>
              <div className="row">
                <span>{t("onb.tier")}:</span> <TierBadge tier={hw.data.tier} />
                <span className="muted">{hw.data.reasons.join("; ")}</span>
              </div>
              <span className="muted mono">
                {hw.data.profile.cpu} · {hw.data.profile.ram_gb} GB RAM ·{" "}
                {t("onb.freeDisk", { n: hw.data.profile.free_disk_gb })} ·{" "}
                {hw.data.profile.gpus.map((g) => g.name).join(", ") || t("onb.noGpu")}
              </span>
            </div>
          )}
        </section>

        <section className="card stack" aria-labelledby="onb-bundle">
          <h2 id="onb-bundle">{t("onb.bundle")}</h2>
          <QueryState query={bundle} />
          <table className="table">
            <tbody>
              {items.map((i) => (
                <tr key={i.task}>
                  <td style={{ width: 220 }}>
                    {t(`task.${i.task}`)}
                    <div className="muted" style={{ fontSize: 12 }}>
                      {i.mandatory ? t("onb.mandatory") : t("onb.optional")}
                    </div>
                  </td>
                  <td>
                    {i.entry ? (
                      <>
                        {i.entry.name} <span className="muted mono">({i.entry.license})</span>
                      </>
                    ) : (
                      <span className="muted">{t("onb.none")}</span>
                    )}
                    <div className="muted" style={{ fontSize: 12 }}>{i.reason}</div>
                  </td>
                  <td style={{ width: 160 }}>
                    <CompatBadge compat={i.compat} />
                  </td>
                  <td className="mono muted" style={{ width: 80 }}>{fmtSize(itemSize(i))}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {bundle.data && !asrReady && (
            <div className="stack">
              <div className="notice warn" role="note">{t("onb.r0")}</div>
              <p className="muted">{t("onb.offline")}</p>
              <PackPanel importOnly />
            </div>
          )}

          {asrReady && (
            <>
              <label className="row check">
                <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                {t("onb.consent")}
              </label>
              {job && <JobLine job={job} />}
              {failed && <p className="muted">{t("onb.resumeHint")}</p>}
              <ErrorText error={install.error} />
            </>
          )}

          <div className="row">
            {asrReady && !failed && (
              <button type="button" className="btn primary" disabled={!consent || running || job?.status === "done"}
                      onClick={() => install.mutate()}>
                {t("onb.start")} {total > 0 && `· ${fmtSize(total)}`}
              </button>
            )}
            {asrReady && failed && (
              <button type="button" className="btn primary" disabled={running} onClick={() => install.mutate()}>
                {t("onb.resume")}
              </button>
            )}
            {(hasAsr || job?.status === "done") && (
              <button type="button" className="btn primary" onClick={() => nav("/projects")}>
                {t("onb.continue")}
              </button>
            )}
            <button type="button" className="btn ghost" onClick={() => nav("/projects")}>
              {t("onb.skip")}
            </button>
          </div>
        </section>
      </div>
    </main>
  );
}
