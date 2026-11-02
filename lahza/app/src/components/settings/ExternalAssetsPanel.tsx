import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { get, post, put, errorText } from "../../api/client";
import type { FxRef, MontageTimeline } from "../../api/types";
import { interopDictionaries } from "../../i18n/interop";
import { useSettings } from "../../store/settings";
import { PathPicker } from "../PathPicker";

interface Report {
  path: string;
  format: string;
  can_apply: boolean;
  importability: string;
  unsupported_features: string[];
  normalized: { fx?: FxRef; [key: string]: unknown };
}
interface Montage { id: string; name: string; status: string }

export function ExternalAssetsPanel() {
  const locale = useSettings((s) => s.locale);
  const t = interopDictionaries[locale];
  const [path, setPath] = useState("");
  const [mid, setMid] = useState("");
  const qc = useQueryClient();
  const inspection = useMutation({ mutationFn: (file: string) => post<Report>("/v1/interop/inspect", { path: file }) });
  const report = inspection.data;
  const montages = useQuery({ queryKey: ["interop", "montages"], queryFn: () => get<Montage[]>("/v1/montages"), enabled: !!report?.can_apply });
  const apply = useMutation({
    mutationFn: async () => {
      if (!report?.can_apply || !mid) throw new Error(t.choose);
      // Reinspect before apply; do not reuse a stale validation result after file changes.
      const checked = await post<Report>("/v1/interop/inspect", { path: report.path });
      if (!checked.can_apply || !checked.normalized.fx) throw new Error(t.no);
      const saved = await get<{ timeline: MontageTimeline | null }>(`/v1/montages/${encodeURIComponent(mid)}`);
      if (!saved.timeline) throw new Error(t.no);
      return put(`/v1/montages/${encodeURIComponent(mid)}/timeline`, { ...saved.timeline, color: checked.normalized.fx });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["montages"] });
      void qc.invalidateQueries({ queryKey: ["montage", mid] });
    },
  });
  const busy = inspection.isPending || apply.isPending;
  const ready = montages.data?.filter((m) => m.status === "ready") ?? [];
  return <section className="card stack" aria-label={t.title}>
    <h2>{t.title}</h2>
    <p className="muted">{t.notice}</p>
    <fieldset disabled={busy} style={{ border: 0, padding: 0 }}>
      <PathPicker label={t.path} value={path} onChange={(p) => { setPath(p); inspection.reset(); apply.reset(); }}
        options={{ extensions: ["cube", "srt", "prfpset", "mogrt", "ffx", "aep", "prproj", "aex", "plugin", "ccx", "zxp"] }} />
      <button className="btn" disabled={!path} onClick={() => { apply.reset(); inspection.mutate(path); }}>{busy ? t.busy : t.inspect}</button>
    </fieldset>
    {inspection.isError && <p role="alert">{errorText(inspection.error)}</p>}
    {!report && !inspection.isPending && <p className="muted">{t.empty}</p>}
    {report && <div className="stack">
      <p><strong>{report.format}</strong> · {report.importability} · {report.can_apply ? t.yes : t.no}</p>
      {report.unsupported_features.map((feature) => <p key={feature}>{feature}</p>)}
      <pre style={{ whiteSpace: "pre-wrap", maxHeight: 240, overflow: "auto" }}>{JSON.stringify(report.normalized, null, 2)}</pre>
      {report.can_apply && <>
        <label className="field">{t.montage}
          <select className="select" value={mid} disabled={busy} onChange={(e) => { setMid(e.target.value); apply.reset(); }}>
            <option value="">{t.choose}</option>
            {ready.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </label>
        {montages.isPending && <p role="status">{t.busy}</p>}
        {montages.isError && <p role="alert">{errorText(montages.error)}</p>}
        {!montages.isPending && ready.length === 0 && <p>{t.noMontages}</p>}
        <button className="btn" disabled={busy || montages.isFetching} onClick={() => void montages.refetch()}>{t.refresh}</button>
        <button className="btn" disabled={busy || !ready.some((m) => m.id === mid)} onClick={() => apply.mutate()}>{apply.isPending ? t.busy : t.apply}</button>
      </>}
    </div>}
    {apply.isError && <p role="alert">{errorText(apply.error)}</p>}
    {apply.isSuccess && <p role="status">{t.applied}</p>}
  </section>;
}
