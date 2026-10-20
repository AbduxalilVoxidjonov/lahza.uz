import type { TextAnimation, TextCard, TextKind, TextPosition } from "../../api/types";
import { useT, type MessageKey } from "../../i18n";
import { Check, ColorField, NumField, SelectField, TextField } from "../montage/fields";

export const TEXT_KINDS: TextKind[] = ["card", "title", "hook", "cta", "lower_third"];
export const TEXT_POSITIONS: TextPosition[] = ["upper", "middle", "lower"];
export const TEXT_ANIMS: TextAnimation[] = ["none", "fade", "pop", "slide_up"];

/** Intro / hook / outro kartasi. `null` - o'chirilgan. */
export function TextCardEditor({ label, value, onChange, defaultKind }: {
  label: string;
  value: TextCard | null | undefined;
  onChange: (v: TextCard | null) => void;
  defaultKind: TextKind;
}) {
  const t = useT();
  const enabled = !!value;
  return (
    <div className="stack" style={{ gap: 8 }}>
      <Check label={label} checked={enabled}
             onChange={(on) => onChange(on ? {
               text: defaultKind === "cta" ? "{cta}" : "{sarlavha}",
               dur_ms: 2000,
               kind: defaultKind,
               background: defaultKind === "card" ? "#111111" : null,
               position: defaultKind === "hook" ? "upper" : "middle",
               animation: "fade",
             } : null)} />
      {value && (
        <div className="stack" style={{ gap: 8, paddingLeft: 22 }}>
          <TextField label={t("tpl.cardText")} value={value.text} onChange={(text) => onChange({ ...value, text })} />
          <span className="muted" style={{ fontSize: 12 }}>{t("tpl.cardVars")}</span>
          <div className="row" style={{ alignItems: "flex-end" }}>
            <NumField label={t("tpl.cardDur")} suffix="s" value={value.dur_ms / 1000} min={0.5} max={10} step={0.1}
                      onChange={(s) => onChange({ ...value, dur_ms: Math.round(s * 1000) })} />
            <SelectField label={t("txt.kind")} value={value.kind}
                         options={TEXT_KINDS.map((k) => ({ value: k, label: t(`txt.kind.${k}` as MessageKey) }))}
                         onChange={(kind) => onChange({ ...value, kind })} />
            <SelectField label={t("txt.position")} value={value.position}
                         options={TEXT_POSITIONS.map((k) => ({ value: k, label: t(`pos.${k}` as MessageKey) }))}
                         onChange={(position) => onChange({ ...value, position })} />
            <SelectField label={t("txt.animation")} value={value.animation}
                         options={TEXT_ANIMS.map((k) => ({ value: k, label: t(`txt.anim.${k}` as MessageKey) }))}
                         onChange={(animation) => onChange({ ...value, animation })} />
            {value.kind === "card" && (
              <ColorField label={t("txt.background")} value={value.background ?? "#111111"}
                          onChange={(background) => onChange({ ...value, background })} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
