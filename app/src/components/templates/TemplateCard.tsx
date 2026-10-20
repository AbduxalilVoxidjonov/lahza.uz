import type { ReactNode } from "react";

import { useFx } from "../../api/hooks";
import type { Template } from "../../api/types";
import { useT, type MessageKey } from "../../i18n";
import { fxName, localText } from "../../lib/montage";
import { useSettings } from "../../store/settings";

/** Aspect nisbatidagi kichik belgi (karta burchagida). */
export function AspectGlyph({ aspect }: { aspect: Template["aspect"] }) {
  const [w, h] = aspect === "9:16" ? [9, 16] : aspect === "1:1" ? [12, 12] : [16, 9];
  return (
    <span className="badge" title={aspect}>
      <span aria-hidden className="aspect-glyph" style={{ width: w, height: h }} />
      {aspect}
    </span>
  );
}

/** Shablon effektlarining qisqa ro'yxati: o'tish, harakat, rang. */
export function useTemplateFxSummary(tpl: Template): string[] {
  const fx = useFx();
  const locale = useSettings((s) => s.locale);
  const out: string[] = [];
  if (tpl.transition) out.push(fxName(fx.data, tpl.transition.plugin, locale));
  for (const r of tpl.fx ?? []) {
    const n = fxName(fx.data, r.plugin, locale);
    if (!out.includes(n)) out.push(n);
  }
  if (tpl.color) out.push(fxName(fx.data, tpl.color, locale));
  return out;
}

export function TemplateCard({ tpl, selected, actions, compact }: {
  tpl: Template;
  selected?: boolean;
  actions?: ReactNode;
  compact?: boolean;
}) {
  const t = useT();
  const locale = useSettings((s) => s.locale);
  const effects = useTemplateFxSummary(tpl);
  const name = localText(tpl.name, locale) || tpl.id;
  const desc = localText(tpl.description, locale);
  return (
    <article className={`card tpl-card${selected ? " active" : ""}`} aria-label={name}>
      <div className="tpl-cover" data-cat={tpl.category} aria-hidden>
        <span>{t(`tpl.cat.${tpl.category}` as MessageKey)}</span>
      </div>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <h3 className="tpl-title">{name}</h3>
        {!tpl.builtin && <span className="badge accent">{t("tpl.mine")}</span>}
      </div>
      {!compact && desc && <p className="muted tpl-desc">{desc}</p>}
      <div className="row" style={{ gap: 6 }}>
        <AspectGlyph aspect={tpl.aspect} />
        <span className="badge">{t("common.seconds", { n: Math.round(tpl.target_duration_ms / 1000) })}</span>
        <span className="badge">{t(`tpl.sel.${tpl.selection}` as MessageKey)}</span>
        {tpl.captions && <span className="badge">{t("tpl.captions")}</span>}
        {tpl.music?.required && <span className="badge warn">{t("tpl.musicRequired")}</span>}
      </div>
      {!compact && effects.length > 0 && (
        <p className="muted tpl-fx">
          <span className="sr-only">{t("tpl.effects")}: </span>
          {effects.join(" · ")}
        </p>
      )}
      {actions && <div className="row" style={{ marginTop: "auto" }}>{actions}</div>}
    </article>
  );
}
