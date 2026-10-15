import { memo, useCallback, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useCreateClip, useEditWord, useEpisode, useSpeakers, useTranscript } from "../api/hooks";
import type { Sentence, Speaker } from "../api/types";
import { LexiconForm } from "../components/transcript/LexiconForm";
import { SearchReplace } from "../components/transcript/SearchReplace";
import { SpeakerName } from "../components/transcript/SpeakerName";
import { WordToken } from "../components/transcript/WordToken";
import { Empty, ErrorText, fmtTime, QueryState } from "../components/ui";
import { useT } from "../i18n";
import { flattenWords, type FlatWord } from "../lib/words";

const NO_SPEAKERS: Speaker[] = [];

/** Transkript muharriri (M2-APP-4) va matndan klip yaratish (M2-APP-5). */
export function Transcript() {
  const t = useT();
  const { episodeId = "" } = useParams();
  const transcript = useTranscript(episodeId);
  const speakers = useSpeakers(episodeId);
  const episode = useEpisode(episodeId);
  const editWord = useEditWord(episodeId);

  const sentences = useMemo(() => transcript.data?.sentences ?? [], [transcript.data]);
  const words = useMemo(() => flattenWords(sentences), [sentences]);
  // Har gap uchun so'zlar bo'lagi oldindan - SentenceRow memo'si buzilmasin.
  const rows = useMemo(() => {
    let start = 0;
    return sentences.map((s) => {
      const row = { sentence: s, start, words: words.slice(start, start + s.words.length) };
      start += s.words.length;
      return row;
    });
  }, [sentences, words]);

  const [anchor, setAnchor] = useState<number | null>(null);
  const [focus, setFocus] = useState<number | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const [replacing, setReplacing] = useState(false);

  const sel = anchor == null || focus == null ? null : ([Math.min(anchor, focus), Math.max(anchor, focus)] as const);
  const selected = sel ? words.slice(sel[0], sel[1] + 1) : [];

  const q = query.trim().toLowerCase();
  const matches = useMemo(() => (q ? words.filter((w) => w.text.toLowerCase().includes(q)).map((w) => w.idx) : []), [words, q]);
  const matchSet = useMemo(() => new Set(matches), [matches]);

  const onSelect = useCallback((idx: number, extend: boolean) => {
    setEditing(null);
    setFocus(idx);
    setAnchor((a) => (extend && a != null ? a : idx));
  }, []);

  const clearSel = () => {
    setAnchor(null);
    setFocus(null);
  };

  const { mutate: mutateWord } = editWord;
  const commit = useCallback(
    (w: FlatWord, text: string) => {
      setEditing(null);
      if (text === w.text) return;
      mutateWord({ sentence_id: w.sentenceId, ord: w.ord, text });
      setAnchor(null);
      setFocus(null);
    },
    [mutateWord],
  );
  const cancelEdit = useCallback(() => setEditing(null), []);

  const goMatch = (dir: 1 | -1) => {
    if (!matches.length) return;
    const next = (cursor + dir + matches.length) % matches.length;
    setCursor(next);
    const idx = matches[next];
    if (idx === undefined) return;
    onSelect(idx, false);
    document.getElementById(`w-${idx}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  };

  /** Almashtirish so'z darajasida: har bir mos so'z alohida PATCH (faqat o'sha gap qayta tekislanadi). */
  const replace = async (replacement: string, all: boolean) => {
    const re = new RegExp(query.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
    const targets = all ? matches : matches.slice(cursor, cursor + 1);
    // O'chirishlar gapdagi tartibni siljitmasligi uchun oxiridan boshlab.
    const list = targets
      .map((i) => words[i])
      .filter((w): w is FlatWord => !!w)
      .sort((a, b) => b.idx - a.idx);
    setReplacing(true);
    try {
      for (const w of list) {
        await editWord.mutateAsync({ sentence_id: w.sentenceId, ord: w.ord, text: w.text.replace(re, replacement).trim() });
      }
    } catch {
      /* xato editWord.error orqali ko'rsatiladi */
    } finally {
      setReplacing(false);
    }
  };

  return (
    <div className="stack" style={{ gap: 16 }}>
      <div className="page-head">
        <div>
          <Link to={`/episodes/${episodeId}`} className="muted">← {t("tr.backToClips")}</Link>
          <h1>{t("tr.title")}{episode.data ? ` · ${episode.data.title}` : ""}</h1>
        </div>
        <SearchReplace
          query={query}
          onQuery={(v) => {
            setQuery(v);
            setCursor(0);
          }}
          count={matches.length}
          current={cursor}
          onNext={goMatch}
          onReplace={(r, all) => void replace(r, all)}
          busy={replacing || editWord.isPending}
        />
      </div>

      <p className="muted">{t("tr.hint")}</p>
      <QueryState query={transcript} />
      <ErrorText error={editWord.error} />
      {transcript.data && sentences.length === 0 && <Empty>{t("tr.empty")}</Empty>}

      {selected.length > 0 && (
        <SelectionBar
          episodeId={episodeId}
          showId={episode.data?.show_id}
          words={selected}
          onEdit={selected.length === 1 && selected[0] ? () => setEditing(selected[0]!.idx) : undefined}
          onClear={clearSel}
        />
      )}

      <div className="card transcript" aria-busy={editWord.isPending}>
        {rows.map(({ sentence: s, start, words: sw }, i) => {
          const end = start + sw.length - 1;
          const inSel = sel && sel[1] >= start && sel[0] <= end ? sel : null;
          const inEdit = editing != null && editing >= start && editing <= end ? editing : null;
          const prev = sentences[i - 1];
          return (
            <SentenceRow
              key={s.id}
              episodeId={episodeId}
              sentence={s}
              words={sw}
              speakers={speakers.data ?? NO_SPEAKERS}
              showSpeaker={!prev || prev.speaker !== s.speaker}
              sel={inSel}
              editing={inEdit}
              matchSet={q ? matchSet : null}
              onSelect={onSelect}
              onEditStart={setEditing}
              onCommit={commit}
              onCancel={cancelEdit}
            />
          );
        })}
      </div>
    </div>
  );
}

const SentenceRow = memo(function SentenceRow(p: {
  episodeId: string;
  sentence: Sentence;
  words: FlatWord[];
  speakers: Speaker[];
  showSpeaker: boolean;
  sel: readonly [number, number] | null;
  editing: number | null;
  matchSet: Set<number> | null;
  onSelect: (idx: number, extend: boolean) => void;
  onEditStart: (idx: number) => void;
  onCommit: (w: FlatWord, text: string) => void;
  onCancel: () => void;
}) {
  return (
    <div className="sentence">
      <div className="sentence-meta">
        {p.showSpeaker && p.sentence.speaker && (
          <SpeakerName episodeId={p.episodeId} label={p.sentence.speaker} speakers={p.speakers} />
        )}
        <span className="mono muted">{fmtTime(p.sentence.start_ms)}</span>
      </div>
      <div className="words">
        {p.words.map((w) => (
          <WordToken
            key={w.idx}
            word={w}
            selected={!!p.sel && w.idx >= p.sel[0] && w.idx <= p.sel[1]}
            editing={p.editing === w.idx}
            match={!!p.matchSet?.has(w.idx)}
            onSelect={p.onSelect}
            onEditStart={p.onEditStart}
            onEditCommit={p.onCommit}
            onEditCancel={p.onCancel}
          />
        ))}
      </div>
    </div>
  );
});

function SelectionBar({
  episodeId,
  showId,
  words,
  onEdit,
  onClear,
}: {
  episodeId: string;
  showId: string | undefined;
  words: FlatWord[];
  onEdit?: () => void;
  onClear: () => void;
}) {
  const t = useT();
  const nav = useNavigate();
  const createClip = useCreateClip(episodeId);
  const [lexOpen, setLexOpen] = useState(false);
  const [title, setTitle] = useState("");
  const first = words[0];
  const last = words[words.length - 1];
  if (!first || !last) return null;
  const text = words.map((w) => w.text).join(" ");

  return (
    <div className="card stack selection-bar" role="region" aria-label={t("tr.selection")}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span>
          <strong>{t("tr.selected", { n: words.length })}</strong>{" "}
          <span className="muted mono">{fmtTime(first.start_ms)} – {fmtTime(last.end_ms)}</span>
        </span>
        <button type="button" className="btn small ghost" onClick={onClear}>{t("common.clear")}</button>
      </div>
      <div className="row">
        {onEdit && <button type="button" className="btn small" onClick={onEdit}>{t("tr.editWord")}</button>}
        <button type="button" className="btn small" aria-expanded={lexOpen} onClick={() => setLexOpen((v) => !v)}>
          {t("tr.addLexicon")}
        </button>
        <input className="input" style={{ width: 220 }} aria-label={t("ed.titleField")} placeholder={t("tr.clipTitle")}
               value={title} onChange={(e) => setTitle(e.target.value)} />
        <button
          type="button"
          className="btn small primary"
          disabled={createClip.isPending}
          onClick={() =>
            createClip.mutate(
              { start_sentence_id: first.sentenceId, end_sentence_id: last.sentenceId, title: title.trim() || undefined },
              { onSuccess: (c) => nav(`/episodes/${episodeId}/clips/${c.id}`) },
            )
          }
        >
          {t("tr.createClip")}
        </button>
        <ErrorText error={createClip.error} />
      </div>
      {lexOpen && <LexiconForm showId={showId} initialTerm={text} initialVariants={text} onDone={() => setLexOpen(false)} />}
    </div>
  );
}
