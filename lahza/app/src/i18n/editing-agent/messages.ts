export const uz = {
  title: "Montaj yordamchisi", mode: "Tahrirlash usuli", local: "Mahalliy buyruqlar", ai: "AI yordamchi",
  capabilities: "Video formatini o‘zgartiring, subtitr qo‘shing yoki o‘lchamini sozlang, rang bering va tanlangan klipda stop-kadr yarating.",
  checking: "AI modeli tekshirilmoqda…", retryStatus: "Qayta tekshirish", model: "Model:", available: "tayyor",
  unavailable: "AI hozir mavjud emas:", missing: "Tahrirlash modeli o‘rnatilmagan.", settings: "Sozlamalar → Modellar", refresh: "Holatni yangilash",
  request: "Qanday tahrir kerak?", working: "Tayyorlanmoqda…", retryPlan: "Rejani qayta tuzish", generate: "AI rejasini tuzish", apply: "AI rejasini qo‘llash",
  stale: "Montaj, so‘rov yoki tanlov o‘zgardi. Yangi reja tuzing.", planModel: "Reja modeli:", noChanges: "O‘zgarish taklif qilinmadi.",
  applied: "Montaj qoralamasiga qo‘llandi. O‘zgarishni bekor qilish mumkin.", localHint: "Internetsiz aniq iboralar bilan ishlash uchun «Mahalliy buyruqlar»ni tanlang.",
  refusal: "So‘rovning ayrim qismlarini bajarib bo‘lmaydi. Ularni aniqlashtirib, yangi reja tuzing. Hozircha o‘zgarishlar qo‘llanmaydi.",
  invalidStatus: "AI holati haqidagi javob noto‘g‘ri. Qayta tekshiring.", invalidPlan: "AI rejasi noto‘g‘ri shaklda keldi. Qayta reja tuzing.", invalidPreview: "O‘zgarishlarni tekshirish javobi noto‘g‘ri. Qayta reja tuzing.",
};
export type Messages = { [K in keyof typeof uz]: string };
const en: Messages = {
  title: "Editing assistant", mode: "Editing mode", local: "Local commands", ai: "AI assistant",
  capabilities: "Change the video format, add or resize captions, adjust colors and freeze a frame in the selected clip.",
  checking: "Checking AI model…", retryStatus: "Retry status", model: "Model:", available: "ready", unavailable: "AI unavailable:", missing: "No editing model installed.", settings: "Settings → Models", refresh: "Refresh status",
  request: "Describe your edit", working: "Working…", retryPlan: "Retry plan", generate: "Generate AI plan", apply: "Apply AI plan",
  stale: "The montage, request or selection changed. Generate a new plan.", planModel: "Plan model:", noChanges: "No changes proposed.", applied: "Applied to the draft. Undo is available.", localHint: "Choose Local commands to work offline with supported phrases.",
  refusal: "Some parts of this request cannot be completed. Clarify them and generate a new plan. No changes can be applied yet.",
  invalidStatus: "The AI status response was invalid. Check again.", invalidPlan: "The AI plan response was invalid. Generate a new plan.", invalidPreview: "The edit review response was invalid. Generate a new plan.",
};
const ru: Messages = {
  title: "Помощник монтажа", mode: "Режим редактирования", local: "Локальные команды", ai: "AI-помощник",
  capabilities: "Изменяйте формат видео, добавляйте субтитры и меняйте их размер, настраивайте цвет и создавайте стоп-кадр в выбранном клипе.",
  checking: "Проверяем модель AI…", retryStatus: "Повторить проверку", model: "Модель:", available: "готова", unavailable: "AI недоступен:", missing: "Модель для редактирования не установлена.", settings: "Настройки → Модели", refresh: "Обновить статус",
  request: "Опишите нужные изменения", working: "Подготовка…", retryPlan: "Повторить планирование", generate: "Создать план AI", apply: "Применить план AI",
  stale: "Монтаж, запрос или выбор изменились. Создайте новый план.", planModel: "Модель плана:", noChanges: "Изменений не предложено.", applied: "Применено к черновику. Изменение можно отменить.", localHint: "Для работы без интернета с готовыми фразами выберите «Локальные команды».",
  refusal: "Некоторые части запроса выполнить нельзя. Уточните их и создайте новый план. Пока изменения применить нельзя.",
  invalidStatus: "Некорректный ответ о статусе AI. Повторите проверку.", invalidPlan: "Некорректный ответ с планом AI. Создайте новый план.", invalidPreview: "Некорректный ответ проверки изменений. Создайте новый план.",
};
const cyrl: Messages = {
  title: "Монтаж ёрдамчиси", mode: "Таҳрирлаш усули", local: "Маҳаллий буйруқлар", ai: "AI ёрдамчи",
  capabilities: "Видео форматини ўзгартиринг, субтитр қўшинг ёки ўлчамини созланг, ранг беринг ва танланган клипда стоп-кадр яратинг.",
  checking: "AI модели текширилмоқда…", retryStatus: "Қайта текшириш", model: "Модель:", available: "тайёр", unavailable: "AI ҳозир мавжуд эмас:", missing: "Таҳрирлаш модели ўрнатилмаган.", settings: "Созламалар → Моделлар", refresh: "Ҳолатни янгилаш",
  request: "Қандай таҳрир керак?", working: "Тайёрланмоқда…", retryPlan: "Режани қайта тузиш", generate: "AI режасини тузиш", apply: "AI режасини қўллаш",
  stale: "Монтаж, сўров ёки танлов ўзгарди. Янги режа тузинг.", planModel: "Режа модели:", noChanges: "Ўзгариш таклиф қилинмади.", applied: "Монтаж қораламасига қўлланди. Ўзгаришни бекор қилиш мумкин.", localHint: "Интернетсиз аниқ иборалар билан ишлаш учун «Маҳаллий буйруқлар»ни танланг.",
  refusal: "Сўровнинг айрим қисмларини бажариб бўлмайди. Уларни аниқлаштириб, янги режа тузинг. Ҳозирча ўзгаришлар қўлланмайди.",
  invalidStatus: "AI ҳолати ҳақидаги жавоб нотўғри. Қайта текширинг.", invalidPlan: "AI режаси нотўғри шаклда келди. Қайта режа тузинг.", invalidPreview: "Ўзгаришларни текшириш жавоби нотўғри. Қайта режа тузинг.",
};
export const dictionaries = { uz, en, ru, "uz-Cyrl": cyrl };
