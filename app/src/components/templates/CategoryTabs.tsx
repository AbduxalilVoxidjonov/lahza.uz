import type { Template, TemplateCategory } from "../../api/types";
import { useT, type MessageKey } from "../../i18n";
import { TEMPLATE_CATEGORIES } from "../../lib/montage";

export type CategoryFilter = "all" | "mine" | TemplateCategory;

export function filterTemplates(list: Template[], f: CategoryFilter): Template[] {
  if (f === "all") return list;
  if (f === "mine") return list.filter((x) => !x.builtin);
  // "E'lon" toifasiga ta'lim e'lonlari ham kiradi - shablon o'z toifasida ko'rinadi.
  return list.filter((x) => x.category === f);
}

/** Galereya toifalari: Hammasi, Podkast, E'lon, ..., Mening shablonlarim. Bo'sh toifalar yashiriladi. */
export function CategoryTabs({ value, onChange, templates }: {
  value: CategoryFilter;
  onChange: (v: CategoryFilter) => void;
  templates: Template[];
}) {
  const t = useT();
  const present = new Set(templates.map((x) => x.category));
  const cats: CategoryFilter[] = [
    "all",
    ...TEMPLATE_CATEGORIES.filter((c) => c !== "boshqa" || present.has("boshqa")),
    "mine",
  ];
  return (
    <div className="tabs" role="tablist" aria-label={t("tpl.categories")}>
      {cats.map((c) => (
        <button
          key={c}
          type="button"
          role="tab"
          aria-selected={value === c}
          className={`tab${value === c ? " active" : ""}`}
          onClick={() => onChange(c)}
        >
          {c === "all" ? t("common.all") : c === "mine" ? t("tpl.mineTab") : t(`tpl.cat.${c}` as MessageKey)}
          <span className="muted mono"> {filterTemplates(templates, c).length}</span>
        </button>
      ))}
    </div>
  );
}
