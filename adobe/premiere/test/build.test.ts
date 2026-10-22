import { describe, expect, it } from "vitest";

import type { PlaceVideoRequest } from "../src/host/adapter";
import { cropFromRect, resolveOverlaps, trackLayout } from "../src/host/build";
import { FakeAdapter } from "../src/host/fake";
import { clipPlan, montagePlan, splitPlan } from "./fixtures";

const codes = (ws: { code: string }[]) => ws.map((w) => w.code);

describe("buildFromPlan (fake host)", () => {
  it("klip rejasi: sekvensiya, tartib, treklar, vaqtlar, kalit kadrlar, captions, markerlar", async () => {
    const a = new FakeAdapter();
    const res = await a.buildFromPlan(clipPlan());
    const ops = a.ops;

    // amallar ketma-ketligi: import -> sekvensiya -> kliplar -> musiqa -> subtitr -> markerlar
    const order = ops.calls.map((c) => c.op);
    expect(order[0]).toBe("importFiles");
    expect(order[1]).toBe("createSequence");
    expect(order.indexOf("placeAudio")).toBeGreaterThan(order.lastIndexOf("placeVideo"));
    expect(order.indexOf("importCaptions")).toBeGreaterThan(order.indexOf("placeAudio"));
    expect(order.indexOf("addMarker")).toBeGreaterThan(order.indexOf("importCaptions"));

    expect(ops.of("importFiles")[0].args[0]).toEqual(["/media/podcast.mp4", "/media/music.mp3"]);
    const seq = ops.of("createSequence")[0].args[0] as { width: number; height: number; fps: number };
    expect([seq.width, seq.height, seq.fps]).toEqual([1080, 1920, 30]);

    // kliplar rec_in bo'yicha; bg (V1) main (V2) dan oldin; bg audiosiz
    const places = ops.of("placeVideo").map((c) => c.args[0] as PlaceVideoRequest);
    expect(places.map((p) => p.itemId)).toEqual(["v1:bg", "v1:main", "v2:main"]);
    expect(places.map((p) => p.videoTrack)).toEqual([0, 1, 1]);
    expect(places.map((p) => p.audioTrack)).toEqual([null, 0, 0]);
    expect(places.map((p) => [p.recIn, p.recOut, p.srcIn, p.srcOut])).toEqual([
      [0, 4, 100, 104],
      [0, 4, 100, 104],
      [4, 9, 104, 109],
    ]);
    expect(places[1].name).toBe("hook · main");

    // kalit kadrlar soni: bg 1, main 1, v2 main 3
    expect(ops.of("setTransform").map((c) => (c.args[1] as unknown[]).length)).toEqual([1, 1, 3]);
    // blur faqat bg qatlamda
    const blur = ops.of("addGaussianBlur");
    expect(blur).toHaveLength(1);
    expect(String(blur[0].args[0])).toContain("v1:bg");
    expect(blur[0].args[1]).toBe(60);
    // ovoz -3 dB faqat asosiy qatlamga
    expect(ops.of("setClipAudio")).toHaveLength(1);
    expect(String(ops.of("setClipAudio")[0].args[0])).toContain("v1:main");
    // cut o'tishi qo'yilmaydi
    expect(ops.of("addTransition")).toHaveLength(0);

    // musiqa A2, daraja -14
    expect(ops.of("placeAudio")[0].args[0]).toMatchObject({ audioTrack: 1, recIn: 0, recOut: 9 });
    expect(ops.of("setAudioLevel")[0].args[1]).toBe(-14);

    expect(ops.of("importCaptions")[0].args[0]).toBe("/out/mehmon.srt");
    // 2 marker + 1 matn (marker sifatida, davomiyligi bilan)
    const markers = ops.of("addMarker");
    expect(markers).toHaveLength(3);
    expect(markers[2].args[1]).toBe(2);

    expect(res.sequenceName).toBe("Lahza — Mehmon gapi");
    expect(res.placedClips).toBe(2);
    const c = codes(res.warnings);
    expect(c).toContain("not_translated");
    expect(res.warnings.find((w) => w.code === "not_translated")?.detail).toBe("shake (asosiy)");
    expect(c).toContain("text_as_marker");
    expect(c).toContain("music_fades");
    expect(c).toContain("music_duck");
    expect(c).not.toContain("captions_imported_only");

    // progress qadamlari: oxirgisi done, total izchil
    expect(a.steps[0].key).toBe("import");
    expect(a.steps.at(-1)?.key).toBe("done");
    expect(new Set(a.steps.map((s) => s.total)).size).toBe(1);
  });

  it("kalit kadrlar qo'llanmasa - statik fallback + ogohlantirish", async () => {
    const a = new FakeAdapter({ unsupported: { "setTransform:multi": "keyframes_static" } });
    const res = await a.buildFromPlan(clipPlan());
    const lens = a.ops.of("setTransform").map((c) => (c.args[1] as { pos_x: number }[]));
    expect(lens.map((k) => k.length)).toEqual([1, 1, 1]);
    expect(lens[2][0].pos_x).toBe(700); // birinchi kadr
    expect(codes(res.warnings)).toContain("keyframes_static");
  });

  it("SRT faqat import qilinsa va effektlar yo'q bo'lsa - aniq ogohlantirishlar, qurish davom etadi", async () => {
    const a = new FakeAdapter({ captions: "imported", unsupported: { addGaussianBlur: "blur_missing", setClipAudio: "audio_level" } });
    const res = await a.buildFromPlan(clipPlan());
    const c = codes(res.warnings);
    expect(c).toContain("captions_imported_only");
    expect(c).toContain("blur_missing");
    expect(c).toContain("audio_level");
    expect(res.placedClips).toBe(2);
  });

  it("tezlik != 1: srcOut rec davomiyligiga moslanadi va ogohlantiriladi", async () => {
    const p = clipPlan();
    p.video[0] = { ...p.video[0], speed: 2, src_out: 114 };
    const a = new FakeAdapter();
    const res = await a.buildFromPlan(p);
    const v2 = a.ops.of("placeVideo").map((c) => c.args[0] as PlaceVideoRequest).find((r) => r.itemId === "v2:main")!;
    expect(v2.srcOut).toBe(109);
    expect(codes(res.warnings)).toContain("speed");
  });

  it("split: top/bottom treklar va crop foizlari", async () => {
    const a = new FakeAdapter();
    await a.buildFromPlan(splitPlan());
    const places = a.ops.of("placeVideo").map((c) => c.args[0] as PlaceVideoRequest);
    expect(places.map((p) => [p.itemId, p.videoTrack])).toEqual([
      ["s1:bottom", 0],
      ["s1:top", 1],
    ]);
    // audio birinchi qatlamdan (main yo'q) - top
    expect(places.find((p) => p.itemId === "s1:top")?.audioTrack).toBe(0);
    expect(places.find((p) => p.itemId === "s1:bottom")?.audioTrack).toBeNull();
    const crops = a.ops.of("setCrop").map((c) => c.args[1]);
    expect(crops).toHaveLength(2);
    // manba 1920x1080 @100%: markaz (540,480) -> manba chap cheti -420; ko'rinadigan 0..1080
    expect(crops[1]).toEqual({ left: 21.875, top: 5.556, right: 21.875, bottom: 5.556 });
  });

  it("montaj: ustma-ust o'tish kesimga keltiriladi, lumetri ogohlantiriladi", async () => {
    const a = new FakeAdapter();
    const res = await a.buildFromPlan(montagePlan());
    const places = a.ops.of("placeVideo").map((c) => c.args[0] as PlaceVideoRequest);
    expect(places.map((p) => [p.recIn, p.recOut, p.srcIn])).toEqual([
      [0, 3, 20],
      [3, 6, 50.5],
      [6, 8, 80],
    ]);
    const tr = a.ops.of("addTransition").map((c) => [c.args[1], c.args[2]]);
    expect(tr).toEqual([
      ["cross_dissolve", 0.5],
      ["zoom", 0.4],
    ]);
    // "b" kalit kadrlari 0.5 s chapga surilgan: 0.25 dagi kadr 0 ga (boshlanish holati), 2 -> 1.5
    const keysB = a.ops.of("setTransform")[1].args[1] as { t: number; scale_pct: number }[];
    expect(keysB.map((k) => [k.t, k.scale_pct])).toEqual([
      [0, 105],
      [1.5, 120],
    ]);
    expect(codes(res.warnings).filter((c) => c === "lumetri")).toHaveLength(3);
  });
});

describe("yordamchi funksiyalar", () => {
  it("trackLayout faqat mavjud rollarga trek beradi", () => {
    expect(trackLayout(clipPlan())).toMatchObject({ bg: 0, main: 1 });
    expect(trackLayout(splitPlan())).toMatchObject({ bottom: 0, top: 1 });
    expect(trackLayout(montagePlan())).toMatchObject({ main: 0 });
  });

  it("resolveOverlaps ustma-ust bo'lmaganlarni o'zgartirmaydi", () => {
    const items = clipPlan().video;
    const out = resolveOverlaps(items);
    expect(out.map((i) => i.id)).toEqual(["v1", "v2"]);
    expect(out[1]).toBe(items[0]);
  });

  it("cropFromRect: to'liq ko'rinadigan kadr - 0%", () => {
    expect(cropFromRect([0, 0, 1080, 1920], { scale_pct: 100, pos_x: 540, pos_y: 960 }, 1080, 1920)).toEqual({
      left: 0,
      top: 0,
      right: 0,
      bottom: 0,
    });
  });
});
