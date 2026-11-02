import type { Locale } from "..";

export const interopEn = {
  title: "External editing assets", path: "Local asset file", inspect: "Inspect", busy: "Working…",
  notice: "Lahza reads supported asset data. Adobe plugins and projects cannot run here.",
  montage: "Target montage", choose: "Select a montage", apply: "Replace montage color with this LUT",
  applied: "LUT saved to montage timeline.", empty: "Select a local file to inspect compatibility.",
  yes: "Can apply", no: "Cannot apply", refresh: "Refresh montages", noMontages: "No ready montages available.",
};
type Messages = { [K in keyof typeof interopEn]: string };
export const interopUz: Messages = {
  title: "Tashqi montaj resurslari", path: "Lokal resurs fayli", inspect: "Tekshirish", busy: "Bajarilmoqda…",
  notice: "Lahza mos resurs ma’lumotlarini o‘qiydi. Adobe plaginlari va loyihalari bu yerda ishlamaydi.",
  montage: "Maqsad montaj", choose: "Montajni tanlang", apply: "Montaj rangini shu LUT bilan almashtirish",
  applied: "LUT montaj timeline’iga saqlandi.", empty: "Moslikni tekshirish uchun lokal faylni tanlang.",
  yes: "Qo‘llash mumkin", no: "Qo‘llab bo‘lmaydi", refresh: "Montajlarni yangilash", noMontages: "Tayyor montajlar yo‘q.",
};
export const interopUzCyrl: Messages = {
  title: "Ташқи монтаж ресурслари", path: "Локал ресурс файли", inspect: "Текшириш", busy: "Бажарилмоқда…",
  notice: "Lahza мос ресурс маълумотларини ўқийди. Adobe плагинлари ва лойиҳалари бу ерда ишламайди.",
  montage: "Мақсад монтаж", choose: "Монтажни танланг", apply: "Монтаж рангини шу LUT билан алмаштириш",
  applied: "LUT монтаж timeline’ига сақланди.", empty: "Мосликни текшириш учун локал файлни танланг.",
  yes: "Қўллаш мумкин", no: "Қўллаб бўлмайди", refresh: "Монтажларни янгилаш", noMontages: "Тайёр монтажлар йўқ.",
};
export const interopRu: Messages = {
  title: "Внешние ресурсы монтажа", path: "Локальный файл ресурса", inspect: "Проверить", busy: "Обработка…",
  notice: "Lahza читает данные поддерживаемых ресурсов. Плагины и проекты Adobe здесь не запускаются.",
  montage: "Целевой монтаж", choose: "Выберите монтаж", apply: "Заменить цвет монтажа этим LUT",
  applied: "LUT сохранён в таймлайне монтажа.", empty: "Выберите локальный файл для проверки совместимости.",
  yes: "Можно применить", no: "Нельзя применить", refresh: "Обновить монтажи", noMontages: "Нет готовых монтажей.",
};
export const interopDictionaries: Record<Locale, Messages> = {
  en: interopEn, uz: interopUz, "uz-Cyrl": interopUzCyrl, ru: interopRu,
};
