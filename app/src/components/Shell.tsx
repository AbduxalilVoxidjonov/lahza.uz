import { NavLink, Outlet } from "react-router-dom";

import { FirstRunSetup } from "./FirstRunSetup";

import { useT } from "../i18n";

export function Shell() {
  const t = useT();
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
        <NavLink to="/montages" end className={link}>{t("nav.montages")}</NavLink>
        <details className="nav-more">
          <summary>{t("quick.library")}</summary>
          <NavLink to="/projects" className={link}>{t("nav.projects")}</NavLink>
          <NavLink to="/templates" className={link}>{t("nav.templates")}</NavLink>
          <NavLink to="/onboarding" className={link}>{t("quick.setup")}</NavLink>
        </details>
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
