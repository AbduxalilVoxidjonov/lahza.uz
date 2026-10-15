import type { ReactNode } from "react";

import { useFonts } from "../../api/hooks";
import type { LogoPosition, Orthography, StyleTemplate } from "../../api/types";
import { useT } from "../../i18n";
import { ListInput } from "../ListInput";
import { PathPicker } from "../PathPicker";
import { QueryState } from "../ui";
import { StyleLibrary } from "./StyleLibrary";

const POSITIONS: StyleTemplate["position"][] = ["lower", "middle", "upper"];
const ANIMATIONS: StyleTemplate["animation"][] = ["karaoke", "pop", "none"];
const ORTHS: Orthography[] = ["official", "ascii", "new"];
const LOGO_POS: LogoPosition[] = ["top_left", "top_right", "bottom_left", "bottom_right"];

type Change = (s: Partial<StyleTemplate>) => void;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="fieldset stack">
      <legend>{title}</legend>
      {children}
    </fieldset>
  );
}

function Num({ label, value, min, max, step = 1, onChange }: {
  label: string; value: number; min: number; max: number; step?: number; onChange: (v: number) => void;
}) {
  return (
    <label className="field" style={{ width: 120 }}>
      {label}
      <input className="input" type="number" min={min} max={max} step={step} value={value}
             onChange={(e) => {
               const v = Number(e.target.value);
               if (Number.isFinite(v)) onChange(Math.max(min, Math.min(max, v)));
             }} />
    </label>
  );
}

function Color({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="field">
      {label}
      <input type="color" value={value} onChange={(e) => onChange(e.target.value.toUpperCase())} />
    </label>
  );
}

function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="row muted check">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

/** Uslub tabi (M2-APP-7): StyleTemplate'ning barcha maydonlari va shablonlar kutubxonasi. */
export function StyleTab({ style, onChange, onReplace }: { style: StyleTemplate; onChange: Change; onReplace: (s: StyleTemplate) => void }) {
  const t = useT();
  const fonts = useFonts();
  // Glif tekshiruvidan o'tmagan shriftlar ko'rsatilmaydi (o'zbek harflari yo'q).
  const okFonts = [...new Set((fonts.data ?? []).filter((f) => f.ok).map((f) => f.family))].sort();
  const fontOptions = okFonts.includes(style.font_family) ? okFonts : [style.font_family, ...okFonts];

  return (
    <div className="stack">
      <StyleLibrary style={style} onLoad={onReplace} />

      <Section title={t("style.text")}>
        <div className="row">
          <label className="field" style={{ flex: 1 }}>
            {t("style.font")}
            <select className="select" value={style.font_family} onChange={(e) => onChange({ font_family: e.target.value })}>
              {fontOptions.map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </label>
          <Num label={t("style.size")} value={style.font_size} min={24} max={200} onChange={(v) => onChange({ font_size: v })} />
        </div>
        <QueryState query={fonts} />
        <div className="row">
          <Check label={t("style.bold")} checked={style.bold} onChange={(v) => onChange({ bold: v })} />
          <Check label={t("style.uppercase")} checked={style.uppercase} onChange={(v) => onChange({ uppercase: v })} />
        </div>
        <div className="row">
          <label className="field" style={{ flex: 1 }}>
            {t("style.position")}
            <select className="select" value={style.position} onChange={(e) => onChange({ position: e.target.value as StyleTemplate["position"] })}>
              {POSITIONS.map((p) => <option key={p} value={p}>{t(`pos.${p}`)}</option>)}
            </select>
          </label>
          <Num label={t("style.maxWords")} value={style.max_words} min={1} max={8} onChange={(v) => onChange({ max_words: v })} />
          <Num label={t("style.maxLines")} value={style.max_lines} min={1} max={3} onChange={(v) => onChange({ max_lines: v })} />
        </div>
      </Section>

      <Section title={t("style.colors")}>
        <div className="row">
          <Color label={t("style.primary")} value={style.primary_color} onChange={(v) => onChange({ primary_color: v })} />
          <Color label={t("style.highlight")} value={style.highlight_color} onChange={(v) => onChange({ highlight_color: v })} />
          <Color label={t("style.outline")} value={style.outline_color} onChange={(v) => onChange({ outline_color: v })} />
          <Num label={t("style.outlineWidth")} value={style.outline_width} min={0} max={20} step={0.5} onChange={(v) => onChange({ outline_width: v })} />
          <Num label={t("style.shadow")} value={style.shadow} min={0} max={10} step={0.5} onChange={(v) => onChange({ shadow: v })} />
        </div>
        <div className="row">
          <Check label={t("style.box")} checked={style.box} onChange={(v) => onChange({ box: v })} />
          {style.box && (
            <>
              <Color label={t("style.boxColor")} value={style.box_color} onChange={(v) => onChange({ box_color: v })} />
              <Num label={t("style.boxOpacity")} value={style.box_opacity} min={0} max={1} step={0.05} onChange={(v) => onChange({ box_opacity: v })} />
            </>
          )}
        </div>
      </Section>

      <Section title={t("style.animation")}>
        <div className="row">
          <label className="field" style={{ flex: 1 }}>
            {t("style.animation")}
            <select className="select" value={style.animation} onChange={(e) => onChange({ animation: e.target.value as StyleTemplate["animation"] })}>
              {ANIMATIONS.map((a) => <option key={a} value={a}>{t(`anim.${a}`)}</option>)}
            </select>
          </label>
          {style.animation === "pop" && (
            <label className="field" style={{ flex: 1 }}>
              {t("style.popScale")} <span className="mono">{style.pop_scale}%</span>
              <input type="range" min={100} max={160} step={5} value={style.pop_scale}
                     onChange={(e) => onChange({ pop_scale: Number(e.target.value) })} />
            </label>
          )}
        </div>
        <ListInput label={t("style.keywords")} value={style.keywords} onChange={(v) => onChange({ keywords: v })} />
      </Section>

      <Section title={t("style.cleanup")}>
        <label className="field">
          {t("style.orthography")}
          <select className="select" value={style.orthography} onChange={(e) => onChange({ orthography: e.target.value as Orthography })}>
            {ORTHS.map((o) => <option key={o} value={o}>{t(`orth.${o}`)}</option>)}
          </select>
        </label>
        <Check label={t("style.removeFillers")} checked={style.remove_fillers} onChange={(v) => onChange({ remove_fillers: v })} />
        <ListInput label={t("style.fillerWords")} value={style.filler_words} disabled={!style.remove_fillers}
                   onChange={(v) => onChange({ filler_words: v })} />
        <Check label={t("style.maskProfanity")} checked={style.mask_profanity} onChange={(v) => onChange({ mask_profanity: v })} />
        <ListInput label={t("style.profanityWords")} value={style.profanity_words} disabled={!style.mask_profanity}
                   onChange={(v) => onChange({ profanity_words: v })} />
      </Section>

      <Section title={t("style.logo")}>
        <PathPicker label={t("style.logoPath")} value={style.logo_path ?? ""}
                    onChange={(v) => onChange({ logo_path: v.trim() || null })}
                    options={{ extensions: ["png", "jpg", "jpeg", "webp"], filterName: "Logo" }} />
        {style.logo_path && (
          <div className="row">
            <label className="field" style={{ flex: 1 }}>
              {t("style.logoPosition")}
              <select className="select" value={style.logo_position} onChange={(e) => onChange({ logo_position: e.target.value as LogoPosition })}>
                {LOGO_POS.map((p) => <option key={p} value={p}>{t(`logo.${p}`)}</option>)}
              </select>
            </label>
            <label className="field" style={{ flex: 1 }}>
              {t("style.logoOpacity")} <span className="mono">{Math.round(style.logo_opacity * 100)}%</span>
              <input type="range" min={0} max={1} step={0.05} value={style.logo_opacity}
                     onChange={(e) => onChange({ logo_opacity: Number(e.target.value) })} />
            </label>
            <button type="button" className="btn small ghost" onClick={() => onChange({ logo_path: null })}>
              {t("common.remove")}
            </button>
          </div>
        )}
      </Section>
    </div>
  );
}
