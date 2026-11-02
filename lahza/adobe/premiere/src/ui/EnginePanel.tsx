import { useState } from "react";

import type { ConnectResult } from "../connection";
import { HOSTPLAN_SCHEMA } from "@shared/hostplan";
import { Section, store, useT } from "./common";

export function EnginePanel({
  state,
  checking,
  onRetry,
  onManual,
}: {
  state: ConnectResult | null;
  checking: boolean;
  onRetry: () => void;
  onManual: (port: string, token: string) => void;
}) {
  const t = useT();
  const [port, setPort] = useState(store.get("port") ?? "");
  const [token, setToken] = useState("");
  const [showManual, setShowManual] = useState(false);

  const ok = state?.ok === true;
  const schemaBad = ok && !state.conn.probe.schemaOk;
  return (
    <Section
      title={t("tab.engine")}
      aside={
        <button className="btn small ghost" onClick={onRetry} disabled={checking}>
          {t("engine.retry")}
        </button>
      }
    >
      {checking && <div className="muted small">{t("engine.checking")}</div>}
      {!checking && ok && (
        <div className="row">
          <span className={`badge ${schemaBad ? "warn" : "good"}`}>
            {t("engine.ok", { version: state.conn.probe.version })}
          </span>
          {state.conn.transport() === "ipc" && <span className="badge warn">{t("engine.via_ipc")}</span>}
        </div>
      )}
      {!checking && schemaBad && (
        <div className="error small">{t("engine.schema_mismatch", { schema: `${state.conn.probe.schema} ≠ ${HOSTPLAN_SCHEMA}` })}</div>
      )}
      {!checking && state && !state.ok && (
        <div className="stack-sm">
          <span className="badge bad">{t("engine.missing")}</span>
          <p className="small">{t("engine.help")}</p>
          {state.locate?.path && <div className="mono muted">{t("engine.discovery_file", { path: state.locate.path })}</div>}
          <div className="mono muted">{state.error}</div>
        </div>
      )}
      {!ok && (
        <div className="stack-sm">
          <button className="btn small ghost" onClick={() => setShowManual((v) => !v)}>
            {t("engine.manual")}
          </button>
          {showManual && (
            <div className="row">
              <label className="field">
                {t("engine.port")}
                <input className="input" value={port} onChange={(e) => setPort(e.currentTarget.value)} inputMode="numeric" />
              </label>
              <label className="field grow">
                {t("engine.token")}
                <input className="input" type="password" value={token} onChange={(e) => setToken(e.currentTarget.value)} />
              </label>
              <button
                className="btn small primary"
                onClick={() => {
                  store.set("port", port);
                  onManual(port, token);
                }}
              >
                {t("engine.connect")}
              </button>
            </div>
          )}
        </div>
      )}
    </Section>
  );
}
