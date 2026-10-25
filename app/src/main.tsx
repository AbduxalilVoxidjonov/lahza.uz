import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createHashRouter, Navigate, RouterProvider } from "react-router-dom";

import { useEngineEvents } from "./api/hooks";
import { Shell } from "./components/Shell";
import { ClipEditor } from "./pages/ClipEditor";
import { Episode } from "./pages/Episode";
import { Exports } from "./pages/Exports";
import { Montage } from "./pages/Montage";
import { MontageNew } from "./pages/MontageNew";
import { Montages } from "./pages/Montages";
import { Onboarding } from "./pages/Onboarding";
import { Projects } from "./pages/Projects";
import { Settings } from "./pages/Settings";
import { TemplateEditor } from "./pages/TemplateEditor";
import { Templates } from "./pages/Templates";
import { Transcript } from "./pages/Transcript";
import { useDocumentLang } from "./i18n";
import "./styles/app.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

/** Montajni boshlash uchun ASR modeli talab qilinmaydi. */
function Home() {
  return <Navigate to="/montages/new" replace />;
}

/** WebSocket hodisalari ilova bo'ylab bir marta ulanadi (onboarding ham shu jumladan). */
function EngineEvents() {
  useEngineEvents();
  useDocumentLang();
  return null;
}

// Hash router: desktop WebView'da server tomonidagi marshrutlash yo'q.
const router = createHashRouter([
  { path: "/onboarding", element: <Onboarding /> },
  {
    element: <Shell />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/projects", element: <Projects /> },
      { path: "/projects/:projectId", element: <Projects /> },
      { path: "/episodes/:episodeId", element: <Episode /> },
      { path: "/episodes/:episodeId/transcript", element: <Transcript /> },
      { path: "/episodes/:episodeId/clips/:clipId", element: <ClipEditor /> },
      { path: "/templates", element: <Templates /> },
      { path: "/templates/:id", element: <TemplateEditor /> },
      { path: "/montages", element: <Montages /> },
      { path: "/montages/new", element: <MontageNew /> },
      { path: "/montages/:id", element: <Montage /> },
      { path: "/exports", element: <Exports /> },
      { path: "/settings", element: <Settings /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <EngineEvents />
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
