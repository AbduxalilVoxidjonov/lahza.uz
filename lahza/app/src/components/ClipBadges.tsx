import type { ClipKind, ClipStatus } from "../api/types";
import { useT } from "../i18n";

export const CLIP_KINDS: ClipKind[] = ["maslahat", "hikoya", "kulgili", "bahsli_fikr", "fakt", "savol_javob"];
export const CLIP_STATUSES: ClipStatus[] = ["nomzod", "qabul", "rad", "eksport_qilingan"];

export function KindBadge({ kind }: { kind: ClipKind | null }) {
  const t = useT();
  if (!kind) return null;
  return <span className="badge">{t(`kind.${kind}`)}</span>;
}

export function StatusBadge({ status }: { status: ClipStatus }) {
  const t = useT();
  const cls = status === "qabul" ? "good" : status === "rad" ? "bad" : status === "eksport_qilingan" ? "accent" : "";
  return <span className={`badge ${cls}`}>{t(`status.${status}`)}</span>;
}
