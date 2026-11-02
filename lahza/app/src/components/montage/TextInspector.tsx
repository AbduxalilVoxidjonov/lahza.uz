import type { TextItem } from "../../api/types";
import { useT, type MessageKey } from "../../i18n";
import { TEXT_ANIMS, TEXT_KINDS, TEXT_POSITIONS } from "../templates/TextCardEditor";
import { Check, ColorField, NumField, SelectField, TextField } from "./fields";

export function TextInspector({ item, total, onChange, onDelete }: {
  item: TextItem;
  total: number;
  onChange: (x: TextItem) => void;
  onDelete: () => void;
}) {
  const t = useT();
  const set = (p: Partial<TextItem>) => onChange({ ...item, ...p });
  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <strong>{t("mon.textItem")}</strong>
        <button type="button" className="btn small bad" onClick={onDelete}>{t("common.delete")} <kbd>Del</kbd></button>
      </div>
      <TextField label={t("tpl.cardText")} value={item.text} multiline onChange={(text) => set({ text })} />
      <div className="row" style={{ alignItems: "flex-end" }}>
        <NumField label={t("mon.start")} suffix="ms" value={item.start_ms} min={0} max={Math.max(0, item.end_ms - 1)} step={1}
                  onChange={(v) => set({ start_ms: Math.round(v) })} />
        <NumField label={t("mon.end")} suffix="ms" value={item.end_ms} min={item.start_ms + 1} max={Math.max(total, item.end_ms)} step={1}
                  onChange={(v) => set({ end_ms: Math.round(v) })} />
      </div>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <SelectField label={t("txt.kind")} value={item.kind}
                     options={TEXT_KINDS.map((k) => ({ value: k, label: t(`txt.kind.${k}` as MessageKey) }))}
                     onChange={(kind) => set({ kind, background: kind === "card" ? item.background ?? "#111111" : null })} />
        <SelectField label={t("txt.position")} value={item.position}
                     options={TEXT_POSITIONS.map((k) => ({ value: k, label: t(`pos.${k}` as MessageKey) }))}
                     onChange={(position) => set({ position })} />
        <SelectField label={t("txt.animation")} value={item.animation}
                     options={TEXT_ANIMS.map((k) => ({ value: k, label: t(`txt.anim.${k}` as MessageKey) }))}
                     onChange={(animation) => set({ animation })} />
      </div>
      <div className="row" style={{ alignItems: "flex-end" }}>
        {item.kind === "card" && (
          <ColorField label={t("txt.background")} value={item.background ?? "#111111"} onChange={(background) => set({ background })} />
        )}
        <Check label={t("mon.customFontSize")} checked={item.font_size != null}
               onChange={(on) => set({ font_size: on ? 72 : null })} />
        {item.font_size != null && (
          <NumField label={t("style.size")} value={item.font_size} min={16} max={240} onChange={(v) => set({ font_size: Math.round(v) })} />
        )}
      </div>
    </div>
  );
}
