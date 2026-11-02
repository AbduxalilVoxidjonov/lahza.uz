// host.jsx ni soxta AE obyekt modelida (vm, ES3 ga yaqin muhit) ishga tushirib, namunaviy reja bo'yicha
// lahza_buildComp / lahza_buildKaraoke natijasini tekshiradi.
import { fileURLToPath } from "node:url";
import { beforeEach, describe, expect, it } from "vitest";
import {
  CompItem,
  FootageItem,
  KeyframeInterpolationType as KIT,
  MockGroup,
  MockLayer,
  MockProperty,
  createAE,
  loadHost,
} from "./mock-ae";
import { MUSIC, SRC, samplePlan } from "./fixtures";

const JSX = fileURLToPath(new URL("../jsx", import.meta.url));

function prop(layer: MockLayer, ...path: string[]): MockProperty {
  let cur: MockGroup | MockProperty | null = layer.root;
  for (const p of path) cur = (cur as MockGroup).property(p);
  if (!(cur instanceof MockProperty)) throw new Error(`property yo'q: ${path.join(" > ")}`);
  return cur;
}
const xf = (l: MockLayer, mn: string) => prop(l, "ADBE Transform Group", mn);
const byName = (comp: CompItem, name: string) => {
  const l = comp.layers.list.find((x) => x.name === name);
  if (!l) throw new Error(`qatlam yo'q: ${name}; bor: ${comp.layers.list.map((x) => x.name).join(", ")}`);
  return l;
};
const close = (a: number, b: number) => expect(a).toBeCloseTo(b, 4);

function setup() {
  const ae = createAE({
    [SRC]: { width: 1920, height: 1080, duration: 120, hasAudio: true },
    [MUSIC]: { width: 0, height: 0, duration: 90, hasAudio: true },
  });
  const host = loadHost(ae, JSX);
  return { ae, host };
}

describe("lahza_buildComp", () => {
  let ae: ReturnType<typeof createAE>;
  let host: ReturnType<typeof loadHost>;
  let res: { ok: boolean; comp: string; warnings: string[]; layers: number; error?: string };
  let comp: CompItem;

  beforeEach(() => {
    ({ ae, host } = setup());
    res = JSON.parse(host.lahza_buildComp(JSON.stringify(samplePlan())));
    comp = ae.comps().find((c) => c.name === res.comp)!;
  });

  it("kompozitsiya parametrlari va undo group", () => {
    expect(res.error).toBeUndefined();
    expect(res.ok).toBe(true);
    expect(comp).toBeDefined();
    expect([comp.width, comp.height, comp.frameRate, comp.duration, comp.pixelAspect]).toEqual([1080, 1920, 30, 12, 1]);
    expect(comp.name).toBe("Lahza — Hook");
    expect(comp.opened).toBe(true);
    expect(ae.log).toEqual(["begin:Lahza: kompozitsiya yasash", "end"]);
    expect(ae.undoDepth).toBe(0);
  });

  it("media bir marta import qilinadi va qayta ishlatiladi", () => {
    expect(ae.imports).toEqual([SRC, MUSIC]);
    // ikkinchi qurish — import yo'q (loyihada bor)
    const r2 = JSON.parse(host.lahza_buildComp(JSON.stringify(samplePlan())));
    expect(r2.ok).toBe(true);
    expect(r2.comp).toBe("Lahza — Hook (2)");
    expect(ae.imports).toHaveLength(2);
  });

  it("qatlamlar soni va tartibi (tepadan pastga)", () => {
    expect(comp.layers.list.map((l) => l.name)).toEqual([
      "Lahza matn 2 (card)",
      "Lahza karta 2",
      "Lahza matn 1 (hook)",
      "Lahza dip (qora)",
      "klip #3 · main",
      "klip #2 · bottom",
      "klip #2 · top",
      "hook #1 · main",
      "hook #1 · bg",
      "Lahza musiqa 1",
    ]);
    expect(res.layers).toBe(10);
    // split uchun 2 ta precomp
    expect(ae.comps()).toHaveLength(3);
  });

  it("fit_blur: bg (fill + Gaussian Blur) va main (ease kalit kadrlar)", () => {
    const bg = byName(comp, "hook #1 · bg");
    const main = byName(comp, "hook #1 · main");
    for (const l of [bg, main]) {
      close(l.startTime, -10);
      close(l.inPoint, 0);
      close(l.outPoint, 4.5); // keyingi klip cross_dissolve 0.5 s — cho'zildi
      expect(l.stretch).toBe(100);
      expect(xf(l, "ADBE Anchor Point").value).toEqual([960, 540]);
    }
    expect(xf(bg, "ADBE Scale").value).toEqual([177.78, 177.78]);
    expect(xf(bg, "ADBE Position").value).toEqual([540, 960]);
    const fx = (bg.property("ADBE Effect Parade") as MockGroup).property(1) as MockGroup;
    expect(fx.matchName).toBe("ADBE Gaussian Blur 2");
    expect((fx.property("ADBE Gaussian Blur 2-0001") as MockProperty).value).toBe(60);
    expect(bg.audioEnabled).toBe(false);
    expect(main.audioEnabled).toBe(true);

    const sc = xf(main, "ADBE Scale");
    expect(sc.keys.map((k) => k.t)).toEqual([0, 3.5]);
    expect(sc.keys.map((k) => k.v)).toEqual([
      [56.25, 56.25],
      [62, 62],
    ]);
    expect(sc.keys.every((k) => k.inType === KIT.BEZIER && k.outType === KIT.BEZIER && k.easeIn?.length === 3)).toBe(true);
    const pos = xf(main, "ADBE Position");
    expect(pos.keys.map((k) => k.v)).toEqual([
      [540, 960],
      [520, 960],
    ]);
    expect(pos.keys.every((k) => k.easeIn?.length === 1)).toBe(true); // spatial -> 1 ta KeyframeEase
  });

  it("split: precomp + mask, cross_dissolve opacity, ovoz faqat top'da", () => {
    const top = byName(comp, "klip #2 · top");
    const bottom = byName(comp, "klip #2 · bottom");
    for (const l of [top, bottom]) {
      expect(l.source).toBeInstanceOf(CompItem);
      close(l.startTime, 4);
      close(l.inPoint, 4);
      close(l.outPoint, 8);
      const op = xf(l, "ADBE Opacity");
      expect(op.keys.map((k) => [k.t, k.v])).toEqual([
        [4, 0],
        [4.5, 100],
      ]);
      const pre = l.source as CompItem;
      expect([pre.width, pre.height]).toEqual([1080, 1920]);
      const inner = pre.layer(1);
      expect(inner.source).toBeInstanceOf(FootageItem);
      close(inner.startTime, -20);
      close(inner.inPoint, 0);
      close(inner.outPoint, 4);
    }
    const mask = (top.property("ADBE Mask Parade") as MockGroup).property(1) as MockGroup;
    expect(mask.matchName).toBe("ADBE Mask Atom");
    const shape = (mask.property("ADBE Mask Shape") as MockProperty).value as { vertices: number[][]; closed: boolean };
    expect(shape.vertices).toEqual([
      [0, 0],
      [1080, 0],
      [1080, 960],
      [0, 960],
    ]);
    expect(shape.closed).toBe(true);
    const bShape = ((bottom.property("ADBE Mask Parade") as MockGroup).property(1) as MockGroup).property("ADBE Mask Shape") as MockProperty;
    expect((bShape.value as { vertices: number[][] }).vertices[0]).toEqual([0, 960]);
    const innerTop = (top.source as CompItem).layer(1);
    expect(xf(innerTop, "ADBE Position").value).toEqual([300, 480]);
    expect(top.audioEnabled).toBe(true);
    expect(prop(top, "ADBE Audio Group", "ADBE Audio Levels").value).toEqual([-3, -3]);
    expect(bottom.audioEnabled).toBe(false);
  });

  it("speed -> stretch, hold kalit kadrlar, dip_to_black solid", () => {
    const l = byName(comp, "klip #3 · main");
    close(l.stretch, 100 / 1.5);
    close(l.startTime, 8 - 40 / 1.5);
    close(l.inPoint, 8);
    close(l.outPoint, 12);
    const sc = xf(l, "ADBE Scale");
    expect(sc.keys.map((k) => k.t)).toEqual([8, 10]);
    expect(sc.keys.every((k) => k.inType === KIT.HOLD && k.outType === KIT.HOLD)).toBe(true);
    const dip = byName(comp, "Lahza dip (qora)");
    close(dip.inPoint, 7.8);
    close(dip.outPoint, 8.2);
    const op = xf(dip, "ADBE Opacity").keys.map((k) => [Number(k.t.toFixed(3)), k.v]);
    expect(op).toEqual([
      [7.8, 0],
      [8, 100],
      [8.2, 0],
    ]);
    // klip #2 dip oldidan cho'zilmaydi
    close(byName(comp, "klip #2 · top").outPoint, 8);
  });

  it("matnlar: hook yuqori xavfsiz zonada, card — rangli solid fon", () => {
    const hook = byName(comp, "Lahza matn 1 (hook)");
    close(hook.inPoint, 0);
    close(hook.outPoint, 2.5);
    const doc = prop(hook, "ADBE Text Properties", "ADBE Text Document").value as Record<string, unknown>;
    expect(doc.text).toBe("Buni bilmasangiz...");
    expect(doc.fontSize).toBe(86);
    expect(doc.font).toBe("Inter-Bold");
    expect(doc.fillColor).toEqual([1, 1, 1]);
    expect(doc.applyStroke).toBe(true);
    const p = xf(hook, "ADBE Position").value as number[];
    expect(p).toEqual([540, 1920 * 0.14]);
    const card = byName(comp, "Lahza karta 2");
    expect(card.source).toBeInstanceOf(FootageItem);
    expect([(card.source as FootageItem).width, (card.source as FootageItem).height]).toEqual([1080, 1920]);
    close(card.inPoint, 10);
    close(card.outPoint, 12);
    expect(xf(byName(comp, "Lahza matn 2 (card)"), "ADBE Position").value).toEqual([540, 960]);
  });

  it("markerlar comp'ga", () => {
    const mk = comp.markerProperty.keys;
    expect(mk.map((k) => k.t)).toEqual([0, 5.2]);
    const v = mk.map((k) => k.v as { comment: string; label: number });
    expect(v[0]).toMatchObject({ comment: "Hook — kirish gapi", label: 1 });
    expect(v[1]).toMatchObject({ comment: "Urg'u", label: 2 });
  });

  it("musiqa: fade va nutq bo'laklarida duck", () => {
    const m = byName(comp, "Lahza musiqa 1");
    close(m.startTime, 0);
    close(m.outPoint, 12);
    const lev = prop(m, "ADBE Audio Group", "ADBE Audio Levels").keys.map((k) => [Number(k.t.toFixed(3)), (k.v as number[])[0]]);
    // nutq: [0.5..3.8] (qatorlar 0.4 s dan yaqin — birlashtirildi) va [6.0..7.5]
    expect(lev).toEqual([
      [0, -60],
      [0.5, -14],
      [0.65, -24],
      [3.8, -24],
      [4.05, -14],
      [5.85, -14],
      [6, -24],
      [7.5, -24],
      [7.75, -14],
      [10.5, -14],
      [12, -60],
    ]);
  });

  it("ogohlantirishlar: o'tmagan narsalar", () => {
    expect(res.warnings.some((w) => w.includes("warm"))).toBe(true);
    expect(res.warnings.some((w) => w.includes("shake fx (v3)"))).toBe(true);
  });

  it("noto'g'ri reja — ok:false, undo ochiq qolmaydi", () => {
    const bad = JSON.parse(host.lahza_buildComp('{"schema":"x"}'));
    expect(bad).toEqual({ ok: false, error: expect.stringContaining("hostplan") });
    const broken = JSON.parse(host.lahza_buildComp("{not json"));
    expect(broken.ok).toBe(false);
    const p = samplePlan();
    p.media[0]!.path = "/yo'q/fayl.mp4";
    const r = JSON.parse(host.lahza_buildComp(JSON.stringify(p)));
    expect(r.ok).toBe(true);
    expect(r.warnings.some((w: string) => w.includes("/yo'q/fayl.mp4"))).toBe(true);
    expect(ae.undoDepth).toBe(0);
  });
});

describe("lahza_buildKaraoke", () => {
  it("har qator — Text qatlam, so'z highlight Range Selector kalit kadrlari bilan", () => {
    const { ae, host } = setup();
    const built = JSON.parse(host.lahza_buildComp(JSON.stringify(samplePlan())));
    const before = ae.comps().find((c) => c.name === built.comp)!.numLayers;
    const res = JSON.parse(host.lahza_buildKaraoke(JSON.stringify(samplePlan()), built.comp));
    expect(res).toMatchObject({ ok: true, comp: built.comp, lines: 3 });
    const comp = ae.comps().find((c) => c.name === built.comp)!;
    expect(comp.numLayers).toBe(before + 3);

    const l1 = byName(comp, "Lahza karaoke 01");
    const l2 = byName(comp, "Lahza karaoke 02");
    const l3 = byName(comp, "Lahza karaoke 03");
    expect([l1.inPoint, l1.outPoint, l2.inPoint, l2.outPoint, l3.inPoint, l3.outPoint]).toEqual([0.5, 2.0, 2.1, 3.8, 6.0, 7.5]);

    // joylashuv: pastki xavfsiz zona (pastdan 35%), markazda
    expect(xf(l2, "ADBE Position").value).toEqual([540, 1920 * 0.65]);
    const doc = prop(l2, "ADBE Text Properties", "ADBE Text Document").value as Record<string, unknown>;
    expect(doc).toMatchObject({ text: "muhim sirni aytaman", fontSize: 72, strokeWidth: 5, strokeColor: [0, 0, 0] });

    const animators = (l2.property("ADBE Text Properties") as MockGroup).property("ADBE Text Animators") as MockGroup;
    const anim = animators.property(1) as MockGroup;
    expect(anim.matchName).toBe("ADBE Text Animator");
    const fill = (anim.property("ADBE Text Animator Properties") as MockGroup).property(1) as MockProperty;
    expect(fill.matchName).toBe("ADBE Text Fill Color");
    expect(fill.value).toEqual([1, 212 / 255, 0, 1]);
    const sel = (anim.property("ADBE Text Selectors") as MockGroup).property(1) as MockGroup;
    expect(sel.matchName).toBe("ADBE Text Selector");
    expect(((sel.property("ADBE Text Range Advanced") as MockGroup).property("ADBE Text Range Units") as MockProperty).value).toBe(2);
    const start = sel.property("ADBE Text Index Start") as MockProperty;
    const end = sel.property("ADBE Text Index End") as MockProperty;
    // "muhim sirni aytaman": muhim [0,5), sirni [6,11), aytaman [12,19)
    expect(start.keys.map((k) => [k.t, k.v])).toEqual([
      [2.1, 0],
      [2.5, 6],
      [3.0, 12],
    ]);
    expect(end.keys.map((k) => [k.t, k.v])).toEqual([
      [2.1, 5],
      [2.5, 11],
      [3.0, 19],
    ]);
    expect([...start.keys, ...end.keys].every((k) => k.inType === KIT.HOLD && k.outType === KIT.HOLD)).toBe(true);

    // 1-qator: so'zlar orasida 0.1 s pauza — highlight o'chadi; oxirgi so'zdan keyin ham
    const s1 = (((l1.property("ADBE Text Properties") as MockGroup).property("ADBE Text Animators") as MockGroup).property(1) as MockGroup)
      .property("ADBE Text Selectors") as MockGroup;
    const e1 = (s1.property(1) as MockGroup).property("ADBE Text Index End") as MockProperty;
    expect(e1.keys.map((k) => [k.t, k.v])).toEqual([
      [0.5, 5],
      [0.9, 0],
      [1.0, 11],
      [1.6, 0],
    ]);
    // 3-qator: "oʻzbek" (U+02BB) to'g'ri topiladi
    const s3 = ((((l3.property("ADBE Text Properties") as MockGroup).property("ADBE Text Animators") as MockGroup).property(1) as MockGroup)
      .property("ADBE Text Selectors") as MockGroup).property(1) as MockGroup;
    expect((s3.property("ADBE Text Index End") as MockProperty).keys.map((k) => k.v)).toEqual([6, 0, 13]);
    expect(ae.undoDepth).toBe(0);
  });

  it("comp topilmasa yangisini yaratadi; uppercase + box uslubi", () => {
    const { ae, host } = setup();
    const p = samplePlan();
    p.captions.style = { ...p.captions.style, uppercase: true, box: true, box_color: "#000000", box_opacity: 0.5, animation: "none" };
    const res = JSON.parse(host.lahza_buildKaraoke(JSON.stringify(p)));
    expect(res.ok).toBe(true);
    expect(res.warnings.join(" ")).toContain("yangisi yaratildi");
    const comp = ae.comps()[0]!;
    // 3 matn + 3 fon
    expect(comp.numLayers).toBe(6);
    const t = byName(comp, "Lahza karaoke 01");
    const box = byName(comp, "Lahza karaoke foni 01");
    expect(comp.layers.list.indexOf(box)).toBe(comp.layers.list.indexOf(t) + 1); // fon matndan pastda
    expect(xf(box, "ADBE Opacity").value).toBe(50);
    expect((prop(t, "ADBE Text Properties", "ADBE Text Document").value as { text: string }).text).toBe("BUGUN SIZGA");
    expect(((t.property("ADBE Text Properties") as MockGroup).property("ADBE Text Animators") as MockGroup).numProperties).toBe(0);
  });

  it("qatorlar yo'q — xato", () => {
    const { host } = setup();
    const p = samplePlan();
    p.captions.lines = [];
    expect(JSON.parse(host.lahza_buildKaraoke(JSON.stringify(p)))).toMatchObject({ ok: false });
  });
});

describe("lahza_selectedFootagePaths", () => {
  it("Project paneli tanlovi + faol comp tanlangan qatlam manbalari, takrorsiz", () => {
    const { ae, host } = setup();
    const built = JSON.parse(host.lahza_buildComp(JSON.stringify(samplePlan())));
    const comp = ae.comps().find((c) => c.name === built.comp)!;
    const footage = ae.items.filter((i): i is FootageItem => i instanceof FootageItem && i.file !== null);
    ae.app.project.selection = [footage[0]!, comp];
    ae.app.project.activeItem = comp;
    comp.selectedLayers = [byName(comp, "hook #1 · main"), byName(comp, "Lahza musiqa 1"), byName(comp, "Lahza karta 2")];
    const res = JSON.parse(host.lahza_selectedFootagePaths());
    expect(res).toMatchObject({ ok: true, comp: built.comp, paths: [SRC, MUSIC], warnings: [] });
  });

  it("hech narsa tanlanmagan — bo'sh ro'yxat", () => {
    const { host } = setup();
    expect(JSON.parse(host.lahza_selectedFootagePaths())).toMatchObject({ ok: true, paths: [] });
  });
});

describe("montaj rejasi: o'tishli element oldingisi bilan ustma-ust", () => {
  it("cross_dissolve — oldingi qatlam cho'zilmaydi; dip — o'rtada almashadi", () => {
    const { ae, host } = setup();
    const p = samplePlan();
    p.source = "montage";
    // v2 v1 bilan 0.5 s ustma-ust (engine MontageTimeline.item_starts), v3 v2 bilan 0.4 s
    p.video[1]!.rec_in = 3.5;
    p.video[1]!.rec_out = 7.5;
    p.video[2]!.rec_in = 7.1;
    p.video[2]!.rec_out = 11.1;
    const res = JSON.parse(host.lahza_buildComp(JSON.stringify(p)));
    expect(res.ok).toBe(true);
    const comp = ae.comps().find((c) => c.name === res.comp)!;
    close(byName(comp, "hook #1 · main").outPoint, 4); // cho'zilmadi
    const top = byName(comp, "klip #2 · top");
    close(top.inPoint, 3.5);
    expect(xf(top, "ADBE Opacity").keys.map((k) => [k.t, k.v])).toEqual([
      [3.5, 0],
      [4, 100],
    ]);
    expect((top.source as CompItem).duration).toBeCloseTo(4, 4); // precomp'ga dum qo'shilmadi
    const v3 = byName(comp, "klip #3 · main");
    close(v3.inPoint, 7.3); // ustma-ust oraliq [7.1..7.5] o'rtasi
    close(v3.startTime, 7.1 - 40 / 1.5);
    const dip = byName(comp, "Lahza dip (qora)");
    close(dip.inPoint, 7.1);
    close(dip.outPoint, 7.5);
    expect(xf(dip, "ADBE Opacity").keys.map((k) => Number(k.t.toFixed(3)))).toEqual([7.1, 7.3, 7.5]);
  });
});

describe("karaoke: kalit so'zlar", () => {
  it("style.keywords — to'liq so'z, statik selektor highlight rangida", () => {
    const { ae, host } = setup();
    const p = samplePlan();
    p.captions.style = { ...p.captions.style, keywords: ["sir", "sirni", "Tilida"] };
    const res = JSON.parse(host.lahza_buildKaraoke(JSON.stringify(p)));
    expect(res.ok).toBe(true);
    const comp = ae.comps()[0]!;
    const anims = (l: MockLayer) => (l.property("ADBE Text Properties") as MockGroup).property("ADBE Text Animators") as MockGroup;
    const l2 = byName(comp, "Lahza karaoke 02");
    const kw = anims(l2).property(1) as MockGroup;
    expect(kw.name).toBe("Lahza kalit so'zlar");
    const sels = kw.property("ADBE Text Selectors") as MockGroup;
    expect(sels.numProperties).toBe(1); // "sir" — "sirni" ichida, to'liq so'z emas
    const s = sels.property(1) as MockGroup;
    expect([(s.property("ADBE Text Index Start") as MockProperty).value, (s.property("ADBE Text Index End") as MockProperty).value]).toEqual([6, 11]);
    expect((anims(l2).property(2) as MockGroup).name).toBe("Lahza highlight");
    expect(anims(byName(comp, "Lahza karaoke 01")).numProperties).toBe(1); // faqat highlight
    expect(anims(byName(comp, "Lahza karaoke 03")).numProperties).toBe(2);
  });
});
