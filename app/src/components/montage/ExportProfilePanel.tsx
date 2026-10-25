import type { ExportProfile, MontageTimeline } from "../../api/types";
import { useExportProfileEvaluation, useExportProfiles } from "../../api/hooks";
import { useEditorT } from "../../i18n/editor-extra";
import { applyRecommendedFormat, profileIssues } from "../../lib/export-profiles";
import { useDebounced } from "../../lib/useDebounced";
import { ErrorText } from "../ui";

export function ProfileChecks({ tl, profile }: { tl: MontageTimeline; profile: ExportProfile }) {
  const et = useEditorT();
  const issues = profileIssues(tl, profile);
  const delayed = useDebounced(tl, 350);
  const check = useExportProfileEvaluation(delayed);
  const result = delayed === tl ? check.data : undefined;
  return <div className="stack" aria-live="polite">
    <strong>{profile.name}</strong>
    {result ? <>
      {result.errors.map((message, i) => <div key={`e${i}`} className="notice bad" role="alert">{message}</div>)}
      {result.warnings.map((message, i) => <div key={`w${i}`} className="notice warn" role="note">{message}</div>)}
    </> : issues.map((issue, i) => <div key={`${issue.code}-${i}`} className={`notice ${issue.severity === "error" ? "bad" : "warn"}`} role={issue.severity === "error" ? "alert" : "note"}>
      {et(issue.code)} {issue.value}
    </div>)}
    {check.isFetching && <span className="muted" role="status">{et("loading")}</span>}
    <ErrorText error={check.error} />
    <span className="muted">{et("platformDisclaimer")}</span>
  </div>;
}

export function ExportProfilePanel({ tl, edit }: { tl: MontageTimeline; edit: (fn: (tl: MontageTimeline) => MontageTimeline) => void }) {
  const et = useEditorT();
  const profiles = useExportProfiles();
  const profile = profiles.data?.profiles.find(p => p.id === (tl.target_platform ?? "custom"));
  return <fieldset className="fieldset stack">
    <legend>{et("platform")}</legend>
    {profiles.isPending && <span role="status">{et("loading")}</span>}
    <ErrorText error={profiles.error} />
    {profiles.isError && <button type="button" className="btn" onClick={() => void profiles.refetch()}>{et("retry")}</button>}
    <label className="field">{et("platform")}
      <select className="select" disabled={!profiles.data} value={tl.target_platform ?? "custom"} onChange={e => {
        const selected = profiles.data?.profiles.find(p => p.id === e.target.value);
        if (selected) edit(x => ({ ...x, target_platform: selected.id }));
      }}>
        {!profiles.data && <option value={tl.target_platform ?? "custom"}>{tl.target_platform ?? "custom"}</option>}
        {profiles.data?.profiles.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
    </label>
    <button type="button" className="btn" disabled={!profile?.recommended_format} onClick={() => profile && edit(x => applyRecommendedFormat(x, profile))}>{et("applyFormat")}</button>
    <span className="muted">{et("applyFormatHint")}</span>
    {profile && <>
      <ProfileChecks tl={tl} profile={profile} />
      <span className="muted">{profile.safe_zone_note}</span>
      <span className="mono muted">{profile.recommendations.encoding} · {profile.verified_at}</span>
      <details><summary>{et("profileSources")}</summary>
        <ul>{profile.sources.map(s => <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.url}</a> · {s.verification_status}<p>{s.note}</p></li>)}</ul>
      </details>
    </>}
  </fieldset>;
}
