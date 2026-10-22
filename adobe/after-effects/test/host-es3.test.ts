// host.jsx (va json2.jsx) ExtendScript = ES3: acorn ecmaVersion 3 bilan parse + ES5+ API chaqiruvlari yo'qligi.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { parse, type Node } from "acorn";
import { describe, expect, it } from "vitest";

const JSX = fileURLToPath(new URL("../jsx/", import.meta.url));

// ES3 da yo'q (yoki ExtendScript'da ishonchsiz) metodlar.
const FORBIDDEN_MEMBERS = new Set([
  "map", "forEach", "filter", "reduce", "reduceRight", "some", "every", "find", "findIndex", "includes",
  "trim", "bind", "startsWith", "endsWith", "padStart", "repeat",
]);
// Statik ES5+ funksiyalar: Object.keys(...), Array.isArray(...), Date.now() — `keys` kabi maydon nomlari emas.
const FORBIDDEN_STATIC: Record<string, Set<string>> = {
  Object: new Set(["keys", "values", "entries", "assign", "create", "defineProperty", "freeze", "getPrototypeOf"]),
  Array: new Set(["isArray", "from", "of"]),
  Date: new Set(["now"]),
};
// json2.jsx o'zi polyfill: Object.prototype.hasOwnProperty / Date toJSON ishlatadi — unga faqat sintaksis tekshiruvi.

function walk(node: unknown, visit: (n: Node & Record<string, unknown>) => void) {
  if (!node || typeof node !== "object") return;
  if (Array.isArray(node)) {
    for (const c of node) walk(c, visit);
    return;
  }
  const n = node as Node & Record<string, unknown>;
  if (typeof n.type === "string") visit(n);
  for (const k of Object.keys(n)) if (k !== "loc") walk(n[k], visit);
}

function es3Violations(src: string): string[] {
  const ast = parse(src, { ecmaVersion: 3, locations: true });
  const out: string[] = [];
  walk(ast, (n) => {
    if (n.type === "MemberExpression" && !n.computed) {
      const p = n.property as unknown as { name?: string };
      const o = n.object as unknown as { type: string; name?: string };
      if (p.name && FORBIDDEN_MEMBERS.has(p.name)) out.push(`.${p.name} (qator ${n.loc?.start.line})`);
      if (p.name && o.type === "Identifier" && o.name && FORBIDDEN_STATIC[o.name]?.has(p.name)) {
        out.push(`${o.name}.${p.name} (qator ${n.loc?.start.line})`);
      }
    }
    if (n.type === "Identifier" && (n as unknown as { name: string }).name === "alert") out.push(`alert (qator ${n.loc?.start.line})`);
  });
  return out;
}

describe("host.jsx ES3", () => {
  const host = readFileSync(`${JSX}host.jsx`, "utf8");

  it("acorn ecmaVersion 3 bilan parse bo'ladi", () => {
    expect(() => parse(host, { ecmaVersion: 3 })).not.toThrow();
  });

  it("ES5+ metodlar va alert yo'q", () => {
    expect(es3Violations(host)).toEqual([]);
  });

  it("let/const/arrow/template/spread/trailing comma qatnashmaydi (parser haqiqatan ES3)", () => {
    for (const bad of ["let a = 1;", "const a = 1;", "var f = (x) => x;", "var s = `a`;", "f(...a);", "var o = {a: 1,};", "for (var x of y) {}", "class A {}"]) {
      expect(() => parse(bad, { ecmaVersion: 3 }), bad).toThrow();
    }
    expect(es3Violations("var a = [1].map(function (x) { return x; });")).toHaveLength(1);
    expect(es3Violations("var k = Object.keys(o); var d = plan.keys;")).toEqual(["Object.keys (qator 1)"]);
  });

  it("ommaviy funksiyalar e'lon qilingan", () => {
    for (const fn of ["lahza_selectedFootagePaths", "lahza_buildComp", "lahza_buildKaraoke", "lahza_projectInfo", "lahza_ping"]) {
      expect(host).toMatch(new RegExp(`^function ${fn}\\(`, "m"));
    }
  });
});

describe("json2.jsx ES3", () => {
  it("acorn ecmaVersion 3 bilan parse bo'ladi", () => {
    const src = readFileSync(`${JSX}json2.jsx`, "utf8");
    expect(() => parse(src, { ecmaVersion: 3 })).not.toThrow();
  });
});
