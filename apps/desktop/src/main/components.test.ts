import { describe, expect, it } from "vitest";
import type { ContentItem, ContentItemStatus, ContentQueueEntry } from "../shared/content-download";
import { CONTENT_CATALOG } from "../shared/content-catalog";
import { componentsToInstall, componentsView, type ComponentsDeps } from "./components";

function deps(over: Partial<ComponentsDeps> & { installed?: string[]; queue?: ContentQueueEntry[] } = {}): ComponentsDeps {
  const installed = new Set(over.installed ?? []);
  const queue = over.queue ?? [];
  return {
    catalog: over.catalog ?? CONTENT_CATALOG,
    platform: "linux-x64",
    statusOf: (item: ContentItem): ContentItemStatus =>
      item.platforms["linux-x64"] === undefined ? { state: "unavailable" }
        : installed.has(item.id) ? { state: "installed", entryPath: "/e", installDir: "/d" } : { state: "not_installed" },
    entryOf: (id) => queue.find((e) => e.itemId === id),
    isOnline: () => true,
    ...over,
  };
}
const AUTO = CONTENT_CATALOG.filter((i) => i.autoInstall).map((i) => i.id);

describe("componentsToInstall", () => {
  it("enqueues every missing auto-install component on a fresh machine, and no model", () => {
    const ids = componentsToInstall(deps());
    expect(ids.sort()).toEqual([...AUTO].sort());
    expect(ids).not.toContain("whisper-model-base");
    expect(ids).not.toContain("asr-navaistt");
  });
  it("skips installed ones and ones already in flight", () => {
    const ids = componentsToInstall(deps({
      installed: ["yt-dlp"],
      queue: [{ itemId: "hyperframes", state: "downloading", receivedBytes: 1, totalBytes: 2 }],
    }));
    expect(ids).not.toContain("yt-dlp");
    expect(ids).not.toContain("hyperframes");
    expect(ids).toContain("remotion-core");
  });
  it("re-enqueues an errored one (retry)", () => {
    const ids = componentsToInstall(deps({ queue: [{ itemId: "yt-dlp", state: "error", receivedBytes: 0, totalBytes: 1, error: "x" }] }));
    expect(ids).toContain("yt-dlp");
  });
  it("offline: nothing is enqueued, so the retry budget is not burned", () => {
    expect(componentsToInstall(deps({ isOnline: () => false }))).toEqual([]);
  });
  it("an unknown platform enqueues nothing", () => {
    expect(componentsToInstall(deps({ platform: null }))).toEqual([]);
  });
});

describe("componentsView", () => {
  it("lists components plus the pinned NavaiST rows, joined with status and queue", () => {
    const view = componentsView(deps({
      installed: ["yt-dlp"],
      queue: [{ itemId: "openmontage", state: "downloading", receivedBytes: 5, totalBytes: 10 }],
    }));
    const by = (id: string) => view.components.find((c) => c.id === id)!;
    expect(view.online).toBe(true);
    expect(by("yt-dlp").status).toBe("installed");
    expect(by("openmontage").queue?.receivedBytes).toBe(5);
    expect(by("openmontage").bytes).toBeGreaterThan(0);
    expect(by("asr-navaistt").license).toMatch(/permission required/);
    expect(by("asr-navaistt").bytes).toBe(1527906453);
    expect(by("asr-navaistt").status).toBe("not_installed");
    expect(view.components.map((c) => c.id)).not.toContain("whisper-model-base");
  });
  it("reports offline", () => {
    expect(componentsView(deps({ isOnline: () => false })).online).toBe(false);
  });
});
