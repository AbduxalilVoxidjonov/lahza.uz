import { useState } from "react";

import { useT } from "../../i18n";

interface Props {
  query: string;
  onQuery: (q: string) => void;
  count: number;
  current: number;
  onNext: (dir: 1 | -1) => void;
  onReplace: (replacement: string, all: boolean) => void;
  busy: boolean;
}

export function SearchReplace(p: Props) {
  const t = useT();
  const [repl, setRepl] = useState("");
  return (
    <div className="row" role="search">
      <input
        className="input"
        style={{ width: 220 }}
        type="search"
        aria-label={t("tr.search")}
        placeholder={t("tr.search")}
        value={p.query}
        onChange={(e) => p.onQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            p.onNext(e.shiftKey ? -1 : 1);
          }
        }}
      />
      <span className="muted mono" aria-live="polite">
        {p.query ? t("tr.matches", { i: p.count ? p.current + 1 : 0, n: p.count }) : ""}
      </span>
      <button type="button" className="btn small" disabled={!p.count} onClick={() => p.onNext(-1)} aria-label={t("tr.prev")}>
        ↑
      </button>
      <button type="button" className="btn small" disabled={!p.count} onClick={() => p.onNext(1)} aria-label={t("tr.next")}>
        ↓
      </button>
      <input
        className="input"
        style={{ width: 180 }}
        aria-label={t("tr.replaceWith")}
        placeholder={t("tr.replaceWith")}
        value={repl}
        onChange={(e) => setRepl(e.target.value)}
      />
      <button type="button" className="btn small" disabled={!p.count || p.busy} onClick={() => p.onReplace(repl, false)}>
        {t("tr.replace")}
      </button>
      <button type="button" className="btn small" disabled={!p.count || p.busy} onClick={() => p.onReplace(repl, true)}>
        {t("tr.replaceAll")}
      </button>
    </div>
  );
}
