import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { del, errorText, get, put } from "../../api/client";
import { licenseKeyDictionaries } from "../../i18n/license-key";
import {
  keyInputReady,
  licenseErrorCode,
  licensePanelVisible,
  stateTone,
  type LicenseStatus,
} from "../../lib/license-key";
import { useSettings } from "../../store/settings";

const KEY = ["license"] as const;

/**
 * Oflayn litsenziya kaliti (V1-3, ADR-0016). Engine bayrog'i (`licensing_enabled`) o'chiq bo'lsa -
 * standart holat - panel hech narsa chizmaydi. Tekshiruv engine'da, tarmoqsiz.
 */
export function LicensePanel() {
  const t = licenseKeyDictionaries[useSettings((s) => s.locale)];
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [done, setDone] = useState<"activated" | "removed" | null>(null);
  // Eski engine'da endpoint bo'lmasa (404) - panel shunchaki ko'rinmaydi.
  const status = useQuery({ queryKey: KEY, queryFn: () => get<LicenseStatus>("/v1/license"), retry: false });
  const onSettled = (data: LicenseStatus) => qc.setQueryData(KEY, data);
  const activate = useMutation({
    mutationFn: (key: string) => put<LicenseStatus>("/v1/license", { key }),
    onSuccess: (data) => { onSettled(data); setText(""); setDone("activated"); },
  });
  const remove = useMutation({
    mutationFn: () => del<LicenseStatus>("/v1/license"),
    onSuccess: (data) => { onSettled(data); setDone("removed"); },
  });
  const st = status.data;
  if (!licensePanelVisible(st) || !st) return null;

  const busy = activate.isPending || remove.isPending;
  const err = activate.error ?? remove.error;
  const errMsg = err ? errorText(err) : null;
  const code = errMsg ? licenseErrorCode(errMsg) : null;
  const lic = st.license;
  const range = lic && (lic.min_version || lic.max_version)
    ? `${lic.min_version ?? t.anyVersion} – ${lic.max_version ?? t.anyVersion}`
    : t.anyVersion;
  return (
    <section className="card stack" aria-labelledby="set-license">
      <h2 id="set-license">{t.heading}</h2>
      <p className="muted">{t.intro}</p>
      <div className="row" role="status">
        <strong>{t.status}:</strong>
        <span className={`badge ${stateTone(st.state)}`}>{t[`state_${st.state}`]}</span>
      </div>
      {lic && (
        <table className="table">
          <tbody>
            <tr><th>{t.licensee}</th><td>{lic.licensee}</td></tr>
            <tr><th>{t.edition}</th><td>{lic.edition}</td></tr>
            <tr><th>{t.issued}</th><td className="mono">{lic.issued}</td></tr>
            <tr><th>{t.expires}</th><td className="mono">{lic.perpetual ? t.perpetual : lic.expires}</td></tr>
            {(lic.max_devices != null || lic.device_locked) && (
              <tr><th>{t.devices}</th><td>{[lic.max_devices, lic.device_locked ? t.deviceLocked : null].filter((v) => v != null).join(" · ")}</td></tr>
            )}
            <tr><th>{t.versions}</th><td className="mono">{range}</td></tr>
          </tbody>
        </table>
      )}
      {st.device_id && (
        <div className="stack" style={{ gap: 2 }}>
          <span>{t.deviceId}: <span className="mono" style={{ userSelect: "all" }}>{st.device_id}</span></span>
          <span className="muted">{t.deviceHint}</span>
        </div>
      )}
      {st.state !== "not_configured" && (
        <fieldset disabled={busy} className="stack" style={{ border: 0, padding: 0 }}>
          <label className="field">
            {t.input}
            <textarea className="input mono" rows={3} value={text} placeholder={t.placeholder}
                      spellCheck={false} autoCapitalize="characters" autoComplete="off"
                      onChange={(e) => { setText(e.target.value); setDone(null); activate.reset(); }} />
          </label>
          <div className="row">
            <button type="button" className="btn" disabled={!keyInputReady(text)}
                    onClick={() => { setDone(null); remove.reset(); activate.mutate(text); }}>
              {busy ? t.busy : t.activate}
            </button>
            {lic && (
              <button type="button" className="btn ghost"
                      onClick={() => { if (window.confirm(t.confirmDeactivate)) { setDone(null); activate.reset(); remove.mutate(); } }}>
                {t.deactivate}
              </button>
            )}
          </div>
        </fieldset>
      )}
      {done && <span className="muted" role="status">{t[done]}</span>}
      {errMsg && <span className="error" role="alert">{code ? t[`err_${code}`] : errMsg}</span>}
    </section>
  );
}
