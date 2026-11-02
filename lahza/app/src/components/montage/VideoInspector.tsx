import { useFx } from "../../api/hooks";
import type { FxRef, ItemReframe, MediaRef, VideoItem } from "../../api/types";
import { useT } from "../../i18n";
import { baseName } from "../../lib/dialog";
import { clamp, defaultParams, outDur } from "../../lib/montage";
import { fmtTimePrecise } from "../ui";
import { FxParamsForm, FxSelect, useManifest } from "./FxControls";
import { Check, NumField, SelectField, Slider } from "./fields";

const REFRAMES: ItemReframe[] = ["auto", "focus", "fit_blur", "center"];

/** Manba vaqti: raqam (ms) + ±1 kadr tugmalari. */
function SrcTime({ label, value, frame, onChange }: { label: string; value: number; frame: number; onChange: (v: number) => void }) {
  const t = useT();
  return (
    <div className="row" style={{ gap: 4, alignItems: "flex-end", flexWrap: "nowrap" }}>
      <NumField label={label} suffix="ms" value={value} min={0} step={Math.round(frame)} onChange={(v) => onChange(Math.round(v))} />
      <button type="button" className="btn small ghost" onClick={() => onChange(Math.round(value - frame))}
              aria-label={t("mon.frameBack", { field: label })}>−1f</button>
      <button type="button" className="btn small ghost" onClick={() => onChange(Math.round(value + frame))}
              aria-label={t("mon.frameFwd", { field: label })}>+1f</button>
      <span className="mono muted" style={{ paddingBottom: 8 }}>{fmtTimePrecise(value)}</span>
    </div>
  );
}

function FxRow({ fx, onChange, onRemove, itemDur }: { fx: FxRef; onChange: (f: FxRef) => void; onRemove: () => void; itemDur: number }) {
  const t = useT();
  const manifest = useManifest(fx.plugin);
  const freeze = fx.plugin === "uz.lahza.speed.freeze";
  return (
    <li className="card stack" style={{ gap: 8, padding: 10 }}>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <FxSelect label={t("tpl.plugin")} kinds={["motion", "speed", "audio", "overlay"]} value={fx.plugin}
                  onChange={(id) => id && onChange({ ...fx, plugin: id, params: {}, source: "qolda" })} />
        <span className="badge">{t(`mon.fxSource.${fx.source}`)}</span>
        <button type="button" className="btn small ghost bad" onClick={onRemove}>{t("common.remove")}</button>
      </div>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <NumField label={t("mon.fxAt")} suffix="ms" value={fx.at_ms} min={0} max={Math.max(0, itemDur - 1)} step={50}
                  onChange={(at_ms) => onChange({ ...fx, at_ms: Math.round(at_ms), source: "qolda" })} />
        <NumField label={t("mon.fxDur")} suffix="ms" value={fx.dur_ms ?? 0} min={freeze ? 100 : 0} max={freeze ? 5000 : itemDur} step={50}
                  onChange={(d) => onChange({ ...fx, dur_ms: d > 0 ? Math.round(d) : null, params: freeze ? { ...fx.params, dur_ms: Math.round(d) } : fx.params, source: "qolda" })} />
      </div>
      <span className="muted" style={{ fontSize: 12 }}>{t("mon.fxDurHint")}</span>
      {!freeze && <FxParamsForm manifest={manifest} params={fx.params} onChange={(params) => onChange({ ...fx, params, source: "qolda" })} />}
    </li>
  );
}

export function VideoInspector({ item, index, count, media, fps, onChange, onMove, onDelete, onDuplicate }: {
  item: VideoItem;
  index: number;
  count: number;
  media: MediaRef | undefined;
  fps: number;
  onChange: (it: VideoItem) => void;
  onMove: (d: -1 | 1) => void;
  onDelete: () => void;
  onDuplicate: () => void;
}) {
  const t = useT();
  const fxAll = useFx();
  const trManifest = useManifest(item.transition_in?.plugin);
  const frame = 1000 / (fps > 0 ? fps : 30);
  const maxSrc = media?.duration_ms ?? Number.MAX_SAFE_INTEGER;
  const set = (p: Partial<VideoItem>) => onChange({ ...item, ...p, user_edited: true });
  const setIn = (v: number) => set({ src_in_ms: clamp(v, 0, item.src_out_ms - Math.ceil(frame)) });
  const setOut = (v: number) => set({ src_out_ms: clamp(v, item.src_in_ms + Math.ceil(frame), maxSrc) });
  const crop = item.crop ?? { cx: 0.5, cy: 0.5, zoom: 1 };

  const addFx = () => {
    const m = fxAll.data?.find((x) => x.kind === "motion");
    const plugin = m?.id ?? "uz.lahza.motion.punch-in";
    set({ fx: [...item.fx, { plugin, at_ms: 0, dur_ms: null, params: defaultParams(m?.params), source: "qolda" }] });
  };

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <strong>{t("mon.itemN", { n: index + 1, total: count })}</strong>
        <span className="row" style={{ gap: 4 }}>
          <button type="button" className="btn small ghost" disabled={index === 0} onClick={() => onMove(-1)}
                  aria-label={t("mon.moveLeft")}>←</button>
          <button type="button" className="btn small ghost" disabled={index === count - 1} onClick={() => onMove(1)}
                  aria-label={t("mon.moveRight")}>→</button>
          <button type="button" className="btn small" onClick={onDuplicate}>{t("mon.duplicate")}</button>
          <button type="button" className="btn small bad" onClick={onDelete}>{t("common.delete")} <kbd>Del</kbd></button>
        </span>
      </div>
      <div className="muted" style={{ fontSize: 12 }}>
        <div className="mono" title={media?.path}>{t("ed.source")}: {media ? baseName(media.path) : item.media}</div>
        {item.role && <div>{t("mon.role")}: {item.role}</div>}
        {item.reason && <div>{t("ed.reason")}: {item.reason}</div>}
        <div>{t("mon.outDur")}: {fmtTimePrecise(outDur(item))}</div>
      </div>

      <fieldset className="fieldset stack">
        <legend>{t("mon.sec.range")}</legend>
        <SrcTime label={t("mon.srcIn")} value={item.src_in_ms} frame={frame} onChange={setIn} />
        <SrcTime label={t("mon.srcOut")} value={item.src_out_ms} frame={frame} onChange={setOut} />
        <Slider label={t("mon.speed")} value={item.speed} min={0.25} max={4} step={0.05} format={(v) => `${v.toFixed(2)}×`}
                onChange={(speed) => set({ speed })} />
      </fieldset>

      <fieldset className="fieldset stack">
        <legend>{t("mon.sec.audio")}</legend>
        <Check label={t("mon.mute")} checked={item.mute} onChange={(mute) => set({ mute })} />
        <Slider label={t("mon.volume")} value={item.volume_db} min={-60} max={12} step={0.5} format={(v) => `${v} dB`}
                disabled={item.mute} onChange={(volume_db) => set({ volume_db })} />
      </fieldset>

      <fieldset className="fieldset stack">
        <legend>{t("mon.sec.frame")}</legend>
        <SelectField label={t("tpl.reframe")} value={item.reframe}
                     options={REFRAMES.map((r) => ({ value: r, label: t(`reframe.${r}`) }))}
                     onChange={(reframe) => set({ reframe })} />
        <Check label={t("mon.manualCrop")} checked={!!item.crop} onChange={(on) => set({ crop: on ? crop : null })} />
        {item.crop && (
          <div className="row">
            <Slider label="X" value={crop.cx} min={0} max={1} step={0.01} format={(v) => v.toFixed(2)}
                    onChange={(cx) => set({ crop: { ...crop, cx } })} />
            <Slider label="Y" value={crop.cy} min={0} max={1} step={0.01} format={(v) => v.toFixed(2)}
                    onChange={(cy) => set({ crop: { ...crop, cy } })} />
            <Slider label={t("mon.zoom")} value={crop.zoom} min={1} max={4} step={0.05} format={(v) => `${v.toFixed(2)}×`}
                    onChange={(zoom) => set({ crop: { ...crop, zoom } })} />
          </div>
        )}
      </fieldset>

      <fieldset className="fieldset stack">
        <legend>{t("tpl.transition")}</legend>
        {index === 0 ? (
          <span className="muted">{t("mon.firstNoTransition")}</span>
        ) : (
          <>
            <div className="row" style={{ alignItems: "flex-end" }}>
              <FxSelect label={t("tpl.plugin")} kinds={["transition"]} value={item.transition_in?.plugin} allowNone
                        onChange={(plugin) => set({ transition_in: plugin ? { plugin, dur_ms: item.transition_in?.dur_ms ?? 400, params: {} } : null })} />
              {item.transition_in && (
                <NumField label={t("tpl.transitionDur")} suffix="ms" value={item.transition_in.dur_ms} min={0} max={3000} step={50}
                          onChange={(dur_ms) => item.transition_in && set({ transition_in: { ...item.transition_in, dur_ms: Math.round(dur_ms) } })} />
              )}
            </div>
            {item.transition_in && (
              <FxParamsForm manifest={trManifest} params={item.transition_in.params}
                            onChange={(params) => item.transition_in && set({ transition_in: { ...item.transition_in, params } })} />
            )}
          </>
        )}
      </fieldset>

      <fieldset className="fieldset stack">
        <legend>{t("mon.sec.fx")}</legend>
        {item.fx.length === 0 && <span className="muted">{t("mon.noFx")}</span>}
        <ul className="stack plain-list" style={{ gap: 6 }}>
          {item.fx.map((f, i) => (
            <FxRow key={i} fx={f} itemDur={outDur(item)}
                   onChange={(nf) => set({ fx: item.fx.map((x, j) => (j === i ? nf : x)) })}
                   onRemove={() => set({ fx: item.fx.filter((_, j) => j !== i) })} />
          ))}
        </ul>
        <div><button type="button" className="btn small" onClick={addFx}>{t("mon.addFx")}</button></div>
      </fieldset>
    </div>
  );
}
