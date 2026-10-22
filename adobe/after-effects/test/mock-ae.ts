// Node'dagi soxta After Effects obyekt modeli (faqat host.jsx ishlatadigan qism).
// Nomlar va xatti-harakatlar ae-scripting.docsforadobe.dev ga mos: kolleksiyalar 1-asosli, yangi qatlam
// tepaga (index 1) qo'shiladi, property'lar matchName bo'yicha, setTemporalEaseAtKey o'lchamlari
// propertyValueType bo'yicha (TwoD -> 2, ThreeD -> 3, boshqa -> 1) tekshiriladi.
import { readFileSync } from "node:fs";
import vm from "node:vm";

export const PropertyValueType = {
  NO_VALUE: 6412,
  ThreeD_SPATIAL: 6413,
  ThreeD: 6414,
  TwoD_SPATIAL: 6415,
  TwoD: 6416,
  OneD: 6417,
  COLOR: 6418,
  CUSTOM_VALUE: 6419,
  MARKER: 6420,
  LAYER_INDEX: 6421,
  MASK_INDEX: 6422,
  SHAPE: 6423,
  TEXT_DOCUMENT: 6424,
} as const;

export const KeyframeInterpolationType = { LINEAR: 6612, BEZIER: 6613, HOLD: 6614 } as const;

type Spec = { kind: "prop"; type: number; init: unknown } | { kind: "group"; children: [string, Spec][]; addable?: string[] };

const P = (type: number, init: unknown): Spec => ({ kind: "prop", type, init });
const G = (children: [string, Spec][], addable?: string[]): Spec => ({ kind: "group", children, addable });

// addProperty() bilan qo'shiladigan guruhlar shabloni
const ADDABLE: Record<string, () => Spec> = {
  "ADBE Gaussian Blur 2": () =>
    G([
      ["ADBE Gaussian Blur 2-0001", P(PropertyValueType.OneD, 0)],
      ["ADBE Gaussian Blur 2-0002", P(PropertyValueType.OneD, 1)],
      ["ADBE Gaussian Blur 2-0003", P(PropertyValueType.OneD, 0)],
    ]),
  "ADBE Mask Atom": () =>
    G([
      ["ADBE Mask Shape", P(PropertyValueType.SHAPE, null)],
      ["ADBE Mask Feather", P(PropertyValueType.TwoD, [0, 0])],
      ["ADBE Mask Opacity", P(PropertyValueType.OneD, 100)],
    ]),
  "ADBE Text Animator": () =>
    G([
      ["ADBE Text Selectors", G([], ["ADBE Text Selector"])],
      ["ADBE Text Animator Properties", G([], ["ADBE Text Fill Color"])],
    ]),
  "ADBE Text Selector": () =>
    G([
      ["ADBE Text Percent Start", P(PropertyValueType.OneD, 0)],
      ["ADBE Text Percent End", P(PropertyValueType.OneD, 100)],
      ["ADBE Text Index Start", P(PropertyValueType.OneD, 0)],
      ["ADBE Text Index End", P(PropertyValueType.OneD, 0)],
      ["ADBE Text Range Advanced", G([["ADBE Text Range Units", P(PropertyValueType.OneD, 1)]])],
    ]),
  "ADBE Text Fill Color": () => P(PropertyValueType.COLOR, [1, 0, 0, 1]),
};

function layerSpec(text: boolean): [string, Spec][] {
  const base: [string, Spec][] = [
    ["ADBE Marker", P(PropertyValueType.MARKER, null)],
    ["ADBE Mask Parade", G([], ["ADBE Mask Atom"])],
    ["ADBE Effect Parade", G([], ["ADBE Gaussian Blur 2"])],
    [
      "ADBE Transform Group",
      G([
        ["ADBE Anchor Point", P(PropertyValueType.TwoD_SPATIAL, [0, 0])],
        ["ADBE Position", P(PropertyValueType.TwoD_SPATIAL, [0, 0])],
        ["ADBE Scale", P(PropertyValueType.ThreeD, [100, 100, 100])],
        ["ADBE Rotate Z", P(PropertyValueType.OneD, 0)],
        ["ADBE Opacity", P(PropertyValueType.OneD, 100)],
      ]),
    ],
    ["ADBE Audio Group", G([["ADBE Audio Levels", P(PropertyValueType.TwoD, [0, 0])]])],
  ];
  if (text) {
    base.unshift([
      "ADBE Text Properties",
      G([
        ["ADBE Text Document", P(PropertyValueType.TEXT_DOCUMENT, null)],
        ["ADBE Text Animators", G([], ["ADBE Text Animator"])],
      ]),
    ]);
  }
  return base;
}

export interface Key {
  t: number;
  v: unknown;
  inType: number;
  outType: number;
  easeIn?: unknown[];
}

export class MockProperty {
  keys: Key[] = [];
  private _value: unknown;
  constructor(
    public matchName: string,
    public propertyValueType: number,
    init: unknown,
  ) {
    this._value = init;
  }
  get name() {
    return this.matchName;
  }
  get numKeys() {
    return this.keys.length;
  }
  get value() {
    if (this.propertyValueType === PropertyValueType.TEXT_DOCUMENT) {
      return { ...(this._value as object) };
    }
    return this._value;
  }
  private check(v: unknown) {
    const t = this.propertyValueType;
    const len = Array.isArray(v) ? v.length : -1;
    const ok =
      t === PropertyValueType.OneD
        ? typeof v === "number" && !Number.isNaN(v)
        : t === PropertyValueType.TwoD || t === PropertyValueType.TwoD_SPATIAL
          ? len === 2
          : t === PropertyValueType.ThreeD || t === PropertyValueType.ThreeD_SPATIAL
            ? len === 2 || len === 3
            : t === PropertyValueType.COLOR
              ? len === 3 || len === 4
              : true;
    if (!ok) throw new Error(`${this.matchName}: noto'g'ri qiymat ${JSON.stringify(v)}`);
    // Qiymat vm (ES3 ga yaqin) kontekstidan keladi — u yerda Array.prototype.some o'chirilgan.
    if (Array.isArray(v)) {
      for (let i = 0; i < v.length; i++) {
        if (typeof v[i] !== "number" || Number.isNaN(v[i])) throw new Error(`${this.matchName}: NaN qiymat`);
      }
    }
  }
  setValue(v: unknown) {
    if (this.keys.length) throw new Error(`${this.matchName}: kalit kadrli property'ga setValue`);
    this.check(v);
    this._value = v;
  }
  setValueAtTime(t: number, v: unknown) {
    if (typeof t !== "number" || Number.isNaN(t)) throw new Error("vaqt NaN");
    this.check(v);
    const ex = this.keys.find((k) => Math.abs(k.t - t) < 1e-6);
    if (ex) ex.v = v;
    else {
      this.keys.push({ t, v, inType: KeyframeInterpolationType.LINEAR, outType: KeyframeInterpolationType.LINEAR });
      this.keys.sort((a, b) => a.t - b.t);
    }
  }
  nearestKeyIndex(t: number) {
    let best = 0;
    this.keys.forEach((k, i) => {
      if (Math.abs(k.t - t) < Math.abs(this.keys[best]!.t - t)) best = i;
    });
    return best + 1;
  }
  key(i: number): Key {
    const k = this.keys[i - 1];
    if (!k) throw new Error(`${this.matchName}: kalit ${i} yo'q`);
    return k;
  }
  keyTime(i: number) {
    return this.key(i).t;
  }
  keyValue(i: number) {
    return this.key(i).v;
  }
  setInterpolationTypeAtKey(i: number, inType: number, outType?: number) {
    const k = this.key(i);
    k.inType = inType;
    k.outType = outType ?? inType;
  }
  setTemporalEaseAtKey(i: number, eIn: unknown[], eOut?: unknown[]) {
    const t = this.propertyValueType;
    const need = t === PropertyValueType.TwoD ? 2 : t === PropertyValueType.ThreeD ? 3 : 1;
    if (!Array.isArray(eIn) || eIn.length !== need || (eOut && eOut.length !== need)) {
      throw new Error(`${this.matchName}: KeyframeEase soni ${need} bo'lishi kerak`);
    }
    this.key(i).easeIn = eIn;
  }
}

export class MockGroup {
  children: (MockGroup | MockProperty)[] = [];
  name: string;
  constructor(
    public matchName: string,
    spec: Spec & { kind: "group" },
    public parent: MockGroup | MockLayer | null,
  ) {
    this.name = matchName;
    this.addable = spec.addable ?? [];
    for (const [mn, s] of spec.children) this.children.push(build(mn, s, this));
  }
  addable: string[];
  get numProperties() {
    return this.children.length;
  }
  property(nameOrIndex: string | number) {
    if (typeof nameOrIndex === "number") return this.children[nameOrIndex - 1] ?? null;
    return this.children.find((c) => c.matchName === nameOrIndex) ?? null;
  }
  canAddProperty(mn: string) {
    return this.addable.includes(mn);
  }
  addProperty(mn: string) {
    if (!this.addable.includes(mn) || !ADDABLE[mn]) throw new Error(`${this.matchName}: ${mn} qo'shib bo'lmaydi`);
    const p = build(mn, ADDABLE[mn](), this);
    this.children.push(p);
    return p;
  }
}

function build(mn: string, s: Spec, parent: MockGroup): MockGroup | MockProperty {
  return s.kind === "group" ? new MockGroup(mn, s, parent) : new MockProperty(mn, s.type, s.init);
}

let nextId = 1;

export class MockItem {
  id = nextId++;
  parentFolder: MockItem | null = null;
  constructor(public name: string) {}
}
export class FolderItem extends MockItem {}
export class FootageItem extends MockItem {
  footageMissing = false;
  hasVideo: boolean;
  constructor(
    name: string,
    public file: MockFile | null,
    public width: number,
    public height: number,
    public duration: number,
    public hasAudio: boolean,
  ) {
    super(name);
    this.hasVideo = width > 0;
  }
}

export class MockLayer {
  name: string;
  startTime = 0;
  inPoint: number;
  outPoint: number;
  stretch = 100;
  comment = "";
  audioEnabled = true;
  matchName: string;
  root: MockGroup;
  constructor(
    public containingComp: CompItem,
    public source: MockItem | null,
    public isText: boolean,
    public hasAudio: boolean,
  ) {
    this.name = source ? source.name : "Text";
    this.inPoint = 0;
    this.outPoint = containingComp.duration;
    this.matchName = isText ? "ADBE Text Layer" : "ADBE AV Layer";
    this.root = new MockGroup("root", { kind: "group", children: layerSpec(isText) }, this);
  }
  property(mn: string) {
    return this.root.property(mn);
  }
  get marker() {
    return this.property("ADBE Marker");
  }
  get index() {
    return this.containingComp.layers.list.indexOf(this) + 1;
  }
  moveAfter(other: MockLayer) {
    const l = this.containingComp.layers.list;
    l.splice(l.indexOf(this), 1);
    l.splice(l.indexOf(other) + 1, 0, this);
  }
  moveToEnd() {
    const l = this.containingComp.layers.list;
    l.splice(l.indexOf(this), 1);
    l.push(this);
  }
  sourceRectAtTime() {
    const doc = (this.property("ADBE Text Properties") as MockGroup | null)?.property("ADBE Text Document") as MockProperty | undefined;
    const d = (doc?.value ?? { text: "", fontSize: 10 }) as { text: string; fontSize: number };
    const w = d.text.length * d.fontSize * 0.55;
    return { left: -w / 2, top: -d.fontSize, width: w, height: d.fontSize * 1.2 };
  }
}

export class LayerCollection {
  list: MockLayer[] = [];
  constructor(private comp: CompItem) {}
  private push(l: MockLayer) {
    this.list.unshift(l);
    return l;
  }
  add(item: MockItem) {
    if (!(item instanceof FootageItem || item instanceof CompItem)) throw new Error("add: AVItem emas");
    const hasAudio = item instanceof FootageItem ? item.hasAudio : true;
    const l = new MockLayer(this.comp, item, false, hasAudio);
    l.outPoint = item instanceof FootageItem ? item.duration : (item as CompItem).duration;
    return this.push(l);
  }
  addSolid(color: number[], name: string, w: number, h: number, pa: number) {
    if (color.length !== 3 || !(color[0]! >= 0 && color[0]! <= 1 && color[1]! >= 0 && color[1]! <= 1 && color[2]! >= 0 && color[2]! <= 1)) {
      throw new Error("addSolid: rang 0..1");
    }
    if (!(w >= 4 && h >= 4 && pa > 0)) throw new Error("addSolid: o'lcham");
    const src = new FootageItem(name, null, w, h, 0, false);
    const l = new MockLayer(this.comp, src, false, false);
    l.name = name;
    return this.push(l);
  }
  addText(text: string) {
    const l = new MockLayer(this.comp, null, true, false);
    const doc = (l.property("ADBE Text Properties") as MockGroup).property("ADBE Text Document") as MockProperty;
    doc.setValue({ text, fontSize: 36, font: "ArialMT" });
    l.name = text;
    return this.push(l);
  }
}

export class CompItem extends MockItem {
  layers: LayerCollection;
  markerProperty: MockProperty;
  selectedLayers: MockLayer[] = [];
  opened = false;
  constructor(
    name: string,
    public width: number,
    public height: number,
    public pixelAspect: number,
    public duration: number,
    public frameRate: number,
  ) {
    super(name);
    this.layers = new LayerCollection(this);
    this.markerProperty = new MockProperty("ADBE Marker", PropertyValueType.MARKER, null);
  }
  get numLayers() {
    return this.layers.list.length;
  }
  layer(i: number) {
    const l = this.layers.list[i - 1];
    if (!l) throw new Error(`layer(${i}) yo'q`);
    return l;
  }
  openInViewer() {
    this.opened = true;
  }
}

export class MockFile {
  constructor(
    public fsName: string,
    public exists: boolean,
  ) {}
  get parent() {
    return { fsName: this.fsName.replace(/[/\\][^/\\]*$/, "") };
  }
}

export interface MediaInfo {
  width: number;
  height: number;
  duration: number;
  hasAudio: boolean;
}

export function createAE(files: Record<string, MediaInfo>) {
  const items: MockItem[] = [];
  const rootFolder = new FolderItem("root");
  const log: string[] = [];
  let undoDepth = 0;
  const imports: string[] = [];

  class File extends MockFile {
    constructor(path: string) {
      super(String(path), Object.prototype.hasOwnProperty.call(files, String(path)));
    }
  }
  const ImportAsType = { COMP_CROPPED_LAYERS: 3812, FOOTAGE: 3813, COMP: 3814, PROJECT: 3815 };
  class ImportOptions {
    importAs = ImportAsType.FOOTAGE;
    constructor(public file: MockFile) {}
    canImportAs(t: number) {
      return t === ImportAsType.FOOTAGE;
    }
  }
  class MarkerValue {
    label = 0;
    duration = 0;
    constructor(public comment: string) {}
  }
  class KeyframeEase {
    constructor(
      public speed: number,
      public influence: number,
    ) {}
  }
  class Shape {
    vertices: number[][] = [];
    closed = false;
  }

  const addItem = <T extends MockItem>(it: T) => {
    it.parentFolder = rootFolder;
    items.push(it);
    return it;
  };

  const project = {
    rootFolder,
    selection: [] as MockItem[],
    activeItem: null as MockItem | null,
    file: null as MockFile | null,
    get numItems() {
      return items.length;
    },
    item(i: number) {
      const it = items[i - 1];
      if (!it) throw new Error(`item(${i}) yo'q`);
      return it;
    },
    items: {
      addComp(name: string, w: number, h: number, pa: number, dur: number, fps: number) {
        if ([name, w, h, pa, dur, fps].some((x) => x === undefined)) throw new Error("addComp: 6 argument shart");
        if (!(dur > 0 && fps >= 1 && w >= 4 && h >= 4)) throw new Error("addComp: noto'g'ri parametr");
        return addItem(new CompItem(name, w, h, pa, dur, fps));
      },
      addFolder(name: string) {
        return addItem(new FolderItem(name));
      },
    },
    importFile(io: ImportOptions) {
      const info = files[io.file.fsName];
      if (!info) throw new Error("import: fayl yo'q");
      imports.push(io.file.fsName);
      const name = io.file.fsName.split(/[/\\]/).pop() ?? "media";
      return addItem(new FootageItem(name, io.file, info.width, info.height, info.duration, info.hasAudio));
    },
  };

  const app = {
    version: "25.0.0",
    project,
    beginUndoGroup(name: string) {
      undoDepth++;
      log.push(`begin:${name}`);
    },
    endUndoGroup() {
      undoDepth--;
      log.push("end");
    },
  };

  const context = {
    app,
    File,
    ImportOptions,
    ImportAsType,
    MarkerValue,
    KeyframeEase,
    Shape,
    CompItem,
    FootageItem,
    FolderItem,
    PropertyValueType,
    KeyframeInterpolationType,
    ParagraphJustification: { LEFT_JUSTIFY: 7413, CENTER_JUSTIFY: 7415, RIGHT_JUSTIFY: 7414 },
  };

  return {
    context,
    app,
    items,
    imports,
    log,
    get undoDepth() {
      return undoDepth;
    },
    comps: () => items.filter((i): i is CompItem => i instanceof CompItem),
  };
}

/**
 * host.jsx ni ES3 ga yaqin muhitda yuklaydi: ES5+ massiv/obyekt metodlari va native JSON o'chiriladi,
 * shuning uchun json2.jsx haqiqatan ishlatiladi va .map/.forEach chaqiruvlari yiqitadi.
 */
export function loadHost(ae: ReturnType<typeof createAE>, jsxDir: string) {
  const ctx = vm.createContext({ ...ae.context });
  vm.runInContext(
    `delete Array.prototype.map; delete Array.prototype.forEach; delete Array.prototype.filter;
     delete Array.prototype.reduce; delete Array.prototype.some; delete Array.prototype.every;
     delete Object.keys; delete String.prototype.trim; delete Function.prototype.bind; delete this.JSON;`,
    ctx,
  );
  vm.runInContext(readFileSync(`${jsxDir}/json2.jsx`, "utf8"), ctx, { filename: "json2.jsx" });
  vm.runInContext(readFileSync(`${jsxDir}/host.jsx`, "utf8"), ctx, { filename: "host.jsx" });
  return ctx as vm.Context & {
    lahza_buildComp(plan: string): string;
    lahza_buildKaraoke(plan: string, comp?: string): string;
    lahza_selectedFootagePaths(): string;
    lahza_projectInfo(): string;
    lahza__musicLevels(m: unknown, segs: unknown, duck: number): [number, number][];
  };
}
