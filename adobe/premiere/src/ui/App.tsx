import { useCallback, useEffect, useMemo, useState } from "react";

import { connectEngine, type ConnectResult } from "../connection";
import { hostOutDir, manualEngine, toUxpFileUrl, uxpLocatorEnv } from "../engineLocator";
import type { FlowDeps } from "../flow";
import type { HostAdapter } from "../host/adapter";
import type { Locale } from "../i18n";
import { uxpIpcFs } from "../transport";
import { hostRequire, type UxpFs } from "../uxp-env";
import { LocaleContext, errMsg, store, useT } from "./common";
import { EnginePanel } from "./EnginePanel";
import { MontageTab } from "./MontageTab";
import { ReelsTab } from "./ReelsTab";

type Tab = "reels" | "montage";

export function App({ adapter }: { adapter: HostAdapter }) {
  const [locale, setLocale] = useState<Locale>(store.get("locale") === "en" ? "en" : "uz");
  return (
    <LocaleContext.Provider value={locale}>
      <Shell
        adapter={adapter}
        locale={locale}
        toggleLocale={() => {
          const next = locale === "uz" ? "en" : "uz";
          store.set("locale", next);
          setLocale(next);
        }}
      />
    </LocaleContext.Provider>
  );
}

function Shell({ adapter, locale, toggleLocale }: { adapter: HostAdapter; locale: Locale; toggleLocale: () => void }) {
  const t = useT();
  const env = useMemo(() => uxpLocatorEnv(), []);
  const fs = useMemo(() => hostRequire<UxpFs>("fs"), []);
  const [conn, setConn] = useState<ConnectResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [tab, setTab] = useState<Tab>("reels");

  const connect = useCallback(
    async (manual?: { port: string; token: string }) => {
      setChecking(true);
      try {
        const info = manual ? manualEngine(manual.port, manual.token) : null;
        setConn(
          await connectEngine({
            env,
            manual: info,
            httpFetch: (u, i) => fetch(u, i),
            ipcFs: fs ? uxpIpcFs(fs, toUxpFileUrl) : null,
          }),
        );
      } catch (e) {
        setConn({ ok: false, locate: null, error: errMsg(e) });
      } finally {
        setChecking(false);
      }
    },
    [env, fs],
  );

  useEffect(() => {
    void connect();
  }, [connect]);

  const deps: FlowDeps | null = useMemo(() => {
    if (!conn?.ok) return null;
    const base = env ?? { platform: "darwin" as const, home: "/tmp" };
    return {
      client: conn.conn.client,
      adapter,
      outDir: (name) => hostOutDir(base, name),
      prepareOutDir: fs
        ? async (dir) => {
            const parent = dir.replace(/[\\/][^\\/]+$/, "");
            try {
              await fs.mkdir(toUxpFileUrl(parent), { recursive: true });
            } catch {
              /* allaqachon bor */
            }
          }
        : undefined,
    };
  }, [conn, env, fs, adapter]);

  return (
    <div className="app">
      <header className="top">
        <span className="brand">
          <span className="brand-mark" /> {t("app.title")}
        </span>
        <nav className="tabs">
          <button className={`tab ${tab === "reels" ? "active" : ""}`} onClick={() => setTab("reels")}>
            {t("tab.reels")}
          </button>
          <button className={`tab ${tab === "montage" ? "active" : ""}`} onClick={() => setTab("montage")}>
            {t("tab.montage")}
          </button>
        </nav>
        <button className="btn small ghost" onClick={toggleLocale}>
          {t("common.lang")}
        </button>
      </header>
      <main className="stack">
        <EnginePanel state={conn} checking={checking} onRetry={() => void connect()} onManual={(port, token) => void connect({ port, token })} />
        {deps && tab === "reels" && <ReelsTab deps={deps} />}
        {deps && tab === "montage" && <MontageTab deps={deps} locale={locale} />}
      </main>
    </div>
  );
}
