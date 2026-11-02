import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { del, errorText, get, post } from "../../api/client";
import { skillsDictionaries } from "../../i18n/skills";
import { useSettings } from "../../store/settings";
import { PathPicker } from "../PathPicker";

type Skill = { id: string; name: string; version: string; description: string; permissions: string[]; actions: Record<string, unknown>[]; path?: string };
type Catalog = { items: Skill[]; builtins: Skill[] };
type Montage = { id: string; name: string; status: string };

export function EditingSkillsPanel() {
  const t = skillsDictionaries[useSettings((s) => s.locale)];
  const qc = useQueryClient();
  const [path, setPath] = useState("");
  const [replace, setReplace] = useState(false);
  const [mid, setMid] = useState("");
  const [title, setTitle] = useState("");
  const catalog = useQuery({ queryKey: ["editing-skills"], queryFn: () => get<Catalog>("/v1/skills") });
  const montages = useQuery({ queryKey: ["editing-skills", "montages"], queryFn: () => get<Montage[]>("/v1/montages") });
  const install = useMutation({
    mutationFn: (file: string) => post<Skill>("/v1/skills:install", { path: file, replace }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["editing-skills"] }); },
  });
  const apply = useMutation({
    mutationFn: (id: string) => post(`/v1/skills/${encodeURIComponent(id)}:apply`, { montage_id: mid, title }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["montages"] });
      void qc.invalidateQueries({ queryKey: ["montage", mid] });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => del(`/v1/skills/${encodeURIComponent(id)}`),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["editing-skills"] }); },
  });
  const busy = install.isPending || apply.isPending || remove.isPending;
  const ready = montages.data?.filter((m) => m.status === "ready") ?? [];
  const reset = () => { install.reset(); apply.reset(); remove.reset(); };
  const details = (skill: Skill) => <>
    <p><strong>{skill.name}</strong> · {skill.id} · v{skill.version}</p>
    <p>{skill.description}</p>
    <p className="muted">{t.permissions}: {skill.permissions.join(", ")}</p>
    <details><summary>{t.actions}</summary><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(skill.actions, null, 2)}</pre></details>
  </>;
  return <section className="card stack" aria-label={t.heading}>
    <h2>{t.heading}</h2>
    <p className="muted">{t.notice}</p>
    <fieldset disabled={busy} className="stack" style={{ border: 0, padding: 0 }}>
      <PathPicker label={t.path} value={path} onChange={(p) => { setPath(p); reset(); }} options={{ extensions: ["lahzaskill", "json"] }} />
      <label><input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} /> {t.replace}</label>
      <button className="btn" disabled={!path} onClick={() => { reset(); install.mutate(path); }}>{t.install}</button>
      <h3>{t.examples}</h3>
      {catalog.data?.builtins.map((skill) => <div key={skill.id}>
        {details(skill)}
        <button className="btn" disabled={!skill.path || catalog.data.items.some((s) => s.id === skill.id)} onClick={() => { if (skill.path) { reset(); install.mutate(skill.path); } }}>{t.install}</button>
      </div>)}
      <h3>{t.installed}</h3>
      <p role="note">{t.draft}</p>
      <label className="field">{t.montage}<select className="select" value={mid} onChange={(e) => { setMid(e.target.value); apply.reset(); }}>
        <option value="">{t.choose}</option>
        {ready.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
      </select></label>
      <label className="field">{t.title}<input className="input" value={title} maxLength={500} onChange={(e) => { setTitle(e.target.value); apply.reset(); }} /></label>
      {!montages.isPending && !montages.isError && ready.length === 0 && <p>{t.noMontages}</p>}
      {catalog.data?.items.length === 0 && <p>{t.empty}</p>}
      {catalog.data?.items.map((skill) => <article key={skill.id} className="stack">
        {details(skill)}
        <div className="row">
          <button className="btn" disabled={!ready.some((m) => m.id === mid)} onClick={() => { reset(); apply.mutate(skill.id); }}>{t.apply}</button>
          <button className="btn" onClick={() => { if (window.confirm(t.confirm)) { reset(); remove.mutate(skill.id); } }}>{t.remove}</button>
        </div>
      </article>)}
    </fieldset>
    <button className="btn" disabled={busy || catalog.isFetching || montages.isFetching} onClick={() => { void catalog.refetch(); void montages.refetch(); }}>{t.refresh}</button>
    {(busy || catalog.isPending || montages.isPending) && <p role="status">{t.busy}</p>}
    {[catalog.error, montages.error, install.error, apply.error, remove.error].filter(Boolean).map((error, i) => <p role="alert" key={i}>{errorText(error)}</p>)}
    {apply.isSuccess && <p role="status">{t.success}</p>}
    {install.isSuccess && <p role="status">{t.done}</p>}
    {remove.isSuccess && <p role="status">{t.deleted}</p>}
  </section>;
}
