import { useSettings } from "../../store/settings";
import type { Locale } from "..";

// PRO-3 "Hook oldinga" matnlari (umumiy lug'atlarga tegmaslik uchun alohida modul).
const en = {
  title: "Hook first", toggle: "Put the strongest line at the start",
  hint: "A 2–4 s fragment is copied to the very beginning, then the clip plays from its start.",
  current: "Hook:", other: "Choose another line", auto: "Auto", busy: "Saving…", none: "No suitable fragment found.",
};
type Messages = { [K in keyof typeof en]: string };
const uz: Messages = {
  title: "Hook oldinga", toggle: "Eng kuchli jumlani boshiga qo‘yish",
  hint: "2–4 soniyalik bo‘lak klip boshiga nusxalanadi, keyin klip o‘z boshidan davom etadi.",
  current: "Hook:", other: "Boshqa jumlani tanlash", auto: "Avto", busy: "Saqlanmoqda…", none: "Mos bo‘lak topilmadi.",
};
const cyrl: Messages = {
  title: "Ҳук олдинга", toggle: "Энг кучли жумлани бошига қўйиш",
  hint: "2–4 сониялик бўлак клип бошига нусхаланади, кейин клип ўз бошидан давом этади.",
  current: "Ҳук:", other: "Бошқа жумлани танлаш", auto: "Авто", busy: "Сақланмоқда…", none: "Мос бўлак топилмади.",
};
const ru: Messages = {
  title: "Хук в начало", toggle: "Поставить самую сильную фразу в начало",
  hint: "Фрагмент 2–4 с копируется в начало, затем клип идёт с самого начала.",
  current: "Хук:", other: "Выбрать другую фразу", auto: "Авто", busy: "Сохранение…", none: "Подходящий фрагмент не найден.",
};
const dictionaries: Record<Locale, Messages> = { en, uz, ru, "uz-Cyrl": cyrl };
export function useHookT() { const locale = useSettings((s) => s.locale); return (key: keyof Messages) => dictionaries[locale][key]; }
