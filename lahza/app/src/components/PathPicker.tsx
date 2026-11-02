import { useId } from "react";

import { hasNativeDialog, pickPath, type PickOptions } from "../lib/dialog";
import { useT } from "../i18n";

/**
 * Yo'l tanlash maydoni. Tauri'da - tizim dialogi (maydon faqat o'qiladi);
 * brauzerda (dasturlash) - yo'l qo'lda yoziladi.
 */
export function PathPicker({
  label,
  value,
  onChange,
  options,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: PickOptions;
  placeholder?: string;
}) {
  const t = useT();
  const id = useId();
  const native = hasNativeDialog();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="row" style={{ flexWrap: "nowrap" }}>
        <input
          id={id}
          className="input mono"
          value={value}
          readOnly={native}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
        {native && (
          <button
            type="button"
            className="btn small"
            onClick={() => void pickPath({ title: label, defaultPath: value || undefined, ...options }).then((p) => p && onChange(p))}
          >
            {t("common.choose")}
          </button>
        )}
      </div>
    </div>
  );
}
