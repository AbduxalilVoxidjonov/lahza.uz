import { useState } from "react";

import { useAddLexicon } from "../../api/hooks";
import type { LexiconKind } from "../../api/types";
import { useT } from "../../i18n";
import { ErrorText } from "../ui";

export const LEXICON_KINDS: LexiconKind[] = ["ism", "brend", "atama"];

/** Lug'atga yozuv qo'shish: to'g'ri yozilish (term) va ASR adashadigan variantlar. */
export function LexiconForm({
  showId,
  initialTerm = "",
  initialVariants = "",
  onDone,
}: {
  showId?: string;
  initialTerm?: string;
  initialVariants?: string;
  onDone?: () => void;
}) {
  const t = useT();
  const add = useAddLexicon();
  const [term, setTerm] = useState(initialTerm);
  const [variants, setVariants] = useState(initialVariants);
  const [kind, setKind] = useState<LexiconKind>("atama");
  return (
    <form
      className="row"
      onSubmit={(e) => {
        e.preventDefault();
        if (!term.trim()) return;
        add.mutate(
          {
            show_id: showId,
            term: term.trim(),
            variants: variants.split(",").map((v) => v.trim()).filter(Boolean),
            kind,
          },
          {
            onSuccess: () => {
              setTerm("");
              setVariants("");
              onDone?.();
            },
          },
        );
      }}
    >
      <input className="input" style={{ width: 180 }} aria-label={t("lex.term")} placeholder={t("lex.term")}
             value={term} onChange={(e) => setTerm(e.target.value)} />
      <input className="input" style={{ width: 220 }} aria-label={t("lex.variants")} placeholder={t("lex.variants")}
             value={variants} onChange={(e) => setVariants(e.target.value)} />
      <select className="select" style={{ width: 120 }} aria-label={t("lex.kind")} value={kind}
              onChange={(e) => setKind(e.target.value as LexiconKind)}>
        {LEXICON_KINDS.map((k) => (
          <option key={k} value={k}>{t(`lex.kind.${k}`)}</option>
        ))}
      </select>
      <button className="btn small primary" disabled={!term.trim() || add.isPending}>{t("lex.add")}</button>
      <ErrorText error={add.error} />
    </form>
  );
}
