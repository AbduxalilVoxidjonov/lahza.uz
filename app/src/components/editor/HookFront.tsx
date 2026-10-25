import { useHookCandidates, usePutHook } from "../../api/hook-front";
import type { Clip } from "../../api/types";
import { useHookT } from "../../i18n/hook-front";
import { hookPrefixMs } from "../../lib/words";
import { ErrorText, fmtTime } from "../ui";

/**
 * PRO-3 "Hook oldinga": eng kuchli 2–4 s bo'lak klip boshiga nusxalanadi (standart - o'chiq).
 * Yoqilganda engine avtomatik tanlaydi; ro'yxatdan boshqa nomzodni tanlash mumkin.
 */
export function HookFront({ clip, episodeId, onSeek }: { clip: Clip; episodeId: string; onSeek: (ms: number) => void }) {
  const t = useHookT();
  const on = !!clip.hook;
  const putHook = usePutHook(episodeId, clip.id);
  const candidates = useHookCandidates(episodeId, clip.id, on);
  const selected = clip.hook ? `${clip.hook.start_ms}-${clip.hook.end_ms}` : "";
  const known = candidates.data?.some((c) => `${c.start_ms}-${c.end_ms}` === selected);

  return (
    <div className="stack" style={{ gap: 6 }} aria-busy={putHook.isPending}>
      <label className="row check">
        <input
          type="checkbox"
          checked={on}
          disabled={putHook.isPending}
          onChange={(e) => putHook.mutate({ enabled: e.target.checked })}
        />
        <strong>{t("title")}</strong>
        <span className="muted">{t("toggle")}</span>
      </label>
      <span className="muted">{t("hint")}</span>
      {clip.hook && (
        <div className="row">
          <button type="button" className="btn small ghost mono" onClick={() => clip.hook && onSeek(clip.hook.start_ms)}>
            {t("current")} {fmtTime(clip.hook.start_ms)} · {(hookPrefixMs(clip) / 1000).toFixed(1)} s
          </button>
          <label className="row muted">
            {t("other")}
            <select
              value={known ? selected : ""}
              disabled={putHook.isPending || !candidates.data?.length}
              onChange={(e) => {
                const c = candidates.data?.find((x) => `${x.start_ms}-${x.end_ms}` === e.target.value);
                if (c) putHook.mutate({ enabled: true, start_ms: c.start_ms, end_ms: c.end_ms });
              }}
            >
              {!known && <option value="">—</option>}
              {candidates.data?.map((c) => (
                <option key={`${c.start_ms}-${c.end_ms}`} value={`${c.start_ms}-${c.end_ms}`}>
                  {fmtTime(c.start_ms)} · {c.text.length > 60 ? `${c.text.slice(0, 57)}…` : c.text}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="btn small" disabled={putHook.isPending} onClick={() => putHook.mutate({ enabled: true })}>
            {t("auto")}
          </button>
        </div>
      )}
      {putHook.isPending && <span className="muted" role="status">{t("busy")}</span>}
      <ErrorText error={putHook.error ?? candidates.error} />
    </div>
  );
}
