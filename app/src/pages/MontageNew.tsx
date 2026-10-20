import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useCreateMontage, useTemplates } from "../api/hooks";
import { ASPECTS, type Aspect, type MontageOverrides, type Template } from "../api/types";
import { PathPicker } from "../components/PathPicker";
import { NumField, Section, SelectField, TextField } from "../components/montage/fields";
import { FxSelect } from "../components/montage/FxControls";
import { SelectedSources } from "../components/montage/SelectedSources";
import { SourcePicker, type PickedSource } from "../components/montage/SourcePicker";
import { CategoryTabs, filterTemplates, type CategoryFilter } from "../components/templates/CategoryTabs";
import { TemplateCard } from "../components/templates/TemplateCard";
import { Empty, ErrorText, QueryState } from "../components/ui";
import { useT } from "../i18n";
import { AUDIO_EXTS, IMAGE_EXTS } from "../lib/dialog";
import { localText } from "../lib/montage";
import { useSettings } from "../store/settings";

type Tri = "default" | "on" | "off";

interface Form {
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

const EMPTY: Form = { name: "", durationS: null, aspect: "", music: "", title: "", cta: "", shou: "", captions: "default",
  transition: null, color: null, logo: "" };

function toOverrides(f: Form): MontageOverrides {
  const o: MontageOverrides = {};
  if (f.durationS) o.target_duration_ms = Math.round(f.durationS * 1000);
  if (f.aspect) o.aspect = f.aspect;
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
  const set = (p: Partial<Form>) => setForm((f) => ({ ...f, ...p }));

  const tpl: Template | undefined = templates.data?.find((x) => x.id === templateId);
  const musicRequired = !!tpl?.music?.required;
  const problems: string[] = [];
  if (!tpl) problems.push(t("mon.err.template"));
  if (!sources.length) problems.push(t("mon.err.sources"));
  if (musicRequired && !form.music.trim()) problems.push(t("mon.err.music"));

  const addSources = (items: PickedSource[]) =>
    setSources((old) => [...old, ...items.filter((x) => !old.some((o) => o.key === x.key))]);

  const submit = () => {
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
    <div className="stack" style={{ gap: 18, maxWidth: 1100 }}>
      <div className="page-head">
        <div>
          <Link to="/montages" className="muted">← {t("nav.montages")}</Link>
          <h1>{t("mon.new")}</h1>
        </div>
      </div>

      <Section title={t("mon.step1")}>
        <QueryState query={templates} />
        {templates.data && (
          <>
            <CategoryTabs value={cat} onChange={setCat} templates={templates.data} />
            {shown.length === 0 && <Empty>{t("tpl.empty")}</Empty>}
            <div className="grid tpl-grid-compact" role="radiogroup" aria-label={t("mon.step1")}>
              {shown.map((x) => (
                <button key={x.id} type="button" role="radio" aria-checked={x.id === templateId} className="tpl-pick"
                        onClick={() => setTemplateId(x.id)}>
                  <TemplateCard tpl={x} compact selected={x.id === templateId} />
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

      <Section title={t("mon.step2")}>
        <SourcePicker picked={sources} onAdd={addSources}
                      onRemoveKey={(k) => setSources((old) => old.filter((x) => x.key !== k))} />
        <SelectedSources items={sources} onChange={setSources} />
      </Section>

      <Section title={t("mon.step3")}>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <TextField label={t("mon.name")} value={form.name} placeholder={tpl ? localText(tpl.name, locale) : ""}
                     onChange={(name) => set({ name })} />
          <NumField label={t("tpl.duration")} suffix="s" value={form.durationS ?? (tpl ? tpl.target_duration_ms / 1000 : 30)}
                    min={5} max={600} onChange={(v) => set({ durationS: v })} />
          <SelectField label={t("mon.aspect")} value={form.aspect}
                       options={[{ value: "" as const, label: t("mon.fromTemplate", { v: tpl?.aspect ?? "" }) },
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
      </Section>

      {tried && problems.length > 0 && (
        <div className="notice warn" role="alert">
          <ul style={{ margin: 0, paddingLeft: 18 }}>{problems.map((p) => <li key={p}>{p}</li>)}</ul>
        </div>
      )}
      <ErrorText error={create.error} />
      <div className="row">
        <button type="button" className="btn primary" disabled={create.isPending} onClick={submit}>
          {create.isPending ? t("common.loading") : t("mon.create")}
        </button>
        <span className="muted">{t("mon.createHint", { n: sources.length })}</span>
      </div>
    </div>
  );
}
