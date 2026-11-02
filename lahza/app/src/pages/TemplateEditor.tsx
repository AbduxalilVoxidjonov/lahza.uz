import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useDuplicateTemplate, useSaveTemplate, useTemplate } from "../api/hooks";
import { ASPECTS, DEFAULT_STYLE, type LocalText, type Template } from "../api/types";
import { StyleTab } from "../components/editor/StyleTab";
import { Check, NumField, Section, SelectField, Slider, TextField } from "../components/montage/fields";
import { FxParamsForm, FxSelect, useManifest } from "../components/montage/FxControls";
import { FxRulesEditor } from "../components/templates/FxRulesEditor";
import { TextCardEditor } from "../components/templates/TextCardEditor";
import { ErrorText, QueryState } from "../components/ui";
import { LOCALE_NAMES, useT, type Locale, type MessageKey } from "../i18n";
import { useHotkeys } from "../lib/hotkeys";
import { blankTemplate, localText, TEMPLATE_CATEGORIES, templateProblems, withTemplateDefaults } from "../lib/montage";
import { LOCALES, useSettings } from "../store/settings";

export function TemplateEditor() {
  const t = useT();
  const { id = "" } = useParams();
  const isNew = id === "new";
  const q = useTemplate(isNew ? undefined : id);
  if (isNew) return <TemplateForm key="new" initial={blankTemplate()} isNew />;
  if (!q.data) return q.isLoading || q.error ? <QueryState query={q} /> : <div className="center">{t("tpl.notFound")}</div>;
  return <TemplateForm key={q.data.id} initial={withTemplateDefaults(q.data)} isNew={false} />;
}

/** Bo'sh tarjimalarni `null` ga aylantiradi (`uz` majburiy). */
function cleanLocal(lt: LocalText | null | undefined): LocalText | null {
  if (!lt) return null;
  const out: LocalText = { uz: lt.uz.trim() };
  for (const l of ["uz-Cyrl", "ru", "en"] as const) {
    const v = lt[l]?.trim();
    if (v) out[l] = v;
  }
  return out.uz ? out : null;
}

function LocalTextFields({ label, value, onChange, multiline }: {
  label: string; value: LocalText | null | undefined; onChange: (v: LocalText) => void; multiline?: boolean;
}) {
  const v: LocalText = value ?? { uz: "" };
  return (
    <div className="stack" style={{ gap: 6 }}>
      <span className="muted" style={{ fontSize: 12 }}>{label}</span>
      <div className="row" style={{ alignItems: "flex-start" }}>
        {LOCALES.map((l: Locale) => (
          <TextField key={l} label={`${LOCALE_NAMES[l]}${l === "uz" ? " *" : ""}`} multiline={multiline}
                     value={(l === "uz" ? v.uz : v[l]) ?? ""}
                     onChange={(s) => onChange({ ...v, [l]: s })} />
        ))}
      </div>
    </div>
  );
}

function TransitionFields({ tpl, set }: { tpl: Template; set: (p: Partial<Template>) => void }) {
  const t = useT();
  const manifest = useManifest(tpl.transition?.plugin);
  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <FxSelect label={t("tpl.transition")} kinds={["transition"]} value={tpl.transition?.plugin} allowNone
                  onChange={(plugin) => set({ transition: plugin ? { plugin, dur_ms: tpl.transition?.dur_ms ?? 400, params: {} } : null })} />
        {tpl.transition && (
          <NumField label={t("tpl.transitionDur")} suffix="ms" value={tpl.transition.dur_ms} min={0} max={3000} step={50}
                    onChange={(dur_ms) => tpl.transition && set({ transition: { ...tpl.transition, dur_ms } })} />
        )}
      </div>
      {tpl.transition && (
        <FxParamsForm manifest={manifest} params={tpl.transition.params}
                      onChange={(params) => tpl.transition && set({ transition: { ...tpl.transition, params } })} />
      )}
    </div>
  );
}

function TemplateForm({ initial, isNew }: { initial: Template; isNew: boolean }) {
  const t = useT();
  const navigate = useNavigate();
  const locale = useSettings((s) => s.locale);
  const save = useSaveTemplate();
  const dup = useDuplicateTemplate();
  const [tpl, setTpl] = useState<Template>(initial);
  const [saved, setSaved] = useState<Template>(initial);
  const [showErrors, setShowErrors] = useState(false);
  const readOnly = tpl.builtin;
  const dirty = useMemo(() => JSON.stringify(tpl) !== JSON.stringify(saved), [tpl, saved]);
  const problems = templateProblems(tpl);
  const set = (p: Partial<Template>) => setTpl((old) => ({ ...old, ...p }));

  const onSave = () => {
    if (readOnly) return;
    setShowErrors(true);
    if (problems.length) return;
    const body: Template = {
      ...tpl,
      name: cleanLocal(tpl.name) ?? tpl.name,
      description: cleanLocal(tpl.description),
    };
    save.mutate({ template: body, isNew }, {
      onSuccess: (res) => {
        const next = withTemplateDefaults(res);
        setTpl(next);
        setSaved(next);
        if (isNew || res.id !== tpl.id) navigate(`/templates/${encodeURIComponent(res.id)}`, { replace: true });
      },
    });
  };

  useHotkeys({ "mod+s": onSave });

  const music = tpl.music;
  return (
    <div className="stack" style={{ gap: 16, maxWidth: 1100 }}>
      <div className="page-head">
        <div>
          <Link to="/templates" className="muted">← {t("tpl.title")}</Link>
          <h1>{isNew ? t("tpl.new") : localText(tpl.name, locale) || tpl.id}</h1>
          <span className="muted mono">{tpl.id} · v{tpl.version}</span>
        </div>
        <div className="row">
          {readOnly ? (
            <>
              <span className="badge">{t("tpl.builtinReadonly")}</span>
              <button type="button" className="btn primary" disabled={dup.isPending}
                      onClick={() => dup.mutate({ id: tpl.id }, { onSuccess: (c) => navigate(`/templates/${encodeURIComponent(c.id)}`) })}>
                {t("tpl.duplicateEdit")}
              </button>
            </>
          ) : (
            <>
              {dirty && <span className="badge warn" role="status">{t("common.unsaved")}</span>}
              <button type="button" className="btn" disabled={!dirty} onClick={() => setTpl(saved)}>{t("common.cancel")}</button>
              <button type="button" className="btn primary" disabled={save.isPending || (!dirty && !isNew)} onClick={onSave}>
                {t("common.save")} <kbd>⌘S</kbd>
              </button>
            </>
          )}
          {!isNew && (
            <button type="button" className="btn" onClick={() => navigate(`/montages/new?template=${encodeURIComponent(tpl.id)}`)}>
              {t("tpl.apply")}
            </button>
          )}
        </div>
      </div>

      {showErrors && problems.length > 0 && (
        <div className="notice warn" role="alert">
          <ul style={{ margin: 0, paddingLeft: 18 }}>{problems.map((p) => <li key={p}>{t(p)}</li>)}</ul>
        </div>
      )}
      <ErrorText error={save.error ?? dup.error} />

      <fieldset disabled={readOnly} className="stack" style={{ border: "none", padding: 0, margin: 0, gap: 16 }}>
        <Section title={t("tpl.sec.main")}>
          <LocalTextFields label={t("tpl.name")} value={tpl.name} onChange={(name) => set({ name })} />
          <LocalTextFields label={t("tpl.description")} value={tpl.description} multiline onChange={(description) => set({ description })} />
          <div className="row" style={{ alignItems: "flex-end" }}>
            <SelectField label={t("tpl.category")} value={tpl.category}
                         options={TEMPLATE_CATEGORIES.map((c) => ({ value: c, label: t(`tpl.cat.${c}` as MessageKey) }))}
                         onChange={(category) => set({ category })} />
            <SelectField label={t("mon.aspect")} value={tpl.aspect} options={ASPECTS.map((a) => ({ value: a, label: a }))}
                         onChange={(aspect) => set({ aspect })} />
            <NumField label={t("tpl.fps")} value={tpl.fps} min={12} max={60} onChange={(fps) => set({ fps })} />
            <NumField label={t("tpl.duration")} suffix="s" value={tpl.target_duration_ms / 1000} min={5} max={600}
                      onChange={(s) => set({ target_duration_ms: Math.round(s * 1000) })} />
            <NumField label={t("tpl.minShot")} suffix="s" value={tpl.min_shot_ms / 1000} min={0.3} max={60} step={0.1}
                      onChange={(s) => set({ min_shot_ms: Math.round(s * 1000) })} />
            <NumField label={t("tpl.maxShot")} suffix="s" value={tpl.max_shot_ms / 1000} min={0.5} max={120} step={0.1}
                      onChange={(s) => set({ max_shot_ms: Math.round(s * 1000) })} />
          </div>
        </Section>

        <Section title={t("tpl.sec.selection")}>
          <div className="row" style={{ alignItems: "flex-end" }}>
            <SelectField label={t("tpl.selection")} value={tpl.selection}
                         options={(["highlight", "scenes", "full"] as const).map((x) => ({ value: x, label: t(`tpl.sel.${x}`) }))}
                         onChange={(selection) => set({ selection })} />
            <SelectField label={t("tpl.order")} value={tpl.order}
                         options={(["berilgan", "xronologik", "ball"] as const).map((x) => ({ value: x, label: t(`tpl.order.${x}`) }))}
                         onChange={(order) => set({ order })} />
            <NumField label={t("tpl.maxPerSource")} value={tpl.max_per_source ?? 0} min={0} max={100}
                      onChange={(v) => set({ max_per_source: v > 0 ? Math.round(v) : null })} />
            <SelectField label={t("tpl.reframe")} value={tpl.reframe}
                         options={(["auto", "fit_blur", "center"] as const).map((x) => ({ value: x, label: t(`reframe.${x}`) }))}
                         onChange={(reframe) => set({ reframe })} />
          </div>
          <span className="muted" style={{ fontSize: 12 }}>{t("tpl.maxPerSourceHint")}</span>
          <Check label={t("tpl.respectSentences")} checked={tpl.respect_sentences} onChange={(respect_sentences) => set({ respect_sentences })} />
        </Section>

        <Section title={t("tpl.sec.look")}>
          <TransitionFields tpl={tpl} set={set} />
          <FxSelect label={t("tpl.color")} kinds={["color"]} value={tpl.color} allowNone onChange={(color) => set({ color })} />
        </Section>

        <Section title={t("tpl.sec.fx")}>
          <FxRulesEditor rules={tpl.fx} onChange={(fx) => set({ fx })} />
        </Section>

        <Section title={t("tpl.sec.captions")}>
          <Check label={t("tpl.captions")} checked={tpl.captions} onChange={(captions) => set({ captions })} />
          {tpl.captions && (
            <Check label={t("tpl.customStyle")} checked={!!tpl.caption_style}
                   onChange={(on) => set({ caption_style: on ? { ...DEFAULT_STYLE } : null })} />
          )}
          {tpl.captions && tpl.caption_style && (
            <StyleTab style={tpl.caption_style}
                      onChange={(s) => setTpl((old) => ({ ...old, caption_style: { ...(old.caption_style ?? DEFAULT_STYLE), ...s } }))}
                      onReplace={(s) => set({ caption_style: s })} />
          )}
        </Section>

        <Section title={t("tpl.sec.structure")}>
          <TextCardEditor label={t("tpl.intro")} value={tpl.intro} defaultKind="card" onChange={(intro) => set({ intro })} />
          <TextCardEditor label={t("tpl.hook")} value={tpl.hook_text} defaultKind="hook" onChange={(hook_text) => set({ hook_text })} />
          <TextCardEditor label={t("tpl.outro")} value={tpl.outro} defaultKind="cta" onChange={(outro) => set({ outro })} />
        </Section>

        <Section title={t("tpl.sec.audio")}>
          <Check label={t("tpl.music")} checked={!!music}
                 onChange={(on) => set({ music: on ? { required: false, gain_db: -14, duck: true, fade_in_ms: 500, fade_out_ms: 1500 } : null })} />
          {music && (
            <div className="stack" style={{ gap: 8, paddingLeft: 22 }}>
              <Check label={t("tpl.musicRequired")} checked={music.required} onChange={(required) => set({ music: { ...music, required } })} />
              <Check label={t("mon.duck")} checked={music.duck} onChange={(duck) => set({ music: { ...music, duck } })} />
              <div className="row" style={{ alignItems: "flex-end" }}>
                <Slider label={t("mon.musicGain")} value={music.gain_db} min={-60} max={6} step={0.5} format={(v) => `${v} dB`}
                        onChange={(gain_db) => set({ music: { ...music, gain_db } })} />
                <NumField label={t("mon.fadeIn")} suffix="ms" value={music.fade_in_ms} min={0} max={10000} step={100}
                          onChange={(fade_in_ms) => set({ music: { ...music, fade_in_ms } })} />
                <NumField label={t("mon.fadeOut")} suffix="ms" value={music.fade_out_ms} min={0} max={10000} step={100}
                          onChange={(fade_out_ms) => set({ music: { ...music, fade_out_ms } })} />
              </div>
            </div>
          )}
          <div className="row" style={{ alignItems: "flex-end" }}>
            <Slider label={t("mon.sourceGain")} value={tpl.source_gain_db} min={-30} max={12} step={0.5} format={(v) => `${v} dB`}
                    onChange={(source_gain_db) => set({ source_gain_db })} />
          </div>
          <Check label={t("tpl.muteSources")} checked={tpl.mute_sources} onChange={(mute_sources) => set({ mute_sources })} />
          <div className="row" style={{ alignItems: "flex-end" }}>
            <Check label={t("mon.loudnorm")} checked={tpl.loudnorm_lufs != null}
                   onChange={(on) => set({ loudnorm_lufs: on ? -14 : null })} />
            {tpl.loudnorm_lufs != null && (
              <NumField label="LUFS" value={tpl.loudnorm_lufs} min={-30} max={-6} step={0.5}
                        onChange={(loudnorm_lufs) => set({ loudnorm_lufs })} />
            )}
          </div>
          <Check label={t("tpl.logo")} checked={tpl.logo} onChange={(logo) => set({ logo })} />
        </Section>
      </fieldset>
    </div>
  );
}
