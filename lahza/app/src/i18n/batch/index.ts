import type { Locale } from "..";

// Partiyaviy tahlil navbati (PRO-5).
export const batchUz = {
  title: "Partiyaviy tahlil", hint: "Bir nechta videoni navbatga qo'shing - ular ketma-ket, bittadan tahlil qilinadi. Bitta faylning xatosi qolganlarini to'xtatmaydi.",
  pick: "Fayllarni tanlash", paths: "Video yo'llari (har qatorda bittadan)", selected: "Tanlangan: {n}", clearSelection: "Tanlovni tozalash",
  add: "Navbatga qo'shish", focus: "Ustuvor mavzu (ixtiyoriy)", lite: "LLM'siz (tezkor)",
  queue: "Tahlil navbati", empty: "Navbat bo'sh.", summary: "Tayyor: {done}/{total} · xato: {failed}",
  queued: "Navbatda", running: "Tahlil qilinmoqda", done: "Tayyor", failed: "Xato", cancelled: "Bekor qilindi",
  up: "Yuqoriga", down: "Pastga", top: "Birinchi qilish", cancel: "Bekor qilish", remove: "Olib tashlash",
  retry: "Qayta urinish", clearFinished: "Tugaganlarni tozalash", open: "Epizodni ochish", stage: "Bosqich: {stage}",
};
type Messages = { [K in keyof typeof batchUz]: string };
export const batchUzCyrl: Messages = {
  title: "Партиявий таҳлил", hint: "Бир нечта видеони навбатга қўшинг - улар кетма-кет, биттадан таҳлил қилинади. Битта файлнинг хатоси қолганларини тўхтатмайди.",
  pick: "Файлларни танлаш", paths: "Видео йўллари (ҳар қаторда биттадан)", selected: "Танланган: {n}", clearSelection: "Танловни тозалаш",
  add: "Навбатга қўшиш", focus: "Устувор мавзу (ихтиёрий)", lite: "LLM'сиз (тезкор)",
  queue: "Таҳлил навбати", empty: "Навбат бўш.", summary: "Тайёр: {done}/{total} · хато: {failed}",
  queued: "Навбатда", running: "Таҳлил қилинмоқда", done: "Тайёр", failed: "Хато", cancelled: "Бекор қилинди",
  up: "Юқорига", down: "Пастга", top: "Биринчи қилиш", cancel: "Бекор қилиш", remove: "Олиб ташлаш",
  retry: "Қайта уриниш", clearFinished: "Тугаганларни тозалаш", open: "Эпизодни очиш", stage: "Босқич: {stage}",
};
export const batchRu: Messages = {
  title: "Пакетный анализ", hint: "Добавьте несколько видео в очередь - они анализируются по одному. Ошибка в одном файле не останавливает остальные.",
  pick: "Выбрать файлы", paths: "Пути к видео (по одному в строке)", selected: "Выбрано: {n}", clearSelection: "Очистить выбор",
  add: "Добавить в очередь", focus: "Приоритетная тема (необязательно)", lite: "Без LLM (быстро)",
  queue: "Очередь анализа", empty: "Очередь пуста.", summary: "Готово: {done}/{total} · ошибок: {failed}",
  queued: "В очереди", running: "Анализируется", done: "Готово", failed: "Ошибка", cancelled: "Отменено",
  up: "Выше", down: "Ниже", top: "Сделать первым", cancel: "Отменить", remove: "Убрать",
  retry: "Повторить", clearFinished: "Убрать завершённые", open: "Открыть эпизод", stage: "Этап: {stage}",
};
export const batchEn: Messages = {
  title: "Batch analysis", hint: "Add several videos to the queue - they are analyzed one at a time. A failure in one file does not stop the rest.",
  pick: "Choose files", paths: "Video paths (one per line)", selected: "Selected: {n}", clearSelection: "Clear selection",
  add: "Add to queue", focus: "Focus topic (optional)", lite: "Without LLM (fast)",
  queue: "Analysis queue", empty: "The queue is empty.", summary: "Done: {done}/{total} · failed: {failed}",
  queued: "Queued", running: "Analyzing", done: "Done", failed: "Failed", cancelled: "Cancelled",
  up: "Move up", down: "Move down", top: "Move to top", cancel: "Cancel", remove: "Remove",
  retry: "Retry", clearFinished: "Clear finished", open: "Open episode", stage: "Stage: {stage}",
};
export const batchDictionaries: Record<Locale, Messages> = {
  uz: batchUz, "uz-Cyrl": batchUzCyrl, ru: batchRu, en: batchEn,
};

export const fmt = (s: string, vars: Record<string, string | number>) =>
  Object.entries(vars).reduce((acc, [k, v]) => acc.replaceAll(`{${k}}`, String(v)), s);
