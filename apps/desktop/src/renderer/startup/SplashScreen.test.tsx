// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "../i18n";
import { SplashScreen } from "./SplashScreen";
import type { StartupProgress } from "./initializeRenderer";

const READY_PROGRESS: StartupProgress = {
  pending: [],
  completed: 4,
  total: 4,
};
const READY_STATUS_PROPS = {
  startupProgress: READY_PROGRESS,
  routePending: false,
};

beforeEach(async () => {
  vi.useFakeTimers();
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false })));
  await i18n.changeLanguage("en-US");
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("SplashScreen launch mark", () => {
  it("shows the Lahza Studio logo and wordmark", () => {
    const { container } = render(
      <SplashScreen {...READY_STATUS_PROPS} ready onComplete={() => {}} />,
    );
    const mark = container.querySelector(".splash-mark img");
    expect(mark?.getAttribute("src")).toBe("./icons/lahza.png");
    expect(container.querySelector(".splash-wordmark")?.textContent).toBe("Lahza Studio");
  });
});
