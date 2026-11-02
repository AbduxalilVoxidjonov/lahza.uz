import { describe, expect, it } from "vitest";
import type { ComponentView } from "../../shared/content-download";
import { componentRowState } from "./componentRow";
import uz from "../i18n/locales/uz-UZ";
import en from "../i18n/locales/en-US";

const base: ComponentView = { id: "x", labelKey: "content_ytdlp", kind: "tool", license: "MIT", bytes: 100, status: "not_installed" };

describe("componentRowState", () => {
  it("installed wins over everything but an unpinned item", () => {
    expect(componentRowState({ ...base, status: "installed" }, false)).toEqual({ kind: "installed" });
    expect(componentRowState({ ...base, status: "unavailable", pendingReason: "401" }, true)).toEqual({ kind: "pending_upstream" });
  });
  it("shows a percent from the queue and the right phase", () => {
    const q = (state: "downloading" | "verifying", received: number) =>
      componentRowState({ ...base, queue: { itemId: "x", state, receivedBytes: received, totalBytes: 200 } }, true);
    expect(q("downloading", 50)).toEqual({ kind: "downloading", phase: "downloading", percent: 25 });
    expect(q("verifying", 200)).toEqual({ kind: "downloading", phase: "verifying", percent: 100 });
  });
  it("a failed item shows its error even when offline", () => {
    expect(componentRowState({ ...base, queue: { itemId: "x", state: "error", receivedBytes: 0, totalBytes: 1, error: "sha256 mismatch" } }, false))
      .toEqual({ kind: "error", message: "sha256 mismatch" });
  });
  it("offline with nothing moving is its own state; online it is idle", () => {
    expect(componentRowState(base, false)).toEqual({ kind: "offline" });
    expect(componentRowState(base, true)).toEqual({ kind: "idle" });
  });
  it("unavailable platform", () => {
    expect(componentRowState({ ...base, status: "unavailable" }, true)).toEqual({ kind: "unavailable" });
  });
});

describe("components i18n", () => {
  it("uz-UZ and en-US define the same non-empty keys", () => {
    const u = uz.components as Record<string, string>;
    const e = en.components as Record<string, string>;
    expect(Object.keys(u).sort()).toEqual(Object.keys(e).sort());
    for (const v of [...Object.values(u), ...Object.values(e)]) expect(v.length).toBeGreaterThan(0);
    for (const k of ["state_installed", "state_pending_upstream", "state_unavailable", "state_queued", "state_idle", "state_offline", "phase_resuming", "phase_downloading", "phase_verifying", "phase_extracting"]) expect(u[k], k).toBeDefined();
  });
});
