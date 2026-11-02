import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { MODEL_EVENTS } from "../../shared/inference-models";
import type { ComponentsView } from "../../shared/content-download";
import { componentsCancel, componentsList, componentsRetry } from "../ipc";
import { listen, type UnlistenFn } from "@/bridge/events";
import { Button } from "@/components/ui/button";
import { modelSize } from "./ModelSection";
import { componentRowState } from "./componentRow";

/** First-run components (yt-dlp, Remotion, HyperFrames, skill packs). A pure
 *  projection of the main-owned content queue: it re-reads on the same
 *  `models:changed` ping the model rows use and owns no transfer state. */
export function ComponentsSection({ onError }: { onError(msg: string): void }) {
  const { t } = useTranslation();
  const [view, setView] = useState<ComponentsView | null>(null);
  const [online, setOnline] = useState(typeof navigator === "undefined" ? true : navigator.onLine);
  useEffect(() => {
    let disposed = false;
    let unlisten: UnlistenFn | undefined;
    const refresh = () => { componentsList().then(v => { if (!disposed) setView(v); }).catch(e => { if (!disposed) onError(String(e)); }); };
    const goOnline = () => { setOnline(true); componentsRetry().then(v => { if (!disposed) setView(v); }).catch(e => onError(String(e))); };
    const goOffline = () => { setOnline(false); refresh(); };
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    void listen(MODEL_EVENTS.changed, refresh).then(u => { if (disposed) u(); else unlisten = u; });
    refresh();
    return () => { disposed = true; unlisten?.(); window.removeEventListener("online", goOnline); window.removeEventListener("offline", goOffline); };
  }, []);
  if (!view || view.components.length === 0) return null;
  const isOnline = online && view.online;
  const retry = () => { componentsRetry().then(setView).catch(e => onError(String(e))); };
  return <section className="settings-section" aria-label={t("components.heading")}>
    <h3>{t("components.heading")}</h3>
    <p className="settings-model-state">{t("components.hint")}</p>
    {!isOnline && <p className="settings-status" role="status">{t("components.offline")}</p>}
    <ul className="settings-model-list">
      {view.components.map(c => {
        const row = componentRowState(c, isOnline);
        const text = row.kind === "downloading" ? t(`components.phase_${row.phase}`, { percent: row.percent })
          : row.kind === "error" ? t("components.error", { message: row.message })
          : t(`components.state_${row.kind}`);
        return <li key={c.id} className="settings-model-row">
          <strong>{t(`settings.${c.labelKey}`)}</strong>
          <span className="settings-model-state">{c.bytes > 0 ? `${modelSize(c.bytes)} · ` : ""}{c.license}</span>
          <span className="settings-model-state" role="status">{text}</span>
          {row.kind === "pending_upstream" && <span className="settings-model-state">{t("components.pending_hint")}</span>}
          {(row.kind === "error" || row.kind === "idle") && <Button size="sm" variant="ghost" disabled={!isOnline} onClick={retry}>{t("components.retry")}</Button>}
          {(row.kind === "downloading" || row.kind === "queued") && <Button size="sm" variant="ghost" onClick={() => void componentsCancel(c.id)}>{t("components.pause")}</Button>}
        </li>;
      })}
    </ul>
  </section>;
}
