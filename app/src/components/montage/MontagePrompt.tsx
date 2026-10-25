import { useEditingAgentStatus } from "../../api/editing-agent";
import { resolvePromptMode, type PromptMode } from "../../lib/prompt-mode";
import { useState } from "react";
import { useT } from "../../i18n";
import { EditingAssistant } from "./EditingAssistant";
import type { ExportProfile, MontageTimeline } from "../../api/types";
import { useEditingAgentT } from "../../i18n/editing-agent";
import { useEditorT } from "../../i18n/editor-extra";
import { applyMontagePrompt, planMontagePrompt, promptPlanIsCurrent, type PromptPlan, type PromptSelection } from "../../lib/montage-prompt";

export function MontagePrompt({ tl, selection, profiles, edit }: {
  tl: MontageTimeline;
  selection: PromptSelection;
  profiles: ExportProfile[];
  edit: (fn: (timeline: MontageTimeline) => MontageTimeline) => void;
}) {
  const t = useT();
  const et = useEditorT();
  const at = useEditingAgentT();
  const status = useEditingAgentStatus();
  const [modeChoice, setMode] = useState<PromptMode | null>(null);
  const mode = resolvePromptMode(modeChoice, status.isSuccess && status.data.available);
  const [input, setInput] = useState("");
  const changeInput = (value: string) => { setMode(mode); setInput(value); };
  const [plan, setPlan] = useState<PromptPlan | null>(null);
  const [applied, setApplied] = useState(false);
  const current = !!plan && plan.input === input && promptPlanIsCurrent(plan, tl, selection);
  const canApply = current && !!plan?.changes.length && !plan.issues.length;
  return <section className="card stack">
    <h2>{t("quick.prompt")}</h2>
    <details className="quick-details"><summary>{t("quick.promptMode")}</summary>
    <label className="field">{at("mode")}
      <select className="select" value={mode} onChange={e => { setMode(e.target.value === "ai" ? "ai" : "local"); setPlan(null); setApplied(false); }}>
        <option value="local">{at("local")}</option><option value="ai">{at("ai")}</option>
      </select>
    </label>
    </details>
    {mode === "ai" ? <EditingAssistant tl={tl} selection={selection} edit={edit} prompt={input} onPromptChange={changeInput} /> : <>
    <p className="muted" style={{ margin: 0 }}>{t("quick.localHint")}</p>
    <div className="row">
      <button type="button" className="btn small" onClick={() => { changeInput(t("quick.example")); setPlan(null); setApplied(false); }}>Reels · {t("quick.warm")}</button>
      <button type="button" className="btn small" onClick={() => { changeInput("shorts format"); setPlan(null); setApplied(false); }}>YouTube Shorts</button>
    </div>
    <label className="field">{t("quick.prompt")}
      <textarea className="input" rows={3} maxLength={2000} value={input} onChange={e => { changeInput(e.target.value); setApplied(false); }} placeholder={t("quick.example")} />
    </label>
    <details><summary>{et("promptExamples")}</summary>
      <p>{et("promptHelp")}</p>
      <p>{et("promptLocal")}</p>
      <ul>
        <li><code>reels format; shorts format; youtube format</code> — {et("promptExampleAlternatives")}</li>
        <li><code>reels formati; shorts formati; youtube formati</code></li>
        <li><code>captions on; captions off; captions larger; captions smaller</code></li>
        <li><code>subtitr yoq; subtitr o‘chir; subtitr kattaroq; subtitr kichikroq</code></li>
        <li><code>warm color</code> / <code>iliq rang</code>; <code>cinematic color</code> / <code>kino rangi</code></li>
        <li><code>videoni Reels formatida qil; captionni kattalashtir; 3-soniyada stop-kadr qo‘y</code></li>
        <li><code>freeze selected at 3s for 1s</code></li>
        <li><code>tanlangan klipning 3-soniyasida 1 soniya stop-kadr</code></li>
        <li><code>caption "Hello" 1s–3s</code> / <code>subtitr "Salom" 1s–3s</code></li>
      </ul>
      <p>{et("promptCaptionScope")}</p>
    </details>
    <div className="row">
      <button type="button" className="btn" disabled={!input.trim()} onClick={() => { setPlan(planMontagePrompt(input, tl, selection, profiles)); setApplied(false); }}>{et("promptPlan")}</button>
      <button type="button" className="btn primary" disabled={!canApply} onClick={() => {
        if (!plan || !canApply) return;
        // Recheck inside the functional edit, against the actual current draft.
        edit(current => applyMontagePrompt(plan, current, selection) ?? current);
        setPlan(null); setApplied(true);
      }}>{et("promptApply")}</button>
    </div>
    {plan && <div className="stack" aria-live="polite">
      {!current && <div className="notice warn" role="alert">{et("promptStale")}</div>}
      <ol>{plan.changes.map((change, i) => <li key={i}>{et(change.kind)} {change.detail}</li>)}</ol>
      {plan.issues.map((issue, i) => <div key={i} className="notice warn" role="alert">{et(issue.code)} <code>{issue.command}</code></div>)}
      {!!plan.issues.length && <p>{et("promptBlocked")}</p>}
    </div>}
    {applied && <span role="status">{et("promptApplied")}</span>}
    </>}
  </section>;
}
