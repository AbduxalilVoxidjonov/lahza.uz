// First-run components (yt-dlp, Remotion, HyperFrames, skill packs): the
// catalog items of kind tool / package / skill-pack, fetched by the SAME
// resumable content queue as the models (ADR 0061) — this module only decides
// WHAT to enqueue and projects queue + disk state for the Settings list. Pure
// + DI like contentQueue.ts; the Electron binding lives in src/main/index.ts.

import {
  COMPONENT_KINDS,
  type ComponentsView,
  type ContentItem,
  type ContentItemStatus,
  type ContentPlatformKey,
  type ContentQueueEntry,
} from "../shared/content-download";

export interface ComponentsDeps {
  catalog: readonly ContentItem[];
  platform: ContentPlatformKey | null;
  statusOf(item: ContentItem): ContentItemStatus;
  entryOf(id: string): ContentQueueEntry | undefined;
  isOnline(): boolean;
}

const isComponent = (item: ContentItem): boolean =>
  COMPONENT_KINDS.includes(item.kind) || item.pending !== undefined;

/** Ids the first-run lane should fetch now: auto-install items that have an
 *  artifact on this platform, are not installed, and are not already queued.
 *  An `error` entry counts as not queued, so a retry re-enqueues it. Empty
 *  while offline — the renderer's `online` event (or the next boot) retries,
 *  rather than burning the 3-attempt budget against a dead network. */
export function componentsToInstall(deps: ComponentsDeps): string[] {
  if (!deps.isOnline()) return [];
  return deps.catalog
    .filter((item) => item.autoInstall === true && !item.pending)
    .filter((item) => deps.platform !== null && item.platforms[deps.platform] !== undefined)
    .filter((item) => deps.statusOf(item).state !== "installed")
    .filter((item) => {
      const entry = deps.entryOf(item.id);
      return !entry || entry.state === "error";
    })
    .map((item) => item.id);
}

export function componentsView(deps: ComponentsDeps): ComponentsView {
  return {
    online: deps.isOnline(),
    components: deps.catalog.filter(isComponent).map((item) => {
      const artifact = deps.platform ? item.platforms[deps.platform] : undefined;
      const queue = deps.entryOf(item.id);
      return {
        id: item.id,
        labelKey: item.labelKey,
        kind: item.kind,
        license: item.license.name,
        bytes: artifact?.bytes ?? 0,
        status: deps.statusOf(item).state,
        ...(queue ? { queue: { ...queue } } : {}),
        ...(item.pending ? { pendingReason: item.pending.reason } : {}),
      };
    }),
  };
}
