import { useId, useState } from "react";

import type { LogoPosition, MediaRef, MontageTimeline, MusicItem } from "../../api/types";
import { useT, type MessageKey } from "../../i18n";
import { AUDIO_EXTS, baseName, hasNativeDialog, IMAGE_EXTS, pickPath } from "../../lib/dialog";
import { defaultParams } from "../../lib/montage";
import { useAddMontageMedia, useFx } from "../../api/hooks";
import { ErrorText } from "../ui";
import { StyleTab } from "../editor/StyleTab";
import { PathPicker } from "../PathPicker";
import { FxParamsForm, FxSelect, useManifest } from "./FxControls";
import { Check, NumField, Section, SelectField, Slider } from "./fields";

const LOGO_POS: LogoPosition[] = ["top_left", "top_right", "bottom_left", "bottom_right"];

type Edit = (fn: (tl: MontageTimeline) => MontageTimeline) => void;

function MusicRow({ m, path, onChange }: { m: MusicItem; path: string; onChange: (m: MusicItem) => void }) {
  const t = useT();
  return (
    <div className="stack" style={{ gap: 8 }}>
      <span className="mono muted" title={path}>♪ {baseName(path)}</span>
      <Check label={t("mon.duck")} checked={m.duck} onChange={(duck) => onChange({ ...m, duck })} />
      <div className="row" style={{ alignItems: "flex-end" }}>
        <Slider label={t("mon.musicGain")} value={m.gain_db} min={-60} max={6} step={0.5} format={(v) => `${v} dB`}
                onChange={(gain_db) => onChange({ ...m, gain_db })} />
        <NumField label={t("mon.fadeIn")} suffix="ms" value={m.fade_in_ms} min={0} max={10000} step={100}
                  onChange={(fade_in_ms) => onChange({ ...m, fade_in_ms })} />
        <NumField label={t("mon.fadeOut")} suffix="ms" value={m.fade_out_ms} min={0} max={10000} step={100}
                  onChange={(fade_out_ms) => onChange({ ...m, fade_out_ms })} />
      </div>
    </div>
  );
}

const MUSIC_DEFAULTS: Omit<MusicItem, "media"> = {
  src_in_ms: 0, start_ms: 0, end_ms: null, gain_db: -14, duck: true, fade_in_ms: 500, fade_out_ms: 1500,
};

/**
 * Musiqa qo'shish/almashtirish/olib tashlash. Fayl engine'da tekshiriladi (`POST /media`) va
 * montaj media'siga qo'shiladi; MusicItem esa draft'ga yoziladi (saqlash - umumiy "Saqlash" bilan).
 */
function MusicControls({ montageId, tl, edit }: { montageId: string; tl: MontageTimeline; edit: Edit }) {
  const t = useT();
  const id = useId();
  const add = useAddMontageMedia(montageId);
  const [path, setPath] = useState("");
  const native = hasNativeDialog();
  const has = tl.music.length > 0;

  const apply = (ref: MediaRef) =>
    edit((x) => ({
      ...x,
      media: { ...x.media, [ref.id]: ref },
      music: [{ ...MUSIC_DEFAULTS, ...(x.music[0] ?? {}), media: ref.id, src_in_ms: 0 }],
    }));
  const submit = (p: string) => {
    const v = p.trim();
    if (!v) return;
    add.mutate({ path: v, role: "music" }, { onSuccess: (res) => { apply(res.media); setPath(""); } });
  };
  const choose = () =>
    void pickPath({ title: t("mon.musicPick"), extensions: AUDIO_EXTS, filterName: t("mon.trackMusic") })
      .then((p) => p && submit(p));

  return (
    <div className="stack" style={{ gap: 6 }}>
      {native ? (
        <div className="row">
          <button type="button" className="btn small" disabled={add.isPending} onClick={choose}>
            {has ? t("mon.musicReplace") : t("mon.musicAdd")}
          </button>
          {has && (
            <button type="button" className="btn small ghost" onClick={() => edit((x) => ({ ...x, music: [] }))}>
              {t("mon.musicRemove")}
            </button>
          )}
        </div>
      ) : (
        <div className="field">
          <label htmlFor={id}>{t("mon.musicPath")}</label>
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <input id={id} className="input mono" value={path} placeholder="/…/music.mp3"
                   onChange={(e) => setPath(e.target.value)}
                   onKeyDown={(e) => { if (e.key === "Enter") submit(path); }} />
            <button type="button" className="btn small" disabled={add.isPending || !path.trim()} onClick={() => submit(path)}>
              {has ? t("mon.musicReplace") : t("mon.musicAdd")}
            </button>
            {has && (
              <button type="button" className="btn small ghost" onClick={() => edit((x) => ({ ...x, music: [] }))}>
                {t("mon.musicRemove")}
              </button>
            )}
          </div>
        </div>
      )}
      {add.isPending && <span className="muted" role="status">{t("mon.musicChecking")}</span>}
      <ErrorText error={add.error} />
    </div>
  );
}

/** Butun montajga oid sozlamalar: rang, subtitr, musiqa, ovoz, logo. */
export function GlobalPanel({ tl, edit, montageId }: { tl: MontageTimeline; edit: Edit; montageId: string }) {
  const t = useT();
  const fx = useFx();
  const colorManifest = useManifest(tl.color?.plugin);
  return (
    <div className="stack">
      <Section title={t("tpl.color")}>
        <FxSelect label={t("tpl.plugin")} kinds={["color"]} value={tl.color?.plugin} allowNone
                  onChange={(plugin) => edit((x) => ({
                    ...x,
                    color: plugin
                      ? { plugin, at_ms: 0, dur_ms: null, params: defaultParams(fx.data?.find((m) => m.id === plugin)?.params), source: "qolda" }
                      : null,
                  }))} />
        {tl.color && (
          <FxParamsForm manifest={colorManifest} params={tl.color.params}
                        onChange={(params) => edit((x) => (x.color ? { ...x, color: { ...x.color, params, source: "qolda" } } : x))} />
        )}
      </Section>

      <Section title={t("tpl.sec.captions")}>
        <Check label={t("tpl.captions")} checked={tl.captions.enabled}
               onChange={(enabled) => edit((x) => ({ ...x, captions: { ...x.captions, enabled } }))} />
        {tl.captions.enabled && tl.captions.words.length === 0 && (
          <span className="muted" style={{ fontSize: 12 }}>{t("mon.noCaptionWords")}</span>
        )}
        {tl.captions.enabled && (
          <details>
            <summary className="muted" style={{ cursor: "pointer" }}>{t("mon.captionStyle")}</summary>
            <StyleTab style={tl.captions.style}
                      onChange={(s) => edit((x) => ({ ...x, captions: { ...x.captions, style: { ...x.captions.style, ...s } } }))}
                      onReplace={(s) => edit((x) => ({ ...x, captions: { ...x.captions, style: s } }))} />
          </details>
        )}
      </Section>

      <Section title={t("mon.trackMusic")}>
        {tl.music.length === 0 && <span className="muted">{t("mon.noMusic")}</span>}
        {tl.music.map((m, i) => (
          <MusicRow key={i} m={m} path={tl.media[m.media]?.path ?? m.media}
                    onChange={(nm) => edit((x) => ({ ...x, music: x.music.map((y, j) => (j === i ? nm : y)) }))} />
        ))}
        <MusicControls montageId={montageId} tl={tl} edit={edit} />
      </Section>

      <Section title={t("mon.sec.audio")}>
        <Slider label={t("mon.sourceGain")} value={tl.audio.source_gain_db} min={-30} max={12} step={0.5} format={(v) => `${v} dB`}
                onChange={(source_gain_db) => edit((x) => ({ ...x, audio: { ...x.audio, source_gain_db } }))} />
        <div className="row" style={{ alignItems: "flex-end" }}>
          <Check label={t("mon.loudnorm")} checked={tl.audio.loudnorm_lufs != null}
                 onChange={(on) => edit((x) => ({ ...x, audio: { ...x.audio, loudnorm_lufs: on ? -14 : null } }))} />
          {tl.audio.loudnorm_lufs != null && (
            <NumField label="LUFS" value={tl.audio.loudnorm_lufs} min={-30} max={-6} step={0.5}
                      onChange={(v) => edit((x) => ({ ...x, audio: { ...x.audio, loudnorm_lufs: v } }))} />
          )}
          <NumField label={t("mon.audioFade")} suffix="ms" value={tl.audio.fade_ms} min={0} max={2000} step={10}
                    onChange={(fade_ms) => edit((x) => ({ ...x, audio: { ...x.audio, fade_ms } }))} />
        </div>
      </Section>

      <Section title={t("style.logo")}>
        <PathPicker label={t("style.logoPath")} value={tl.brand.logo_path ?? ""}
                    onChange={(v) => edit((x) => ({ ...x, brand: { ...x.brand, logo_path: v.trim() || null } }))}
                    options={{ extensions: IMAGE_EXTS, filterName: "Logo" }} />
        {tl.brand.logo_path && (
          <div className="row" style={{ alignItems: "flex-end" }}>
            <SelectField label={t("style.logoPosition")} value={tl.brand.logo_position}
                         options={LOGO_POS.map((p) => ({ value: p, label: t(`logo.${p}` as MessageKey) }))}
                         onChange={(logo_position) => edit((x) => ({ ...x, brand: { ...x.brand, logo_position } }))} />
            <Slider label={t("style.logoOpacity")} value={tl.brand.logo_opacity} min={0} max={1} step={0.05}
                    format={(v) => `${Math.round(v * 100)}%`}
                    onChange={(logo_opacity) => edit((x) => ({ ...x, brand: { ...x.brand, logo_opacity } }))} />
          </div>
        )}
      </Section>
    </div>
  );
}
