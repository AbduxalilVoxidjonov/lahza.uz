import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fill, licensesDictionaries, type LicensesMessages } from "../../i18n/licenses";
import {
  CATEGORY_ORDER, categoryCounts, componentTexts, ffmpegComponent, filterComponents, isUnresolved, licenseSummary,
  sortComponents, type CategoryFilter, type LicenseComponent, type LicenseData,
} from "../../lib/licenses";
import { useSettings } from "../../store/settings";

const PAGE = 100;

// JSON alohida chunk sifatida faqat panel ochilganda yuklanadi (bundle ichida, tarmoqsiz).
async function loadLicenses(): Promise<LicenseData> {
  const mod = await import("../../generated/licenses.json");
  return mod.default as unknown as LicenseData;
}

const catKey = (c: LicenseComponent["category"]) => `cat_${c}` as keyof LicensesMessages;

export function LicensesPanel() {
  const t = licensesDictionaries[useSettings((s) => s.locale)];
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<CategoryFilter>("all");
  const [limit, setLimit] = useState(PAGE);
  const [selected, setSelected] = useState<LicenseComponent | null>(null);
  const data = useQuery({ queryKey: ["third-party-licenses"], queryFn: loadLicenses, enabled: open, staleTime: Infinity });

  const all = useMemo(() => sortComponents(data.data?.components ?? []), [data.data]);
  const counts = useMemo(() => categoryCounts(all), [all]);
  const shown = useMemo(() => filterComponents(all, query, category), [all, query, category]);
  const ffmpeg = ffmpegComponent(all);
  useEffect(() => setLimit(PAGE), [query, category]);

  return (
    <section className="card stack" aria-labelledby="set-licenses">
      <details onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
        <summary><h2 id="set-licenses" style={{ display: "inline" }}>{t.heading}</h2></summary>
        <div className="stack" style={{ marginTop: 12 }}>
          <p className="muted">{t.intro}</p>
          {data.isLoading && <p className="muted">{t.loading}</p>}
          {data.isError && <p className="error" role="alert">{t.loadError}</p>}
          {data.data && <>
            <div className="row">
              <label className="field" style={{ flex: "1 1 260px" }}>
                {t.search}
                <input className="input" type="search" value={query} placeholder={t.searchPlaceholder}
                  onChange={(e) => setQuery(e.target.value)} />
              </label>
              <label className="field" style={{ width: 300 }}>
                {t.category}
                <select className="select" value={category} onChange={(e) => setCategory(e.target.value as CategoryFilter)}>
                  <option value="all">{t.all} ({counts.all})</option>
                  {CATEGORY_ORDER.filter((c) => counts[c] > 0).map((c) => (
                    <option key={c} value={c}>{t[catKey(c)]} ({counts[c]})</option>
                  ))}
                  <option value="unresolved">{t.unresolved} ({counts.unresolved})</option>
                </select>
              </label>
            </div>
            <p className="muted" style={{ margin: 0 }}>
              {t.summary}: {licenseSummary(shown).map(([lic, n]) => `${lic} (${n})`).join(", ")}
            </p>
            <p className="muted" aria-live="polite" style={{ margin: 0 }}>
              {fill(t.count, { shown: Math.min(limit, shown.length), total: shown.length })}
            </p>
            {shown.length === 0 ? <p className="muted">{t.empty}</p> : (
              <div style={{ maxHeight: 460, overflow: "auto" }}>
                <table className="table">
                  <thead>
                    <tr><th>{t.name}</th><th>{t.version}</th><th>{t.license}</th><th>{t.type}</th><th /></tr>
                  </thead>
                  <tbody>
                    {shown.slice(0, limit).map((c) => (
                      <tr key={c.id}>
                        <td>{c.name}{c.risk && <> <span className="badge error">{c.risk}</span></>}</td>
                        <td className="mono">{c.version}</td>
                        <td className={isUnresolved(c) ? "error" : undefined}>{c.license}</td>
                        <td className="muted">{t[catKey(c.category)]}</td>
                        <td><button className="btn" type="button" onClick={() => setSelected(c)}>{t.open}</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {shown.length > limit && (
              <button className="btn" type="button" onClick={() => setLimit((n) => n + PAGE)}>
                {fill(t.showMore, { n: Math.min(PAGE, shown.length - limit) })}
              </button>
            )}
            <div className="notice stack" style={{ gap: 6 }}>
              <strong>{t.lgplTitle}</strong>
              <p style={{ margin: 0 }}>{fill(t.lgplBody, { version: ffmpeg?.version ?? "?", url: ffmpeg?.url ?? "" })}</p>
            </div>
          </>}
        </div>
      </details>
      {selected && data.data && <LicenseDialog t={t} data={data.data} item={selected} onClose={() => setSelected(null)} />}
    </section>
  );
}

function LicenseDialog({ t, data, item, onClose }: {
  t: LicensesMessages; data: LicenseData; item: LicenseComponent; onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
  }, []);
  const texts = componentTexts(data, item);
  const meta: [string, string][] = [
    [t.license, item.license], [t.type, t[catKey(item.category)]], [t.via, item.via], [t.basis, item.basis],
    [t.attribution, item.attribution], [t.notes, item.notes], [t.source, item.url],
  ];
  return (
    <dialog ref={ref} className="card" onClose={onClose} aria-labelledby="license-dialog-title"
      style={{ width: "min(860px, 92vw)", maxHeight: "86vh", color: "inherit", padding: 20 }}>
      <div className="stack">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h3 id="license-dialog-title" style={{ margin: 0 }}>{item.name} <span className="muted mono">{item.version}</span></h3>
          <button className="btn" type="button" onClick={() => ref.current?.close()} autoFocus>{t.close}</button>
        </div>
        <table className="table">
          <tbody>
            {meta.filter(([, v]) => v).map(([k, v]) => (
              <tr key={k}><th style={{ width: 180 }}>{k}</th><td style={{ overflowWrap: "anywhere" }}>{v}</td></tr>
            ))}
          </tbody>
        </table>
        {texts.length === 0 ? <p className="muted">{t.noText} {item.url || "—"}</p> : texts.map((x, i) => (
          <section key={i} className="stack" style={{ gap: 6 }}>
            <strong className="mono">{x.title}</strong>
            <pre className="mono" style={{ whiteSpace: "pre-wrap", maxHeight: "50vh", overflow: "auto", margin: 0 }}>{x.body}</pre>
          </section>
        ))}
      </div>
    </dialog>
  );
}
