import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { PathPicker } from "../PathPicker";
import { normalizeSticker, scaleStickerSize } from "../../lib/montage";
import { api, post } from "../../api/client";
import type { StickerItem } from "../../api/types";
import { useEditorT } from "../../i18n/editor-extra";
import { ErrorText } from "../ui";
import { NumField, SelectField } from "./fields";

export interface StickerAsset { path: string; width: number; height: number; animated: boolean; format: string; name?: string }
function asset(value: unknown): StickerAsset {
  if (!value || typeof value !== "object") throw new Error("Invalid sticker response");
  const a = value as Record<string, unknown>;
  if (typeof a.path !== "string" || !a.path || typeof a.width !== "number" || !Number.isFinite(a.width) || a.width <= 0 || typeof a.height !== "number" || !Number.isFinite(a.height) || a.height <= 0 || typeof a.animated !== "boolean" || typeof a.format !== "string") throw new Error("Invalid sticker response");
  return { path: a.path, width: a.width, height: a.height, animated: a.animated, format: a.format, name: typeof a.name === "string" ? a.name : undefined };
}
export function StickerLibrary({ onAdd }: { onAdd: (a: StickerAsset) => void }) {
  const t = useEditorT();
  const [path, setPath] = useState("");
  const q = useQuery({ queryKey: ["editor-stickers"], queryFn: async ({ signal }) => {
    const response = await api<unknown>("/v1/stickers", { signal });
    if (!response || typeof response !== "object" || !("items" in response) || !Array.isArray(response.items)) throw new Error(t("invalid"));
    return response.items.map(asset);
  }, staleTime: 60_000 });
  const pick = useMutation({ mutationFn: async (path: string) => {
    onAdd(asset(await post<unknown>("/v1/stickers:inspect", { path })));
  } });
  return <section className="stack" aria-label={t("stickers")}>
    <strong>{t("stickers")}</strong>
    <PathPicker label={t("file")} value={path} onChange={setPath} options={{ extensions: ["png", "webp", "gif"], filterName: "Stickers" }} />
    <button type="button" className="btn" disabled={pick.isPending || !path.trim()} onClick={() => pick.mutate(path.trim())}>{pick.isPending ? t("loading") : t("file")}</button>
    <ErrorText error={pick.error ?? q.error} />
    {q.isPending && <span role="status">{t("loading")}</span>}
    {q.isError && <button type="button" className="btn" onClick={() => void q.refetch()}>{t("retry")}</button>}
    {q.data?.length === 0 && <span className="muted">{t("empty")}</span>}
    <div className="row">{q.data?.map((a) => <button type="button" className="btn small" key={a.path} onClick={() => onAdd(a)}>{a.name ?? a.path.split(/[\\/]/).pop()}</button>)}</div>
  </section>;
}
export function StickerInspector({ item, onChange, onDelete, onDuplicate }: {
  item: StickerItem; onChange: (it: StickerItem) => void; onDelete: () => void; onDuplicate: () => void;
}) {
  const t = useEditorT();
  const [base] = useState(() => { const valid = normalizeSticker(item); return { width: valid.width, height: valid.height }; });
  const set = (p: Partial<StickerItem>) => onChange(normalizeSticker({ ...item, ...p }));
  return <div className="stack">
    <strong>{t("stickers")}</strong><span className="muted">{item.path.split(/[\\/]/).pop()}</span>
    <div className="row"><button type="button" className="btn" onClick={onDuplicate}>{t("duplicate")}</button><button type="button" className="btn bad" onClick={onDelete}>{t("remove")}</button></div>
    <div className="row"><NumField label={t("start")} suffix="ms" value={item.start_ms} min={0} max={item.end_ms - 1} onChange={v => set({ start_ms: Math.round(v) })} /><NumField label={t("end")} suffix="ms" value={item.end_ms} min={item.start_ms + 1} onChange={v => set({ end_ms: Math.round(v) })} /></div>
    <div className="row"><NumField label="X" value={item.x} min={0} max={1} step={0.01} onChange={x => set({ x })} /><NumField label="Y" value={item.y} min={0} max={1} step={0.01} onChange={y => set({ y })} /></div>
    <div className="row"><NumField label={t("width")} value={item.width} min={0.02} max={2} step={0.01} onChange={width => set({ width })} /><NumField label={t("height")} value={item.height} min={0.02} max={2} step={0.01} onChange={height => set({ height })} /></div>
    <NumField label={t("scale")} suffix="%" value={item.width / base.width * 100} step={0.1}
      min={Math.max(0.02 / base.width, 0.02 / base.height) * 100}
      max={Math.min(2 / base.width, 2 / base.height) * 100}
      onChange={v => set(scaleStickerSize(base.width, base.height, v / 100))} />
    <div className="row"><NumField label={t("rotation")} value={item.rotation} min={-180} max={180} onChange={rotation => set({ rotation })} /><NumField label={t("opacity")} value={item.opacity} min={0} max={1} step={0.05} onChange={opacity => set({ opacity })} /></div>
    <NumField label={t("layer")} value={item.layer} min={0} max={1000} onChange={layer => set({ layer: Math.round(layer) })} />
    <SelectField label={t("animation")} value={item.animation} options={(["none", "fade", "pop"] as const).map(value => ({ value, label: t(value) }))} onChange={animation => set({ animation })} />
  </div>;
}
