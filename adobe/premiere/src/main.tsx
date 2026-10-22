// Panel kirish nuqtasi. Premiere ichida - haqiqiy adapter; oddiy brauzerda (UI ko'rish) - soxta adapter.
import { createRoot } from "react-dom/client";

import { FakeAdapter } from "./host/fake";
import { PremiereAdapter } from "./host/premiere";
import { App } from "./ui/App";
import { isInPremiere } from "./uxp-env";

const adapter = isInPremiere() ? new PremiereAdapter() : new FakeAdapter({ selected: ["/demo/podcast.mp4"] });
const el = document.getElementById("root");
if (el) createRoot(el).render(<App adapter={adapter} />);
