import { useSetYoutubeImport, useYoutubeImportStatus } from "../../api/youtube";
import { youtubeDictionaries } from "../../i18n/youtube";
import { useSettings } from "../../store/settings";
import { YoutubeComponentsInstall } from "../import/YoutubeComponentsInstall";
import { ErrorText, QueryState } from "../ui";

/** YT-1 (ADR-0010): funksiya standart o'chiq - shu yerda yoqiladi; komponentlar holati. */
export function YoutubeImportPanel() {
  const locale = useSettings((s) => s.locale);
  const y = youtubeDictionaries[locale];
  const status = useYoutubeImportStatus();
  const set = useSetYoutubeImport();
  const st = status.data;
  const yn = (v: boolean) => <span className={`badge ${v ? "good" : "warn"}`}>{v ? y.yes : y.no}</span>;
  return (
    <section className="card stack" aria-labelledby="set-youtube">
      <h2 id="set-youtube">{y.setTitle}</h2>
      <QueryState query={status} />
      {st && (
        <>
          <label className="row">
            <input type="checkbox" checked={st.enabled} disabled={set.isPending}
                   onChange={(e) => set.mutate(e.target.checked)} />
            {y.setToggle}
          </label>
          <span className="muted">{y.setHint}</span>
          <span className="muted">{y.setLegal}</span>
          {!st.installed && <div className="notice warn">{y.notInstalled}</div>}
          <YoutubeComponentsInstall st={st} updates />
          <table className="table">
            <tbody>
              <tr><th>{y.compYtdlp}</th><td>{yn(st.installed)} {st.version && <span className="mono muted">{st.version}</span>}</td></tr>
              <tr><th>{y.compEjs}</th><td>{yn(st.ejs)}</td></tr>
              <tr><th>{y.compJs}</th><td>{yn(!!st.js_runtime)} {st.js_runtime && <span className="mono muted">{st.js_runtime}</span>}</td></tr>
              <tr><th>{y.compFfmpeg}</th><td>{yn(st.ffmpeg)}</td></tr>
            </tbody>
          </table>
        </>
      )}
      <ErrorText error={set.error} />
    </section>
  );
}
