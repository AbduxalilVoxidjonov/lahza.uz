import { useCapabilities } from "../../api/hooks";
import type { Capabilities } from "../../api/types";
import { useT, type MessageKey } from "../../i18n";
import { QueryState } from "../ui";

const FLAGS: { key: keyof Capabilities; label: MessageKey }[] = [
  { key: "ffmpeg", label: "cap.ffmpeg" },
  { key: "libass", label: "cap.libass" },
  { key: "aligner", label: "cap.aligner" },
  { key: "diarizer", label: "cap.diarizer" },
  { key: "face_detector", label: "cap.face" },
  { key: "llm", label: "cap.llm" },
];

/** Engine imkoniyatlari; libass yo'q bo'lsa subtitr kuydirilmaydi - ogohlantiramiz. */
export function CapabilitiesPanel() {
  const t = useT();
  const caps = useCapabilities();
  const c = caps.data;
  return (
    <section className="card stack" aria-labelledby="set-caps">
      <h2 id="set-caps">{t("cap.title")}</h2>
      <QueryState query={caps} />
      {c && !c.libass && <div className="notice warn" role="alert">{t("cap.noLibass")}</div>}
      {c && !c.ffmpeg && <div className="notice bad" role="alert">{t("cap.noFfmpeg")}</div>}
      {c && (
        <table className="table">
          <tbody>
            {FLAGS.map((f) => (
              <tr key={f.key}>
                <th>{t(f.label)}</th>
                <td>
                  <span className={`badge ${c[f.key] ? "good" : "warn"}`}>{c[f.key] ? t("cap.yes") : t("cap.no")}</span>
                </td>
              </tr>
            ))}
            <tr>
              <th>{t("cap.vad")}</th>
              <td className="mono">{c.vad}</td>
            </tr>
            <tr>
              <th>{t("cap.encoders")}</th>
              <td className="mono">{c.encoders.join(", ") || "—"}</td>
            </tr>
          </tbody>
        </table>
      )}
    </section>
  );
}
