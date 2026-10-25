import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useCreateMontage, useExportProfiles, useTemplates } from "../api/hooks";
import { ASPECTS, type Aspect, type MontageOverrides, type Template, type TargetPlatform } from "../api/types";
import { PathPicker } from "../components/PathPicker";
import { NumField, Section, SelectField, TextField } from "../components/montage/fields";
import { FxSelect } from "../components/montage/FxControls";
import { SelectedSources } from "../components/montage/SelectedSources";
import { SourcePicker, type PickedSource } from "../components/montage/SourcePicker";
import { CategoryTabs, filterTemplates, type CategoryFilter } from "../components/templates/CategoryTabs";
import { TemplateCard } from "../components/templates/TemplateCard";
import { Empty, ErrorText, QueryState } from "../components/ui";
import { useEditorT } from "../i18n/editor-extra";
import { platformCreationOverrides } from "../lib/export-profiles";
import { useT } from "../i18n";
import { AUDIO_EXTS, IMAGE_EXTS } from "../lib/dialog";
import { localText } from "../lib/montage";
import { useSettings } from "../store/settings";

type Tri = "default" | "on" | "off";

interface Form {
  platform: TargetPlatform;
  name: string;
  durationS: number | null;
  aspect: Aspect | "";
  music: string;
  title: string;
  cta: string;
  shou: string;
  captions: Tri;
  transition: string | null;
  color: string | null;
  logo: string;
}

const EMPTY: Form = { platform: "instagram_reels", name: "", durationS: null, aspect: "", music: "", title: "", cta: "", shou: "", captions: "default",
  transition: null, color: null, logo: "" };

function toOverrides(f: Form): MontageOverrides {
  const o: MontageOverrides = platformCreationOverrides(f.platform, f.aspect);
  if (f.durationS) o.target_duration_ms = Math.round(f.durationS * 1000);
  if (f.music.trim()) o.music_path = f.music.trim();
  if (f.title.trim()) o.title = f.title.trim();
  if (f.cta.trim()) o.cta = f.cta.trim();
  if (f.shou.trim()) o.shou = f.shou.trim();
  if (f.captions !== "default") o.captions = f.captions === "on";
  if (f.transition) o.transition = f.transition;
  if (f.color) o.color = f.color;
  if (f.logo.trim()) o.logo_path = f.logo.trim();
  return o;
}

/** Yangi montaj: shablon -> videolar -> sozlamalar -> "Montaj qilish". */
export function MontageNew() {
  const t = useT();
  const et = useEditorT();
  const profiles = useExportProfiles();
  const navigate = useNavigate();
  const locale = useSettings((s) => s.locale);
  const [params] = useSearchParams();
  const templates = useTemplates();
  const create = useCreateMontage();
  const [templateId, setTemplateId] = useState(params.get("template") ?? "");
  const [cat, setCat] = useState<CategoryFilter>("all");
  const [sources, setSources] = useState<PickedSource[]>([]);
  const [form, setForm] = useState<Form>(EMPTY);
  const [tried, setTried] = useState(false);
  const [step, setStep] = useState<1 | 2>(1);
  const formatRef = useRef<HTMLDivElement>(null);
  const choosingFormat = step === 2 && sources.length > 0;
  useEffect(() => {
    if (choosingFormat) formatRef.current?.focus();
  }, [choosingFormat]);
  const set = (p: Partial<Form>) => setForm((f) => ({ ...f, ...p }));

  const tpl: Template | undefined = templateId
    ? templates.data?.find((x) => x.id === templateId)
    : templates.data?.find((x) => x.id === "uz.lahza.tpl.daily-story" && !x.music?.required)
      ?? templates.data?.find((x) => !x.music?.required);
  const profile = profiles.data?.profiles.find(p => p.id === form.platform);
  const profileFormat = profile?.recommended_format;
  const musicRequired = !!tpl?.music?.required;
  const problems: string[] = [];
  if (!tpl) problems.push(t("mon.err.template"));
  if (!sources.length) problems.push(t("mon.err.sources"));
  if (musicRequired && !form.music.trim()) problems.push(t("mon.err.music"));

  const addSources = (items: PickedSource[]) => {
    if (!items.length) return;
    setSources((old) => [...old, ...items.filter((x) => !old.some((o) => o.key === x.key))]);
    setStep(2);
  };

  const submit = () => {
    if (create.isPending) return;
    setTried(true);
    if (problems.length || !tpl) return;
    const projectId = sources.find((s) => s.projectId)?.projectId;
    create.mutate(
      {
        name: form.name.trim() || undefined,
        project_id: projectId,
        template_id: tpl.id,
        sources: sources.map((s) => s.source),
        overrides: toOverrides(form),
      },
      { onSuccess: (res) => navigate(`/montages/${res.montage_id}`) },
    );
  };

  const shown = filterTemplates(templates.data ?? [], cat);

  return (
    <div className="stack quick-start" style={{ gap: 18, maxWidth: 900 }}>
      <div className="page-head">
        <div>
          <Link to="/montages" className="muted">← {t("nav.montages")}</Link>
          <h1>{t("quick.title")}</h1>
          <p className="lead">{t("quick.lead")}</p>
        </div>
      </div>

      <ol className="quick-steps" aria-label={t("quick.steps")}>
        <li aria-current={!choosingFormat ? "step" : undefined}>{t("quick.upload")}</li>
        <li aria-current={choosingFormat ? "step" : undefined}>{t("quick.format")}</li>
        <li>{t("quick.review")}</li>
        <li>{t("quick.export")}</li>
      </ol>
      <Section title={t("quick.upload")}>
        {!choosingFormat ? <SourcePicker picked={sources} onAdd={addSources}
                      onRemoveKey={(k) => setSources((old) => old.filter((x) => x.key !== k))} />
          : <div className="row"><span className="badge good" role="status">✓ {t("quick.selected")}</span>
            <button type="button" className="btn" onClick={() => setStep(1)}>{t("quick.changeVideo")}</button></div>}
        <SelectedSources items={sources} onChange={setSources} />
        {!choosingFormat && sources.length > 0 && <button type="button" className="btn primary" onClick={() => setStep(2)}>{t("quick.next")}</button>}
      </Section>

      <div ref={formatRef} tabIndex={-1} hidden={!choosingFormat} className="stack" aria-label={t("quick.format")}>
      <Section title={t("quick.format")}>
        <SelectField label={et("platform")} value={form.platform}
          options={profiles.data?.profiles.map(p => ({ value: p.id, label: p.name })) ?? [{ value: "instagram_reels", label: "Instagram Reels" }, { value: "youtube_shorts", label: "YouTube Shorts" }, { value: "youtube_video", label: "YouTube" }, { value: "custom", label: "Custom" }]}
          onChange={platform => set({ platform })} />
        <ErrorText error={profiles.error} />
        {profiles.isError && <button type="button" className="btn" onClick={() => void profiles.refetch()}>{et("retry")}</button>}
        {tpl && <p className="muted">{t("quick.auto")}</p>}
        <QueryState query={templates} />
        {templates.isError && <div className="notice bad" role="alert">
          <p>{t("quick.engineError")}</p>
          <button type="button" className="btn" onClick={() => void templates.refetch()}>{et("retry")}</button>
        </div>}
        {templates.data?.length === 0 && <div className="notice warn" role="status">
          <p>{t("quick.noTemplate")}</p><Link to="/templates">{t("nav.templates")}</Link>
        </div>}
        <details className="quick-details" open={!tpl || undefined}>
          <summary>{t("quick.style")}{tpl ? ` · ${localText(tpl.name, locale)}` : ""}</summary>
      <Section title={t("mon.step1")}>
        <QueryState query={templates} />
        {templates.data && (
          <>
            <CategoryTabs value={cat} onChange={setCat} templates={templates.data} />
            {shown.length === 0 && <Empty>{t("tpl.empty")}</Empty>}
            <div className="grid tpl-grid-compact" role="radiogroup" aria-label={t("mon.step1")}>
              {shown.map((x) => (
                <button key={x.id} type="button" role="radio" aria-checked={x.id === tpl?.id} className="tpl-pick"
                        onClick={() => setTemplateId(x.id)}>
                  <TemplateCard tpl={x} compact selected={x.id === tpl?.id} />
                </button>
              ))}
            </div>
          </>
        )}
        {tpl && (
          <p className="muted" role="status">
            {t("mon.chosen", { name: localText(tpl.name, locale) })}{" "}
            <Link to={`/templates/${encodeURIComponent(tpl.id)}`}>{t("tpl.view")}</Link>
          </p>
        )}
      </Section>

        </details>
        <details className="quick-details" open={musicRequired || undefined}>
          <summary>{t("quick.advanced")}</summary>
          <div className="stack">
        <span className="muted">{et("platformDisclaimer")}</span>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <TextField label={t("mon.name")} value={form.name} placeholder={tpl ? localText(tpl.name, locale) : ""}
                     onChange={(name) => set({ name })} />
          <NumField label={t("tpl.duration")} suffix="s" value={form.durationS ?? (tpl ? tpl.target_duration_ms / 1000 : 30)}
                    min={5} max={600} onChange={(v) => set({ durationS: v })} />
          <SelectField label={t("mon.aspect")} value={form.aspect}
                       options={[{ value: "" as const, label: profileFormat ? `${et("profileDefault")} ${profile?.name} · ${profileFormat.aspect} · ${profileFormat.w}×${profileFormat.h} · ${profileFormat.fps} fps` : t("mon.fromTemplate", { v: tpl?.aspect ?? "" }) },
                         ...ASPECTS.map((a) => ({ value: a, label: a }))]}
                       onChange={(aspect) => set({ aspect })} />
        </div>
        <div className="stack" style={{ gap: 4 }}>
          <PathPicker label={`${t("mon.music")}${musicRequired ? " *" : ""}`} value={form.music}
                      onChange={(music) => set({ music })} options={{ extensions: AUDIO_EXTS, filterName: "Audio" }} />
          {musicRequired && <span className="badge warn" style={{ alignSelf: "flex-start" }}>{t("tpl.musicRequired")}</span>}
          <span className="muted" style={{ fontSize: 12 }}>{t("mon.musicHint")}</span>
        </div>
        <div className="row">
          <TextField label={t("mon.titleText")} value={form.title} onChange={(title) => set({ title })} />
          <TextField label={t("mon.cta")} value={form.cta} onChange={(cta) => set({ cta })} />
          <TextField label={t("mon.shou")} value={form.shou} onChange={(shou) => set({ shou })} />
        </div>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <SelectField label={t("tpl.captions")} value={form.captions}
                       options={[
                         { value: "default", label: t("mon.fromTemplate", { v: tpl ? (tpl.captions ? t("common.on") : t("common.off")) : "" }) },
                         { value: "on", label: t("common.on") },
                         { value: "off", label: t("common.off") },
                       ]}
                       onChange={(captions) => set({ captions })} />
          <FxSelect label={t("tpl.transition")} kinds={["transition"]} value={form.transition} allowNone
                    noneLabel={t("mon.fromTemplate", { v: "" })} onChange={(transition) => set({ transition })} />
          <FxSelect label={t("tpl.color")} kinds={["color"]} value={form.color} allowNone
                    noneLabel={t("mon.fromTemplate", { v: "" })} onChange={(color) => set({ color })} />
        </div>
        <PathPicker label={t("style.logoPath")} value={form.logo} onChange={(logo) => set({ logo })}
                    options={{ extensions: IMAGE_EXTS, filterName: "Logo" }} />
        {tpl?.logo && !form.logo && <span className="muted" style={{ fontSize: 12 }}>{t("mon.logoHint")}</span>}
          </div>
        </details>
      </Section>

      {tried && problems.length > 0 && (
        <div className="notice warn" role="alert">
          <ul style={{ margin: 0, paddingLeft: 18 }}>{problems.map((p) => <li key={p}>{p}</li>)}</ul>
        </div>
      )}
      <ErrorText error={create.error} />
      <div className="row">
        <button type="button" className="btn primary" disabled={create.isPending || !sources.length || templates.isPending} onClick={submit}>
          {create.isPending ? t("common.loading") : t("quick.continue")}
        </button>
        <span className="muted">{t("mon.createHint", { n: sources.length })}</span>
      </div>
      </div>
    </div>
  );
}
