import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import type { MontageTimeline } from "../../api/types";
import { ApiError, errorText } from "../../api/client";
import { useEditingAgentPlan, useEditingAgentPreview, useEditingAgentStatus } from "../../api/editing-agent";
import { contextStamp, reviewAgentPlan, RequestGate, selectedVideoId, type AgentContext, type parsePlan } from "../../lib/editing-agent";
import { useEditingAgentT } from "../../i18n/editing-agent";
import type { PromptSelection } from "../../lib/montage-prompt";

type Ticket = ReturnType<RequestGate["capture"]>;
type Proposal = { ticket: Ticket; result: ReturnType<typeof parsePlan>; changes: string[]; warnings: string[]; unresolved: string[] };
export function EditingAssistant({ tl, selection, edit, prompt, onPromptChange }: {
  tl: MontageTimeline; selection: PromptSelection;
  prompt: string; onPromptChange: (value: string) => void;
  edit: (fn: (timeline: MontageTimeline) => MontageTimeline) => void;
}) {
  const t = useEditingAgentT();
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [error, setError] = useState("");
  const [applied, setApplied] = useState(false);
  const [busy, setBusy] = useState(false);
  const status = useEditingAgentStatus();
  const planner = useEditingAgentPlan();
  const preview = useEditingAgentPreview();
  const gate = useRef(new RequestGate());
  const context = useRef<AgentContext>({ prompt, timeline: tl, selection, mode: "ai" });
  context.current = { prompt, timeline: tl, selection, mode: "ai" };
  gate.current.update(contextStamp(context.current));
  const request = useRef<AbortController | null>(null);
  const lock = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; request.current?.abort(); gate.current.update("unmounted"); };
  }, []);
  const current = !!proposal && gate.current.current(proposal.ticket);
  const available = status.isSuccess && !status.isError && status.data.available;
  const run = async (apply: boolean) => {
    if (lock.current || !available || !prompt.trim() || (apply && (!current || !!proposal?.unresolved.length))) return;
    lock.current = true; setBusy(true); setError(""); setApplied(false);
    const controller = new AbortController(); request.current = controller;
    const snapshot = context.current;
    const ticket = gate.current.capture();
    const live = () => mounted.current && gate.current.current(ticket);
    try {
      const args = { timeline: snapshot.timeline, selected_video_id: selectedVideoId(snapshot.selection), signal: controller.signal };
      const result = apply && proposal ? proposal.result : await planner.mutateAsync({ ...args, prompt: snapshot.prompt });
      if (!live()) return;
      // Refusals never enter the executor. Resolved plans pass through unchanged.
      const review = await reviewAgentPlan(result.plan, plan => preview.mutateAsync({ ...args, plan }));
      if (!live()) return;
      if (review.kind === "refused") {
        setProposal({ ticket, result, changes: result.changes, warnings: result.warnings, unresolved: review.unresolved });
        return;
      }
      const validated = review.preview;
      const next = validated.timeline;
      if (apply) {
        edit(draft => gate.current.current(ticket, contextStamp({ ...context.current, timeline: draft })) ? next : draft);
        setProposal(null); setApplied(true);
      } else setProposal({ ticket, result, changes: validated.changes, warnings: [...result.warnings, ...validated.warnings], unresolved: [] });
    } catch (e) {
      if (live()) {
        setProposal(null);
        setError(e instanceof ApiError && e.status === 409 ? t("stale") : e instanceof Error && e.message === "Invalid editing-agent plan response" ? t("invalidPlan") : e instanceof Error && e.message.startsWith("Invalid editing-agent preview") ? t("invalidPreview") : errorText(e));
      }
    } finally {
      lock.current = false;
      if (mounted.current) setBusy(false);
    }
  };
  return <div className="stack">
    <p className="muted">{t("capabilities")}</p>
    {status.isPending && <p role="status">{t("checking")}</p>}
    {status.isError && <div role="alert">{status.error instanceof Error && status.error.message === "Invalid editing-agent status response" ? t("invalidStatus") : errorText(status.error)} <button className="btn" disabled={status.isFetching} onClick={() => void status.refetch()}>{t("retryStatus")}</button></div>}
    {status.data && <div>
      {status.data.available ? <span>{t("available")}</span> : <span role="status">{t("unavailable")} {status.data.reason ?? t("missing")} <Link to="/settings">{t("settings")}</Link></span>}
      <button className="btn" disabled={status.isFetching || busy} onClick={() => void status.refetch()}>{t("refresh")}</button>
    </div>}
    <label className="field">{t("request")}
      <textarea className="input" rows={3} maxLength={2000} value={prompt} onChange={e => {
        const value = e.target.value;
        gate.current.update(contextStamp({ ...context.current, prompt: value }));
        onPromptChange(value); setApplied(false);
      }} />
    </label>
    <div className="row">
      <button className="btn" disabled={busy || !available || !prompt.trim()} onClick={() => void run(false)}>{busy ? t("working") : error ? t("retryPlan") : t("generate")}</button>
      <button className="btn primary" disabled={busy || !available || !current || !proposal?.changes.length || !!proposal?.unresolved.length} onClick={() => void run(true)}>{t("apply")}</button>
    </div>
    {error && <div role="alert" className="notice warn">{error}</div>}
    {proposal && <div aria-live="polite">
      {!current && <p role="alert">{t("stale")}</p>}
      <details><summary>{t("planModel")}</summary><p>{proposal.result.model_id}</p></details>
      {!!proposal.unresolved.length && <div role="alert" className="notice warn">
        <p>{t("refusal")}</p>
        <ul>{proposal.unresolved.map((reason, i) => <li key={i}>{reason}</li>)}</ul>
      </div>}
      <ol>{proposal.changes.map((change, i) => <li key={i}>{change}</li>)}</ol>
      {!proposal.changes.length && <p>{t("noChanges")}</p>}
      {proposal.warnings.map((warning, i) => <p className="notice warn" key={i}>{warning}</p>)}
    </div>}
    {applied && <p role="status">{t("applied")}</p>}
    <p className="muted">{t("localHint")}</p>
  </div>;
}
