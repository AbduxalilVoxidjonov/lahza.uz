import { useEffect, useId, useState, type FormEvent } from "react";

import { useClipMetrics, useSaveClipMetrics } from "../../api/learning";
import { fmt, learningDictionaries } from "../../i18n/learning";
import { parseCount } from "../../lib/learning";
import { useSettings } from "../../store/settings";
import { ErrorText } from "../ui";

type M = (typeof learningDictionaries)["uz"];

/** Ko'rishlar/like kiritish (PRO-6) - sof ko'rinish (node testlari uchun). */
export function ClipMetricsView(p: {
  m: M;
  title: string;
  views: string;
  likes: string;
  invalid: boolean;
  saved: boolean;
  busy: boolean;
  onViews: (v: string) => void;
  onLikes: (v: string) => void;
  onSave: () => void;
}) {
  const id = useId();
  const submit = (e: FormEvent) => {
    e.preventDefault();
    p.onSave();
  };
  return (
    <form className="row clip-metrics" style={{ gap: 6 }} onSubmit={submit} noValidate>
      <label htmlFor={`${id}-v`} className="muted">{p.m.views}</label>
      <input id={`${id}-v`} className="input" inputMode="numeric" style={{ width: 90 }} value={p.views}
             aria-label={fmt(p.m.viewsLabel, { title: p.title })} aria-invalid={p.invalid || undefined}
             onChange={(e) => p.onViews(e.target.value)} />
      <label htmlFor={`${id}-l`} className="muted">{p.m.likes}</label>
      <input id={`${id}-l`} className="input" inputMode="numeric" style={{ width: 70 }} value={p.likes}
             aria-label={fmt(p.m.likesLabel, { title: p.title })} onChange={(e) => p.onLikes(e.target.value)} />
      <button type="submit" className="btn small ghost" disabled={p.busy || !p.views.trim()}>{p.m.save}</button>
      {p.invalid && <span className="error" role="alert">{p.m.invalid}</span>}
      {p.saved && !p.invalid && <span className="muted" role="status">{p.m.saved}</span>}
    </form>
  );
}

/** Klip kartasidagi natija maydoni: epizod bo'yicha bitta so'rov (react-query keshi). */
export function ClipMetrics({ episodeId, clipId, title }: { episodeId: string; clipId: string; title: string }) {
  const m = learningDictionaries[useSettings((s) => s.locale)];
  const all = useClipMetrics(episodeId);
  const save = useSaveClipMetrics(episodeId);
  const cur = all.data?.[clipId];
  const [views, setViews] = useState("");
  const [likes, setLikes] = useState("");
  const [invalid, setInvalid] = useState(false);
  useEffect(() => {
    if (cur) {
      setViews(String(cur.views));
      setLikes(cur.likes == null ? "" : String(cur.likes));
    }
  }, [cur]);
  const onSave = () => {
    const v = parseCount(views);
    const l = parseCount(likes);
    if (v === null || Number.isNaN(v) || Number.isNaN(l)) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    save.mutate({ clipId, views: v, likes: l });
  };
  return (
    <>
      <ClipMetricsView m={m} title={title} views={views} likes={likes} invalid={invalid}
                       saved={save.isSuccess} busy={save.isPending}
                       onViews={(v) => { setViews(v); setInvalid(false); save.reset(); }}
                       onLikes={(v) => { setLikes(v); setInvalid(false); save.reset(); }}
                       onSave={onSave} />
      <ErrorText error={save.error} />
    </>
  );
}
