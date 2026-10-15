import { useEffect, useId, useState } from "react";

const parse = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

/** Vergul bilan ajratilgan ro'yxat maydoni (kalit so'zlar, to'ldiruvchi so'zlar va h.k.). */
export function ListInput({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: string[];
  onChange: (v: string[]) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const [text, setText] = useState(value.join(", "));
  // Tashqaridan o'zgarsa (shablon yuklandi) - matnni yangilash; yozish paytida tegmaslik.
  useEffect(() => {
    setText((cur) => (parse(cur).join("|") === value.join("|") ? cur : value.join(", ")));
  }, [value]);
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        className="input"
        disabled={disabled}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          onChange(parse(e.target.value));
        }}
      />
    </div>
  );
}
