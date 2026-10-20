import { useRef, type KeyboardEvent } from "react";

import { useT } from "../../i18n";
import type { PickedSource } from "./SourcePicker";

/**
 * Tanlangan manbalar tartibi. Klaviatura: element fokusda - Alt+↑/↓ (yoki Cmd/Ctrl+↑/↓) ko'chiradi,
 * Delete/Backspace olib tashlaydi.
 */
export function SelectedSources({ items, onChange }: { items: PickedSource[]; onChange: (v: PickedSource[]) => void }) {
  const t = useT();
  const refs = useRef<(HTMLLIElement | null)[]>([]);

  const move = (i: number, d: -1 | 1) => {
    const j = i + d;
    if (j < 0 || j >= items.length) return;
    const next = [...items];
    const [x] = next.splice(i, 1);
    if (x) next.splice(j, 0, x);
    onChange(next);
    requestAnimationFrame(() => refs.current[j]?.focus());
  };
  const remove = (i: number) => {
    onChange(items.filter((_, k) => k !== i));
    requestAnimationFrame(() => refs.current[Math.min(i, items.length - 2)]?.focus());
  };
  const onKey = (e: KeyboardEvent<HTMLLIElement>, i: number) => {
    if (e.target !== e.currentTarget) return;
    const mod = e.altKey || e.metaKey || e.ctrlKey;
    if (e.key === "ArrowUp" && mod) { e.preventDefault(); move(i, -1); }
    else if (e.key === "ArrowDown" && mod) { e.preventDefault(); move(i, 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); refs.current[i - 1]?.focus(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); refs.current[i + 1]?.focus(); }
    else if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); remove(i); }
  };

  if (!items.length) return <p className="muted">{t("mon.noneSelected")}</p>;
  return (
    <div className="stack" style={{ gap: 6 }}>
      <span className="muted" style={{ fontSize: 12 }}>{t("mon.orderHint")}</span>
      <ol className="stack plain-list" style={{ gap: 6 }} aria-label={t("mon.selected")}>
        {items.map((it, i) => (
          <li key={it.key} ref={(el) => { refs.current[i] = el; }} tabIndex={0} className="card row src-row"
              onKeyDown={(e) => onKey(e, i)}
              aria-label={t("mon.srcItem", { n: i + 1, name: it.label })}>
            <span className="mono muted" style={{ width: 22 }}>{i + 1}</span>
            <span className="badge">{t(`mon.kind.${it.source.kind}`)}</span>
            <span style={{ flex: 1, minWidth: 0 }}>
              <span style={{ fontWeight: 600 }}>{it.label}</span>
              {it.detail && <span className="muted mono src-detail"> {it.detail}</span>}
            </span>
            <button type="button" className="btn small ghost" disabled={i === 0} onClick={() => move(i, -1)}
                    aria-label={t("mon.moveUp", { name: it.label })}>↑</button>
            <button type="button" className="btn small ghost" disabled={i === items.length - 1} onClick={() => move(i, 1)}
                    aria-label={t("mon.moveDown", { name: it.label })}>↓</button>
            <button type="button" className="btn small ghost bad" onClick={() => remove(i)}
                    aria-label={t("mon.removeSrc", { name: it.label })}>✕</button>
          </li>
        ))}
      </ol>
    </div>
  );
}
