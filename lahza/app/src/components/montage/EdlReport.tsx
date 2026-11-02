import { useFx } from "../../api/hooks";
import type { MontageTimeline } from "../../api/types";
import { useT } from "../../i18n";
import { baseName } from "../../lib/dialog";
import { fxName, itemStarts, outDur } from "../../lib/montage";
import { useSettings } from "../../store/settings";
import { fmtTimePrecise } from "../ui";

/** Montaj hisoboti (EDL ko'rinishi): har element qayerdan olingani va nega (ADR-0013 - haqiqiy kadr). */
export function EdlReport({ tl, onSelect }: { tl: MontageTimeline; onSelect: (id: string) => void }) {
  const t = useT();
  const fx = useFx();
  const locale = useSettings((s) => s.locale);
  const starts = itemStarts(tl);
  const name = (id: string | undefined | null) => fxName(fx.data, id, locale);
  return (
    <div className="stack">
      <p className="muted" style={{ margin: 0 }}>{t("mon.edlLead")}</p>
      <div style={{ overflowX: "auto" }}>
        <table className="table edl">
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">{t("mon.edlOut")}</th>
              <th scope="col">{t("ed.source")}</th>
              <th scope="col">{t("mon.edlSrc")}</th>
              <th scope="col">{t("mon.edlFx")}</th>
              <th scope="col">{t("ed.reason")}</th>
            </tr>
          </thead>
          <tbody>
            {tl.video.map((it, i) => {
              const m = tl.media[it.media];
              const s = starts[i] ?? 0;
              const fxList = [
                it.transition_in ? `${name(it.transition_in.plugin)} (${it.transition_in.dur_ms} ms)` : "",
                ...it.fx.map((f) => name(f.plugin)),
                it.speed !== 1 ? `${it.speed}×` : "",
              ].filter(Boolean);
              return (
                <tr key={it.id}>
                  <td><button type="button" className="btn small ghost" onClick={() => onSelect(it.id)}>{i + 1}</button></td>
                  <td className="mono">{fmtTimePrecise(s)}–{fmtTimePrecise(s + outDur(it))}</td>
                  <td className="mono" title={m?.path}>{m ? baseName(m.path) : it.media}<br /><span className="muted">{m?.origin}</span></td>
                  <td className="mono">{fmtTimePrecise(it.src_in_ms)}–{fmtTimePrecise(it.src_out_ms)}</td>
                  <td>{fxList.join(", ") || "—"}</td>
                  <td>
                    {it.role && <span className="badge">{it.role}</span>} {it.reason || "—"}
                    {it.user_edited && <span className="badge accent">{t("mon.userEdited")}</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="muted" style={{ fontSize: 12 }}>
        {tl.color && <div>{t("tpl.color")}: {name(tl.color.plugin)}</div>}
        {tl.provenance.template_id && <div>{t("mon.template")}: <span className="mono">{tl.provenance.template_id} {tl.provenance.template_version}</span></div>}
        {tl.provenance.planner && <div>{t("mon.planner")}: {tl.provenance.planner}</div>}
        {(tl.provenance?.notes ?? []).length > 0 && (
          <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{(tl.provenance?.notes ?? []).map((n, i) => <li key={i}>{n}</li>)}</ul>
        )}
      </div>
    </div>
  );
}
