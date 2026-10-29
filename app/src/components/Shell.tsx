import { NavLink, Outlet } from "react-router-dom";

import { FirstRunSetup } from "./FirstRunSetup";

import { useT } from "../i18n";
import { youtubeDictionaries } from "../i18n/youtube";
import { useSettings } from "../store/settings";

export function Shell() {
  const t = useT();
  const locale = useSettings((s) => s.locale);
  const link = ({ isActive }: { isActive: boolean }) => `nav-link${isActive ? " active" : ""}`;
  return (
    <div className="shell">
      {/* Hash router: href o'rniga fokusni qo'lda ko'chiramiz. */}
      <a
        href="#main"
        className="skip-link"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main")?.focus();
        }}
      >
        {t("a11y.skip")}
      </a>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden />
          {t("app.name")}
        </div>
        <nav aria-label={t("a11y.nav")} className="stack" style={{ gap: 4 }}>
        <NavLink to="/montages/new" className={link}>{t("quick.start")}</NavLink>
        {/* YT-1: YouTube havolasi Boshlash sahifasining 1-qadamida; bu havola maydonga fokus beradi. */}
        <div className="nav-group" style={{ margin: 0 }}>
          <NavLink to="/montages/new?src=youtube" className={() => "nav-link"}>▶ {youtubeDictionaries[locale].navLink}</NavLink>
        </div>
        <NavLink to="/montages" end className={link}>{t("nav.montages")}</NavLink>
        <details className="nav-more">
          <summary>{t("quick.library")}</summary>
          <NavLink to="/projects" className={link}>{t("nav.projects")}</NavLink>
          <NavLink to="/templates" className={link}>{t("nav.templates")}</NavLink>
          <NavLink to="/onboarding" className={link}>{t("quick.setup")}</NavLink>
        </details>
        <NavLink to="/claude" className={link}>{t("nav.claude")}</NavLink>
        <NavLink to="/exports" className={link}>
          {t("nav.exports")}
        </NavLink>
        <NavLink to="/settings" className={link}>
          {t("nav.settings")}
        </NavLink>
        </nav>
        <div className="sidebar-foot">{t("set.privacy")}</div>
      </aside>
      <main className="main" id="main" tabIndex={-1}>
        <FirstRunSetup />
        <Outlet />
      </main>
    </div>
  );
}
