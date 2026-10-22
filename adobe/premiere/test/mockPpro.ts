// premierepro modulining kichik soxta modeli: premiere.ts ning API'dan foydalanish tartibini tekshirish uchun.
// Muhim qoida (changelog 26.3) taqlid qilinadi: action faqat lockedAccess ichida yaratiladi, tranzaksiya ham.
/* eslint-disable @typescript-eslint/no-explicit-any */

type Act = { label: string; run: () => void };

export interface MockParam {
  displayName: string;
  timeVarying: boolean;
  value: unknown;
  keys: { t: number; v: unknown; interp?: number }[];
}

export function makeMockPpro(opts: { transitions?: string[]; filters?: string[] } = {}) {
  let inLock = false;
  const log: string[] = [];
  const need = (what: string) => {
    if (!inLock) throw new Error(`${what}: lockedAccess tashqarisida`);
  };
  const act = (label: string, run: () => void): Act => {
    need(label);
    return { label, run };
  };

  const tick = (s: number) => ({ seconds: s });
  const TickTime = {
    createWithSeconds: (s: number) => tick(s),
    createWithFrameAndFrameRate: (f: number, fr: { value: number }) => tick(f / fr.value),
    TIME_ZERO: tick(0),
  };

  function param(displayName: string, value: unknown): any {
    const p: MockParam & Record<string, any> = {
      displayName,
      timeVarying: false,
      value,
      keys: [],
      areKeyframesSupported: async () => true,
      createSetTimeVaryingAction: (v: boolean) => act(`tv ${displayName}`, () => (p.timeVarying = v)),
      createKeyframe: (v: unknown) => {
        need("createKeyframe");
        return { value: { value: v }, position: tick(0) };
      },
      createSetValueAction: (kf: any) => act(`set ${displayName}`, () => (p.value = kf.value.value)),
      createAddKeyframeAction: (kf: any) => act(`key ${displayName}`, () => p.keys.push({ t: kf.position.seconds, v: kf.value.value })),
      createSetInterpolationAtKeyframeAction: (t: any, mode: number) =>
        act(`interp ${displayName}`, () => {
          const k = p.keys.find((x) => Math.abs(x.t - t.seconds) < 1e-9);
          if (!k) throw new Error("kalit kadr yo'q");
          k.interp = mode;
        }),
    };
    return p;
  }

  function component(matchName: string, params: [string, unknown][]): any {
    const ps = params.map(([n, v]) => param(n, v));
    return { matchName, params: ps, getMatchName: async () => matchName, getParamCount: () => ps.length, getParam: (i: number) => ps[i] };
  }

  function chain(comps: any[]): any {
    return {
      comps,
      getComponentCount: () => comps.length,
      getComponentAtIndex: (i: number) => comps[i],
      createAppendComponentAction: (c: any) => act(`append ${c.matchName}`, () => comps.push(c)),
    };
  }

  function trackItem(kind: "video" | "audio", start: number, inP: number, outP: number): any {
    const it: any = {
      kind,
      start,
      end: start + (outP - inP),
      inP,
      outP,
      disabled: false,
      name: "",
      transitions: [] as unknown[],
      chain:
        kind === "video"
          ? chain([
              component("AE.ADBE Opacity", [["Opacity", 100]]),
              component("AE.ADBE Motion", [
                ["Position", null],
                ["Scale", 100],
                ["Scale Width", 100],
                ["Uniform Scale", true],
                ["Rotation", 0],
              ]),
            ])
          : chain([component("audio.Volume", [["Bypass", false], ["Level", 1]])]),
      getStartTime: async () => tick(it.start),
      getEndTime: async () => tick(it.end),
      getInPoint: async () => tick(it.inP),
      getOutPoint: async () => tick(it.outP),
      getComponentChain: async () => it.chain,
      createSetInPointAction: (t: any) => act("in", () => (it.inP = t.seconds)),
      createSetOutPointAction: (t: any) => act("out", () => (it.outP = t.seconds)),
      createSetEndAction: (t: any) => act("end", () => (it.end = t.seconds)),
      createSetNameAction: (n: string) => act("name", () => (it.name = n)),
      createSetDisabledAction: (d: boolean) => act("disable", () => (it.disabled = d)),
      createAddVideoTransitionAction: (tr: any, o: any) => act("transition", () => it.transitions.push({ name: tr.name, ...o.state })),
    };
    return it;
  }

  const sequences: any[] = [];
  function sequence(name: string): any {
    const vt: any[][] = [[], [], []];
    const at: any[][] = [[], [], []];
    const s: any = {
      name,
      frame: { width: 1920, height: 1080 },
      fps: 25,
      markers: [] as any[],
      vt,
      at,
      getSettings: async () => {
        const pending: any = {};
        return {
          pending,
          setVideoFrameRect: async (r: any) => ((pending.rect = { width: r.width, height: r.height }), true),
          setVideoFrameRate: (fr: any) => ((pending.fps = fr.value), true),
          setAudioSampleRate: async (fr: any) => ((pending.hz = fr.value), true),
          setVideoPixelAspectRatio: async (p: string) => ((pending.par = p), true),
        };
      },
      createSetSettingsAction: (st: any) =>
        act("settings", () => {
          if (st.pending.rect) s.frame = st.pending.rect;
          if (st.pending.fps) s.fps = st.pending.fps;
          s.par = st.pending.par;
        }),
      getFrameSize: async () => s.frame,
      getVideoTrack: async (i: number) => ({ getTrackItems: () => vt[i] ?? [] }),
      getAudioTrackCount: async () => at.length,
      getAudioTrack: async (i: number) => ({ getTrackItems: () => at[i] ?? [] }),
    };
    sequences.push(s);
    return s;
  }

  const rootItems: any[] = [{ kind: "clip", path: "/old/other.mov", inP: null, outP: null }];
  const decorateClip = (c: any) =>
    Object.assign(c, {
      getMediaFilePath: async () => c.path,
      getContentType: async () => 2,
      createSetInOutPointsAction: (a: any, b: any) => act("clip in/out", () => ((c.inP = a.seconds), (c.outP = b.seconds))),
      createClearInOutPointsAction: () => act("clip clear", () => ((c.inP = null), (c.outP = null))),
    });
  rootItems.forEach(decorateClip);
  const imported: string[][] = [];

  const project: any = {
    name: "Demo",
    path: "/p/Demo.prproj",
    lockedAccess: (cb: () => void) => {
      inLock = true;
      try {
        cb();
      } finally {
        inLock = false;
      }
    },
    executeTransaction: (cb: (ca: any) => void, label: string) => {
      need(`transaction ${label}`);
      const acts: Act[] = [];
      cb({ addAction: (a: Act) => (acts.push(a), true) });
      for (const a of acts) a.run();
      log.push(label);
      return true;
    },
    getRootItem: async () => ({ kind: "folder", getItems: async () => [...rootItems] }),
    importFiles: async (paths: string[]) => {
      imported.push(paths);
      for (const p of paths) rootItems.push(decorateClip({ kind: "clip", path: p, inP: null, outP: null }));
      return true;
    },
    getSequences: async () => sequences,
    createSequence: async (n: string) => sequence(n),
    openSequence: async () => true,
    setActiveSequence: async () => true,
    getActiveSequence: async () => sequences.at(-1) ?? null,
  };

  const ppro: any = {
    TickTime,
    FrameRate: { createWithValue: (v: number) => ({ value: v }) },
    RectF: class {
      width = 0;
      height = 0;
    },
    PointF: class {
      constructor(
        public x = 0,
        public y = 0,
      ) {}
    },
    SequenceSettings: { PAR_SQUARE: "1:1" },
    Constants: {
      TrackItemType: { CLIP: 1 },
      ContentType: { MEDIA: 2 },
      InterpolationMode: { BEZIER: 0, HOLD: 1, LINEAR: 2 },
      MarkerColor: { GREEN: 0, RED: 1, YELLOW: 5, BLUE: 6 },
    },
    Marker: { MARKER_TYPE_COMMENT: "Comment" },
    ClipProjectItem: { cast: (it: any) => (it?.kind === "clip" ? it : null) },
    FolderItem: { cast: (it: any) => (it?.kind === "folder" ? it : null) },
    Project: { getActiveProject: async () => project },
    ProjectUtils: { getSelection: async () => ({ getItems: async () => rootItems.slice(-1) }) },
    SequenceEditor: {
      getEditor: (seq: any) => ({
        createInsertProjectItemAction: (item: any, time: any, v: number, a: number, limit: boolean) =>
          act("insert", () => {
            if (!limit) throw new Error("limitShift kutilgan");
            const inP = item.inP ?? 0;
            const outP = item.outP ?? 3600;
            const isAudioOnly = item.path.endsWith(".mp3");
            if (!isAudioOnly) (seq.vt[v] ??= []).push(trackItem("video", time.seconds, inP, outP));
            (seq.at[a] ??= []).push(trackItem("audio", time.seconds, inP, outP));
          }),
      }),
    },
    VideoFilterFactory: {
      getMatchNames: async () => opts.filters ?? ["AE.ADBE Gaussian Blur 2", "AE.ADBE Crop", "PR.ADBE Gamma Correction"],
      createComponent: async (m: string) =>
        m.includes("Crop")
          ? component(m, [["Left", 0], ["Top", 0], ["Right", 0], ["Bottom", 0]])
          : component(m, [["Blurriness", 0], ["Blur Dimensions", 1], ["Repeat Edge Pixels", false]]),
    },
    TransitionFactory: {
      getVideoTransitionMatchNames: async () => opts.transitions ?? ["ADBE Cross Dissolve New", "ADBE Dip To Black", "ADBE Push"],
      createVideoTransition: (name: string) => ({ name }),
    },
    AddTransitionOptions: () => {
      const o: any = { state: {} };
      o.setApplyToStart = (v: boolean) => ((o.state.start = v), o);
      o.setDuration = (t: any) => ((o.state.dur = t.seconds), o);
      return o;
    },
    Markers: {
      getMarkers: async (seq: any) => ({
        createAddMarkerAction: (name: string, type: string, start: any, dur: any, comment: string) =>
          act("marker", () => {
            const m: any = { name, type, start: start.seconds, dur: dur.seconds, comment, color: null };
            m.getName = () => m.name;
            m.getStart = () => tick(m.start);
            m.createSetColorByIndexAction = (c: number) => act("color", () => (m.color = c));
            seq.markers.push(m);
          }),
        getMarkers: () => seq.markers,
      }),
    },
  };

  return { ppro, project, sequences, log, imported, rootItems };
}
