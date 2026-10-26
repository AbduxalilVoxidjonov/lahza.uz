import { useEffect, useRef, useState } from "react";

import { useCheckClaudeAuth, useClaudeConnection, useClaudeStatus, useSetClaudeEnabled } from "../api/claude";
import { ClaudeErrorText } from "../components/claude/ClaudeErrorText";
import { useClaudeT } from "../i18n/claude/hook";
import { fmt, type ClaudeMessages } from "../i18n/claude";
import {
  CLAUDE_INSTALL_LINKS, claudeView, confirmableActions,
  type ClaudeAuthState, type ClaudeStatus, type ClaudeTarget,
} from "../lib/claude";

type Kind = "connect" | "disconnect";
type Pending = { kind: Kind; target: ClaudeTarget; actions: string[] };

const AUTH_LABEL: Record<ClaudeAuthState, keyof ClaudeMessages> = {
  unknown: "authUnknown", ok: "authOk", not_logged_in: "authNotLoggedIn", error: "authError",
};
const AUTH_BADGE: Record<ClaudeAuthState, string> = { unknown: "", ok: "good", not_logged_in: "warn", error: "bad" };

/** "Claude montaj" bo'limi: holat, yoqish, login tekshiruvi, MCP ulash/uzish, o'rnatish yo'riqnomasi. */
export function Claude() {
  const { c } = useClaudeT();
  const status = useClaudeStatus();
  const st = status.data;
  return (
    <div className="stack" style={{ gap: 20, maxWidth: 980 }}>
      <h1>{c.title}</h1>
      <p className="muted" style={{ margin: 0 }}>{c.lead}</p>
      {status.isLoading && <span className="muted" role="status">{c.statusTitle}…</span>}
      {status.error && (
        <div className="row">
          {status.error instanceof Error && status.error.message === "Invalid claude status response"
            ? <span className="error" role="alert">{c.invalidStatus}</span>
            : <ClaudeErrorText error={status.error} />}
          <button className="btn small" disabled={status.isFetching} onClick={() => void status.refetch()}>{c.refresh}</button>
        </div>
      )}
      {st && <EnableCard st={st} />}
      {st && <StatusCard st={st} onRefresh={() => void status.refetch()} refreshing={status.isFetching} />}
      {st && <McpCard st={st} />}
      {st && claudeView(st).showInstallGuide && <InstallGuide st={st} />}
    </div>
  );
}

function EnableCard({ st }: { st: ClaudeStatus }) {
  const { c } = useClaudeT();
  const set = useSetClaudeEnabled();
  return (
    <section className="card stack" aria-labelledby="claude-enable">
      <h2 id="claude-enable" style={{ margin: 0 }}>{c.toggle}</h2>
      <div className="notice warn">{c.privacy}</div>
      <label className="row">
        <input type="checkbox" checked={st.enabled} disabled={set.isPending}
               onChange={(e) => set.mutate(e.target.checked)} />
        {c.toggle}
      </label>
      <ClaudeErrorText error={set.error} />
    </section>
  );
}

function StatusCard({ st, onRefresh, refreshing }: { st: ClaudeStatus; onRefresh: () => void; refreshing: boolean }) {
  const { c } = useClaudeT();
  const check = useCheckClaudeAuth();
  const view = claudeView(st);
  const yn = (v: boolean) => <span className={`badge ${v ? "good" : "warn"}`}>{v ? c.found : c.missing}</span>;
  return (
    <section className="card stack" aria-labelledby="claude-status">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 id="claude-status" style={{ margin: 0 }}>{c.statusTitle}</h2>
        <button className="btn small" disabled={refreshing} onClick={onRefresh}>{c.refresh}</button>
      </div>
      <table className="table">
        <tbody>
          <tr>
            <th>{c.cli}</th>
            <td>
              {yn(st.cli.installed)}{" "}
              {st.cli.version && <span className="mono muted">{c.version}: {st.cli.version}</span>}
              {st.cli.path && <div className="mono muted" style={{ overflowWrap: "anywhere" }}>{c.path}: {st.cli.path}</div>}
            </td>
          </tr>
          <tr>
            <th>{c.desktop}</th>
            <td>
              {yn(st.desktop.installed)}
              {st.desktop.path && <div className="mono muted" style={{ overflowWrap: "anywhere" }}>{c.path}: {st.desktop.path}</div>}
            </td>
          </tr>
          <tr>
            <th>{c.auth}</th>
            <td>
              <div className="row">
                <span className={`badge ${AUTH_BADGE[st.auth.state]}`}>{c[AUTH_LABEL[st.auth.state]]}</span>
                <button className="btn small" disabled={!view.canCheckAuth || check.isPending} onClick={() => check.mutate()}>
                  {check.isPending ? c.checkingAuth : c.checkAuth}
                </button>
                {st.auth.checked_at && <span className="muted">{fmt(c.checkedAt, { v: new Date(st.auth.checked_at).toLocaleString() })}</span>}
              </div>
              {st.auth.detail && <div className="mono muted">{st.auth.detail}</div>}
              {st.auth.state === "not_logged_in" && <div className="muted">{c.notLoggedInHint}</div>}
              <ClaudeErrorText error={check.error} />
            </td>
          </tr>
          <tr>
            <th>{c.mcpTitle}</th>
            <td className="row">
              {view.targets.map((x) => (
                <span key={x.target} className={`badge ${x.connected ? "good" : ""}`}>
                  {x.target === "claude_code" ? c.cli : c.desktop}: {x.connected ? c.connected : c.notConnected}
                </span>
              ))}
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  );
}

function McpCard({ st }: { st: ClaudeStatus }) {
  const { c } = useClaudeT();
  const connect = useClaudeConnection("connect");
  const disconnect = useClaudeConnection("disconnect");
  const [pending, setPending] = useState<Pending | null>(null);
  const [done, setDone] = useState(false);
  const mutation = (k: Kind) => (k === "connect" ? connect : disconnect);
  const busy = connect.isPending || disconnect.isPending;
  const label = (target: ClaudeTarget) => (target === "claude_code" ? c.cli : c.desktop);

  // 1-qadam: dry_run - faqat amallar ro'yxati, hech narsa o'zgarmaydi.
  const prepare = (kind: Kind, target: ClaudeTarget) => {
    setDone(false);
    connect.reset(); disconnect.reset();
    mutation(kind).mutate({ target, dry_run: true }, {
      onSuccess: (res) => setPending({ kind, target, actions: res.actions }),
    });
  };
  // 2-qadam: foydalanuvchi tasdiqlagandan keyin haqiqiy chaqiruv.
  const confirm = () => {
    if (!pending) return;
    mutation(pending.kind).mutate({ target: pending.target, dry_run: false }, {
      onSuccess: () => { setPending(null); setDone(true); },
    });
  };

  return (
    <section className="card stack" aria-labelledby="claude-mcp">
      <h2 id="claude-mcp" style={{ margin: 0 }}>{c.mcpTitle}</h2>
      <span className="muted">{c.mcpHint}</span>
      <table className="table">
        <tbody>
          {claudeView(st).targets.map((x) => (
            <tr key={x.target}>
              <th>{label(x.target)}</th>
              <td>
                <div className="row">
                  <span className={`badge ${x.connected ? "good" : ""}`}>{x.connected ? c.connected : c.notConnected}</span>
                  {!x.installed && <span className="badge warn">{c.missing}</span>}
                  {x.connected
                    ? <button className="btn small" disabled={busy || !x.canDisconnect} onClick={() => prepare("disconnect", x.target)}>{c.disconnect}</button>
                    : <button className="btn small" disabled={busy || !x.canConnect} onClick={() => prepare("connect", x.target)}>{c.connect}</button>}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {st.mcp_command.length > 0 && (
        <details>
          <summary className="muted">{c.mcpCommand}</summary>
          <code className="mono" style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", userSelect: "text" }}>{st.mcp_command.join(" ")}</code>
        </details>
      )}
      {busy && !pending && <span className="muted" role="status">{c.preparing}</span>}
      {done && <span role="status" className="badge good">{c.done}</span>}
      {!pending && <ClaudeErrorText error={connect.error ?? disconnect.error} />}
      {pending && (
        <ConfirmDialog
          title={fmt(pending.kind === "connect" ? c.connectTitle : c.disconnectTitle, { target: label(pending.target) })}
          actions={pending.actions}
          busy={busy}
          error={mutation(pending.kind).error}
          onConfirm={confirm}
          onClose={() => { if (!busy) setPending(null); }}
        />
      )}
    </section>
  );
}

function ConfirmDialog({ title, actions, busy, error, onConfirm, onClose }: {
  title: string; actions: string[]; busy: boolean; error: unknown; onConfirm: () => void; onClose: () => void;
}) {
  const { c } = useClaudeT();
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
  }, []);
  const list = confirmableActions(actions);
  return (
    <dialog ref={ref} className="card" onClose={onClose} onCancel={(e) => { if (busy) e.preventDefault(); }}
      aria-labelledby="claude-confirm-title" style={{ width: "min(720px, 92vw)", color: "inherit", padding: 20 }}>
      <div className="stack">
        <h3 id="claude-confirm-title" style={{ margin: 0 }}>{title}</h3>
        {list.empty ? <p className="muted">{c.noActions}</p> : (
          <>
            <p style={{ margin: 0 }}>{c.confirmLead}</p>
            <ol className="mono" style={{ margin: 0, overflowWrap: "anywhere" }}>
              {list.actions.map((a, i) => <li key={i}>{a}</li>)}
            </ol>
          </>
        )}
        <ClaudeErrorText error={error} />
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button className="btn" type="button" disabled={busy} onClick={() => ref.current?.close()} autoFocus>{c.cancel}</button>
          <button className="btn primary" type="button" disabled={busy || list.empty} onClick={onConfirm}>
            {busy ? c.preparing : c.confirm}
          </button>
        </div>
      </div>
    </dialog>
  );
}

function InstallGuide({ st }: { st: ClaudeStatus }) {
  const { c } = useClaudeT();
  return (
    <section className="card stack" aria-labelledby="claude-install">
      <h2 id="claude-install" style={{ margin: 0 }}>{c.installTitle}</h2>
      {!st.cli.installed && <LinkLine text={c.installCode} url={CLAUDE_INSTALL_LINKS.claude_code} />}
      {!st.desktop.installed && <LinkLine text={c.installDesktop} url={CLAUDE_INSTALL_LINKS.claude_desktop} />}
      <span className="muted">{c.installCopy} {c.installAfter}</span>
    </section>
  );
}

/** Tashqi havola matn sifatida (ilovada tashqi brauzer ochuvchi plagin yo'q) + nusxalash. */
function LinkLine({ text, url }: { text: string; url: string }) {
  const { c } = useClaudeT();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(url); setCopied(true); } catch { setCopied(false); }
  };
  return (
    <div className="stack" style={{ gap: 4 }}>
      <span>{text}</span>
      <div className="row">
        <code className="mono" style={{ userSelect: "all", overflowWrap: "anywhere" }}>{url}</code>
        <button className="btn small" type="button" onClick={() => void copy()}>{copied ? c.copied : c.copy}</button>
      </div>
    </div>
  );
}
