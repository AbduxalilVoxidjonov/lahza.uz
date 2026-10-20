import type { FxKind, FxRule, FxTrigger } from "../../api/types";
import { useFx } from "../../api/hooks";
import { useT, type MessageKey } from "../../i18n";
import { defaultParams } from "../../lib/montage";
import { FxParamsForm, FxSelect, useManifest } from "../montage/FxControls";
import { NumField, SelectField } from "../montage/fields";

const TRIGGERS: FxTrigger[] = ["on_start", "on_end", "on_cut", "on_emphasis", "on_speaker_change", "every_n"];
const RULE_KINDS: FxKind[] = ["motion", "speed", "audio"];

function RuleRow({ rule, index, onChange, onRemove }: {
  rule: FxRule; index: number; onChange: (r: FxRule) => void; onRemove: () => void;
}) {
  const t = useT();
  const manifest = useManifest(rule.plugin);
  return (
    <li className="card stack" style={{ gap: 8, padding: 12 }} aria-label={t("tpl.rule", { n: index + 1 })}>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <FxSelect label={t("tpl.plugin")} kinds={RULE_KINDS} value={rule.plugin}
                  onChange={(id) => id && onChange({ ...rule, plugin: id, params: {} })} />
        <SelectField label={t("tpl.trigger")} value={rule.trigger}
                     options={TRIGGERS.map((x) => ({ value: x, label: t(`trg.${x}` as MessageKey) }))}
                     onChange={(trigger) => onChange({ ...rule, trigger, every_n: trigger === "every_n" ? rule.every_n ?? 3 : rule.every_n })} />
        <button type="button" className="btn small ghost bad" onClick={onRemove} aria-label={t("tpl.removeRule", { n: index + 1 })}>
          {t("common.remove")}
        </button>
      </div>
      <div className="row" style={{ alignItems: "flex-end" }}>
        {rule.trigger === "every_n" && (
          <NumField label={t("tpl.everyN")} value={rule.every_n ?? 3} min={1} max={50}
                    onChange={(v) => onChange({ ...rule, every_n: Math.round(v) })} />
        )}
        <NumField label={t("tpl.maxCount")} value={rule.max_count ?? 0} min={0} max={100}
                  onChange={(v) => onChange({ ...rule, max_count: v > 0 ? Math.round(v) : null })} />
        <NumField label={t("tpl.minGap")} suffix="s" value={rule.min_gap_ms / 1000} min={0} max={60} step={0.1}
                  onChange={(v) => onChange({ ...rule, min_gap_ms: Math.round(v * 1000) })} />
      </div>
      <span className="muted" style={{ fontSize: 12 }}>{t("tpl.maxCountHint")}</span>
      <FxParamsForm manifest={manifest} params={rule.params} onChange={(params) => onChange({ ...rule, params })} />
    </li>
  );
}

export function FxRulesEditor({ rules, onChange }: { rules: FxRule[]; onChange: (r: FxRule[]) => void }) {
  const t = useT();
  const fx = useFx();
  const add = () => {
    const first = fx.data?.find((m) => m.kind === "motion");
    const plugin = first?.id ?? "uz.lahza.motion.punch-in";
    onChange([...rules, { plugin, trigger: "on_emphasis", params: defaultParams(first?.params), min_gap_ms: 1500, max_count: null, every_n: null }]);
  };
  return (
    <div className="stack" style={{ gap: 8 }}>
      {rules.length === 0 && <span className="muted">{t("tpl.noRules")}</span>}
      <ul className="stack plain-list" style={{ gap: 8 }}>
        {rules.map((r, i) => (
          <RuleRow key={i} rule={r} index={i}
                   onChange={(nr) => onChange(rules.map((x, j) => (j === i ? nr : x)))}
                   onRemove={() => onChange(rules.filter((_, j) => j !== i))} />
        ))}
      </ul>
      <div><button type="button" className="btn small" onClick={add}>{t("tpl.addRule")}</button></div>
    </div>
  );
}
