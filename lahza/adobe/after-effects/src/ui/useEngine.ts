// Engine ulanish holati: engine.json (CEP Node) -> /v1/health + /v1/hostplan/schema; bo'lmasa qo'lda port/token.
import { useCallback, useEffect, useState } from "react";
import { EngineClient, type EngineInfo } from "../../../shared/src/engine";
import { HOSTPLAN_SCHEMA } from "../../../shared/src/hostplan";
import { probeEngine, readDiscovery } from "../host/discovery";

export type EngineState =
  | { kind: "checking" }
  | { kind: "ok"; client: EngineClient; version: string }
  | { kind: "down"; reason: "missing" | "no-node" | "stale" | "invalid" | "schema"; detail?: string };

const MANUAL_KEY = "lahza.ae.manualEngine";

function loadManual(): EngineInfo | null {
  try {
    const raw = localStorage.getItem(MANUAL_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as EngineInfo;
    return typeof v.port === "number" && typeof v.token === "string" ? v : null;
  } catch {
    return null;
  }
}

function saveManual(info: EngineInfo) {
  try {
    localStorage.setItem(MANUAL_KEY, JSON.stringify({ port: info.port, token: info.token }));
  } catch {
    /* localStorage yo'q — har safar qo'lda */
  }
}

async function tryConnect(info: EngineInfo): Promise<EngineState> {
  const client = new EngineClient(info, (u, i) => fetch(u, i));
  try {
    const p = await probeEngine(client);
    if (p.schema !== HOSTPLAN_SCHEMA) return { kind: "down", reason: "schema", detail: p.schema };
    return { kind: "ok", client, version: p.version };
  } catch (e) {
    return { kind: "down", reason: "stale", detail: e instanceof Error ? e.message : String(e) };
  }
}

export function useEngine() {
  const [state, setState] = useState<EngineState>({ kind: "checking" });

  const check = useCallback(async () => {
    setState({ kind: "checking" });
    const d = readDiscovery();
    if (d.kind === "found") {
      setState(await tryConnect(d.info));
      return;
    }
    const manual = loadManual();
    if (manual) {
      const s = await tryConnect(manual);
      if (s.kind === "ok") {
        setState(s);
        return;
      }
    }
    setState({
      kind: "down",
      reason: d.kind === "no-node" ? "no-node" : d.kind === "invalid" ? "invalid" : "missing",
      detail: d.kind === "invalid" ? d.error : d.kind === "missing" ? d.path : undefined,
    });
  }, []);

  const connectManual = useCallback(async (port: number, token: string) => {
    setState({ kind: "checking" });
    const info = { port, token };
    const s = await tryConnect(info);
    if (s.kind === "ok") saveManual(info);
    setState(s);
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  return { state, check, connectManual };
}
