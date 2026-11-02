import { describe, expect, it } from "vitest";
import { EngineError } from "../../shared/src/engine";
import { discoveryPath, homeDir, nodeEnv, readDiscovery } from "../src/host/discovery";
import { STRINGS } from "../src/i18n";
import { clipDurationS, defaultOutDir, errorText, isAbsolutePath, lostItems } from "../src/ui/workflow";
import { samplePlan } from "./fixtures";

function env(platform: string, files: Record<string, string>, envVars: Record<string, string> = {}) {
  const g = {
    cep_node: {
      process: { platform, env: envVars },
      require: (id: string) =>
        id === "fs"
          ? { existsSync: (p: string) => p in files, readFileSync: (p: string) => files[p] ?? "" }
          : { homedir: () => (platform === "win32" ? "C:\\Users\\me" : "/Users/me") },
    },
  };
  return nodeEnv(g);
}

describe("engine discovery (CEP Node)", () => {
  it("macOS va Windows yo'llari (shared dataDir), LAHZA_DATA_DIR ustun", () => {
    expect(discoveryPath(env("darwin", {})!)).toBe("/Users/me/Library/Application Support/Lahza Studio/engine.json");
    expect(discoveryPath(env("win32", {}, { LOCALAPPDATA: "C:\\Users\\me\\AppData\\Local" })!)).toBe(
      "C:\\Users\\me\\AppData\\Local\\Lahza Studio\\engine.json",
    );
    expect(discoveryPath(env("darwin", {}, { LAHZA_DATA_DIR: "/tmp/lz" })!)).toBe("/tmp/lz/engine.json");
  });

  it("found / missing / invalid / no-node", () => {
    const p = "/Users/me/Library/Application Support/Lahza Studio/engine.json";
    expect(readDiscovery(env("darwin", { [p]: '{"port":51234,"token":"abc","pid":1,"version":"0.1.0"}' }))).toMatchObject({
      kind: "found",
      info: { port: 51234, token: "abc" },
    });
    expect(readDiscovery(env("darwin", {}))).toEqual({ kind: "missing", path: p });
    expect(readDiscovery(env("darwin", { [p]: '{"port":"x"}' })).kind).toBe("invalid");
    expect(readDiscovery(null)).toEqual({ kind: "no-node" });
    expect(nodeEnv({})).toBeNull();
    expect(homeDir(env("win32", {}))).toEqual({ home: "C:\\Users\\me", sep: "\\" });
  });
});

describe("workflow yordamchilari", () => {
  it("out_dir absolyut", () => {
    expect(defaultOutDir("/Users/me/Proj/", "/Users/me")).toBe("/Users/me/Proj/Lahza");
    expect(defaultOutDir(null, "C:\\Users\\me", "\\")).toBe("C:\\Users\\me\\Lahza");
    expect(defaultOutDir(null, null)).toBe("");
    expect(isAbsolutePath("/a")).toBe(true);
    expect(isAbsolutePath("C:\\a")).toBe(true);
    expect(isAbsolutePath("a/b")).toBe(false);
  });
  it("xato matnlari: 409 alohida", () => {
    const t = STRINGS.uz;
    expect(errorText(new EngineError(409, "tahlil yo'q"), t)).toContain("409");
    expect(errorText(new EngineError(0, "aloqa yo'q"), t)).toBe("aloqa yo'q");
  });
  it("davomiylik kesimlardan; nima o'tmadi", () => {
    expect(clipDurationS({ start_ms: 0, end_ms: 10_000, cuts: [[0, 2000], [5000, 6500]] })).toBe(3.5);
    expect(clipDurationS({ start_ms: 1000, end_ms: 4000, cuts: [] })).toBe(3);
    expect(lostItems(samplePlan(), null)).toEqual(["shake fx (v3)"]);
    expect(lostItems(samplePlan(), { ok: true, comp: "c", warnings: ["a", "a", "b"] })).toEqual(["a", "b"]);
  });
  it("uz va en matnlari bir xil kalitlarga ega", () => {
    expect(Object.keys(STRINGS.en).sort()).toEqual(Object.keys(STRINGS.uz).sort());
  });
});
