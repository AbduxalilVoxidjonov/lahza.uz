import type { Locale } from "..";

const en = {
  heading: "Editing skills", notice: "Local recipes contain only editing data. Review their actions before installing or applying.",
  path: "Local .lahzaskill or JSON file", install: "Install", replace: "Replace an installed ID", examples: "Example recipes",
  installed: "Installed recipes", empty: "No editing skills installed.", montage: "Ready montage", choose: "Select a montage",
  title: "Caption title", apply: "Apply to saved timeline", remove: "Remove", confirm: "Remove this installed recipe? Applied edits and montage assets remain.",
  draft: "Save any pending montage draft first. This applies to the saved timeline, starting at the first video, and cannot include unsaved editor changes.",
  refresh: "Refresh", busy: "Working…", success: "Saved to the montage. Open it to review or render.",
  noMontages: "No ready montages available.", permissions: "Permissions", actions: "Actions", done: "Recipe installed.", deleted: "Recipe removed.",
};
type Messages = { [K in keyof typeof en]: string };
const uz: Messages = {
  heading: "Montaj ko‘nikmalari", notice: "Lokal retseptlar faqat montaj ma’lumotlarini saqlaydi. O‘rnatish yoki qo‘llashdan oldin amallarini tekshiring.",
  path: "Lokal .lahzaskill yoki JSON fayli", install: "O‘rnatish", replace: "O‘rnatilgan ID o‘rniga almashtirish", examples: "Namuna retseptlar",
  installed: "O‘rnatilgan retseptlar", empty: "Montaj ko‘nikmalari o‘rnatilmagan.", montage: "Tayyor montaj", choose: "Montajni tanlang",
  title: "Sarlavha matni", apply: "Saqlangan timeline’ga qo‘llash", remove: "O‘chirish", confirm: "O‘rnatilgan retsept o‘chirilsinmi? Qo‘llangan tahrir va montaj resurslari saqlanadi.",
  draft: "Avval saqlanmagan montaj tahririni saqlang. Retsept saqlangan timeline’dagi birinchi videoning boshiga qo‘llanadi; saqlanmagan tahrirlarni qamramaydi.",
  refresh: "Yangilash", busy: "Bajarilmoqda…", success: "Montajga saqlandi. Tekshirish yoki render uchun montajni oching.",
  noMontages: "Tayyor montajlar yo‘q.", permissions: "Ruxsatlar", actions: "Amallar", done: "Retsept o‘rnatildi.", deleted: "Retsept o‘chirildi.",
};
const ru: Messages = {
  heading: "Навыки монтажа", notice: "Локальные рецепты содержат только данные монтажа. Проверьте действия перед установкой или применением.",
  path: "Локальный файл .lahzaskill или JSON", install: "Установить", replace: "Заменить установленный ID", examples: "Примеры рецептов",
  installed: "Установленные рецепты", empty: "Навыки монтажа не установлены.", montage: "Готовый монтаж", choose: "Выберите монтаж",
  title: "Текст заголовка", apply: "Применить к сохранённому таймлайну", remove: "Удалить", confirm: "Удалить рецепт? Применённые изменения и ресурсы монтажа сохранятся.",
  draft: "Сначала сохраните черновик монтажа. Рецепт применяется к сохранённому таймлайну с начала первого видео и не включает несохранённые изменения.",
  refresh: "Обновить", busy: "Обработка…", success: "Сохранено в монтаж. Откройте его для проверки или рендера.",
  noMontages: "Нет готовых монтажей.", permissions: "Разрешения", actions: "Действия", done: "Рецепт установлен.", deleted: "Рецепт удалён.",
};
const cyrl: Messages = {
  heading: "Монтаж кўникмалари", notice: "Локал рецептлар фақат монтаж маълумотларини сақлайди. Ўрнатиш ёки қўллашдан олдин амалларини текширинг.",
  path: "Локал .lahzaskill ёки JSON файли", install: "Ўрнатиш", replace: "Ўрнатилган ID ўрнига алмаштириш", examples: "Намуна рецептлар",
  installed: "Ўрнатилган рецептлар", empty: "Монтаж кўникмалари ўрнатилмаган.", montage: "Тайёр монтаж", choose: "Монтажни танланг",
  title: "Сарлавҳа матни", apply: "Сақланган timeline’га қўллаш", remove: "Ўчириш", confirm: "Ўрнатилган рецепт ўчирилсинми? Қўлланган таҳрир ва монтаж ресурслари сақланади.",
  draft: "Аввал сақланмаган монтаж таҳририни сақланг. Рецепт сақланган timeline’даги биринчи видеонинг бошига қўлланади; сақланмаган таҳрирларни қамрамайди.",
  refresh: "Янгилаш", busy: "Бажарилмоқда…", success: "Монтажга сақланди. Текшириш ёки рендер учун монтажни очинг.",
  noMontages: "Тайёр монтажлар йўқ.", permissions: "Рухсатлар", actions: "Амаллар", done: "Рецепт ўрнатилди.", deleted: "Рецепт ўчирилди.",
};
export const skillsDictionaries: Record<Locale, Messages> = { en, uz, ru, "uz-Cyrl": cyrl };
