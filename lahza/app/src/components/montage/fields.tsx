// Montaj va shablon formalari uchun kichik boshqaruv elementlari.
import { useId, type ReactNode } from "react";

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="fieldset stack">
      <legend>{title}</legend>
      {children}
    </fieldset>
  );
}

export function NumField({ label, value, min, max, step = 1, onChange, width = 130, disabled, suffix }: {
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (v: number) => void;
  width?: number | string;
  disabled?: boolean;
  suffix?: string;
}) {
  return (
    <label className="field" style={{ width }}>
      <span>{label}{suffix ? <span className="muted"> ({suffix})</span> : null}</span>
      <input className="input" type="number" min={min} max={max} step={step} value={Number.isFinite(value) ? value : ""}
             disabled={disabled}
             onChange={(e) => {
               if (e.target.value === "") return;
               let v = Number(e.target.value);
               if (!Number.isFinite(v)) return;
               if (min !== undefined) v = Math.max(min, v);
               if (max !== undefined) v = Math.min(max, v);
               onChange(v);
             }} />
    </label>
  );
}

export function Slider({ label, value, min, max, step = 0.01, onChange, format, disabled }: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  format?: (v: number) => string;
  disabled?: boolean;
}) {
  return (
    <label className="field" style={{ flex: 1, minWidth: 160 }}>
      <span>{label} <span className="mono">{format ? format(value) : value}</span></span>
      <input type="range" min={min} max={max} step={step} value={value} disabled={disabled}
             onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}

export function Check({ label, checked, onChange, disabled }: {
  label: string; checked: boolean; onChange: (v: boolean) => void; disabled?: boolean;
}) {
  return (
    <label className="row muted check">
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

export function SelectField<V extends string>({ label, value, options, onChange, disabled, flex = 1 }: {
  label: string;
  value: V;
  options: { value: V; label: string }[];
  onChange: (v: V) => void;
  disabled?: boolean;
  flex?: number;
}) {
  const id = useId();
  return (
    <div className="field" style={{ flex, minWidth: 140 }}>
      <label htmlFor={id}>{label}</label>
      <select id={id} className="select" value={value} disabled={disabled} onChange={(e) => onChange(e.target.value as V)}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

export function TextField({ label, value, onChange, disabled, placeholder, multiline, flex = 1 }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  placeholder?: string;
  multiline?: boolean;
  flex?: number;
}) {
  return (
    <label className="field" style={{ flex, minWidth: 160 }}>
      {label}
      {multiline ? (
        <textarea className="textarea" value={value} disabled={disabled} placeholder={placeholder}
                  onChange={(e) => onChange(e.target.value)} />
      ) : (
        <input className="input" value={value} disabled={disabled} placeholder={placeholder}
               onChange={(e) => onChange(e.target.value)} />
      )}
    </label>
  );
}

export function ColorField({ label, value, onChange, disabled }: {
  label: string; value: string; onChange: (v: string) => void; disabled?: boolean;
}) {
  return (
    <label className="field">
      {label}
      <input type="color" value={/^#[0-9a-fA-F]{6}$/.test(value) ? value : "#000000"} disabled={disabled}
             onChange={(e) => onChange(e.target.value.toUpperCase())} />
    </label>
  );
}
