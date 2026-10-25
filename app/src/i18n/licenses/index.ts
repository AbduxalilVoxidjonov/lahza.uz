import type { Locale } from "..";

const en = {
  heading: "Third-party licenses",
  intro: "Components bundled with Lahza Studio or downloaded from the model catalog. This list is a technical reference, not legal advice.",
  search: "Search", searchPlaceholder: "Name, license or version", category: "Type",
  all: "All", unresolved: "To be determined",
  cat_python: "Python packages", "cat_python-native": "Native libraries in Python wheels", cat_npm: "npm packages (UI)",
  cat_rust: "Rust crates", cat_runtime: "Native runtimes", cat_native: "Runtime libraries", cat_font: "Fonts", cat_model: "Models",
  name: "Component", version: "Version", license: "License", type: "Type",
  open: "License text", close: "Close", noText: "Full text is not available offline for this component. See the source:",
  source: "Source", attribution: "Attribution", notes: "Notes", via: "Pulled in by", basis: "Determined from",
  empty: "Nothing matches the search.", loading: "Loading the list…", loadError: "The license list could not be loaded.",
  showMore: "Show {n} more", count: "{shown} of {total}", risk: "Risk",
  lgplTitle: "LGPL components and source offer",
  lgplBody: "FFmpeg {version} and the other LGPL libraries are linked dynamically and ship as separate files, so you can replace them with your own compatible build. GPL and nonfree parts are disabled. On request we will provide the complete corresponding source code of these components, with build scripts and configuration flags, for at least 3 years from distribution, for no more than the cost of distribution. FFmpeg source: {url}",
  summary: "Most common licenses",
};
type Messages = { [K in keyof typeof en]: string };

const uz: Messages = {
  heading: "Uchinchi tomon litsenziyalari",
  intro: "Lahza Studio bilan birga keladigan yoki model katalogidan yuklanadigan komponentlar. Ro‘yxat texnik ma’lumot, yuridik xulosa emas.",
  search: "Qidiruv", searchPlaceholder: "Nom, litsenziya yoki versiya", category: "Turi",
  all: "Hammasi", unresolved: "Aniqlanishi kerak",
  cat_python: "Python paketlari", "cat_python-native": "Python g‘ildiraklaridagi native kutubxonalar", cat_npm: "npm paketlari (UI)",
  cat_rust: "Rust crate’lari", cat_runtime: "Native runtime’lar", cat_native: "Runtime kutubxonalari", cat_font: "Shriftlar", cat_model: "Modellar",
  name: "Komponent", version: "Versiya", license: "Litsenziya", type: "Turi",
  open: "Litsenziya matni", close: "Yopish", noText: "Bu komponentning to‘liq matni oflayn mavjud emas. Manbaga qarang:",
  source: "Manba", attribution: "Muallifni ko‘rsatish", notes: "Izoh", via: "Kim tortgan", basis: "Qayerdan aniqlangan",
  empty: "Qidiruvga mos komponent yo‘q.", loading: "Ro‘yxat yuklanmoqda…", loadError: "Litsenziyalar ro‘yxatini yuklab bo‘lmadi.",
  showMore: "Yana {n} tasini ko‘rsatish", count: "{total} tadan {shown} tasi", risk: "Xavf",
  lgplTitle: "LGPL komponentlari va manba taklifi",
  lgplBody: "FFmpeg {version} va boshqa LGPL kutubxonalar dinamik bog‘lanadi va alohida fayl sifatida keladi — ularni mos o‘z yig‘mangiz bilan almashtirishingiz mumkin. GPL va nonfree qismlar o‘chirilgan. So‘rov bo‘yicha bu komponentlarning to‘liq manba kodini yig‘ish skriptlari va konfiguratsiya bayroqlari bilan birga tarqatilgan kundan kamida 3 yil davomida tarqatish xarajatidan oshmaydigan haq evaziga taqdim etamiz. FFmpeg manbasi: {url}",
  summary: "Eng ko‘p uchraydigan litsenziyalar",
};

const cyrl: Messages = {
  heading: "Учинчи томон лицензиялари",
  intro: "Lahza Studio билан бирга келадиган ёки модел каталогидан юкланадиган компонентлар. Рўйхат техник маълумот, юридик хулоса эмас.",
  search: "Қидирув", searchPlaceholder: "Ном, лицензия ёки версия", category: "Тури",
  all: "Ҳаммаси", unresolved: "Аниқланиши керак",
  cat_python: "Python пакетлари", "cat_python-native": "Python ғилдиракларидаги native кутубхоналар", cat_npm: "npm пакетлари (UI)",
  cat_rust: "Rust crate’лари", cat_runtime: "Native runtime’лар", cat_native: "Runtime кутубхоналари", cat_font: "Шрифтлар", cat_model: "Моделлар",
  name: "Компонент", version: "Версия", license: "Лицензия", type: "Тури",
  open: "Лицензия матни", close: "Ёпиш", noText: "Бу компонентнинг тўлиқ матни офлайн мавжуд эмас. Манбага қаранг:",
  source: "Манба", attribution: "Муаллифни кўрсатиш", notes: "Изоҳ", via: "Ким тортган", basis: "Қаердан аниқланган",
  empty: "Қидирувга мос компонент йўқ.", loading: "Рўйхат юкланмоқда…", loadError: "Лицензиялар рўйхатини юклаб бўлмади.",
  showMore: "Яна {n} тасини кўрсатиш", count: "{total} тадан {shown} таси", risk: "Хавф",
  lgplTitle: "LGPL компонентлари ва манба таклифи",
  lgplBody: "FFmpeg {version} ва бошқа LGPL кутубхоналар динамик боғланади ва алоҳида файл сифатида келади — уларни мос ўз йиғмангиз билан алмаштиришингиз мумкин. GPL ва nonfree қисмлар ўчирилган. Сўров бўйича бу компонентларнинг тўлиқ манба кодини йиғиш скриптлари ва конфигурация байроқлари билан бирга тарқатилган кундан камида 3 йил давомида тарқатиш харажатидан ошмайдиган ҳақ эвазига тақдим этамиз. FFmpeg манбаси: {url}",
  summary: "Энг кўп учрайдиган лицензиялар",
};

const ru: Messages = {
  heading: "Лицензии сторонних компонентов",
  intro: "Компоненты, входящие в Lahza Studio или загружаемые из каталога моделей. Список — техническая справка, а не юридическое заключение.",
  search: "Поиск", searchPlaceholder: "Название, лицензия или версия", category: "Тип",
  all: "Все", unresolved: "Требует уточнения",
  cat_python: "Пакеты Python", "cat_python-native": "Нативные библиотеки в колёсах Python", cat_npm: "Пакеты npm (UI)",
  cat_rust: "Крейты Rust", cat_runtime: "Нативные среды выполнения", cat_native: "Библиотеки сред выполнения", cat_font: "Шрифты", cat_model: "Модели",
  name: "Компонент", version: "Версия", license: "Лицензия", type: "Тип",
  open: "Текст лицензии", close: "Закрыть", noText: "Полный текст для этого компонента недоступен офлайн. См. источник:",
  source: "Источник", attribution: "Указание авторства", notes: "Примечание", via: "Подтянут через", basis: "Источник сведений",
  empty: "Ничего не найдено.", loading: "Загрузка списка…", loadError: "Не удалось загрузить список лицензий.",
  showMore: "Показать ещё {n}", count: "{shown} из {total}", risk: "Риск",
  lgplTitle: "Компоненты LGPL и предложение исходного кода",
  lgplBody: "FFmpeg {version} и другие библиотеки LGPL подключаются динамически и поставляются отдельными файлами — их можно заменить собственной совместимой сборкой. Части GPL и nonfree отключены. По запросу мы предоставим полный исходный код этих компонентов со сценариями сборки и флагами конфигурации в течение не менее 3 лет с момента распространения по цене, не превышающей стоимость распространения. Исходный код FFmpeg: {url}",
  summary: "Самые частые лицензии",
};

export type LicensesMessages = Messages;
export const licensesDictionaries: Record<Locale, Messages> = { en, uz, ru, "uz-Cyrl": cyrl };

export function fill(s: string, vars: Record<string, string | number>): string {
  let out = s;
  for (const [k, v] of Object.entries(vars)) out = out.replaceAll(`{${k}}`, String(v));
  return out;
}
