// Oddiy i18n: asosiy lug'at - o'zbek (lotin), en - `satisfies` bilan to'liqligi tekshiriladi.
import type { HostWarning, StepKey, WarnCode } from "./host/adapter";

export type Locale = "uz" | "en";

export const uz = {
  "app.title": "Lahza",
  "tab.reels": "Reels",
  "tab.montage": "Montaj",
  "tab.engine": "Engine",

  "engine.checking": "Engine tekshirilmoqda…",
  "engine.ok": "Engine ulandi · v{version}",
  "engine.via_ipc": "fayl orqali (IPC)",
  "engine.missing": "Lahza Engine topilmadi",
  "engine.help":
    "Lahza Studio dasturini oching (u engine'ni o'zi ishga tushiradi) yoki terminalda: lahza serve --discovery. Panel engine'ni o'zi ishga tushirmaydi.",
  "engine.schema_mismatch": "Engine host-reja sxemasi mos emas ({schema}). Lahza Studio va plaginni yangilang.",
  "engine.retry": "Qayta tekshirish",
  "engine.manual": "Qo'lda ulash",
  "engine.port": "Port",
  "engine.token": "Token",
  "engine.connect": "Ulash",
  "engine.discovery_file": "Fayl: {path}",

  "analyze.title": "Tahlil",
  "analyze.selected": "Tanlangan klip",
  "analyze.none": "Project panelida yoki timeline'da klip tanlang",
  "analyze.refresh": "Tanlovni yangilash",
  "analyze.run": "Tahlil qilish",
  "analyze.running": "Tahlil: {stage}",
  "analyze.cancel": "Bekor qilish",

  "clips.title": "Lahzalar",
  "clips.empty": "Lahzalar hali yo'q",
  "clips.accept": "Qabul",
  "clips.reject": "Rad",
  "clips.duration": "{s} s",
  "clips.make": "Reels yasash",

  "reel.aspect": "Format",
  "reel.orth": "Imlo",
  "orth.official": "Rasmiy lotin",
  "orth.ascii": "ASCII (o' g')",
  "orth.new": "Yangi alifbo",

  "build.progress": "Qurilmoqda: {step} ({i}/{n})",
  "build.done": "Tayyor: «{name}» sekvensiyasi ({n} ta klip)",
  "build.warnings": "Nima o'tmadi yoki taxminiy",
  "build.no_warnings": "Hammasi o'tdi",
  "build.no_project": "Premiere'da loyiha ochiq emas",

  "step.import": "fayllar importi",
  "step.sequence": "sekvensiya",
  "step.clip": "klip",
  "step.music": "musiqa",
  "step.captions": "subtitr",
  "step.markers": "markerlar",
  "step.text": "matnlar",
  "step.done": "yakun",

  "montage.templates": "Shablonlar",
  "montage.sources": "Loyihada tanlangan kliplar ({n})",
  "montage.run": "Montaj qilish",
  "montage.running": "Montaj: {stage}",
  "montage.no_templates": "Shablonlar yo'q",

  "common.error": "Xato: {msg}",
  "common.loading": "Yuklanmoqda…",
  "common.lang": "EN",

  "warn.keyframes_static": "Kalit kadrlar qo'yilmadi — statik masshtab/pozitsiya ishlatildi",
  "warn.transform_failed": "Masshtab/pozitsiya qo'yilmadi",
  "warn.speed": "Tezlik o'zgartirilmadi (API yo'q) — 1x",
  "warn.blur_missing": "Gaussian Blur qo'shilmadi",
  "warn.crop_missing": "Crop (split) qo'yilmadi",
  "warn.lumetri": "Rang preseti (Lumetri) o'tmadi — qo'lda qo'llang",
  "warn.lut": "LUT o'tmadi — Lumetri'da qo'lda tanlang",
  "warn.transition_missing": "Mos o'tish topilmadi",
  "warn.transition_failed": "O'tish qo'yilmadi",
  "warn.audio_level": "Audio daraja qo'yilmadi",
  "warn.audio_level_approx": "Audio daraja taxminiy qo'yildi — tekshiring",
  "warn.music_fades": "Musiqa fade'lari qo'yilmadi",
  "warn.music_duck": "Musiqa ducking'i qo'yilmadi — Essential Sound'da yoqing",
  "warn.captions_imported_only": "Subtitr (SRT) loyihaga import qilindi — uni Timeline'ga sudrab qo'ying",
  "warn.captions_failed": "Subtitr import qilinmadi",
  "warn.captions_none": "Subtitr fayli yo'q",
  "warn.text_as_marker": "Matn qatlami marker sifatida qo'yildi",
  "warn.marker_failed": "Marker qo'yilmadi",
  "warn.clip_failed": "Klip qo'yilmadi",
  "warn.media_missing": "Media topilmadi",
  "warn.sequence_settings": "Sekvensiya sozlamalari to'liq qo'llanmadi",
  "warn.not_translated": "Engine: Premiere'ga o'tmaydi",
} as const;

export type MessageKey = keyof typeof uz;
export type Messages = { readonly [K in MessageKey]: string };

export const en = {
  "app.title": "Lahza",
  "tab.reels": "Reels",
  "tab.montage": "Montage",
  "tab.engine": "Engine",
  "engine.checking": "Checking engine…",
  "engine.ok": "Engine connected · v{version}",
  "engine.via_ipc": "via files (IPC)",
  "engine.missing": "Lahza Engine not found",
  "engine.help":
    "Open the Lahza Studio app (it starts the engine) or run in a terminal: lahza serve --discovery. The panel never starts the engine itself.",
  "engine.schema_mismatch": "Engine host-plan schema mismatch ({schema}). Update Lahza Studio and the plugin.",
  "engine.retry": "Check again",
  "engine.manual": "Connect manually",
  "engine.port": "Port",
  "engine.token": "Token",
  "engine.connect": "Connect",
  "engine.discovery_file": "File: {path}",
  "analyze.title": "Analysis",
  "analyze.selected": "Selected clip",
  "analyze.none": "Select a clip in the Project panel or timeline",
  "analyze.refresh": "Refresh selection",
  "analyze.run": "Analyze",
  "analyze.running": "Analyzing: {stage}",
  "analyze.cancel": "Cancel",
  "clips.title": "Moments",
  "clips.empty": "No moments yet",
  "clips.accept": "Accept",
  "clips.reject": "Reject",
  "clips.duration": "{s} s",
  "clips.make": "Make Reel",
  "reel.aspect": "Aspect",
  "reel.orth": "Spelling",
  "orth.official": "Official Latin",
  "orth.ascii": "ASCII (o' g')",
  "orth.new": "New alphabet",
  "build.progress": "Building: {step} ({i}/{n})",
  "build.done": "Done: sequence “{name}” ({n} clips)",
  "build.warnings": "What did not transfer or is approximate",
  "build.no_warnings": "Everything transferred",
  "build.no_project": "No project is open in Premiere",
  "step.import": "importing files",
  "step.sequence": "sequence",
  "step.clip": "clip",
  "step.music": "music",
  "step.captions": "captions",
  "step.markers": "markers",
  "step.text": "text",
  "step.done": "finishing",
  "montage.templates": "Templates",
  "montage.sources": "Clips selected in project ({n})",
  "montage.run": "Build montage",
  "montage.running": "Montage: {stage}",
  "montage.no_templates": "No templates",
  "common.error": "Error: {msg}",
  "common.loading": "Loading…",
  "common.lang": "UZ",
  "warn.keyframes_static": "Keyframes not applied — static scale/position used",
  "warn.transform_failed": "Scale/position not applied",
  "warn.speed": "Speed not changed (no API) — 1x",
  "warn.blur_missing": "Gaussian Blur not added",
  "warn.crop_missing": "Crop (split) not applied",
  "warn.lumetri": "Color preset (Lumetri) not transferred — apply manually",
  "warn.lut": "LUT not transferred — pick it in Lumetri",
  "warn.transition_missing": "No matching transition found",
  "warn.transition_failed": "Transition not applied",
  "warn.audio_level": "Audio level not applied",
  "warn.audio_level_approx": "Audio level applied approximately — please check",
  "warn.music_fades": "Music fades not applied",
  "warn.music_duck": "Music ducking not applied — enable it in Essential Sound",
  "warn.captions_imported_only": "Captions (SRT) imported into the project — drag them onto the timeline",
  "warn.captions_failed": "Captions not imported",
  "warn.captions_none": "No captions file",
  "warn.text_as_marker": "Text layer placed as a marker",
  "warn.marker_failed": "Marker not added",
  "warn.clip_failed": "Clip not placed",
  "warn.media_missing": "Media not found",
  "warn.sequence_settings": "Sequence settings not fully applied",
  "warn.not_translated": "Engine: not supported in Premiere",
} as const satisfies Messages;

const dicts: Record<Locale, Messages> = { uz, en };

export type TFunc = (key: MessageKey, vars?: Record<string, string | number>) => string;

export function translate(locale: Locale, key: MessageKey, vars?: Record<string, string | number>): string {
  let s: string = dicts[locale][key] ?? uz[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v));
  return s;
}

export function warnText(t: TFunc, w: HostWarning): string {
  const head = t(`warn.${w.code}` as `warn.${WarnCode}`);
  return w.detail ? `${head}: ${w.detail}` : head;
}

export function stepText(t: TFunc, k: StepKey): string {
  return t(`step.${k}` as `step.${StepKey}`);
}
