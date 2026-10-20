// Plagin tanlash va manifest ParamSpec'idan avtomatik parametrlar formasi.
import { useFx } from "../../api/hooks";
import type { FxKind, FxManifest, FxParamSpec } from "../../api/types";
import { useT } from "../../i18n";
import { localText } from "../../lib/montage";
import { useSettings } from "../../store/settings";
import { PathPicker } from "../PathPicker";
import { Check, ColorField, NumField, SelectField, Slider, TextField } from "./fields";

/** Plagin ro'yxati (tur bo'yicha). `allowNone` - "yo'q" varianti (qiymat ""). */
export function FxSelect({ label, kinds, value, onChange, allowNone, noneLabel, disabled }: {
  label: string;
  kinds: FxKind[];
  value: string | null | undefined;
  onChange: (id: string | null) => void;
  allowNone?: boolean;
  noneLabel?: string;
  disabled?: boolean;
}) {
  const t = useT();
  const locale = useSettings((s) => s.locale);
  const fx = useFx();
  const list = (fx.data ?? []).filter((m) => kinds.includes(m.kind));
  const options = [
    ...(allowNone ? [{ value: "", label: noneLabel ?? t("fx.none") }] : []),
    ...list.map((m) => ({ value: m.id, label: localText(m.name, locale) || m.id })),
  ];
  // Reestrda yo'q (masalan, engine hali yuklamagan) qiymat ham ko'rinsin.
  if (value && !options.some((o) => o.value === value)) options.push({ value, label: value });
  return (
    <SelectField label={label} value={value ?? ""} options={options} disabled={disabled || fx.isLoading}
                 onChange={(v) => onChange(v || null)} />
  );
}

function paramLabel(p: FxParamSpec, locale: string): string {
  const n = p.name as Record<string, string> | null | undefined;
  return (n && (n[locale] || n["uz"])) || p.id;
}

function ParamInput({ spec, value, onChange, locale }: {
  spec: FxParamSpec; value: unknown; onChange: (v: unknown) => void; locale: string;
}) {
  const label = paramLabel(spec, locale);
  const dflt = spec.default;
  switch (spec.type) {
    case "float":
    case "int": {
      const v = typeof value === "number" ? value : typeof dflt === "number" ? dflt : spec.min ?? 0;
      const step = spec.type === "int" ? 1 : Math.max(0.01, ((spec.max ?? 1) - (spec.min ?? 0)) / 100);
      if (spec.min != null && spec.max != null) {
        return <Slider label={label} value={v} min={spec.min} max={spec.max} step={step}
                       format={(x) => (spec.type === "int" ? String(Math.round(x)) : x.toFixed(2))}
                       onChange={(x) => onChange(spec.type === "int" ? Math.round(x) : x)} />;
      }
      return <NumField label={label} value={v} min={spec.min ?? undefined} max={spec.max ?? undefined} step={step}
                       onChange={(x) => onChange(spec.type === "int" ? Math.round(x) : x)} />;
    }
    case "enum": {
      const values = spec.values ?? [];
      const v = typeof value === "string" ? value : typeof dflt === "string" ? dflt : values[0] ?? "";
      return <SelectField label={label} value={v} options={values.map((x) => ({ value: x, label: x }))} onChange={onChange} />;
    }
    case "bool":
      return <Check label={label} checked={typeof value === "boolean" ? value : dflt === true} onChange={onChange} />;
    case "color":
      return <ColorField label={label} value={typeof value === "string" ? value : typeof dflt === "string" ? dflt : "#000000"}
                         onChange={onChange} />;
    default: {
      const v = typeof value === "string" ? value : typeof dflt === "string" ? dflt : "";
      // LUT kabi fayl parametrlari.
      if (spec.type === "path" || spec.id === "file") {
        return <PathPicker label={label} value={v} onChange={onChange} options={{ extensions: ["cube"], filterName: "LUT" }} />;
      }
      return <TextField label={label} value={v} onChange={onChange} />;
    }
  }
}

/** Manifest parametrlari asosidagi forma. Manifest topilmasa - hech narsa. */
export function FxParamsForm({ manifest, params, onChange, disabled }: {
  manifest: FxManifest | undefined;
  params: Record<string, unknown> | undefined;
  onChange: (p: Record<string, unknown>) => void;
  disabled?: boolean;
}) {
  const locale = useSettings((s) => s.locale);
  if (!manifest || manifest.params.length === 0) return null;
  return (
    <fieldset className="row" disabled={disabled} style={{ border: "none", padding: 0, margin: 0, alignItems: "flex-end" }}>
      {manifest.params.map((p) => (
        <ParamInput key={p.id} spec={p} value={params?.[p.id]} locale={locale}
                    onChange={(v) => onChange({ ...(params ?? {}), [p.id]: v })} />
      ))}
    </fieldset>
  );
}

export function useManifest(id: string | null | undefined): FxManifest | undefined {
  const fx = useFx();
  return id ? fx.data?.find((m) => m.id === id) : undefined;
}
