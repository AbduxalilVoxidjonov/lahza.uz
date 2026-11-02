"""PRO-3 "Hook oldinga": klip ichidagi eng kuchli jumlani (2-4 s) tanlash (TZ 7-bo'lim).

Sof funksiyalar: transkript (+ ixtiyoriy signallar) -> klip ichidagi hook bo'lagi. Tanlangan bo'lak
render'da klip boshiga nusxa sifatida qo'yiladi (`timeline.clip_timeline`), keyin klip boshidan
to'liq davom etadi.

Manbalar ustuvorligi:
* LLM rejimi: `clip.hook_sentence_id` (LLM javobidagi `hook_id`) katta bonus oladi;
* signallar bo'lsa (balandlik, nutq tezligi, kulgi/olqish, spiker almashinuvi) - gap bali;
* Lite (LLM'siz, signalsiz ham) rejim: matn evristikasi - savol/undov, kuchli so'zlar, sonlar,
  gap chegarasiga moslik; bog'lovchi/olmosh bilan boshlanish jarimasi.

Ball (har oyna = ketma-ket so'zlar, 2-4 s):
    50 + 0.5*(gap signal bali - 50)              # keshdagi signallar: balandlik/cho'qqi z,
                                                 # nutq tezligi o'zgarishi, kulgi/olqish, spiker
  + 40 * (LLM hook_id gapidagi so'zlar ulushi)
  + 10 savol (oxirida "?" yoki savol so'zi bilan boshlanish) + 6 undov
  + min(12, 4 * kuchli so'zlar) + 6 son
  + min(8, 16 * (so'z tezligi / klip medianasi - 1))   # tezroq gapirilgan bo'lak
  + 8 gap boshidan boshlanish + 8 gap oxirida tugash (yoki +3 vergul/ibora oxiri)
  - 20 * boshlanish jarimasi (bog'lovchi / kontekstsiz olmosh)
  - 2 * |davomiylik - 3 s| (soniyada)
Klipning birinchi 2 s ida boshlanadigan oynalar avtomatik tanlovdan chiqariladi.

Tezlik: LLM, ASR yoki audio/video dekod yo'q; klip gaplari ikkilik qidiruv bilan topiladi, har
oyna prefiks yig'indilari bilan O(1) baholanadi (30 daqiqalik epizodda ~0.5 ms/klip).

Kafolat: bo'lak faqat so'z chegaralarida boshlanadi/tugaydi, kesilgan (cuts) so'zlarni o'z ichiga
olmaydi va klip chegarasidan chiqmaydi.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass, field

from lahza_engine.highlight.rules import QUESTION_WORDS, start_penalty
from lahza_engine.highlight.signals import SignalReport
from lahza_engine.text.orthography import fold_for_match
from lahza_engine.types import Clip, ClipHook, Sentence, Word

HOOK_MIN_MS = 2000
HOOK_MAX_MS = 4000
HOOK_TARGET_MS = 3000
PAD_BEFORE_MS = 80
"""So'z boshidan oldingi "nafas" (oldingi so'zga tegmasdan)."""
PAD_AFTER_MS = 120
LLM_HOOK_BONUS = 40.0
"""LLM javobidagi hook_id gapi uchun bonus (TZ: hook_id - eng kuchli jumla)."""
LLM_SIGNAL_DAMP = 0.5
EARLY_ZONE_MS = 2000
"""Klipning shu birinchi qismida boshlanadigan bo'lak avtomatik hook bo'la olmaydi: u baribir
darhol eshitiladi (qo'lda gap tanlanganda cheklov yo'q)."""

# Ball formulasi vaznlari (boshlang'ich; UzHighlight-Eval'da sozlanadi).
W_QUESTION = 10.0
W_EXCLAIM = 6.0
W_STRONG = 4.0
W_STRONG_MAX = 12.0
W_NUMBER = 6.0
W_RATE_MAX = 8.0
W_SENT_EDGE = 8.0
"""Gap boshidan boshlanish / gap oxirida tugash (har biri)."""
W_CLAUSE_END = 3.0
W_START_PENALTY = 20.0
W_LEN = 2.0
"""3 s maqsaddan har soniya uzoqlik uchun jarima."""

# Kuchli/diqqat tortuvchi so'zlar (fold_for_match ko'rinishida; kengaytiriladi).
STRONG_WORDS: frozenset[str] = frozenset(
    {
        "eng", "hech", "hamma", "hammasi", "hech qachon", "hech kim", "aslida", "haqiqat",
        "haqiqatan", "sir", "siri", "muhim", "xato", "xatosi", "katta", "zo'r", "ajoyib", "dahshat",
        "dahshatli", "albatta", "faqat", "birinchi", "oxirgi", "yagona", "million", "milliard",
        "pul", "boy", "qo'rqinchli", "yolg'on", "to'g'ri", "nega", "nima uchun", "hayot", "o'lim",
        "muvaffaqiyat", "bilmaysiz", "bilasizmi", "tasavvur", "e'tibor", "diqqat", "esingizda",
        "hayron", "kutilmagan", "mutlaqo", "umuman",
    }
)
_STRONG_PHRASES = tuple(w for w in STRONG_WORDS if " " in w)
_STRONG_SINGLE = frozenset(w for w in STRONG_WORDS if " " not in w)
_SENT_END = (".", "?", "!", "…")
_CLAUSE_END = (",", ";", ":", "—", *_SENT_END)


@dataclass(frozen=True)
class HookPick:
    start_ms: int
    end_ms: int
    sentence_ids: tuple[int, ...]
    text: str
    score: float
    reasons: list[str] = field(default_factory=list, compare=False)

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def to_hook(self) -> ClipHook:
        return ClipHook(start_ms=self.start_ms, end_ms=self.end_ms)


@dataclass
class _W:
    """So'z + bir marta hisoblangan belgilar (oynalar prefiks yig'indilari bilan baholanadi)."""

    word: Word
    sentence_id: int
    sentence_start: bool
    sentence_end: bool
    signal: float
    strong: int
    number: bool
    exclaim: bool
    llm: bool
    pen: float = 0.0
    pen_reasons: tuple[str, ...] = ()


def _in_cut(w: Word, cuts: Sequence[tuple[int, int]]) -> bool:
    return any(w.start_ms < b and a < w.end_ms for a, b in cuts)


def _tok(text: str) -> str:
    return fold_for_match(text).strip(".,!?;:—-…\"'«» ")


def _clip_words(clip: Clip, sentences: Sequence[Sentence], signals: SignalReport | None
                ) -> list[list[_W]]:
    """Klip ichidagi kesilmagan so'zlar - kesimlar bilan uzilmagan uzluksiz bo'laklarga ajratilgan.

    Gaplar vaqt bo'yicha saralangan: klip boshi ikkilik qidiruv bilan topiladi, faqat klip
    ichidagi gaplar o'qiladi (epizod uzunligiga bog'liq emas).
    """
    sig_by_id = {x.sentence_id: x for x in signals.sentences} if signals else {}
    first = bisect_left(sentences, clip.start_ms, key=lambda x: x.end_ms)
    runs: list[list[_W]] = [[]]
    for s in sentences[first:]:
        if s.start_ms >= clip.end_ms:
            break
        x = sig_by_id.get(s.id)
        sig = x.score() if x is not None else 50.0
        n = len(s.words)
        for k, w in enumerate(s.words):
            if w.end_ms <= w.start_ms or w.start_ms < clip.start_ms or w.end_ms > clip.end_ms:
                continue
            if _in_cut(w, clip.cuts):
                if runs[-1]:
                    runs.append([])
                continue
            t = _tok(w.text)
            runs[-1].append(_W(
                word=w, sentence_id=s.id, sentence_start=k == 0,
                sentence_end=k == n - 1 or w.text.rstrip().endswith(_SENT_END), signal=sig,
                strong=int(t in _STRONG_SINGLE), number=any(ch.isdigit() for ch in w.text),
                exclaim="!" in w.text, llm=clip.hook_sentence_id == s.id,
            ))
    runs = [r for r in runs if r]
    for run in runs:
        for i, x in enumerate(run):
            nxt = run[i + 1] if i + 1 < len(run) else None
            # Ikki so'zli kuchli iboralar ("hech qachon") - birinchi so'zga qo'shimcha hisob.
            if nxt is not None and f"{_tok(x.word.text)} {_tok(nxt.word.text)}" in _STRONG_PHRASES:
                x.strong += 1
            head = " ".join(y.word.text for y in run[i : i + 3])
            pen, why = start_penalty(head)
            x.pen, x.pen_reasons = pen, tuple(why)
    return runs


def _prefix(values: Sequence[float]) -> list[float]:
    out = [0.0]
    for v in values:
        out.append(out[-1] + v)
    return out


def _scan(
    run: Sequence[_W], clip: Clip, lo_k: int, hi_k: int, min_ms: int, max_ms: int,
    manual: bool, median_rate: float,
) -> list[tuple[float, int, int]]:
    """Bir uzluksiz bo'lakdagi barcha oynalar balli: (ball, i, j). Har oyna O(1)."""
    sig = _prefix([x.signal for x in run])
    llm = _prefix([float(x.llm) for x in run])
    strong = _prefix([float(x.strong) for x in run])
    num = _prefix([float(x.number) for x in run])
    exc = _prefix([float(x.exclaim) for x in run])
    out: list[tuple[float, int, int]] = []
    for i in range(lo_k, hi_k + 1):
        w0 = run[i]
        # Bo'lak gap boshidan yoki tinish belgisidan keyin boshlanadi (ibora chegarasi).
        if i > lo_k and not w0.sentence_start and not run[i - 1].word.text.rstrip().endswith(_CLAUSE_END):
            continue
        # Klipning birinchi soniyalari baribir darhol eshitiladi - avtomatik hook bo'la olmaydi.
        if not manual and w0.word.start_ms - clip.start_ms < EARLY_ZONE_MS:
            continue
        head = _start_bonus(w0)
        for j in range(i, hi_k + 1):
            dur = run[j].word.end_ms - w0.word.start_ms
            if dur > max_ms:
                break
            if dur < min_ms and not (manual and i == lo_k and j == hi_k):
                continue
            n = j - i + 1
            score = 50.0 + LLM_SIGNAL_DAMP * ((sig[j + 1] - sig[i]) / n - 50.0)
            score += LLM_HOOK_BONUS * (llm[j + 1] - llm[i]) / n
            score += head
            last = run[j].word.text.rstrip()
            if last.endswith("?") and not _starts_question(w0):
                score += W_QUESTION
            if exc[j + 1] - exc[i]:
                score += W_EXCLAIM
            score += min(W_STRONG_MAX, W_STRONG * (strong[j + 1] - strong[i]))
            if num[j + 1] - num[i]:
                score += W_NUMBER
            rate = n / max(0.001, dur / 1000)
            if median_rate > 0 and rate > median_rate:
                score += min(W_RATE_MAX, W_RATE_MAX * 2 * (rate / median_rate - 1.0))
            if run[j].sentence_end:
                score += W_SENT_EDGE
            elif last.endswith(_CLAUSE_END):
                score += W_CLAUSE_END
            score -= W_LEN * abs(dur - HOOK_TARGET_MS) / 1000
            out.append((score, i, j))
    return out


def _starts_question(w: _W) -> bool:
    return _tok(w.word.text) in QUESTION_WORDS


def _start_bonus(w: _W) -> float:
    b = W_SENT_EDGE if w.sentence_start else 0.0
    b += W_QUESTION if _starts_question(w) else 0.0
    return b - W_START_PENALTY * w.pen


def _reasons(win: Sequence[_W]) -> list[str]:
    r: list[str] = []
    if any(x.llm for x in win):
        r.append("LLM hook gapi")
    if win[-1].word.text.rstrip().endswith("?") or _starts_question(win[0]):
        r.append("savol")
    if any(x.exclaim for x in win):
        r.append("undov")
    if any(x.strong for x in win):
        r.append("kuchli so'zlar")
    if any(x.number for x in win):
        r.append("son")
    r.extend(win[0].pen_reasons)
    return r


def _bounds(run: Sequence[_W], i: int, j: int, clip: Clip) -> tuple[int, int]:
    """So'z chegaralari + kichik "nafas"; qo'shni so'zga va klip/kesim chegarasiga kirmaydi."""
    start = run[i].word.start_ms - PAD_BEFORE_MS
    if i > 0:
        start = max(start, run[i - 1].word.end_ms)
    end = run[j].word.end_ms + PAD_AFTER_MS
    if j + 1 < len(run):
        end = min(end, run[j + 1].word.start_ms)
    for a, b in clip.cuts:  # kesim chegarasiga kirmaslik
        if b <= run[i].word.start_ms:
            start = max(start, b)
        if a >= run[j].word.end_ms:
            end = min(end, a)
    return max(clip.start_ms, start), min(clip.end_ms, end)


def hook_candidates(
    clip: Clip,
    sentences: Sequence[Sentence],
    signals: SignalReport | None = None,
    min_ms: int = HOOK_MIN_MS,
    max_ms: int = HOOK_MAX_MS,
    sentence_id: int | None = None,
    limit: int = 5,
) -> list[HookPick]:
    """Klip ichidagi hook nomzodlari (ball bo'yicha kamayish tartibida, bir-birini qoplamaydi).

    Faqat mavjud ma'lumot: transkript so'z vaqtlari + keshdagi gap signallari (LLM, ASR, audio
    dekod yo'q). Har oyna prefiks yig'indilari bilan O(1) baholanadi; oyna <= max_ms bo'lgani
    uchun jami ish klipdagi so'zlar soniga chiziqli.

    sentence_id berilsa - faqat shu gap ichidagi bo'laklar (qo'lda tanlash; klip boshi ham
    mumkin); gap `min_ms` dan qisqa bo'lsa butun gap qaytariladi.
    """
    runs = _clip_words(clip, sentences, signals)
    rates = sorted(len(r) / max(0.001, (r[-1].word.end_ms - r[0].word.start_ms) / 1000) for r in runs)
    median_rate = rates[len(rates) // 2] if rates else 0.0
    scored: list[tuple[float, int, int, int]] = []
    for ri, run in enumerate(runs):
        idx = [k for k, x in enumerate(run) if sentence_id is None or x.sentence_id == sentence_id]
        if not idx:
            continue
        for score, i, j in _scan(run, clip, idx[0], idx[-1], min_ms, max_ms,
                                 sentence_id is not None, median_rate):
            scored.append((score, ri, i, j))
    scored.sort(key=lambda t: (-t[0], runs[t[1]][t[2]].word.start_ms))
    out: list[HookPick] = []
    for score, ri, i, j in scored:
        run = runs[ri]
        a, b = _bounds(run, i, j, clip)
        if not all(b <= q.start_ms or q.end_ms <= a for q in out):
            continue
        win = run[i : j + 1]
        out.append(HookPick(
            start_ms=a, end_ms=b, sentence_ids=tuple(dict.fromkeys(x.sentence_id for x in win)),
            text=" ".join(x.word.text for x in win), score=round(score, 2), reasons=_reasons(win),
        ))
        if len(out) >= limit:
            break
    return out


def pick_hook(
    clip: Clip,
    sentences: Sequence[Sentence],
    signals: SignalReport | None = None,
    min_ms: int = HOOK_MIN_MS,
    max_ms: int = HOOK_MAX_MS,
    sentence_id: int | None = None,
) -> HookPick | None:
    """Eng kuchli hook bo'lagi; mos bo'lak bo'lmasa None (masalan klip juda qisqa)."""
    found = hook_candidates(clip, sentences, signals, min_ms, max_ms, sentence_id, limit=1)
    return found[0] if found else None


def snap_hook(
    clip: Clip, sentences: Sequence[Sentence], start_ms: int, end_ms: int
) -> ClipHook | None:
    """Qo'lda berilgan oraliqni so'z chegaralariga kengaytiradi va klip ichiga qisadi.

    Natijada kesilmagan so'z qolmasa - None.
    """
    a, b = max(clip.start_ms, start_ms), min(clip.end_ms, end_ms)
    if b <= a:
        return None
    for s in sentences:
        for w in s.words:
            if w.start_ms < a < w.end_ms:
                a = w.start_ms
            if w.start_ms < b < w.end_ms:
                b = w.end_ms
    a, b = max(clip.start_ms, a), min(clip.end_ms, b)
    kept = [
        w for s in sentences for w in s.words
        if a <= w.start_ms and w.end_ms <= b and not _in_cut(w, clip.cuts)
    ]
    if not kept or b <= a:
        return None
    return ClipHook(start_ms=a, end_ms=b)
