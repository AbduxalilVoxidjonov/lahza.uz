// premiere.ts ni soxta `premierepro` modeli bilan tekshirish (haqiqiy Premiere bu mashinada yo'q).
// Bu API'ning haqiqiy xatti-harakatini isbotlamaydi - faqat chaqiruvlar tartibi, lock qoidasi va hisob-kitobni.
import { describe, expect, it } from "vitest";

import type { premierepro } from "@adobe/premierepro";
import { PremiereAdapter, pickName, TRANSITION_PATTERNS } from "../src/host/premiere";
import { clipPlan, montagePlan, splitPlan } from "./fixtures";
import { makeMockPpro, type MockParam } from "./mockPpro";

const motionParam = (item: any, name: string): MockParam =>
  item.chain.comps.find((c: any) => c.matchName === "AE.ADBE Motion").params.find((p: any) => p.displayName === name);

describe("PremiereAdapter (soxta premierepro)", () => {
  it("klip rejasini quradi: sekvensiya sozlamalari, treklar, in/out, Motion, blur, audio, markerlar", async () => {
    const m = makeMockPpro();
    const adapter = new PremiereAdapter(m.ppro as premierepro);
    const res = await adapter.buildFromPlan(clipPlan());
    const seq = m.sequences[0];

    expect(seq.frame).toEqual({ width: 1080, height: 1920 });
    expect(seq.fps).toBe(30);
    expect(seq.par).toBe("1:1");
    expect(m.imported[0]).toEqual(["/media/podcast.mp4", "/media/music.mp3"]);

    // V1: bg, V2: main (ikki element); A1: asosiy audio, A3: bg nusxasi (o'chirilgan), A2: musiqa
    expect(seq.vt[0].map((i: any) => [i.start, i.end, i.inP, i.outP])).toEqual([[0, 4, 100, 104]]);
    expect(seq.vt[1].map((i: any) => [i.start, i.end, i.inP, i.outP])).toEqual([
      [0, 4, 100, 104],
      [4, 9, 104, 109],
    ]);
    expect(seq.vt[1][0].name).toBe("hook · main");
    expect(seq.at[2].map((i: any) => i.disabled)).toEqual([true]);
    expect(seq.at[0].map((i: any) => i.disabled)).toEqual([false, false]);
    expect(seq.at[1]).toHaveLength(1);
    expect(seq.at[1][0].name).toBe("Lahza · musiqa");

    // bg: statik scale 177.78 + markazdagi normallashgan pozitsiya + Gaussian Blur 60
    const bg = seq.vt[0][0];
    expect(motionParam(bg, "Scale")).toMatchObject({ timeVarying: false, value: 177.7778 });
    expect(motionParam(bg, "Position").value).toMatchObject({ x: 0.5, y: 0.5 });
    const blur = bg.chain.comps.find((c: any) => c.matchName === "AE.ADBE Gaussian Blur 2");
    expect(blur.params[0].value).toBe(60);
    expect(blur.params[2].value).toBe(true);

    // v2 main: pozitsiya 3 ta kalit kadr (manba vaqtida: 104 + t), scale o'zgarmas -> statik
    const v2 = seq.vt[1][1];
    const pos = motionParam(v2, "Position");
    expect(pos.timeVarying).toBe(true);
    expect(pos.keys.map((k) => [k.t, (k.v as { x: number }).x, k.interp])).toEqual([
      [104, 700 / 1080, 2],
      [106, 0.5, 1],
      [108.5, 380 / 1080, 2],
    ]);
    expect(motionParam(v2, "Scale").timeVarying).toBe(false);

    // markerlar: 2 + matn; rang hook -> RED(1)
    expect(seq.markers.map((x: any) => [x.name, x.start, x.dur, x.color])).toEqual([
      ["Hook", 0, 0, 1],
      ["Urg'u", 5.5, 0, 5],
      ["[hook] Eng muhim gap", 0, 2, 6],
    ]);

    const codes = res.warnings.map((w) => w.code);
    expect(codes).toContain("captions_imported_only"); // SRT faqat import (API yo'q)
    expect(codes).toContain("audio_level_approx");
    expect(m.imported.at(-1)).toEqual(["/out/mehmon.srt"]);
    expect(res.placedClips).toBe(2);
  });

  it("montaj: o'tishlar runtime nomlaridan tanlanadi, topilmasa ogohlantirish", async () => {
    const m = makeMockPpro();
    const res = await new PremiereAdapter(m.ppro as premierepro).buildFromPlan(montagePlan());
    const v = m.sequences[0].vt[0];
    expect(v.map((i: any) => [i.start, i.end])).toEqual([
      [0, 3],
      [3, 6],
      [6, 8],
    ]);
    expect(v[1].transitions).toEqual([{ name: "ADBE Cross Dissolve New", start: true, dur: 0.5 }]);
    expect(v[2].transitions).toEqual([]); // "zoom" ro'yxatda yo'q
    expect(res.warnings.map((w) => w.code)).toContain("transition_missing");
    // ease -> BEZIER(0)
    expect(motionParam(v[0], "Scale").keys.map((k) => k.interp)).toEqual([0, 0, 0]);
  });

  it("split: Crop effekti foizlari", async () => {
    const m = makeMockPpro();
    await new PremiereAdapter(m.ppro as premierepro).buildFromPlan(splitPlan());
    const top = m.sequences[0].vt[1][0];
    const crop = top.chain.comps.find((c: any) => c.matchName === "AE.ADBE Crop");
    expect(crop.params.map((p: any) => p.value)).toEqual([21.875, 5.556, 21.875, 5.556]);
  });

  it("effektlar ro'yxatida blur yo'q bo'lsa - ogohlantirish, qurish davom etadi", async () => {
    const m = makeMockPpro({ filters: ["PR.ADBE Gamma Correction"] });
    const res = await new PremiereAdapter(m.ppro as premierepro).buildFromPlan(clipPlan());
    expect(res.warnings.map((w) => w.code)).toContain("blur_missing");
    expect(res.placedClips).toBe(2);
  });

  it("tanlangan media va loyiha ma'lumoti", async () => {
    const m = makeMockPpro();
    const a = new PremiereAdapter(m.ppro as premierepro);
    expect(await a.selectedMediaPaths()).toEqual(["/old/other.mov"]);
    expect(await a.projectInfo()).toEqual({ name: "Demo", path: "/p/Demo.prproj", activeSequence: null });
  });

  it("nom tanlash", () => {
    const names = ["ADBE Additive Dissolve", "ADBE Cross Dissolve New", "ADBE Dip To White", "ADBE Wipe", "ADBE Cross Zoom"];
    const pick = (k: string) => pickName(names, TRANSITION_PATTERNS[k].exact, TRANSITION_PATTERNS[k].re);
    expect(pick("cross_dissolve")).toBe("ADBE Cross Dissolve New");
    expect(pick("dip_to_white")).toBe("ADBE Dip To White");
    expect(pick("wipe")).toBe("ADBE Wipe");
    expect(pick("zoom")).toBe("ADBE Cross Zoom");
    expect(pick("dip_to_black")).toBeNull();
  });
});
