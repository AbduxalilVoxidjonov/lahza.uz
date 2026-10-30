import type { Resources } from "./en-US";

// O'zbekcha (uz-UZ, lotin yozuvi). Lahza Studio'ning asosiy tili. en-US bilan
// bir xil tuzilishda — `Resources` turi yetishmagan yoki ortiqcha kalitni
// tekshiruvda ushlaydi. Atamalar: layer/clip → klip, track → yo'lak.
const uzUZ: Resources = {
  resources: {
    memory: "Xotira chegarasi",
    memory_hint: "Kesh va ishlov berish quvvatini boshqaradi. Xotira tanqis bo'lganda ilova fon ishlarini kamaytiradi; qisqa muddatli cho'qqilar bo'lishi mumkin.",
    processing: "Ishlov berish kuchi",
    processing_hint: "Yuqori sozlamalar ishni tezroq tugatadi, lekin boshqa ilovalarga kamroq quvvat qoladi.",
    low: "Kam resurs sarfi", balanced: "Muvozanatli", high: "Yuqori unumdorlik",
    disk: "Vaqtinchalik kesh joyi",
    disk_hint: "Qayta yaratiladigan miniatyuralar, animatsiya kadrlari, ovoz to'lqinlari va ovoz effekti keshlari uchun joy. Asl media, modellar va loyiha fayllari saqlanib qoladi. Standart holatda ish maydoni joylashgan diskning umumiy hajmining 10% (4–64 GiB).",
    background: "O'ynatish paytida fon ishlovini davom ettirish",
    background_hint: "O'chiq bo'lsa, yangi fon media vazifalari o'ynatish to'xtaguncha kutadi. Allaqachon ishlayotgan vazifalar odatdagidek tugaydi.",
    constrained: "Xotira tanqis. Joriy ishlar tugaguncha yangi ishlov kutib turadi.",
    normal: "Resurslar yetarli.", usage: "Ilova xotirasi: taxminan {{used}} GiB.", waiting: "{{count}} ta vazifa kutmoqda.",
  },
  hardware: {
    "probe_heading": "Dekodlash va kodlashni tezlashtirish",
    "test_complete": "Aniqlash tugadi",
    "current_decode_device": "Joriy dekodlash qurilmasi",
    "decode_idle": "Dekodlash seanslari yo'q",
    "decode_cpu": "CPU (dasturiy dekodlash)",
    "decode_browser": "Brauzer dekodlashi (qurilma ma'lum emas)",
    "decode_system": "Tizim video dekoderi",
    "decode_device_unknown": "Apparat dekodlash (qurilma tasdiqlanmagan)",
    "decode_session_scope": "Ochilgan ko'rish oynasi seanslari; pauza paytida ham band bo'lib qolishi mumkin.",
    "open_diagnostics": "Apparat diagnostikasi",
    "diagnostics_title": "Apparat diagnostikasi",
    "diagnostics_devices": "Grafik qurilmalar",
    "render_nodes": "Render qurilmasi yo'llari",
    "hardware_rendering": "Apparat tezlashtirilgan",
    "preview_decode": "Ko'rish oynasi uchun apparat dekodlash",
    "export_encode": "Eksport uchun apparat kodlash",
    "support_available": "Ushbu sinovda mavjud",
    "partial_support": "Ba'zi formatlar mavjud",
    "test_incomplete": "Sinov tugallanmadi",
    "browser_media": "Brauzer media holati",
    "video_decode": "Brauzerda video dekodlash",
    "video_encode": "Brauzerda video kodlash",
    "software_processing": "Dasturiy ishlov",
    "browser_media_scope": "Brauzer imkoniyatlari holati, har bir format bo'yicha sinov emas. Ko'rish oynasi va eksport tezlashtirilishi quyida alohida sinanadi.",
    "render_device": "Render adapteri",
    "render_unresolved": "Render adapterini aniq bir qurilma bilan moslab bo'lmadi.",
    "probe_device_unresolved": "Sinov qurilmasi aniqlanmadi",
    "no_devices": "Hech qanday grafik qurilma aniqlanmadi.",
    "memory_dedicated": "Alohida grafik xotira",
    "memory_shared": "Grafik xotira",
    "memory_local": "Drayver bildirgan mahalliy grafik xotira",
    "memory_unknown": "Grafik xotira",
    "device_memory_used": "Ishlatilgan qurilma xotirasi (barcha ilovalar)",
    "device_memory_free": "Bo'sh qurilma xotirasi",
    "driver": "Drayver",
    "identity_source": "Qurilma ma'lumoti manbai",
    "memory_source": "Xotira o'lchovi manbai",
    "source_nvml": "NVIDIA drayveri",
    "source_amdgpu": "AMD drayveri",
    "source_drm": "Linux grafik drayveri",
    "source_pci-ids": "Mahalliy PCI qurilmalar bazasi",
    "source_electron": "Electron",
    "source_device-id": "Qurilma ID",
    "source_unknown": "Mavjud emas",
    "render_heading": "Render",
    "acceleration_heading": "Video apparat tezlashtirish",
    "compositing": "Interfeys GPU kompozitsiyasi",
    "enabled": "Yoqilgan",
    "disabled": "Yoqilmagan",
    "testing": "Sinanmoqda…",
    "detect": "Tezlashtirishni sinash",
    "refresh": "Apparatni yangilash",
    "probe_scope": "Ko'rish oynasi dekodlashi va eksport kodlashini qisqa namunalar bilan sinaydi. Format qo'llab-quvvatlanishini tekshiradi; o'ynatish tezligi o'lchanmaydi.",
    "decode_heading": "Standart dvigatel ko'rish oynasi dekodlashi",
    "encode_heading": "FFmpeg eksport kodlashi",
    "decode_scope": "Ko'rish oynasi sinovi 8-bitli H.264, HEVC va VP9 ni qamraydi. Linux'da ko'rish oynasi kadrlarni tizim xotirasi orqali nusxalaydi. Eksport dekodlashi hozircha dasturiy usulda.",
    "memory_scope": "Qurilma xotirasi barcha ilovalarni o'z ichiga oladi. U Lahza Studio resurs sarfidan alohida o'lchanadi.",
    "sampled_at": "Oxirgi sinov: {{time}}",
    "stale": "Oxirgi apparat ma'lumoti ko'rsatilmoqda; joriy ma'lumot mavjud emas.",
    "probe_details": "Texnik tafsilotlar",
    "status_available": "Sinovdan o'tdi",
    "status_software": "Dasturiy render",
    "status_unavailable": "Mavjud emas",
    "status_not-tested": "Sinalmagan",
    "reason_permission-denied": "Qurilmaga kirish rad etildi",
    "reason_driver-unavailable": "Drayver yoki qurilma mavjud emas",
    "reason_component-unavailable": "Kerakli ilova komponenti mavjud emas",
    "reason_unsupported": "Qo'llab-quvvatlanadigan backend yo'q",
    "reason_timeout": "Aniqlash vaqti tugadi; tizim bo'sh bo'lganda qayta urining",
    "reason_probe-failed": "Sinov muvaffaqiyatli tugamadi",
    "reason_resource-busy": "Ilova resurslari band; joriy ish tugagach qayta urining",
    "reason_unknown": "Bu o'lchov mavjud emas",
    "cpu": "Protsessor",
    "cpu_processors": "{{count}} ta mantiqiy protsessor",
  },
  performance: {
      "shared_gpu_memory": "Umumiy xotiradan foydalanadi",
      "unknown": "Noma'lum",
      "hardware_vram": "Alohida grafik xotira",
      "hardware_graphics_memory": "Grafik xotira",
      "hardware_gpu": "Asosiy grafik adapter",
      "hardware_ram": "Xotira",
      "hardware_heading": "Ushbu kompyuter",
      "buffer_frames_hint": "Ko'proq kadr ko'proq GPU bufer xotirasini oladi",
      "buffer_frames": "Har bir video uchun buferlangan kadrlar",
      "decoder_limit_hint": "0 GPU dekodlashni o'chiradi",
      "decoder_limit": "Bir vaqtdagi dekoderlar",
      "decode_manual": "Dekodlash sozlamasi: qo'lda",
      "heading": "Unumdorlik",
      "budgets_heading": "Resurs sarfi",
      "budget_cache_mib": "Ko'rish oynasi keshi",
      "budget_cache_mib_hint": "Video, animatsiya, miniatyuralar va ovoz to'lqinlari",
      "budget_gpu_buffer_mib": "GPU bufer chegarasi",
      "budget_gpu_buffer_mib_hint": "Faqat kadr uzatish uchun; boshqa VRAM sarfi kirmaydi",
      "budget_legacy": "Eski sozlamalar ishlatilmoqda. Chegarani o'zgartirsangiz, umumiy taqsimotga o'tiladi.",
      "restore_defaults": "Standart sozlamalarni tiklash",
      "save_failed": "Saqlab bo'lmadi. Bu o'zgarish kuchga kirmadi.",
      "retry_save": "Qayta saqlash",
      "activation": "Keshlar asta-sekin bo'shatiladi; ishlov o'zgarishlari yangi vazifalar va dekoder seanslariga qo'llanadi.",
      "details_heading": "Resurs sarfi tafsilotlari",
      "resources_unavailable": "Resurs holati vaqtincha mavjud emas.",
      "system_memory": "Tizim xotirasi: {{memory}} GiB",
      "budget_gpu_usage": "Umumiy tekstura uzatish buferlari: {{used}} / {{limit}} MiB",
      "allocation_cache_hint": "Asosiy kesh ulushlari (ishlatilmagan sig'im bo'lishiladi)",
      "cache_usage": "Taxminiy kesh: {{used}} / {{limit}} MiB (grafik xotiradagi keshlar ham kiradi)",
      "allocation_decode_count": "Bir vaqtdagi dekoderlar chegarasi",
      "allocation_capacity": "Joriy dekodlash piksel chegarasi",
      "decode_legacy": "Dekodlash sozlamasi: eski",
      "decode_tested": "Dekodlash sozlamasi: kompyuter sinovi",
      "decode_baseline": "Dekodlash sozlamasi: standart, bu kompyuterda sinalmagan",
      "test_heading": "Ushbu kompyuterni sinash (tajribaviy)",
      "test_scope": "Bir vaqtda bir nechta H.264 4K/60 videoni o'ynatishni sinash.",
      "test_start": "Sinovni boshlash",
      "test_cancel": "Sinovni bekor qilish",
      "test_apply": "Tavsiyani saqlash",
      "test_applied": "Tavsiya saqlandi",
      "test_progress": "Sinanmoqda… {{count}}/8 yuklama o'lchandi",
      "test_preparing": "Sinov mediasi tayyorlanmoqda… Birinchi marta bir necha daqiqa olishi mumkin.",
      "test_complete": "O'tdi: {{count}} tagacha 4K video.",
      "test_conservative": "Bitta video maqsadiga erishilmadi. Faqat ehtiyotkor tavsiya.",
      "test_failed": "Sinov muvaffaqiyatsiz. Qayta urining.",
      "test_cancelled": "Sinov bekor qilindi.",
      "test_windows": "Sinov hozircha faqat Windows'da ishlaydi.",
      "test_missing": "Ushbu o'rnatmada FFmpeg yoki FFprobe yo'q.",
      "test_record": "{{date}} · v{{version}} · {{count}} ta video o'tdi",
      "test_record_conservative": "{{date}} · v{{version}} · Ehtiyotkor tavsiya",
      "test_record_budgets": "Kesh {{cache}} MiB · Umumiy tekstura uzatish buferlari {{gpu}} MiB",
      "test_stale": "Qurilma yoki dastur o'zgargan. Yangi sinov o'tkazing.",
      "restore_tested": "Sinov profilini qo'llash",
      "clear_test": "Sinov yozuvini tozalash",
      "preview_gpu_pool_slots": "Har bir video uchun umumiy buferlar",
      "frame_ring_mib": "Video kadr keshi",
      "motif_cache_mib": "Animatsiya kadr keshi",
      "filmstrip_cache_mib": "Video miniatyura keshi",
      "waveform_cache_mib": "Ovoz to'lqini keshi",
      "unit_frames": "kadr",
      "unit_videos": "video",
      "unit_megapixels": "megapiksel"
  },
  retime: {
    "title": "Vaqtni o'zgartirish",
    "apply_selection": "Tanlangan barcha {{count}} ta klipga qo'llash",
    "mixed": "Tanlangan kliplarning tezligi yoki davomiyligi har xil. Qiymat kiritsangiz, u har bir tanlangan klipga qo'llanadi.",
    "refused": "{{reason}}",
    "details": {
      "collision": "«{{clip}}» «{{blocking}}» bilan ustma-ust tushadi. Davomiylikni qisqartiring yoki tezlikni oshiring.",
      "collision_limits": "«{{clip}}» «{{blocking}}» bilan ustma-ust tushadi. Eng uzun davomiylik: {{duration}}; eng past tezlik: ≈{{rate}}×.",
      "transition": "Bu o'zgarish «{{transition}}» o'tishini buzadi. Uning davomiyligi va qo'shni kliplar o'zgarmasligi kerak."
    },
    "pitch_scope_one": "Tanlangan {{count}} ta ovoz yoki Guruh klipiga qo'llanadi.",
    "pitch_scope_other": "Tanlangan {{count}} ta ovoz yoki Guruh klipiga qo'llanadi.",
    "conflicts": {
      "EmptyTargets": "Kamida bitta klipni tanlang.",
      "LayerMissing": "Tanlangan klip endi mavjud emas.",
      "Locked": "Tanlangan klip va uning yo'lagini qulfdan chiqaring.",
      "UnsupportedContent": "Video, ovoz, animatsiyali rasm, Motif yoki Guruhlarni tanlang.",
      "NestedTargets": "Yoki Guruhni, yoki uning ichidagilarini tanlang.",
      "InvalidSnapshot": "Klip vaqtlari noto'g'ri.",
      "InvalidTarget": "Musbat tezlik yoki davomiylik kiriting.",
      "Numeric": "So'ralgan vaqt qo'llab-quvvatlanadigan aniqlikdan oshib ketadi.",
      "DurationTooShort": "Davomiylik kamida bitta kadr yoki ovoz namunasiga teng bo'lishi kerak.",
      "Transition": "Bu o'zgarish mavjud o'tishni buzadi.",
      "Collision": "Yangi davomiylik boshqa klip bilan ustma-ust tushadi. Uni qisqartiring yoki tezlikni oshiring."
    },
    "rate": "Tezlik",
    "duration": "Maqsadli davomiylik",
    "reset": "1× ga qaytarish",
    "pitch": "Ovoz balandligini (tonini) saqlash",
    "hint": "Tezlikni o'zgartirib davomiylikni o'zgartiring, tarkib oralig'i saqlanadi."
  },
  crop: { title: "Kesib olish", edit: "Ko'rish oynasida kesib olish", done: "Kesib olishni tugatish (Enter / Esc)", reset: "Kesib olishni bekor qilish", unavailable: "Kesib olish uchun ko'rish oynasida qulflanmagan, ko'rinadigan video klipni tanlang" },
  layer_scale: { menu_title: "Ko'rish oynasi amallari", fit: "Kadrga sig'dirish", fill: "Kadrni to'ldirish", original: "Asl o'lchamga qaytarish" },
  fonts: {
    app_default: "Ilova standarti (Liberation Sans / Noto Sans SC)",
    loading: "O'rnatilgan shriftlar yuklanmoqda…",
    load_failed: "O'rnatilgan shriftlarni yuklab bo'lmadi.",
    retry: "Qayta urinish",
  },
  text_correction: {
    title: "Matnni tuzatish", script: "Namuna matn", placeholder: "Namuna matningizni shu yerga qo'ying…",
    saved_with_project: "Loyihangiz bilan saqlanadi. Tuzatish subtitrlarni qo'lyozmadagi qator va gap oxirlari bo'yicha bo'ladi yoki birlashtiradi; so'z vaqtlari bo'lmasa, kesish joylari taxminan aniqlanadi.",
    scope: "Qayerga qo'llash", selected: "Tanlangan subtitrlar ({{count}})", all: "Ushbu kompozitsiyadagi barcha subtitrlar ({{count}})",
    apply_selected: "Tanlangan {{count}} ta subtitrni tuzatish", apply_all: "Barcha {{count}} ta subtitrni tuzatish",
    clear: "Matnni tozalash", close: "Yopish", running: "Tuzatilmoqda…", locked: "Matnni tuzatish uchun subtitrlarni qulfdan chiqaring.",
    completed: "Matn tuzatildi ({{count}} ta subtitr o'zgardi)",
  },
  models: {
    current_label: "Joriy model", none_selected: "Yo'q", none_active: "Model tanlanmagan",
    switch_hint: "Avtomatik almashtirish uchun modelni tanlang. Yuklab olish va birinchi sozlash qo'shimcha qadam talab qiladi.",
    needs_download: "Yuklab olish kerak…", needs_configuration: "Sozlash kerak…", setup_model: "{{name}} ni sozlash",
    custom: "Maxsus", add_model: "Maxsus model qo'shish…", edit_model: "Model sozlamalari…",
    custom_type_hint: "Modelingiz yoki xizmatingizga mos adapterni tanlang.",
    add_use: "Qo'shish va ishlatish", configure_use: "Sozlash va ishlatish",
    files_missing: "Mahalliy fayllar yo'q. Model sozlamalarini tekshiring.",
    local: "Mahalliy", online: "Onlayn", online_model: "Onlayn model",
    current: "Ishlatilmoqda", ready: "Tayyor", not_verified: "Tekshirilmagan", not_downloaded: "Yuklab olinmagan",
    downloading: "Yuklab olish tayyorlanmoqda…", verifying: "Model tekshirilmoqda…", error: "Tayyorlab bo'lmadi",
    needs_components: "Windows ishga tushirish komponenti kerak", installing_components: "Ishga tushirish komponentlari o'rnatilmoqda…",
    install_components: "Ishga tushirish komponentlarini o'rnatish", download_size: "Yuklab olish: {{size}}", unsupported: "Bu platformada avtomatik yuklab olish mavjud emas. Mos mahalliy fayllar bilan maxsus model qo'shing.",
    cpu_state: "CPU'da tekshirilgan · Ishlov sekinroq bo'lishi mumkin", online_notice: "Saqlash yoki ishlatish kichik sinov so'rovini yuboradi, bu pullik bo'lishi mumkin. Ishlov berishda media shu xizmatga yuboriladi.",
    download_use: "Yuklab olish va ishlatish", retry: "Qayta urinish", cancel: "Bekor qilish",
    name: "Maxsus model nomi",
    device_auto: "Avtomatik (bo'sh); cpu yoki qurilma identifikatori", restore: "Avtomatik sozlamani tiklash",
    custom_identity: "Ichki modelning fayllari yoki manzilini o'zgartirish nomlangan maxsus model yaratadi. Ichki sozlama saqlanib qoladi.",
    remove: "Maxsus yozuvni o'chirish", confirm_remove: "O'chirishni tasdiqlash",
    empty_hint: "Kerak bo'lganda ro'yxatdan model tanlang. Modellar faqat siz tasdiqlaganingizdan keyin yuklab olinadi.",
    edit: "Tahrirlash",
    editor_hint: "Sozlama saqlashdan oldin tekshiriladi. Bu oynani yopsangiz ham tayyorlash davom etadi.",
    save: "Sozlamalarni saqlash",
    add_only: "Tanlamasdan qo'shish",
    download_save: "Yuklab olish va saqlash",
    details: "Jarayonni ko'rish",
    clear_downloads: "Yuklanmalarni tozalash",
    clear_hint: "Bu modelning ilova boshqaradigan yuklanmalarini o'chiradi. Boshqa modellarga kerak umumiy fayllar va o'zingiz tanlagan fayllar saqlanadi.",
    remove_hint: "Bu maxsus sozlamani va saqlangan API kalitini o'chiradi. Mahalliy fayllar saqlanadi.",
    active_remove_hint: "Bu model hozir tanlangan. O'chirilgandan keyin tanlov «Yo'q» bo'ladi.",
    analysis_options: "Video tahlili sozlamalari",
    openai_speech_hint: "OpenAI Whisper rasmiy OpenAI xizmati va o'zgarmas whisper-1 modelidan foydalanadi. Faqat API kaliti kerak; maxsus server manzillari qo'llab-quvvatlanmaydi.",
    vision_local_hint: "Mos llama-mtmd dasturi, model GGUF va unga mos mmproj proyektoridan foydalaning. Ikkala model fayli ham kerak.",
    funasr_hint: "sherpa-onnx dasturi, mos ONNX modeli va uning tokens faylidan foydalaning.",
    whisper_hint: "whisper.cpp dasturi va mos Whisper model faylidan foydalaning.",
    key_optional: "Autentifikatsiyasiz xizmatlar uchun ixtiyoriy",
    model_optional: "Ixtiyoriy — ko'pchilik transkripsiya serverlari bitta model bilan ishlaydi",
    speech_endpoint_hint: "Har qanday OpenAI-mos transkripsiya serveri. whisper.cpp uchun whisper-server ni --inference-path /v1/audio/transcriptions bilan ishga tushiring yoki uning /inference URL manzilini kiriting.",
    endpoint_timeout: "So'rov kutish vaqti (s)",
    endpoint_timeout_hint: "Avtomatik uchun bo'sh qoldiring: kutish har bir so'rov hajmiga qarab oshadi. Sekin o'z serveringiz bo'lsa, oshiring.",
    endpoint_frames_per_request: "Har so'rovdagi kadrlar",
    endpoint_concurrency: "Bir vaqtdagi so'rovlar",
    endpoint_batching_hint: "Bo'sh qoldirilsa: 16 kadr, bir vaqtda bitta so'rov. Uzun klip siz tanlagan namuna olish tezligida bir nechta so'rov bo'lib yuboriladi; kattaroq kontekstli model har safar ko'proq kadr qabul qiladi, paketli server esa bir nechtasini birdaniga oladi.",
  },
  motion_path: {
    conversion_calculating:"Ko'rish hisoblanmoqda… Tahrirlashni davom ettirishingiz yoki bekor qilishingiz mumkin.",
    conversion_ready:"Ko'rish yangilandi. Bu o'zgartirishni saqlash uchun qo'llang.",
    conversion_limited:"Ko'rish yangilandi, lekin maqsadli xatoga erishilmadi.",
    conversion_applying:"O'zgartirish qo'llanmoqda…",
    conversion_unavailable:"O'zgartirishni hisoblash uchun kompozitsiyani oching.",
    conversion_failed:"Ko'rishni hisoblab bo'lmadi. Sozlamalarni o'zgartiring yoki qayta urinish uchun o'zgartirishni qayta oching.",
    conversion_apply_failed:"O'zgartirishni qo'llab bo'lmadi. Ko'rish saqlanib qoldi; qayta qo'llab ko'ring.",
    conversion_tolerance_error:"Maqsadli xatoga erishilmadi. Oraliqni qisqartiring yoki maqsadli xatoni oshiring.",
    conversion_details:"Bu o'zgartirish haqida",
    conversion_range_note:"Faqat shu oraliqdagi harakat saqlanadi; undan tashqarida joylashuv chekka nuqtalarda qotib turadi.",
    node:"Yo'l nuqtasi", choose_node:"Nuqtani tanlang…", node_progress:"{{index}}-nuqta · {{progress}}",
    arrive_here:"Nuqtaga joriy vaqtda yetish",
    arrival_caption:"O'ynatish ko'rsatkichida jarayon kalit kadrini qo'ying.",
    insert_caption:"Nuqta qo'shish uchun yo'lni ikki marta bosing.",
    arrival_hint:"O'ynatish ko'rsatkichida jarayon kalit kadrini qo'shadi yoki yangilaydi. Mavjud kalitlar saqlanadi.",
    arrival_outside:"Yetib kelish kalit kadrini qo'yish uchun o'ynatish ko'rsatkichini shu klip ichiga suring.",
    // `mode_xy` / `mode_path` are the position mode switcher's segments, and
    // `mode_xy` doubles as the caption on the X|Y value row it governs.
    mode_xy:'XY', mode_path:"Yo'l",
    path:"Yo'l", nodes:"{{count}} ta nuqta", node_of:"Nuqta {{index}} / {{count}}",
    node_mode:"Fazoviy nuqta", select_node:"Tahrirlash uchun yo'ldagi nuqtani tanlang", mode_corner:"Burchak", mode_smooth:"Silliq", mode_auto:"Avto silliq", insert:"Nuqtadan keyin qo'shish",
    insert_hint:"Shaklini o'zgartirmasdan qo'shish uchun yo'lni ikki marta bosing. Qo'shni Avto nuqtalar dastaklarini saqlash uchun Silliq bo'ladi.",
    start_frame:"Boshlanish kadri (mahalliy)", end_frame:"Tugash kadri (kiritilgan)", every_frames:"Eng katta kadr oralig'i", samples_used:"har bir xususiyatga kalit", range_error:"Oraliq shu klip ichida bo'lishi kerak.",
    tolerance:"Maqsadli xato (piksel)", nodes_used:"{{count}} ta yo'l nuqtasi",
    jump_error:"Bu oraliqda joylashuv birdan sakraydi. Alohida oraliqlarni o'zgartiring yoki joriy rejimni saqlang.",
    conversion_method:"O'zgartirish usuli", editable_curves:"Tahrirlanadigan egri chiziqlar", frame_bake:"Kadrma-kadr yozish",
    axis_keys:"X: {{x}} ta kalit · Y: {{y}} ta kalit",
    conversion_range_error:"Mikrosekundga mos kadr tezligi bilan to'g'ri oraliq tanlang.",
    conversion_options_error:"Kamida 0.05 piksel maqsad va musbat butun kadr oralig'idan foydalaning.",
    conversion_capacity_error:"O'zgartirish har bir xususiyat uchun 4096 kalitdan yoki mavjud xotiradan oshib ketadi. Oraliqni qisqartiring yoki maqsadli xatoni yumshating.",
    node_limit:"128 nuqta chegarasi maqsadga yetolmaydi. Faqat ko'rish: oraliqni qisqartiring yoki maqsadni yumshating.",
    key_limit:"Har bir xususiyat uchun 4096 kalit chegarasi maqsadga yetolmaydi. Faqat ko'rish: oraliqni qisqartiring yoki maqsadni yumshating.",
    frame_grid:"Joriy kadr to'ri maqsadga yetolmaydi. Faqat ko'rish: maqsadni yumshating yoki joriy rejimni saqlang.",
    create:"Harakat yo'lini yaratish", edit:"Yo'lni tahrirlash", show:"Traektoriyani ko'rsatish", done:"Tayyor",
    add:"Nuqta qo'shish", curve:"Chiziq / egri", remove:"Nuqtani o'chirish",
    anchor:"Belgilangan tayanch nuqta yo'l bo'ylab yuradi. Dastaklarini tahrirlash uchun nuqtani tanlang.",
    corner:"Belgilangan tayanch nuqta yo'l bo'ylab yuradi.",
    to_path:"XY ni yo'lga aylantirish…", to_xy:"XY ga aylantirish…", preview:"O'zgartirishni ko'rish", apply:"O'zgartirishni qo'llash", cancel:"Bekor qilish",
    error:"O'lchangan joylashuv xatosi: {{error}} px ({{count}} ta tekshiruv)",
    conversion_note:"Faqat tanlangan oraliq saqlanadi; undan tashqarida natija qotib turadi. Tahrirlanadigan egri chiziqlar siyrak kalitlardan foydalanadi va o'zgarmas o'qlarni qimirlatmaydi. Kadrma-kadr yozish muntazam oraliqdagi kalitlarni saqlaydi va kerak bo'lsa ko'proq qo'shadi. Xato kadrlarda, chorak kadrlarda va kalit chegaralarida o'lchanadi, uzluksiz kafolatlanmaydi. Joylashuvning birdan sakrashlari rad etiladi.",
  },
  app: {
    title: "Lahza Studio",
    core_status: "yadro: {{status}}",
    window_title: "Lahza Studio — {{name}}",
  },
  splash: {
    starting: "Tizim tekshiruvlari boshlanmoqda…",
    checking: "Tekshirilmoqda: {{items}}",
    check_separator: " · ",
    resolving_project: "Ishga tushirish loyihasi tekshirilmoqda…",
    ready: "Tayyor",
    check: {
      evaluation_runtime: "hisoblash dvigateli",
      motif_capture_runtime: "Motif yozib olish muhiti",
      motif_catalog: "Motif katalogi",
      motif_catalog_listener: "Motif o'zgarishlarini kuzatuvchi",
    },
  },
  keyframe: {
    stopwatch_enable: "Bu xususiyatni animatsiya qilish (o'ynatish ko'rsatkichida kalit kadr qo'shish)",
    stopwatch_disable: "Animatsiyani to'xtatish — barcha kalit kadrlarni o'chiradi (o'ynatish ko'rsatkichidagi qiymat qoladi; bekor qilish mumkin)",
    stopwatch_offscreen: "Kalit kadr qo'yish uchun o'ynatish ko'rsatkichini klip ustiga suring",
    // The stopwatch's accessible name. A merged axis row puts two of them
    // side by side with no caption, so the name has to carry the param.
    stopwatch_param: "{{param}} — {{action}}",
    nav_prev: "Oldingi kalit kadr",
    nav_set: "O'ynatish ko'rsatkichida kalit kadr qo'shish yoki o'chirish",
    nav_next: "Keyingi kalit kadr",
    interp_hold: "Ushlab turish",
    interp_linear: "Chiziqli",
    interp_ease_in: "Sekin boshlanish",
    interp_ease_out: "Sekin tugash",
    interp_ease: "Silliq",
    interp_ease_in_out: "Sekin boshlanish va tugash",
    // Preset gallery labels — one per canonical-table id (keyframe.interp_<id>,
    // see src/shared/easing.ts), family style matching "Ease In/Out/In-Out".
    interp_ease_in_sine: "Sine In",
    interp_ease_out_sine: "Sine Out",
    interp_ease_in_out_sine: "Sine In-Out",
    interp_ease_in_quad: "Quad In",
    interp_ease_out_quad: "Quad Out",
    interp_ease_in_out_quad: "Quad In-Out",
    interp_ease_in_cubic: "Cubic In",
    interp_ease_out_cubic: "Cubic Out",
    interp_ease_in_out_cubic: "Cubic In-Out",
    interp_ease_in_quart: "Quart In",
    interp_ease_out_quart: "Quart Out",
    interp_ease_in_out_quart: "Quart In-Out",
    interp_ease_in_quint: "Quint In",
    interp_ease_out_quint: "Quint Out",
    interp_ease_in_out_quint: "Quint In-Out",
    interp_ease_in_expo: "Expo In",
    interp_ease_out_expo: "Expo Out",
    interp_ease_in_out_expo: "Expo In-Out",
    interp_ease_in_circ: "Circ In",
    interp_ease_out_circ: "Circ Out",
    interp_ease_in_out_circ: "Circ In-Out",
    interp_ease_in_back: "Back In",
    interp_ease_out_back: "Back Out",
    interp_ease_in_out_back: "Back In-Out",
    interp_ease_in_elastic: "Elastic In",
    interp_ease_out_elastic: "Elastic Out",
    interp_ease_in_out_elastic: "Elastic In-Out",
    interp_ease_in_bounce: "Bounce In",
    interp_ease_out_bounce: "Bounce Out",
    interp_ease_in_out_bounce: "Bounce In-Out",
    elastic_amplitude: "Amplituda",
    elastic_period: "Davr",
    procedural_badge: "Protsedurali",
    smooth: "Silliq",
    easing_library: "Silliqlash kutubxonasi…",
    // Tangent-handle context menu: the key's continuity.
    continuity_smooth: "Silliq",
    continuity_broken: "Uzilgan",
    // Extrapolation submenus on a track's first / last key; the five modes
    // (keyframe.extrapolate_<id>, see renderer/keyframe/curve.ts).
    extrapolate_before: "Oldindan davom ettirish",
    extrapolate_after: "Keyin davom ettirish",
    extrapolate_hold: "Ushlab turish",
    extrapolate_loop: "Takrorlash",
    extrapolate_ping_pong: "Oldinga-orqaga",
    extrapolate_offset: "Siljitish",
    extrapolate_continue: "Davom ettirish",
    // Gallery row labels — one per canonical-table family (keyframe.family_<x>,
    // derived from the preset id's last segment; "classic" heads the table).
    family_classic: "Asosiy",
    family_sine: "Sine",
    family_quad: "Quad",
    family_cubic: "Cubic",
    family_quart: "Quart",
    family_quint: "Quint",
    family_expo: "Expo",
    family_circ: "Circ",
    family_back: "Back",
    family_elastic: "Elastic",
    family_bounce: "Bounce",
  },
  startup: {
    subtitle: "Ochish uchun loyihani tanlang yoki yangisini yarating.",
    new_project: "Yangi loyiha",
    open_project: "Loyihani ochish…",
    open_dialog_title: "Lahza Studio loyiha papkasini ochish",
    recent_heading: "So'nggilar",
    recent_loading: "Yuklanmoqda…",
    recent_empty: "Hali so'nggi loyihalar yo'q.",
    recent_remove_hint: "Ro'yxatdan olib tashlash",
    recent_show_all: "Hammasini ko'rsatish ({{count}})",
    recent_show_less: "Kamroq ko'rsatish",
    recent_open_failed: "Loyihani ochib bo'lmadi: {{detail}}",
    recents_load_failed: "So'nggi loyihalar ro'yxatini yuklab bo'lmadi: {{detail}}",
    not_project_folder:
      "Bu papka Lahza Studio loyihasi emas. Lahza Studio yaratgan papkani tanlang yoki yangi loyiha boshlang.",
    project_folder_missing:
      "Bu loyiha papkasi endi mavjud emas — u ko'chirilgan, qayta nomlangan yoki o'chirilgan bo'lishi mumkin. U so'nggilar ro'yxatidan olib tashlandi.",
    // States the mismatch and stops. "Update WeftCut" is a guess that happens to
    // be wrong for the file this fires on most often — a project left behind by
    // a different build of this same repo.
    project_schema_too_new:
      "Bu loyiha Lahza Studio'ning boshqa versiyasida yozilgan (loyiha formati v{{found}}); bu versiya v{{supported}} ni o'qiydi.",
    project_schema_unreadable:
      "Bu papkadagi project.json da ushbu versiya taniydigan loyiha formati versiyasi ko'rsatilmagan, shuning uchun uni ochib bo'lmaydi.",
    project_file_unreadable:
      "Bu loyihaning project.json faylini o'qib bo'lmadi: {{detail}}",
    project_invalid:
      "Loyiha tarkibi tekshiruvdan o'tmadi — fayl shikastlangan yoki qo'lda tahrirlangan bo'lishi mumkin.",
    time_just_now: "hozirgina",
    time_minutes_ago_one: "{{count}} daqiqa oldin",
    time_minutes_ago_other: "{{count}} daqiqa oldin",
    time_hours_ago_one: "{{count}} soat oldin",
    time_hours_ago_other: "{{count}} soat oldin",
    time_days_ago_one: "{{count}} kun oldin",
    time_days_ago_other: "{{count}} kun oldin",
  },
  // Canvas vocabulary shared by the New Project dialog and Settings > Canvas.
  // Both surfaces author the same two values off the same lists
  // (`startup/canvasPresets.ts`), so the wording lives in one place too.
  canvas: {
    // Parenthetical after a rate — what a newcomer needs in order to pick 25
    // over 30, at the one moment the choice is still freely reversible.
    fps_note: {
      film: "kino",
      pal: "PAL",
      ntsc: "NTSC",
      ntsc_film: "NTSC kino",
    },
    size_range: "Kenglik va balandlik {{min}} dan {{max}} gacha bo'lishi kerak.",
    size_odd: "Kenglik va balandlik butun juft son bo'lishi kerak.",
    size_too_many_pixels: "Kanvasning umumiy maydoni 8K (7680 × 4320) dan oshmasligi kerak.",
  },
  new_project: {
    title: "Yangi loyiha",
    name: "Loyiha nomi",
    name_placeholder: "masalan, Mening hujjatli filmim",
    parent_folder: "Saqlash joyi",
    parent_folder_placeholder: "Asosiy papkani tanlang…",
    choose_folder: "Tanlash…",
    pick_parent_title: "Yangi loyiha uchun asosiy papkani tanlang",
    validation_empty: "Loyiha nomi kiritilishi shart.",
    validation_whitespace: "Loyiha nomi bo'sh joy bilan boshlanmasligi yoki tugamasligi kerak.",
    validation_invalid_chars:
      "Loyiha nomida bu belgilar bo'lmasligi kerak: \\ / : * ? \" < > |",
    validation_trailing_dot: "Loyiha nomi nuqta bilan tugamasligi kerak.",
    validation_reserved: "Bu nom tizim tomonidan band — boshqasini tanlang.",
    resolution: "O'lcham (piksel)",
    resolution_custom: "Maxsus",
    custom_size: "Maxsus o'lcham",
    width: "Kenglik",
    height: "Balandlik",
    frame_rate: "Kadr tezligi",
    create: "Yaratish",
    creating: "Yaratilmoqda…",
    cancel: "Bekor qilish",
    folder_exists:
      "Bu nomli papka allaqachon bor. Boshqa nom yoki boshqa joy tanlang.",
    invalid_preset: "Bu kanvas o'lchami yoki kadr tezligi noto'g'ri — boshqasini tanlang.",
    create_failed: "Loyihani yaratib bo'lmadi: {{detail}}",
  },
  project: {
    canvas: "{{width}}×{{height}} · {{fps}}",
    fps_simple: "{{fps}}fps",
    fps_rational: "{{fps}}fps",
    duration: "{{value}}",
    derivatives_pending_one: "{{count}} ta yordamchi fayl yaratilmoqda…",
    derivatives_pending_other: "{{count}} ta yordamchi fayl yaratilmoqda…",
    derivatives_pending: "{{count}} ta yordamchi fayl yaratilmoqda…",
    derivatives_pending_hint:
      "Qo'shilgan media uchun fonda yengil nusxa (proxy) / miniatyura / ovoz to'lqini tayyorlanmoqda. Bu vaqtda muharrirdan bemalol foydalanishingiz mumkin.",
  },
  menu: {
    file: "Fayl",
    edit: "Tahrirlash",
    insert: "Qo'shish",
    view: "Ko'rinish",
    help: "Yordam",
  },
  dev: {
    menu: "Dev",
    performance_monitor: "Unumdorlik monitori",
  },
  updates: {
    title: "Yangilanishlarni tekshirish",
    button: "Yangilanish mavjud",
    available_manual: "{{version}} versiyasi mavjud. U faqat «Yuklab olish va o'rnatish»ni tanlaganingizda yuklanadi; so'ng ishingizni saqlab, o'rnatish uchun ilovani qayta ishga tushiring.",
    download_install: "Yuklab olish va o'rnatish",
    downloading_action: "Yuklab olinmoqda…",
    'download-failed': "Yangilanishni yuklab bo'lmadi. Ilova qayta ishga tushmadi. Internet aloqasi va diskdagi bo'sh joyni tekshirib, qayta urinib ko'ring.",
    available: "Yangi versiya mavjud",
    version: "{{version}} yuklab olindi va tayyor.",
    restart: "Yangilash va ilovani qayta ishga tushirish",
    later: "Keyinroq",
    restarting: "Saqlanmoqda va qayta ishga tushirilmoqda…",
    ready_auto: "Ishni davom ettirish uchun «Keyinroq»ni tanlang. Yangilanish ilovani yopganingizda o'rnatiladi, ilova qayta ochilmaydi.",
    ready_manual: "Ishni davom ettirish uchun «Keyinroq»ni tanlang. Yangilanishga Yordam menyusidan yoki boshlang'ich ekrandagi yoxud muharrir holat qatoridagi yangilanish belgisidan qaytishingiz mumkin.",
    'not-ready': "Yangilanish hali tayyor emas. Yuklab olish tugashini kuting.",
    'save-failed': "Ish holatini saqlab bo'lmadi. Ilova qayta ishga tushmadi. Diskdagi bo'sh joy va loyiha ruxsatlarini tekshirib, qayta urinib ko'ring.",
    disabled: "Bu versiyada avtomatik yangilanish mavjud emas. Yangi versiyalarni loyiha sahifasidan yuklab oling.",
    idle: "Yangilanishlarni tekshirishga tayyor.",
    checking: "Yangilanishlar tekshirilmoqda…",
    current: "Sizda eng so'nggi versiya o'rnatilgan.",
    downloading: "{{version}} yuklab olinmoqda… {{percent}}%",
    error: "Yangilanishni tekshirib yoki yuklab bo'lmadi. Qayta urinib ko'ring yoki uni relizlar sahifasidan yuklab oling.",
    releases: "Relizlarni ko'rish",
    skip: "Bu versiyani o'tkazib yuborish",
    indicator_available: "{{version}} mavjud",
    indicator_ready: "{{version}} o'rnatishga tayyor",
    indicator_error: "{{version}} ni yuklab bo'lmadi",
  },
  diagnostics: {
    title: "Muammo haqida xabar berish",
    previous_title: "Oldingi seans to'g'ri yakunlanmagan",
    previous_description: "Lahza Studio tugallanmagan seans yoki jarayon nosozligini aniqladi. Bu majburiy yopish yoki elektr uzilishidan keyin ham bo'lishi mumkin. Bu haqda GitHub'da xabar berib, muammoni tekshirishga yordam bera olasiz.",
    description: "Diagnostika ZIP faylini eksport qiling, tarkibini ko'rib chiqing, so'ng uni GitHub'dagi muammo (issue) sahifasiga biriktiring. GitHub ochilganda qoralama tayyorlanadi; uni qachon yuborishni o'zingiz hal qilasiz.",
    privacy: "Ilova va tizim versiyalari, CPU / xotira / GPU ma'lumotlari, so'nggi resurs o'lchovlari va maxfiy qismlari yashirilgan jurnallar kiradi. Loyiha fayllari yoki media qo'shilmaydi. Xato matnlarida baribir shaxsiy ma'lumot bo'lishi mumkin. GitHub muammolari va biriktirmalari hammaga ochiq; hech narsa avtomatik yuklanmaydi.",
    export: "Diagnostika to'plamini eksport qilish…",
    github: "GitHub'da muammo ochish",
    reveal: "Eksport qilingan faylni ko'rsatish",
    later: "Hozir emas",
    saved: "{{path}} ga saqlandi. ZIP faylni ko'rib chiqing va biriktirish uchun uni GitHub'dagi muammo sahifasiga sudrab tashlang.",
    unavailable: "Diagnostika xotirasi mavjud emas. Muammo haqida baribir GitHub'da xabar berishingiz mumkin.",
    error: "Amalni bajarib bo'lmadi. Qayta urinib ko'ring.",
  },
  help: {
    check_updates: "Yangilanishlarni tekshirish…",
    report_issue: "Muammo haqida xabar berish…",
    about: "Lahza Studio haqida",
    version: "Versiya {{version}}",
    developed_by: "UncleChair'ning WeftCut (MIT) dasturi asosida · O'zbekcha dvigatel: Lahza",
    license_mit: "Litsenziya: WeftCut <mit>MIT</mit> litsenziyasi ostida tarqatiladi.",
    third_party:
      "Uchinchi tomon komponentlarining o'z litsenziyalari bor: <notices>THIRD-PARTY-NOTICES.md</notices>.",
    copy_version: "Versiya ma'lumotidan nusxa olish",
    copied: "Nusxa olindi",
    project_link: "Loyiha sahifasi",
  },
  view: {
    display_mode_heading: "Yo'laklarni ko'rsatish",
    panels_heading: "Panellar",
    display_ab_roll: "A/B Roll",
    display_all_tracks: "Barcha yo'laklar",
    follow_playhead: "Taymlaynni avtomatik aylantirish",
    show_markers: "Belgilarni ko'rsatish",
    show_safe_areas: "Xavfsiz hududlarni ko'rsatish",
    review_overlay: "Tekshiruv qatlami",
    close_active_panel: "Faol panelni yopish",
    reset_workspace: "Ish maydonini tiklash",
    workspaces_heading: "Ish maydonlari",
    workspace_editing: "Standart joylashuv",
    save_workspace: "Ish maydonini saqlash",
    save_workspace_as: "Yangi ish maydoni sifatida saqlash…",
    rename_workspace: "Ish maydonini qayta nomlash…",
    delete_workspace: "Ish maydonini o'chirish",
    enter_agent_mode: "AI yordamchi rejimiga o'tish",
  },
  quick_actions: {
    hand_tool_hint:
      "Qo'l vositasi: kattalashtirilgan ko'rish oynasini surish uchun sudrang. Sichqonchaning o'rta tugmasi istalgan vositada suradi, g'ildirak yoki trekpadda chimchilash esa kattalashtiradi. Esc tanlash vositasiga qaytaradi.",
    tools: "Vositalar",
    toggles: "Yoqish/o'chirish",
    edit: "Tahrirlash",
    range: "Boshi/Oxiri",
    markers: "Belgilar",
    resolution: "Ijro o'lchami",
    // The cycling button's three tooltips: current rung, then the rung a click
    // moves to. Both halves are load-bearing here in a way they are not for the
    // two-state toggles below — that button's glyph and pressed border already
    // say which of two states it is in, whereas three rungs mean the successor
    // is genuinely unguessable without being told.
    resolution_full_hint: "Ijro o'lchami: To'liq. 1/2 uchun bosing.",
    resolution_half_hint: "Ijro o'lchami: 1/2. 1/4 uchun bosing.",
    resolution_quarter_hint: "Ijro o'lchami: 1/4. To'liq uchun bosing.",
    // Shown on the disabled Clear button — says why it's disabled rather than
    // repeating the label the user can't act on.
    clear_range_empty: "Boshlanish/tugash nuqtalari belgilanmagan",
    // The Text tool's two tooltips. Armed or armable, the hint teaches the
    // gesture the icon alone cannot; disabled (an empty project has no canvas
    // to click), it names the remedy — `clear_range_empty`'s rule.
    text_tool_hint: "Matn vositasi: matn qo'shish uchun ko'rish oynasini bosing, tahrirlash uchun matnni bosing",
    text_tool_needs_layer: "Avval klip qo'shing yoki Qo'shish menyusidan matn kiriting",
    // The marker toggle's two-state hint: current state, then what a click does.
    // Both halves matter — the pressed border says WHICH state, not what
    // pressing again would get you.
    markers_shown_hint: "Taymlayn belgilari ko'rsatilmoqda. Yashirish uchun bosing.",
    markers_hidden_hint: "Taymlayn belgilari yashirilgan. Ko'rsatish uchun bosing.",
    // Same two-state shape for the three toggles that joined the section: the
    // pressed border says which state, the hint says what a click does.
    snap_on_hint: "Kliplarni yopishtirish yoqilgan. O'chirish uchun bosing.",
    snap_off_hint: "Kliplarni yopishtirish o'chirilgan. Yoqish uchun bosing.",
    review_overlay_on_hint: "Tekshiruv qatlami yoqilgan: izohlar va ko'rib chiqilmagan AI yordamchi o'zgarishlari taymlaynda ko'rinadi. Yashirish uchun bosing.",
    review_overlay_off_hint: "Tekshiruv qatlami o'chirilgan. Izohlar va ko'rib chiqilmagan AI yordamchi o'zgarishlarini taymlaynda ko'rsatish uchun bosing.",
    follow_on_hint: "Taymlaynni avtomatik aylantirish yoqilgan. O'chirish uchun bosing.",
    follow_off_hint: "Taymlaynni avtomatik aylantirish o'chirilgan. Yoqish uchun bosing.",
    safe_area_on_hint: "Xavfsiz hudud chiziqlari ko'rsatilmoqda. Yashirish uchun bosing.",
    safe_area_off_hint: "Xavfsiz hudud chiziqlari yashirilgan. Ko'rsatish uchun bosing.",
    link_override_on_hint: "Bog'lanishlar o'chirilgan — tahrirlar alohida kliplarga ta'sir qiladi. Bog'lanishlarni tiklash uchun bosing.",
    link_override_off_hint: "Bog'lanishlar yoqilgan. Alt'ni bosib turmasdan alohida kliplarni tahrirlash uchun bosing.",
    // Disabled-button reasons, the `clear_range_empty` rule: name the
    // precondition rather than restate a label that can't be acted on.
    link_selected: "Tanlangan kliplarni bog'lash",
    unlink_selected: "Tanlangan kliplarni ajratish",
    link_needs_two: "Bog'lash uchun ikki yoki undan ortiq bog'lanmagan klipni tanlang",
    link_mixed_selection: "Hammasi bog'lanmagan yoki hammasi bitta bog'lanishdagi kliplarni tanlang",
    // Group / Ungroup, same rule: a greyed button names the precondition. The
    // three not-plain reasons are separate strings because each names a
    // different field to reset (`timeline/groupEligibility.ts`).
    group_selected: "Tanlangan kliplarni guruhlash",
    group_needs_selection: "Guruhlash uchun bir yoki bir nechta klipni tanlang",
    group_locked: "Guruhlash uchun tanlangan kliplarni qulfdan chiqaring",
    ungroup_selected: "Guruhni tarqatish — guruh kliplarini joyiga qaytarish",
    ungroup_needs_one_group: "Guruhni tarqatish uchun aynan bitta guruh klipini tanlang",
    ungroup_locked: "Guruhni tarqatish uchun guruh klipini qulfdan chiqaring",
    ungroup_not_plain_transform:
      "Avval guruh transformatsiyasini tiklang — guruhni tarqatishda u ichidagi kliplarga o'tkazilmaydi",
    ungroup_not_plain_opacity:
      "Avval guruh shaffofligini 1 ga tiklang — guruhni tarqatishda u ichidagi kliplarga o'tkazilmaydi",
    ungroup_not_plain_time_map: "Guruhni tarqatishdan oldin guruh tezligini 1× ga tiklang.",
    ungroup_not_plain_effects:
      "Avval guruh effektlarini olib tashlang — guruhni tarqatishda ular ichidagi kliplarga o'tkazilmaydi",
    // Ripple delete. Only TWO reasons live here: the rest of them are refusals
    // the planner returns, and their sentences are the curated refusal copy
    // under `errors.ripple_*` — the same line the status bar shows when the
    // actor refuses for real, so there is no second wording to keep in step
    // (`timeline/rippleEligibility.ts`).
    ripple_needs_selection:
      "O'chirib, keyingi bo'shliqni yopish uchun kliplarni tanlang yoki yopish uchun bo'shliqni bosing",
    // Not a refusal but the precedence rule showing through: the key is about to
    // do the keyframe delete, so the row says so rather than pretending the
    // ripple is merely unavailable.
    ripple_keyframes:
      "Kalit kadrlar tanlangan — bu tugma ularni o'chiradi. Kliplarni siljitib o'chirish uchun kalit kadrlarni tanlovdan chiqaring",
    // Add to Group. Only the clip's context menu shows these, but they are the
    // same kind of sentence as the two above and drift if kept apart. Its shape
    // failures stay separate rather than collapsing the way Ungroup's do: the
    // destination and the members are two different things to go and select.
    add_to_group_needs_selection:
      "Qo'shiladigan kliplarni va ular qo'shiladigan guruh klipini tanlang",
    add_to_group_needs_one_group: "Qo'shish uchun aynan bitta guruh klipini tanlang",
    add_to_group_needs_member:
      "Guruh klipi bilan birga qo'shiladigan kliplarni ham tanlang",
    add_to_group_locked: "Guruhga qo'shilayotgan kliplarni qulfdan chiqaring",
    add_to_group_retimed: "Tarkibini o'zgartirishdan oldin maqsad guruh tezligini 1× ga tiklang.",
    add_to_group_starts_before_group:
      "Bu klip guruhdan oldin boshlanadi — avval uni keyinroqqa suring",
    // Move to…. The first three explain the greyed submenu TRIGGER — what to
    // go and fix about the selection — and the rest explain one greyed
    // destination row, where the answer is to pick a different one. A
    // destination row names itself, so none of these names one (CONTEXT.md's
    // Composition entry says why the word stays out of UI copy).
    move_to_composition_needs_selection: "Ko'chiriladigan kliplarni tanlang",
    move_to_composition_locked: "Ko'chirilayotgan kliplarni qulfdan chiqaring",
    move_to_composition_no_destination:
      "Bu kliplarni boshqa joyga ko'chirib bo'lmaydi",
    move_to_composition_already_there: "Bu kliplar allaqachon shu yerda",
    move_to_composition_cycle:
      "Tanlangan guruh uni allaqachon o'z ichiga oladi — guruh uning ichiga joylasha olmaydi",
    move_to_composition_offscreen:
      "O'ynatish ko'rsatkichida ekranda ko'rinmaydi — kliplar uning boshiga joylashadi",
    // Transcribe. The clip menu is the only surface that shows these, but
    // they are the same kind of sentence as the ones above and drift if kept
    // apart. Each names one thing to go and do — which is why the wrong-kind
    // and speed cases stay separate: "pick a clip with sound" and "split a
    // speed-1 segment off" are different work.
    auto_caption_needs_selection: "Matnga o'girish uchun video yoki ovoz klipini tanlang",
    auto_caption_needs_audio_kind:
      "Bu klipda ovoz yo'q — video yoki ovoz klipini tanlang",
    auto_caption_speed_not_one:
      "Bu klip tezligi o'zgartirilgan — avval undan oddiy tezlikdagi qismni bo'lib oling, aks holda so'zlar noto'g'ri joyga tushadi",
    auto_caption_transcribing: "Matnga o'girish allaqachon bajarilmoqda",
    // Detect pauses. Mostly the transcribe gate, said in the verb the row
    // uses: the place to go is the same, but "to transcribe" and "to measure"
    // are not the same errand.
    //
    // `needs_selection` asks for an AUDIO clip where transcription asks for
    // either kind, and that is not a slip: a picture clip is measurable only
    // through the audio it is linked to, so naming the audio is the shortest
    // route to a selection that works.
    detect_pauses_needs_selection: "O'lchash uchun ovoz klipini tanlang",
    detect_pauses_needs_audio_kind:
      "Bu klipda ovoz yo'q — video yoki ovoz klipini tanlang",
    detect_pauses_speed_not_one:
      "Bu klip tezligi o'zgartirilgan — avval undan oddiy tezlikdagi qismni bo'lib oling, aks holda pauzalar noto'g'ri joyga tushadi",
    // The one reason that belongs to pauses alone: the clip's own file may
    // carry a track, but what plays is the linked Audio layer, and this clip
    // has none (spec Decision 1).
    detect_pauses_plays_no_sound: "Bu klip ovoz chiqarmaydi",
    // Describe content. Its own three sentences again, and the kind case is the
    // one that genuinely differs from the two blocks above: a description reads
    // frames, so sound is not what makes a clip eligible here.
    describe_needs_selection: "Tavsiflash uchun video klipni tanlang",
    describe_needs_video_kind:
      "Tavsif kadrlarga qarab yoziladi — video klipni tanlang",
    describe_speed_not_one:
      "Bu klip tezligi o'zgartirilgan — avval undan oddiy tezlikdagi qismni bo'lib oling, aks holda tavsiflar noto'g'ri joyga tushadi",
    describe_already_running:
      "Tavsiflash allaqachon bajarilmoqda — tugashini kuting",
  },
  dock_workspace: {
    editing_label: "Tahrirlash ish maydoni",
    empty_label: "Bo'sh ish maydoni",
    all_closed: "Barcha panellar yopilgan.",
    open_panel: "Panelni ochish",
    reset: "Ish maydonini tiklash",
    close_panel: "Panelni yopish",
    move_panel: "{{title}} ni ko'chirish uchun sudrang",
    scroll_tabs: {
      start: "Oldingi panel yorliqlarini ko'rsatish",
      end: "Keyingi panel yorliqlarini ko'rsatish",
    },
    // A timeline Panel's own tab: it names the composition it shows, and its
    // tooltip prints the route the Panel was opened along.
    timeline_tab: {
      // The first step of that route. The root composition is never named in
      // the UI — it IS the timeline — so a path starts at the project, and this
      // stands in for a project saved under no name yet.
      project: "Loyiha",
      // Offered only where a Group is placed more than once: two placements are
      // two different answers to "where on the film's clock does this sit", and
      // the tab has to say which one it reads its times against.
      switch_anchor: "Nusxani almashtirish",
      switch_anchor_hint: "Bu guruh taymlayni qaysi joylashuv nusxasiga tayanishini tanlang",
      anchor_entry: "{{path}} · {{time}}",
    },
    panels: {
      media: "Media",
      transitions: "O'tishlar",
      preview: "Ko'rish oynasi",
      timeline: "Taymlayn",
      "quick-actions": "Tezkor amallar",
      attribute: "Xususiyatlar",
      caption: "Subtitr",
      marker: "Belgilar",
      "role-mixer": "Rollar mikseri",
      effect: "Effekt",
      playhead: "O'ynatish ko'rsatkichi",
      agent: "AI yordamchi",
      history: "Tarix",
      // Plural, because the Panel is a list of them and the tab names what it
      // holds. Never "Scene detection" — the detector's name is not what a
      // reviewer is looking at.
      shots: "Sahnalar",
      lahza: "Lahza",
    },
    position: {
      left: "chap",
      right: "o'ng",
      top: "yuqori",
      bottom: "pastki",
      center: "markaz",
    },
    announce: {
      opened: "{{title}} ochildi",
      closed: "{{title}} yopildi",
      maximized: "{{title}} kattalashtirildi",
      restored: "{{title}} tiklandi",
      pick_target:
        "{{source}} ko'chirilmoqda. Maqsad: {{target}}, {{total}} tadan {{current}}-si. Tanlash uchun Enter'ni bosing.",
      pick_edge:
        "{{target}} ning {{position}} tomoniga joylash. Joyni o'zgartirish uchun strelka tugmalaridan foydalaning, so'ng Enter'ni bosing.",
      committed: "{{source}} {{target}} ning {{position}} tomoniga ko'chirildi.",
      cancelled: "Panelni ko'chirish bekor qilindi.",
      not_allowed: "Panelni bunday ko'chirib bo'lmaydi.",
    },
  },
  workspace_name: {
    save_as_title: "Yangi ish maydoni sifatida saqlash",
    rename_title: "Ish maydonini qayta nomlash",
    name_label: "Ish maydoni nomi",
    placeholder: "masalan, Rang tuzatish",
    confirm: "Saqlash",
    cancel: "Bekor qilish",
  },
  marker_rename: {
    title: "Belgini qayta nomlash",
    label: "Belgi nomi",
    placeholder: "masalan, Bu pauzani qisqartirish",
    confirm: "Qayta nomlash",
    cancel: "Bekor qilish",
  },
  marker_panel: {
    // A section heading, and the whole disclosure control: the composition's
    // name plus how many markers it holds. A composition with none still gets
    // one — "nothing is marked here" is an answer, and a missing heading is not.
    section_heading: "{{name}} ({{count}})",
    // The section for markers whose clip no longer shows the frame they name.
    // CONTEXT.md's pinned word.
    hibernating: "Uyqudagi",
    // Row fields. There is deliberately no time field: a marker's time is
    // spatial and belongs to the lane's drag (ADR 0056) — on an anchored marker
    // the next reconcile would overwrite anything typed here.
    label_field: "Belgi nomi",
    note_field: "Belgi izohi",
    color_field: "Belgi rangi",
    // A marker that follows a clip, as against a free one. CONTEXT.md's pinned
    // word — never "clip marker", which would name a second entity.
    anchored: "Bog'langan",
    go_to: "{{timecode}} ga o'tish",
    // A hibernating row seeks nowhere: the frame it names is on no timeline
    // right now, so the only honest destination is the clip it is tied to.
    reveal_clip: "Manba videoda {{timecode}} da — bog'langan klipni ko'rsatish",
    // The one exit from hibernation. CONTEXT.md's pinned word.
    detach: "Ajratish",
    // The row's delete. Same words as the lane's context menu row
    // (`timeline.delete_marker`) and deliberately its own key: the Panel names
    // its own affordances, as `detach` above already does.
    delete: "Belgini o'chirish",
  },
  shots_panel: {
    // State (a): no subject. It names the kind rather than saying "nothing
    // selected", because an Audio or Text clip IS selected and still has no
    // shots to review.
    needs_video_clip: "Sahna kesimlarini ko'rib chiqish uchun video klipni tanlang.",
    // Between the two states, while the probe stats the sidecar. A distinct
    // sentence, because "not analyzed" would be a claim the probe has not made
    // yet — and it flickers past in a frame on a hit.
    checking: "Sahna tahlili tekshirilmoqda…",
    not_analyzed: "«{{clip}}» hali sahna kesimlari uchun tahlil qilinmagan.",
    // No percentage exists to report: the ffmpeg pass emits metadata lines, not
    // progress. A running label and a disabled button are the whole affordance.
    analyzing: "«{{clip}}» tahlil qilinmoqda — bunda butun manba bir marta o'qiladi.",
    analyze: "Tahlil qilish",
    analyze_running: "Tahlil qilinmoqda…",
    // A scanned source whose window holds no boundary above the threshold. An
    // answer, not a failure.
    no_shots: "Bu klip oralig'ida sahna kesimlari yo'q.",
    // The strip's axis, named by what it MEASURES. The wire field is called
    // `sensitivity` and reaches no label: a higher value yields FEWER cuts, so
    // the word reads backwards — the control's meaning is the line's position.
    axis_frame_change: "Kadr o'zgarishi",
    threshold_line: "Sahna kesimi chegarasi",
    threshold_value: "{{value}} kadr o'zgarishi",
    // The floor scan emitted nothing inside this clip's range, so there is no
    // signal for a line to cross.
    no_candidates:
      "Bu klip oralig'ida taxminiy kesimlar yo'q — chegara saralaydigan narsa yo'q.",
    // Output granularity, not accuracy: boundaries closer together than this
    // are dropped. In milliseconds because the source's own frame rate is not
    // known here.
    min_shot_length: "Sahnaning eng kam uzunligi",
    milliseconds: "ms",
    go_to: "{{timecode}} ga o'tish",
    cover_frame: "{{index}}-sahnaning muqova kadri",
    // The pair either side of a candidate boundary — the one look that answers
    // "is this a real cut".
    frame_before: "Kesimdan oldingi kadr",
    frame_after: "Kesimdagi kadr",
    score: "Aniqlagichning bu chegaradagi ishonchi",
    // Checked = this boundary stands. Clearing it merges the shot into the one
    // before it; the cleared boundary stays on that row so it can be restored.
    accept_candidate: "{{index}}-sahna boshidagi kesim",
    restore_candidate: "{{timecode}} dagi kesimni tiklash",
    // The toggle's hover text says the ACTION, as the seam glyph does — the
    // label above names the option, which is not the same thing.
    merge_candidate_hint: "Kesimni olib tashlab, oldingi sahnaga qo'shish",
    restore_candidate_hint: "Shu yerdan bo'lish",
    // Checked = keep. Every row starts kept, so a plain apply is "split here"
    // and discarding is opted into row by row.
    keep_shot: "{{index}}-sahnani saqlab qolish",
    // Absent and not zero: a span nothing has sampled has no brightness, and
    // "0.00" would report a black frame.
    stats_absent: "o'lchanmagan",
    // On-demand measurement of shots without statistics.
    measure: "Sahnalarni o'lchash",
    measure_running: "O'lchanmoqda…",
    measure_hint: "Sahna yorqinligi, harakati va aniqligini o'lchash",
    // Disabled-button reasons, `apply_no_cuts`' rule: name the precondition
    // rather than repeat a label that cannot be acted on.
    measure_all_measured: "Bu ro'yxatdagi barcha sahnalar allaqachon o'lchangan",
    measure_busy: "Qo'llash allaqachon bajarilmoqda",
    brightness: "O'rtacha yorqinlik",
    motion: "Olingan kadrlar orasidagi harakat",
    sharpness: "Aniqlik ko'rsatkichi (Laplasian dispersiyasi)",
    brightness_value: "Y {{value}}",
    motion_value: "H {{value}}",
    sharpness_value: "A {{value}}",
    flag_black: "qora",
    flag_freeze: "qotgan",
    flag_fade: "so'nish",
    // The three verbs over the reviewed list. Named for what they do to the
    // clip, not for the wire's mode: "Split at cuts" says where, and the
    // discarding one says both halves of what it is about to do.
    apply_split: "Kesimlarda bo'lish",
    apply_mark: "Kesimlarni belgilash",
    apply_discard: "Bo'lish va belgilanmaganlarni o'chirish",
    // Disabled-button reasons, `quick_actions.clear_range_empty`'s rule: name
    // the precondition — here the remedy — rather than repeat a label that
    // cannot be acted on. There is deliberately no sentence for an
    // all-unchecked discard: the channel refuses that one and its wording is
    // the only one, so the press goes out and the refusal lands below.
    apply_no_cuts:
      "Chegarani pasaytiring yoki olib tashlangan kesimni tiklang — bu klip bitta sahnadan iborat",
    apply_no_discards: "Avval o'chirmoqchi bo'lgan sahnalaringiz belgisini olib tashlang",
    apply_running: "Qo'llash allaqachon bajarilmoqda",
    // The description column's empty state. A shot without a description is the
    // ordinary case — the phrase says which state it is in, where a blank cell
    // would read as a load that never finished.
    not_described: "Tavsiflanmagan",
    clip_content: "Klip mazmuni",
    // The clip-content section's one disclosure under its lead paragraph (the
    // summary, or a run's first few segments): every segment with its
    // timecode, closed by default.
    clip_details: "Batafsil ({{count}} ta qism)",
    // The one legitimate transient, and only where the cell has nothing else to
    // show: a run whose window overlaps this row is on its way.
    describing: "Tavsiflanmoqda…",
    // The per-row press. Named for the unit it acts on, because the clip-wide
    // gesture has the same verb in the Edit menu and the two must not read as
    // the same button.
    describe_shot: "Sahnani tavsiflash",
    // A row that already has prose. "Again" and not "Re-describe": the row is
    // not being corrected, it is being asked a second time, which is a normal
    // thing to want from a model.
    describe_shot_again: "Qayta tavsiflash",
    describe_shot_hint: "Sahnani vizual model yordamida tavsiflash",
    // What the status-log rows call one shot's run. Interpolated into
    // `log.describe_started` / `log.describe_done` in place of a clip name, so
    // a sweep's rows say which shot each one was.
    describe_shot_subject: "{{clip}} · {{index}}-sahna",
    // The sweep. The count is in the label because the cost is linear in it —
    // hiding the N would hide the whole decision. Pluralized like
    // `project.tracks`, since it is read at 1 as often as at 30.
    describe_all_one: "{{count}} ta sahnani tavsiflash",
    describe_all_other: "{{count}} ta sahnani tavsiflash",
    describe_all_hint: "Sahnalarni vizual model yordamida birdaniga tavsiflash",
    // While it runs the button IS the stop. `done` counts finished runs, so it
    // reads 0/7 while the first one is going.
    describe_all_running: "To'xtatish ({{done}}/{{total}})",
    describe_all_stop_hint:
      "Hozir tavsiflanayotgan sahnadan keyin to'xtatish — boshlangan model ishini bekor qilib bo'lmaydi, uning matni saqlanadi.",
    // Disabled-button reasons, `measure_all_measured`'s rule: name the
    // precondition rather than repeat a label that cannot be acted on.
    describe_all_described: "Bu ro'yxatdagi barcha sahnalar allaqachon tavsiflangan",
    describe_running: "Tavsiflash allaqachon bajarilmoqda",
    describe_sweep_running: "Sahnama-sahna tavsiflash allaqachon bajarilmoqda",
  },
  actions: {
    add_color_layer: "Rangli klip",
    add_text_layer: "Matn",
    select_tool: "Tanlash vositasi",
    toggle_blade_mode: "Kesish vositasi",
    select_text_tool: "Matn vositasi",
    select_hand_tool: "Qo'l vositasi",
    preview_zoom_in: "Ko'rish oynasini kattalashtirish",
    preview_zoom_out: "Ko'rish oynasini kichiklashtirish",
    preview_zoom_fit: "Ko'rish oynasini oynaga moslash",
    move_to_new_track: "Yangi yo'lakka ko'chirish",
    import_media: "Media qo'shish…",
    export: "Eksport…",
    save: "Saqlash",
    save_as: "Boshqacha saqlash…",
    save_and_close: "Saqlash va yopish",
    save_and_close_hint:
      "Barcha kutilayotgan tahrirlarni ish maydoniga yozib, loyiha tanlash oynasiga qaytish.",
    undo: "Bekor qilish",
    redo: "Qaytarish",
    settings: "Sozlamalar…",
    settings_hint: "Afzalliklar, tezkor tugmalar va API kalitlari.",
    motifs: "Motiflar…",
    motifs_hint:
      "Motif qatlamini tanlang (pastki yozuv, sarlavha kartasi, izoh, …) va uni taymlaynga tashlang.",
    open_agent_panel: "AI yordamchi panelini ochish",
    enter_agent_mode: "AI yordamchi rejimiga o'tish",
    create_checkpoint: "Nazorat nuqtasi yaratish…",
    create_checkpoint_hint:
      "Joriy holatga nom bering, keyin unga qaytishingiz mumkin. Faqat shu seans uchun — nazorat nuqtalari loyiha bilan saqlanmaydi.",
    // Not menu items — these labels show up in the Settings → Keyboard
    // panel for shortcuts that don't have a menu home (transport,
    // timeline edits).
    toggle_play: "O'ynatish / pauza",
    // "clips" rather than "layers": the command is reached from the timeline,
    // where what the user sees selected is clips on tracks.
    select_all: "Barcha kliplarni tanlash",
    deselect_all: "Tanlovni bekor qilish",
    delete_selected: "Tanlangan klipni o'chirish",
    // Premiere's own English term. Kept short because it also sits on a 16 px
    // strip button's tooltip and on a context-menu row beside plain Delete,
    // where the contrast between the two labels is the whole explanation.
    ripple_delete_selected: "Siljitib o'chirish",
    copy_selected: "Tanlangan klipdan nusxa olish",
    paste_at_playhead: "Klipni o'ynatish ko'rsatkichiga qo'yish",
    split_at_playhead: "O'ynatish ko'rsatkichida bo'lish",
    toggle_log: "Faoliyat jurnalini ko'rsatish/yashirish",
    focus_log_search: "Faoliyat jurnali qidiruviga o'tish",
    toggle_display_mode: "A/B Roll / Barcha yo'laklarni almashtirish",
    toggle_follow_playhead: "Taymlaynni avtomatik aylantirishni yoqish/o'chirish",
    toggle_markers_visible: "Taymlayn belgilarini yoqish/o'chirish",
    toggle_safe_area_guides: "Xavfsiz hudud chiziqlarini yoqish/o'chirish",
    toggle_tail_snap: "Kliplarni yopishtirishni yoqish/o'chirish",
    toggle_review_overlay: "Tekshiruv qatlamini yoqish/o'chirish",
    // Prefixed, unlike the bare "Full" / "1/2" the Settings radio uses: these
    // labels also appear in the search palette, where a row reading just
    // "1/2" says nothing about what it would change.
    playback_resolution_full: "Ijro o'lchami: To'liq",
    playback_resolution_half: "Ijro o'lchami: 1/2",
    playback_resolution_quarter: "Ijro o'lchami: 1/4",
    // The strip's one-button form. Named for what it does rather than for a
    // value, because unlike the three above it lands somewhere different every
    // time it runs — a palette row promising "1/2" that sometimes gives 1/4
    // would be worse than no row.
    playback_resolution_cycle: "Ijro o'lchamini almashtirish",
    center_horizontally: "Gorizontal markazlash",
    center_vertically: "Vertikal markazlash",
    apply_default_transition: "Standart o'tishni qo'llash (crossfade)",
    zoom_timeline_in: "Taymlaynni kattalashtirish",
    zoom_timeline_out: "Taymlaynni kichiklashtirish",
    focus_next_panel: "Keyingi panelga o'tish",
    focus_previous_panel: "Oldingi panelga o'tish",
    toggle_maximize_panel: "Panelni kattalashtirish / tiklash",
    restore_maximized_panel: "Kattalashtirilgan panelni tiklash",
    group_selected: "Tanlangan kliplarni guruhlash",
    ungroup_selected: "Guruhni tarqatish",
    open_group: "Guruhni ochish",
    add_to_group: "Guruhga qo'shish",
    // The context menu's version, which knows the Group it was opened over. The
    // menus built once — Edit, the native bar, the search palette — keep the
    // plain label above (`menu/CommandContextItem.tsx` says why).
    add_to_group_named: "«{{name}}» ga qo'shish",
    // Two forms, two labels. The submenu trigger is followed by the list of
    // destinations, each of which names itself, so the trigger keeps only the
    // ellipsis; the Edit menu and the palette have no list behind them and
    // that form means "move to the root", so it names the timeline outright
    // (`shortcuts/defs.ts` says what those forms do).
    move_to_composition: "Taymlaynga ko'chirish",
    move_to_composition_submenu: "Ko'chirish…",
    // The three analysis rows name their subject — "selected clip" — because
    // they sit in the Edit menu and the palette as well as on the clip itself,
    // and there a row has to say what it will act on. The context menu keeps
    // the same label: the right-click has just made the clicked clip that
    // selection, so the sentence stays true.
    //
    // "Transcribe" and not "Auto-caption": the row asks the speech engine a
    // question about the clip, and the name says which one. What lands is
    // still a caption track — the Caption panel opens on success to show it.
    // No ellipsis: nothing is asked before it runs. The language is the
    // engine's to detect, so the one field the old dialog carried was a click
    // that asked nothing (`speech/transcribeRun.ts`).
    auto_caption_selected: "Tanlangan klipni matnga o'girish",
    // "Detect pauses" and not "Cut pauses": nothing is removed by the row
    // itself. Measuring is the half every pause recipe shares, and what becomes
    // of the pauses is decided inside the section it opens
    // (`timeline/LayerContextMenu.tsx` carries the whole reason). Ellipsis
    // because that section comes first.
    detect_pauses_selected: "Tanlangan klipdagi pauzalarni aniqlash…",
    // "Content" as the head noun: what the model reads is what is IN the
    // footage, and the row's answer lands as prose on the shot rows rather than
    // as anything about the clip as an object. "Clip" still names the unit the
    // press acts on — the whole clip, where the per-row `describe_shot` button
    // acts on one shot.
    //
    // No ellipsis, like the transcribe row: sampling and focus live in
    // Settings → Video understanding now, so the press runs rather than asks.
    describe_selected: "Tanlangan klip mazmunini tavsiflash",
    open_voiceover: "Diktor ovozi…",
    // Ellipsis because the row opens a surface rather than committing anything:
    // reviewing is what happens next, and the apply is a press inside the Panel.
    review_shots: "Sahnalarni ko'rib chiqish…",
    toggle_link_selected: "Tanlangan kliplarni bog'lash / ajratish",
    toggle_link_override: "Bog'lanishni chetlab o'tishni yoqish/o'chirish",
    // One key, two subjects — the label names the gesture and the hint below it
    // names what each selection makes it do.
    nudge_back: "Biroz oldinroqqa surish",
    nudge_forward: "Biroz keyinroqqa surish",
    nudge_large_back: "Oldinroqqa surish (katta qadam)",
    nudge_large_forward: "Keyinroqqa surish (katta qadam)",
    resync_audio_to_video: "Ovozni videoga qayta moslash",
    seek_frame_back: "Bir kadr orqaga",
    seek_frame_forward: "Bir kadr oldinga",
    seek_second_back: "Bir soniya orqaga",
    seek_second_forward: "Bir soniya oldinga",
    seek_prev_edit: "Oldingi tahrir nuqtasiga o'tish",
    seek_next_edit: "Keyingi tahrir nuqtasiga o'tish",
    seek_start: "Boshiga o'tish",
    seek_end: "Oxiriga o'tish",
    mark_in: "Boshlanish nuqtasini belgilash",
    mark_out: "Tugash nuqtasini belgilash",
    add_marker_at_playhead: "O'ynatish ko'rsatkichida belgi qo'shish",
    // The named flags on the marker lane, NOT the in/out range two lines up:
    // "mark" and "marker" share a root in English and name two different
    // objects here, so a translation must keep them apart.
    seek_prev_marker: "Oldingi belgiga o'tish",
    seek_next_marker: "Keyingi belgiga o'tish",
    clear_range: "Boshlanish/tugash nuqtalarini tozalash",
    open_search: "Hamma narsani qidirish…",
    search: "Qidirish",
  },
  // The second line under an action in Settings → Keyboard. Only the actions
  // whose handler dispatches on which selection is armed carry one: their label
  // can name just one of the two things the key does, so the hint is where the
  // rule itself is stated.
  hints: {
    nudge_back:
      "Tanlangan kalit kadrlarni bir kadr oldinroqqa suradi; kalit kadr tanlanmagan bo'lsa, tanlangan ovozni bir namunaga suradi.",
    nudge_forward:
      "Tanlangan kalit kadrlarni bir kadr keyinroqqa suradi; kalit kadr tanlanmagan bo'lsa, tanlangan ovozni bir namunaga suradi.",
    nudge_large_back:
      "Tanlangan kalit kadrlarni o'n kadr oldinroqqa suradi; kalit kadr tanlanmagan bo'lsa, tanlangan ovozni bir millisoniyaga suradi.",
    nudge_large_forward:
      "Tanlangan kalit kadrlarni o'n kadr keyinroqqa suradi; kalit kadr tanlanmagan bo'lsa, tanlangan ovozni bir millisoniyaga suradi.",
    delete_selected:
      "Kalit kadrlar tanlangan bo'lsa, ularni o'chiradi, aks holda tanlangan kliplarni. Tanlangan bo'shliq esa yopiladi — undan keyingi hamma narsa chapga siljiydi.",
    ripple_delete_selected:
      "Tanlangan kalit kadrlar va tanlangan o'tish, xuddi O'chirishdagidek, birinchi navbatda shu tugmaga bo'ysunadi; aks holda tanlangan kliplar o'chiriladi va ulardan keyingi hamma narsa chapga siljiydi. Tanlangan bo'shliq yopiladi.",
    copy_selected:
      "Kalit kadrlar tanlangan bo'lsa, ulardan nusxa oladi, aks holda tanlangan klipdan.",
    paste_at_playhead:
      "Nusxa olingan kalit kadrlarni o'ynatish ko'rsatkichida tanlangan kliplarga qo'yadi, aks holda nusxa olingan klipni qo'yadi.",
  },
  // The ✕ every AppDialog draws in its own header. One key, not one per
  // feature area: the glyph dismisses the DIALOG, so the wording is the same
  // everywhere and the footer button keeps the contextual verb (Cancel /
  // Stay / Keep). Distinct from `window_controls.close`, which quits the app.
  modal: {
    close: "Yopish",
  },
  dialogs: {
    save_title: "Lahza Studio loyihasini saqlash",
    project_filter: "Lahza Studio loyihasi",
    save_default_name: "untitled.vproj",
    import_title: "Media qo'shish",
    media_filter: "Media fayllar",
  },
  media_pool: {
    empty: "Hali media qo'shilmagan.",
    search_placeholder: "Media qidirish…",
    no_matches: "«{{query}}» bo'yicha hech narsa topilmadi.",
    clear_search: "Qidiruvni tozalash",
    // The pool's session filter. Says "unused", not "isolated": on a Group the
    // state is a remnant, on a media item it is merely never-placed, and the
    // word that covers both is the neutral one.
    unused_filter: "Faqat ishlatilmaganlarni ko'rsatish",
    // Its own dead end, kept apart from `empty` — a pool full of used media
    // must never print "No media imported yet."
    no_unused: "Hamma media qayerdadir ishlatilgan.",
    layout_label: "Ko'rinish",
    layout_large: "Katta kartalar (har qatorda bitta)",
    layout_grid: "To'r (bir xil o'lchamdagi kartalar)",
    layout_list: "Ro'yxat",
    no_duration: "—",
    importing: "Nusxalanmoqda…",
    copy_pending: "Nusxalash kutilmoqda…",
    copy_failed: "Nusxalab bo'lmadi",
    unsupported: "Qo'llab-quvvatlanmaydi",
    unsupported_hint: "Joriy ko'rish dvigateli bu mediani o'qiy olmaydi. Sozlamalarda dekodlash dvigatelini almashtiring yoki mavjud yengil nusxadan (proxy) foydalaning.",
    importing_cancel_hint: "Nusxalashni bekor qilib, asl faylga havolani saqlash",
    missing: "Topilmadi",
    missing_hint: "Manba fayl topilmadi: {{path}}",
    changed: "O'zgargan",
    changed_hint: "{{path}} Lahza Studio'dan tashqarida o'zgartirilgan va endi bu media emas. Tiklash uchun asl faylni qayta qo'shing.",
    proxy_pending: "Tayyorlanmoqda…",
    proxy_pending_hint: "Ko'rish uchun tayyorlanmoqda…",
    optimizing: "Fonda optimallashtirilmoqda",
    optimizing_hint:
      "Hozir tahrirlash mumkin · optimallashgan media fonda tayyorlanmoqda; eksport uni avtomatik kutadi.",
    card_ready_hint: "Qo'shish uchun yo'lakka torting · amallar uchun o'ng tugmani bosing",
    drop_to_import: "Qo'shish uchun fayllarni shu yerga tashlang",
    proxy_mode_auto: "Avto",
    proxy_mode_auto_hint: "Loyihadagi «Yengil nusxani afzal ko'rish» sozlamasiga amal qilish.",
    proxy_mode_proxy: "Yengil nusxa",
    proxy_mode_proxy_hint: "Bu klipni doim 720p yengil nusxadan ko'rsatish.",
    proxy_mode_original: "Asl",
    proxy_mode_original_hint: "Bu klipni doim asl fayldan ko'rsatish.",
    actions_for: "{{label}} uchun media amallari",
    proxy_heading: "Ko'rish manbasi",
    analyze_shots: "Sahnalarni tahlil qilish",
    analyze_shots_running: "Tahlil qilinmoqda…",
    analyze_shots_hint: "Bu klipdagi sahna almashinuvlarini aniqlash",
    remove_menu: "Media ro'yxatidan olib tashlash",
    remove_wait_for_import: "Avval qo'shish tugashini kuting yoki uni bekor qiling",
    remove_title: "Media olib tashlansinmi?",
    remove_body: "«{{label}}» bu loyihadan olib tashlansinmi?",
    remove_unused_note:
      "Manba fayl diskda qoladi. Ishlatilmagan mediani olib tashlashni bekor qilib bo'lmaydi.",
    remove_in_use_title: "Media ishlatilmoqda",
    remove_in_use_body_one:
      "«{{label}}» taymlayndagi {{count}} ta klipda ishlatilgan. Uni olib tashlasangiz, quyidagilar ham o'chadi:",
    remove_in_use_body_other:
      "«{{label}}» taymlayndagi {{count}} ta klipda ishlatilgan. Uni olib tashlasangiz, quyidagilar ham o'chadi:",
    remove_in_use_note:
      "Taymlayndagi bu o'zgarishni bekor qilish mumkin. Manba fayl diskda qoladi.",
    // Last rungs of a reference row's naming chain, for a layer the renderer's
    // snapshot cannot place (`panels/mediaReferences.ts`).
    reference_unknown_layer: "Klip {{id}}",
    reference_unknown_track: "Noma'lum yo'lak",
    remove_cancel: "Bekor qilish",
    remove_confirm: "Olib tashlash",
    remove_force_confirm_one: "Media + {{count}} ta klipni olib tashlash",
    remove_force_confirm_other: "Media + {{count}} ta klipni olib tashlash",
    removing: "Olib tashlanmoqda…",
    remove_failed: "Mediani olib tashlab bo'lmadi: {{detail}}",
    // Group cards, in the same pool list as the media ones.
    // A composition whose last inner layer was deleted. It has no window to
    // place, so the card is not draggable — the hint is what says why.
    groups_empty_hint: "Bu guruh bo'sh. Uni oching va avval klip qo'shing.",
    groups_card_hint:
      "Yana bir nusxasini qo'yish uchun yo'lakka torting · ochish uchun ikki marta bosing · guruh amallari uchun o'ng tugmani bosing",
    // A composition no Group clip references. Not "unused": everything in the
    // pool is unused until it is placed, and this state means the opposite —
    // it WAS placed, the last clip is gone, and the composition is now the only
    // thing holding it.
    groups_isolated: "ajralib qolgan",
    groups_refs_one: "{{count}} ta havola",
    groups_refs_other: "{{count}} ta havola",
    groups_actions_for: "{{label}} uchun guruh amallari",
    groups_delete: "Guruhni o'chirish",
    groups_delete_hint: "Bu guruhni loyihadan olib tashlash",
    groups_delete_in_use:
      "Hali guruh klipida ko'rsatilmoqda. Avval o'sha kliplarni o'chiring yoki guruhdan chiqaring.",
    groups_rename_title: "Guruh nomini o'zgartirish",
    groups_rename_confirm: "Nomini o'zgartirish",
  },
  preview: {
    edit_text: "Matnni tahrirlash",
    empty_hint: "Ko'rishni boshlash uchun klip qo'shing",
    preparing: "Ko'rish oynasi tayyorlanmoqda…",
    // What the preview renders. The list names the timeline and every Group;
    // the default follows whichever timeline holds the keyboard.
    target_label: "Ko'rish oynasida nima ko'rsatiladi",
    target_follow_focus: "Faol taymlaynga ergashish",
    // Percentages are composition pixels per device pixel, so 100 % is the
    // "actual detail" reading. Fit is a mode, not a percentage: it re-fits
    // when the panel is resized.
    zoom_label: "Ko'rish masshtabi",
    zoom_fit: "Sig'dirish",
    zoom_percent: "{{percent}}%",
  },
  timeline: {
    // The Review lane's header cell (ReviewLane.tsx): the row of tack chips.
    review_lane: "Eslatmalar",
    empty_placeholder: "taymlayn (to'ldirish uchun klip qo'shing yoki motif tanlang)",
    empty_ab_roll:
      "Bu yerda A/B roll kontenti yo'q. Klipni $t(tracks.roles.a-roll) yoki $t(tracks.roles.b-roll) yo'lagiga tashlang yoki barcha yo'laklarni ko'rish uchun {{key}} tugmasini bosing.",
    resize_track_hint: "Yo'lak o'lchamini o'zgartirish uchun torting",
    track_eye_hint: "Bu yo'lakni yashirish (eksportga ta'sir qiladi)",
    track_lock_hint: "Bu yo'lakni tahrirdan qulflash",
    drop_collision: "Mavjud media ustiga tushadi",
    drop_locked: "Yo'lak qulflangan",
    clip_lock_hint: "Qulflangan. Ko'rish uchun tanlang; tahrirlash uchun Xususiyatlarda qulfdan chiqaring.",
    clip_track_lock_hint: "Yo'lak qulflangan. Ko'rish uchun tanlang; tahrirlash uchun yo'lakni qulfdan chiqaring.",
    // The selected gap's tooltip — the shape a clip's own title has (`Video:
    // start → end`), with the gap named where the kind would be.
    gap_title: "Bo'shliq: {{start}} → {{end}}",
    // A Group released inside itself, or inside a Group it already contains.
    drop_cycle: "Guruh o'zini o'zi o'z ichiga ololmaydi",
    drop_spawn_hint: "Yangi yo'lak yaratish uchun qo'yib yuboring",
    drop_spawn_drag_hint: "Yangi yo'lak yaratish uchun klipni shu yerga torting",
    delete_track: "Yo'lak va kliplarni o'chirish",
    reorder_track: "{{name}} tartibini o'zgartirish uchun torting",
    reorder_track_reserved: "A/B roll yo'laklari o'z tartibida qoladi",
    reorder_track_locked: "Tartibini o'zgartirish uchun yo'lak va kliplarni qulfdan chiqaring",
    track_move_up: "Yo'lakni yuqoriga surish",
    track_move_down: "Yo'lakni pastga surish",
    track_move_top: "Yo'lakni eng tepaga surish",
    track_move_bottom: "Yo'lakni eng pastga surish",
    track_move_dragging: "{{name}} surilmoqda · Kliplar: {{count}}",
    track_move_above: "{{name}} ustiga qo'yish",
    track_move_below: "{{name}} ostiga qo'yish",
    delete_track_hint: "Bu yo'lak va undagi barcha kliplarni o'chirish. Bekor qilish ularni birga tiklaydi.",
    toggle_keyframe_lanes: "Kalit kadr qatorlarini ochish",
    mode_ab_roll_hint: "A/B roll, boshqa yo'laklar yashirilgan. Hammasini ko'rish uchun bosing.",
    mode_all_tracks_hint: "Barcha yo'laklar, hech narsa yashirilmagan. A/B roll uchun bosing.",
    // Context-menu entries for the right-click menu on layers.
    separate_audio: "Ovozni yangi yo'lakka ajratish",
    prebake_now: "Hozir oldindan tayyorlash",
    mark_shot_cuts: "Sahna almashinuvlarini belgilash",
    mark_shot_cuts_hint:
      "Bu klipdagi sahna chegaralarini aniqlab, har biriga belgi qo'yish.",
    rename: "Nomini o'zgartirish",
    // The Group rows, gated on the right-clicked clip's kind.
    open_group: "Guruhni ochish",
    rename_group: "Guruh nomini o'zgartirish…",
    // Accessible name for the Group clip's inline composition-name editor.
    group_label: "Guruh nomi",
    // A Group with no stored name. The number is its creation order among the
    // unnamed ones (`lib/layerName.ts`), which is what makes two unnamed
    // Groups tellable apart on the timeline.
    group_derived_name: "Guruh {{n}}",
    // The two source-window affordances on a Group clip. Hatched tail: the
    // composition is shorter than the window, so the clip's end shows nothing.
    // Tick: the composition is longer, so there is content to trim out to.
    group_overhang: "{{label}} tugagandan keyin — bu yerda hech narsa ko'rinmaydi",
    group_more_content: "{{label}} uzunroq — ko'proq ko'rsatish uchun bu chetni torting",
    // Tooltip of the `⚑N` badge on a Group clip. The count reaches through
    // every composition nested inside, so the sentence says "inside" rather
    // than naming a timeline — the marks are not all on one.
    group_marker_count_one: "Ichida {{count}} ta belgi — bu guruhni ochish uchun bosing",
    group_marker_count_other:
      "Ichida {{count}} ta belgi — bu guruhni ochish uchun bosing",
    // Accessible name for the label tab's inline editor.
    // Tooltip of the `+N` badge on a link whose members sit on filtered lanes.
    link_hidden_members_one:
      "Yashirin yo'lakda {{count}} ta bog'langan klip — ko'rsatish uchun bosing",
    link_hidden_members_other:
      "Yashirin yo'laklarda {{count}} ta bog'langan klip — keyingisini ko'rsatish uchun bosing",
    // The marker menu names its subject: its target is a ~5 px glyph, so a
    // bare "Delete" would leave "of what?" to a tooltip the menu just covered.
    delete_marker: "Belgini o'chirish",
    // The two anchoring rows, in the glossary's words (CONTEXT.md). "Attach to
    // clip" names its target the way "Delete marker" does — the row acts on the
    // marker but what it needs from the user is a clip.
    attach_marker: "Klipga biriktirish",
    detach_marker: "Ajratish",
    // Accessible name for the lane header's inline rename field — the visible
    // label it replaces is the lane's own name.
    rename_track_label: "{{label}} nomini o'zgartirish",
    enable_layer: "Klipni yoqish",
    disable_layer: "Klipni o'chirib qo'yish",
    enable_layers_one: "{{count}} ta klipni yoqish",
    enable_layers_other: "{{count}} ta klipni yoqish",
    disable_layers_one: "{{count}} ta klipni o'chirib qo'yish",
    disable_layers_other: "{{count}} ta klipni o'chirib qo'yish",
    enabled_tracks_locked: "Yoqish yoki o'chirib qo'yish uchun tegishli klip va yo'laklarni qulfdan chiqaring",
    bake_dot_queued: "Oldindan tayyorlash navbatda",
    bake_dot_paused: "Oldindan tayyorlash to'xtatilgan",
    bake_dot_retrying: "Oldindan tayyorlash qayta urinilmoqda",
    bake_dot_warming: "Qizdirilmoqda…",
    bake_dot_preview_ready: "Ko'rishga tayyor",
    bake_dot_baking: "Oldindan tayyorlanmoqda…",
    bake_dot_ready: "Oldindan tayyorlangan",
    bake_dot_error: "Oldindan tayyorlab bo'lmadi",
    audio_slipped: "Ovoz videodan {{offset}} siljigan",
    audio_units: "Ovoz birliklari",
    audio_units_frames: "Taymkod (HH:MM:SS:FF)",
    audio_units_ms: "Millisekundlar (HH:MM:SS.mmm)",
    audio_units_samples: "Namunalar (48 kHz)",
    // Transition create entries — shown when the right-click lands within
    // the tolerance band of a cut between adjacent visual layers.
    add_transition_crossfade: "Silliq o'tish qo'shish",
    add_transition_wipe: "Surib o'tish qo'shish · {{direction}}",
    add_transition_slide: "Siljib o'tish qo'shish · {{direction}}",
    transition_chip_title: "{{kind}} o'tishi · {{start}} → {{end}}",
    // Chip context-menu submenu triggers; kind/direction values reuse
    // `transitions.*`, delete reuses `property_panel.transition_delete`.
    transition_menu_kind: "Turi",
    transition_menu_direction: "Yo'nalish",
    transition_menu_duration: "Davomiyligi",
    transition_menu_duration_preset: "{{seconds}} s",
    // The marker lane's own header cell: what the row under the ruler is.
    marker_lane: "Belgilar",
    // Hover text for a mark in the marker lane; `label` falls back to
    // `$t(kinds.marker)` at the call site. Which pattern a marker gets is
    // MarkerLane.tsx's `markerTitle`.
    marker_tooltip_point: "{{label}} · {{timecode}}",
    marker_tooltip_region: "{{label}} · {{start}} – {{end}}",
  },
  // Derived track names (`lib/trackName.ts`): what a lane is called when the
  // user has not named it. Kebab role keys so the lookup is the wire value
  // itself. Nested into `timeline.empty_ab_roll` with `$t(…)` so the hint names
  // lanes the way their headers do instead of quoting one language.
  tracks: {
    roles: {
      "a-roll": "A roll",
      "b-roll": "B roll",
      "audio-a": "A roll ovozi",
      "audio-b": "B roll ovozi",
      caption: "Subtitrlar",
    },
    positional: "Yo'lak {{n}}",
  },
  transitions: {
    kind_crossfade: "Silliq o'tish",
    kind_wipe: "Surib o'tish",
    kind_slide: "Siljib o'tish",
    // Direction = MOTION direction (industry convention): "Wipe left" sweeps
    // the reveal boundary right-to-left; "Slide left" enters from the right.
    direction_left: "Chapga",
    direction_right: "O'ngga",
    direction_up: "Yuqoriga",
    direction_down: "Pastga",
    // Why the apply surfaces (strip button, panel cards) are disabled —
    // shared so every outlet explains the same precondition the same way.
    no_target: "Ikki qo'shni vizual klip orasida kesim yo'q",
    // Failure copy moved to `errors.*` (errors/formatCommandError.ts).
  },
  playhead_panel: {
    section_label: "O'ynatish ko'rsatkichi yonidagi yashirin yo'lak kliplari",
    // A row's leading time value: unit letters, not a timecode (see
    // `formatPlayheadDelta`). The phrase around the value is what saves every row a
    // printed field name, so a translation has to keep the relation it states —
    // reducing any of these to the bare number puts the ambiguity back.
    delta_frames: "{{f}}k",
    delta_sec_frames: "{{s}}s {{f}}k",
    delta_min_sec: "{{m}}d {{s}}s",
    delta_hour_min: "{{h}}soat {{m}}d",
    delta_future: "{{value}} dan keyin",
    delta_past: "{{value}} oldin",
    delta_remaining: "{{value}} qoldi",
    // The field names themselves, spent where they cost no width: the
    // accessible name and the hover title. The printed value stays terse; these
    // say in full what it measures.
    delta_future_aria: "O'ynatish ko'rsatkichidan {{value}} keyin boshlanadi",
    delta_past_aria: "O'ynatish ko'rsatkichidan {{value}} oldin tugagan",
    delta_remaining_aria: "O'ynashiga {{value}} qoldi",
    duration_aria: "Davomiyligi {{value}}",
    // The ±Δ window dial. `value` is pre-formatted (playheadItems.ts) and never a
    // count, so these keys take no i18next plural suffixes.
    window_label: "Ko'rsatkich oralig'i",
    window_seconds: "{{value}}s",
    window_minutes: "{{value}}daq",
    // The chips are checkboxes in any combination, and checking none is the
    // unfiltered state — so `filter_empty` must describe a set, not one kind.
    filter_label: "Ko'rsatkich yonidagi elementlarni turi bo'yicha saralash",
    cat_video: "Video",
    cat_audio: "Ovoz",
    cat_text: "Matn",
    filter_empty: "Ko'rsatkich yonida tanlangan turdagi hech narsa yo'q",
    section_at_playhead: "Hozir o'ynamoqda",
    section_nearby: "Yaqinda",
    at_playhead_empty: "Hozir hech narsa o'ynamayapti",
    goto: "Klip boshiga o'tish",
    rename_label: "{{label}} nomini o'zgartirish",
    restack_grip: "{{label}} qatlamini o'zgartirish uchun torting",
    row_menu: "{{label}} qatlamini o'zgartirish",
    restack_forward: "Oldinga olib chiqish",
    restack_backward: "Orqaga surish",
    restack_front: "Eng oldinga olib chiqish",
    restack_back: "Eng orqaga surish",
    restack_above_track: "{{label}} ustiga qo'yish",
    restack_below_track: "{{label}} ostiga qo'yish",
    reference_empty: "Vizual kontent yo'q",
    reference_filtered: "Kontent saralangan",
    linked: "Bog'langan",
    link_menu: "{{label}} ni bog'lash",
    unlink: "Bog'lanishni uzish",
    all_tracks_title: "Barcha yo'laklar",
    all_tracks_msg:
      "Barcha yo'laklar allaqachon taymlaynda — bu panel ko'rsatadigan yashirin narsa yo'q.",
    all_tracks_hint: "A/B roll'ga qaytish uchun <key>{{key}}</key> tugmasini bosing.",
    empty_title: "Ko'rsatkich yonida hech narsa yo'q",
    empty_msg:
      "O'ynatish ko'rsatkichidan ±{{window}} oralig'ida yashirin yo'lak kliplari yo'q. Ko'rsatkichni suring yoki yuqoridagi oraliqni kengaytiring.",
  },
  agent_panel: {
  // The agent view's Jump: the preview's time only, never a selection.
  "jump": "Ko'rish oynasini shu yerga o'tkazish",
  "jump_elsewhere": "Ko'rish oynasidagi taymlaynda emas — uni muharrirda toping",
  "service_unknown": "MCP holati noma'lum",
  "service_ready": "MCP xizmati tayyor",
  "service_offline": "MCP xizmati ishlamayapti",
  "connection_settings": "AI yordamchi ulanish sozlamalari",
  "last_activity": "Oxirgi so'rov · {{time}}",
  "no_connections": "Ro'yxatdan o'tgan mijozlar yo'q",
  "connection_note": "Ro'yxatdan o'tgan seans mijoz hali onlayn ekanini kafolatlamaydi.",
  "running_count": "{{count}} ta amal bajarilmoqda",
  "no_running": "Bajarilayotgan amal yo'q",
  "end_session": "Ish seansini tugatish",
  "end_short": "Tugatish",
  "end_hint": "Bu seansni tugatadi va qulfni bo'shatadi. Bajarilayotgan vazifalar va keyingi AI yordamchi chaqiruvlari davom etishi mumkin.",
  "locked": "Bekor qilish qulflangan",
  "unlock": "Bekor qilishni qulfdan chiqarish",
  "filter": "Faoliyat filtri",
  "filter_all": "Barcha faoliyat",
  "filter_errors": "Xatolar",
  "latest": "Eng so'nggisiga qaytish",
  "truncated": "{{count}} ta eski faoliyat endi ko'rsatilmaydi.",
  "loading": "Faoliyat yuklanmoqda…",
  "no_errors": "Xato bilan tugagan amallar yo'q.",
  "empty": "Mijoz ishlay boshlaganda AI yordamchi faoliyati shu yerda ko'rinadi.",
  "operation_count": "{{count}} ta faoliyat",
  "disconnected": "Ulanish yopildi",
  "session_ended": "Seans tugadi",
  "session_active": "Faol seans",
  "retention": "Loyiha shu safar ochilgandan beri faoliyat. Qayta ochilganda tiklanmaydi.",
  "running": "Bajarilmoqda",
  "done": "Bajarildi",
  "error": "Xato",
  "cancelled": "Bekor qilindi",
  "reverted": "Qaytarildi",
  "partial": "Qisman qaytarildi",
  "reads": "Loyiha va media o'qishlari · {{count}}",
  "restored": "«{{label}}» holatiga tiklandi",
  "checkpoint_missing": "Saqlash nuqtasi mavjud emas",
  "client": "Mijoz",
  "user": "Siz",
  "tool": "Vosita",
  "time": "Boshlangan",
  "locate": "Obyektni topish",
  "object_missing": "Obyekt endi mavjud emas",
  "arguments": "Chaqiruv argumentlari",
  "tabs": "AI yordamchi paneli bo'limlari",
  "tab_activity": "Faoliyat",
  "tab_tacks": "Eslatmalar",
  "tab_changes": "O'zgarishlar",
  "show_changes": "O'zgarishlarini taymlaynda ko'rsatish",
  "highlight_active": "Taymlaynda shu chaqiruv o'zgarishlari · {{count}}",
  "highlight_reverted": "Taymlaynda shu chaqiruv o'zgarishlari · {{count}} (bekor qilingan)",
  "highlight_clear": "Ko'rib chiqilmagan o'zgarishlarga qaytish",
  "changes_unavailable": "O'zgarish tafsilotlari endi mavjud emas: bu chaqiruv bekor qilish tarixidan chiqib ketgan.",
  "changes_none": "Bu chaqiruv loyihaga o'zgarish kiritmadi.",
  "tools": {
    "begin_agent_session": "Ish seansini boshlash",
    "open_project": "Loyihani ochish",
    "create_project": "Yangi loyiha",
    "end_agent_session": "Ish seansini tugatish",
    "set_history_lock": "Bekor qilish qulfini o'rnatish",
    "create_tacks": "Eslatma qo'shish",
    "check_composition": "Montajni tekshirish",
    "render_frames": "Kadrlarni ko'rish",
    "update_tack": "Eslatmani yangilash",
    "delete_tacks": "Eslatmalarni olib tashlash",
    "analyze_clip": "Klipni tahlil qilish",
    "analyze_audio": "Manba ovozini tahlil qilish",
    "describe_clip": "Klip mazmunini tasvirlash",
    "transcribe_clip": "Klip matnini yozib olish",
    "extract_clip_audio": "Klip ovozini ajratib olish",
    "analyze_shots_floor": "Sahnalarni aniqlash",
    "compare_frames": "Kadrlarni solishtirish",
    "detect_pauses": "Pauzalarni aniqlash",
    "import_media": "Media qo'shish",
    "synthesize_speech": "Nutq yaratish",
    "apply_subtitles": "Subtitr qo'shish",
    "auto_split_by_shot": "Sahnalarga bo'lish",
    "remove_pauses": "Pauzalarni olib tashlash",
    "ping": "Ulanishni tekshirish",
    "resources/read": "Resursni o'qish",
    "resources/list": "Resurslar ro'yxati",
    "tools/list": "Vositalar ro'yxati",
    "prompts/list": "Promptlar ro'yxati",
    "prompts/get": "Promptni o'qish",
    // Mutation and history tools. The panel shows these for a call that has no
    // history label yet — refused, failed, dry-run, or still running — so each
    // one is copy, never the tool name. Verbs mirror the history labels.
    "add_track": "Yo'lak qo'shish",
    "delete_track": "Yo'lakni olib tashlash",
    "rename_track": "Yo'lak nomini o'zgartirish",
    "move_track": "Yo'lakni surish",
    "set_track_flags": "Yo'lak belgilarini o'rnatish",
    "separate_audio_to_new_track": "Ovozni alohida yo'lakka ajratish",
    "add_video_layer": "Media klip qo'shish",
    "add_color_layer": "Rangli klip qo'shish",
    "add_audio_layer": "Ovoz klipi qo'shish",
    "add_text_layer": "Matn klipi qo'shish",
    "delete_layers": "Kliplarni o'chirish",
    "set_project_settings": "Loyiha sozlamalarini yangilash",
    "apply_transcripts": "Matndan subtitr qo'shish",
    "correct_caption_text": "Subtitr matnini tuzatish",
    "restyle_captions": "Subtitr uslubini o'zgartirish",
    "restyle_to_taste": "Loyiha uslubiga moslash",
    "list_export_presets": "Eksport shablonlari ro'yxati",
    "create_export_preset": "Eksport shablonini yaratish",
    "update_export_preset": "Eksport shablonini yangilash",
    "rename_export_preset": "Eksport shabloni nomini o'zgartirish",
    "delete_export_preset": "Eksport shablonini o'chirish",
    "set_default_export_preset": "Asosiy eksport shablonini tanlash",
    "get_export_options": "Eksport parametrlarini o'qish",
    "start_export": "Eksportni boshlash",
    "get_export_status": "Eksport holatini o'qish",
    "retry_export": "Eksportni qayta urinish",
    "cancel_export": "Eksportni bekor qilish",
    "lahza_status": "Lahza dvigatelini tekshirish",
    "lahza_analyze_video": "Videoni Lahza bilan tahlil qilish",
    "lahza_get_job": "Lahza vazifasini o'qish",
    "lahza_list_highlights": "Lahza lahzalari ro'yxati",
    "lahza_get_transcript": "O'zbekcha matnni o'qish",
    "lahza_place_highlight": "Lahza lahzasini joylashtirish",
    "lahza_export_reel": "Lahza Reels eksport qilish",
    "export_captions": "Subtitrlarni eksport qilish",
    "merge_captions": "Subtitrlarni birlashtirish",
    "jump_to": "Tarix bandiga o'tish",
    "delete_checkpoint": "Saqlash nuqtasini o'chirish",
    "add_motif_layer": "Motif klipi qo'shish",
    "add_group_layer": "Guruh klipi qo'shish",
    "paste_layers": "Kliplarni nusxalash",
    "update_layer": "Klipni yangilash",
    "update_layer_params": "Klip parametrlarini yangilash",
    "move_layer": "Klipni surish",
    "retime_layers": "Kliplar tezligini o'zgartirish",
    "set_preserve_pitch": "Ovoz balandligi tonini saqlashni sozlash",
    "set_frame_interpolation": "Kadr interpolyatsiyasini sozlash",
    "get_frame_interpolation_capabilities": "Interpolyatsiya imkoniyatlarini o'qish",
    "trim_layer": "Klipni qisqartirish",
    "split_layer": "Klipni bo'lish",
    "ripple_delete_gap": "Bo'shliqni yopish",
    "shift_layers": "Kliplarni siljitish",
    "restack_layer": "Klip qatlamini o'zgartirish",
    "set_layers_enabled": "Kliplarni yoqish yoki o'chirib qo'yish",
    "set_scale_linked": "X/Y o'lchamini bog'lash yoki ajratish",
    "create_link": "Kliplarni bog'lash",
    "delete_link": "Kliplar bog'lanishini uzish",
    "create_group": "Kliplarni guruhlash",
    "add_group_members": "Guruhga klip qo'shish",
    "ungroup_layer": "Guruhdan chiqarish",
    "rename_composition": "Guruh nomini o'zgartirish",
    "move_layers_to_composition": "Kliplarni taymlaynga ko'chirish",
    "delete_composition": "Taymlaynni o'chirish",
    "update_composition": "Taymlayn sozlamalarini yangilash",
    "add_effect": "Effekt qo'shish",
    "update_effect": "Effektni yangilash",
    "move_effect": "Effekt tartibini o'zgartirish",
    "delete_effect": "Effektni olib tashlash",
    "add_transition": "O'tish qo'shish",
    "update_transition": "O'tishni yangilash",
    "delete_transition": "O'tishni olib tashlash",
    "add_marker": "Belgi qo'shish",
    "update_marker": "Belgini yangilash",
    "delete_marker": "Belgini olib tashlash",
    "set_marker_anchor": "Belgini biriktirish yoki ajratish",
    "set_keyframe": "Kalit kadr qo'yish",
    "delete_keyframe": "Kalit kadrni olib tashlash",
    "update_link": "Bog'lanishni yangilash",
    "update_keyframe": "Kalit kadrni yangilash",
    "read_project": "Loyihani o'qish",
    "clear_keyframes": "Kalit kadrlarni tozalash",
    "smooth_keyframes": "Kalit kadrlarni silliqlash",
    "set_param_track": "Parametr animatsiyasini almashtirish",
    "get_param_track": "Parametr animatsiyasini o'qish",
    "set_extrapolation": "Ekstrapolyatsiyani sozlash",
    "set_position": "Joylashuv animatsiyasini sozlash",
    "translate_path": "Harakat yo'lini surish",
    "set_role_gain": "Rol ovoz kuchini sozlash",
    "set_role_flags": "Rol ovozini o'chirish yoki yakkalash",
    "delete_media": "Mediani olib tashlash",
    "undo": "Bekor qilish",
    "redo": "Qaytarish",
    "create_checkpoint": "Saqlash nuqtasi yaratish",
    "restore_checkpoint": "Saqlash nuqtasini tiklash",
    "list_checkpoints": "Saqlash nuqtalari ro'yxati",
    "dry_run": "Sinov ishga tushirish",
    // Motif authoring tools (`main/mcp/motifToolDefs.ts`).
    "list_motifs": "Motiflar ro'yxati",
    "read_motif": "Motif manbasini o'qish",
    "open_motif_draft": "Motif qoralamasini ochish",
    "update_motif_files": "Motif fayllarini tahrirlash",
    "export_motif": "Motifni eksport qilish",
    "begin_file_upload": "Fayl yuklashni boshlash",
    "write_file_chunk": "Fayl qismini yuklash",
    "read_file_transfer": "Fayl uzatishni o'qish",
    "delete_file_transfer": "Fayl uzatishni o'chirish",
    "preview_motif": "Motif qoralamasini ko'rish",
    "install_motif": "Motifni o'rnatish",
    "delete_motif": "Motifni o'chirish"
  }
},
  // Tacks (ADR 0115): agent review marks. English says Tack; Chinese says
  // 批注 everywhere and never shows "Tack" (not 标注, not 备注).
  tacks: {
    subtitle: "AI yordamchi siz ko'rib chiqishingiz uchun qoldirgan eslatmalar",
    closed_section: "Yopilgan {{count}}",
    clear_closed: "Tozalash",
    clear_closed_hint: "Bu guruhdagi hal qilingan va rad etilgan eslatmalarni olib tashlash. Tozalangach, AI yordamchi siz nima qaror qilganingizni o'qiy olmaydi.",
    resolve_all: "Hammasini hal qilish",
    resolve_all_hint: "Bu guruhdagi barcha ochiq eslatmalarni hal qilingan deb belgilash",
    empty: "AI yordamchi siz ko'rib chiqishingiz uchun qoldirgan eslatmalar shu yerda ko'rinadi.",
    outside_session: "Ish seansidan tashqarida",
    earlier_session: "Oldingi ish seansi",
    group_count: "{{count}} tadan {{open}} tasi ochiq",
    kind: "Turi",
    kind_note: "Izoh",
    kind_issue: "Muammo",
    kind_question: "Savol",
    status_open: "Ochiq",
    status_resolved: "Hal qilingan",
    status_dismissed: "Rad etilgan",
    state_unplaced: "Uning kompozitsiyasi endi mavjud emas",
    unplaced_hint: "Uning kompozitsiyasi endi mavjud emas, shuning uchun uni topib ham, aylantirib ham bo'lmaydi",
    outdated: "Kontent o'zgargan",
    outdated_hint: "AI yordamchi yozgandan keyin bu oraliqdagi kontent o'zgargan — hali ham dolzarbligini tekshiring",
    place: "Joylashtirish",
    locate: "Taymlaynda topish",
    resolve: "Hal qilish",
    resolve_hint: "Hal qilish: ko'rsatilgan narsa bo'yicha chora ko'rdingiz",
    dismiss: "Rad etish",
    dismiss_hint: "Rad etish: ko'rsatilgan narsa muhim emas",
    reopen: "Qayta ochish",
    convert: "Belgiga aylantirish",
    convert_hint: "Shu yerga shu nom va izoh bilan oddiy belgi qo'shish (bekor qilsa bo'ladi), so'ng eslatmani olib tashlash",
    no_body: "Tafsilot yo'q.",
    band_tooltip: "Eslatma: {{label}} · {{time}}",
    // The Review lane's group chip: tacks that would overlap, as one chip — its
    // hover title's first line, and each row of its menu.
    band_group_one: "Bu yerda {{count}} ta eslatma",
    band_group_other: "Bu yerda {{count}} ta eslatma",
    group_item: "{{kind}} · {{label}}",
    retention: "Eslatmalar faqat loyiha shu safar ochiq turganda saqlanadi. Ular hech qachon saqlanmaydi va eksport qilinmaydi.",
  },
  changes: {
    subtitle: "Oxirgi tasdiqlashingizdan beri AI yordamchilar nimalarni o'zgartirdi",
    approve_all: "Hammasini tasdiqlash",
    approve_all_hint: "Loyihaning hozirgi holatini yangi tekshiruv asosi qilish — o'z o'zgarishlaringiz ham kiradi",
    revert_all: "Hammasini qaytarish",
    revert_all_hint: "Loyihani tekshiruv asosiga qaytarish, o'shandan beri qilgan o'z o'zgarishlaringiz ham. Bekor qilish hammasini qaytaradi.",
    revert_all_locked: "Tarix qulflangan — qaytarish uchun qulfdan chiqaring",
    approve_stale: "O'zgarishlar yangilandi — qayta ko'rib chiqing. Hech narsa tasdiqlanmadi.",
    // In the toolbar; the full sentence is its title.
    approve_stale_short: "Tasdiqlanmadi: ro'yxat o'zgardi",
    revert_stale: "O'zgarishlar yangilandi — qayta ko'rib chiqing. Hech narsa qaytarilmadi.",
    revert_stale_short: "Qaytarilmadi: ro'yxat o'zgardi",
    show_mine: "Mening o'zgarishlarimni ko'rsatish ({{count}})",
    show_mine_hint: "Faqat siz qilgan o'zgarishlarni ham ko'rsatish. Ular tasdiq talab qilmaydi.",
    mine: "Siz",
    mine_hint: "O'z o'zgarishingiz — tasdiq talab qilmaydi",
    locate: "Taymlaynda topish",
    empty: "Ko'rib chiqish uchun hech narsa yo'q.",
    no_baseline: "AI yordamchi kiritgan o'zgarishlar ko'rib chiqish uchun shu yerda ko'rinadi.",
    retention: "Tasdiqlash tarixga hech narsa yozmaydi; qaytarish — bekor qilsa bo'ladigan bitta qadam. Bitta o'zgarishni olib tashlash uchun uni bekor qiling yoki qo'lda tuzating.",
    group_root: "Asosiy taymlayn",
    group_project: "Loyiha",
    group_gone: "Olib tashlangan guruh",
    group_count: "{{count}} ta ko'rilmagan",
    class_added: "Qo'shilgan",
    class_removed: "Olib tashlangan",
    class_modified: "O'zgartirilgan",
    kind_Layer: "Klip",
    kind_Marker: "Belgi",
    kind_Transition: "O'tish",
    kind_Link: "Bog'lanish",
    kind_AudioRole: "Ovoz roli",
    kind_Media: "Media",
    role_title: "{{name}} miksi",
    kind_Track: "Yo'lak",
    kind_Composition: "Guruh",
    aspect_placement: "Joylashuv",
    aspect_timing: "Vaqt",
    aspect_retime: "Tezlik",
    aspect_params: "Xususiyatlar",
    aspect_keyframes: "Kalit kadrlar",
    aspect_effects: "Effektlar",
    aspect_label: "Nomi",
    aspect_flags: "Yoqilgan / qulflangan",
    // Snapshot facts, with explicit before/after timing values (ADR 0116).
    detail: {
      length_added: "{{s}} s uzunlikda",
      length_removed: "{{s}} s o'chirildi",
      time_start: "Boshi {{from}} → {{to}} s",
      trim_start_cut: "Boshidan {{s}} s kesildi",
      trim_start_extend: "Boshi {{s}} s uzaytirildi",
      trim_end_cut: "Oxiridan {{s}} s kesildi",
      trim_end_extend: "Oxiri {{s}} s uzaytirildi",
      time_end: "Oxiri {{from}} → {{to}} s",
      time_source_start: "Manba boshi {{from}} → {{to}} s",
      time_source_end: "Manba oxiri {{from}} → {{to}} s",
      track_from_to: "{{from}} dan {{to}} ga ko'chirildi",
      track_to: "{{to}} ga ko'chirildi",
      track_other: "Boshqa yo'lakka ko'chirildi",
      composition_to: "«{{name}}» ga ko'chirildi",
      composition_other: "Boshqa taymlaynga ko'chirildi",
      speed: "Tezlik {{from}} → {{to}}",
      speed_changed: "Tezlik o'zgardi",
      gain: "Ovoz kuchi {{from}} → {{to}} dB",
      list_separator: ", ",
      names_more: "{{names}} va yana {{count}} ta",
      keyframes: "{{names}} kalit kadrlari",
      effect_added: "«{{name}}» effekti qo'shildi",
      effect_added_any: "Effekt qo'shildi",
      effect_removed: "«{{name}}» effekti olib tashlandi",
      effect_removed_any: "Effekt olib tashlandi",
      effect_changed: "«{{name}}» effekti yangilandi",
      effect_changed_any: "Effekt yangilandi",
      label: "Nomi o'zgartirildi",
      enabled: "Yoqildi",
      disabled: "O'chirib qo'yildi",
      locked: "Qulflandi",
      unlocked: "Qulfdan chiqarildi",
    },
    from_session: "Manba: {{reason}}",
    n_clips_one: "{{count}} ta klip",
    n_clips_other: "{{count}} ta klip",
    n_markers_one: "{{count}} ta belgi",
    n_markers_other: "{{count}} ta belgi",
    group_badge: "{{count}} ta ko'rib chiqilmagan o'zgarish bor",
    group_badge_activity: "{{count}} ta o'zgarish bor",
    ghost_label: "Olib tashlangan klip, asosiy joylashuv {{start}} – {{end}}",
    // An activity's highlight compares against the project before that call,
    // not against the review baseline.
    ghost_label_activity: "Olib tashlangan klip, shu chaqiruvdan oldingi joylashuv {{start}} – {{end}}",
    before_label: "Asosiy joylashuv",
    before_label_activity: "Shu chaqiruvdan oldingi joylashuv",
    // A row's place, in the seconds its facts speak; the timecode is its tooltip.
    position_span: "Hozir {{start}} – {{end}} s",
    position_point: "Hozir {{t}} s da",
    before_span: "Asosiy joylashuv {{start}} – {{end}} s",
    before_point: "Asosiy joylashuv {{t}} s",
    before_span_activity: "Shu chaqiruvdan oldingi joylashuv {{start}} – {{end}} s",
    before_point_activity: "Shu chaqiruvdan oldingi joylashuv {{t}} s",
    track_title: "«{{name}}» yo'lagi",
    was_label: "Oldin {{start}} – {{end}} s",
    ghost_tag: "Olib tashlangan {{start}} – {{end}} s",
    ghost_tag_activity: "Olib tashlangan · shu chaqiruvdan oldin {{start}} – {{end}} s",
    was_label_activity: "Shu chaqiruvdan oldin {{start}} – {{end}} s",
    marker_ghost_label: "«{{label}}» belgisi olib tashlangan, asosiy joylashuv {{at}}",
    marker_ghost_label_activity: "«{{label}}» belgisi olib tashlangan, shu chaqiruvdan oldingi joylashuv {{at}}",
    // A clip tooltip's line for its review mark: the class, then what it did.
    clip_title: "{{cls}}: {{what}}",
    status: "{{count}} ta ko'rib chiqish kerak",
    status_hint: "AI yordamchining {{count}} ta ko'rib chiqilmagan o'zgarishi — O'zgarishlar bo'limini ochish uchun bosing",
  },
  agent_mode: {
    exit: "Muharrirga chiqish",
    exit_hint: "To'liq muharrirga qaytish. Ish seansi va bekor qilish qulfi o'zgarmaydi.",
    restore: "Tiklash",
    restore_hint: "Loyihani shu saqlash nuqtasiga qaytarish — tiklashni bekor qilsa bo'ladi.",
    running_pill: "AI yordamchi: {{count}} ta bajarilmoqda",
    running_pill_hint: "AI yordamchi amallari hali fonda yakunlanmoqda.",
    resize_record_panel: "Yozuvlar paneli o'lchamini o'zgartirish",
  },
  errors: {
    refresh_failed: "yangilash: {{detail}}",
    // Curated refusal copy (errors/formatCommandError.ts). Names are resolved
    // before interpolation — {{incoming}}/{{blocking}}/{{layer}} are display
    // names, never uuids.
    layer_overlap:
      "«{{incoming}}» ni u yerga qo'yib bo'lmaydi — {{track}} da «{{blocking}}» ustiga tushadi.",
    track_locked: "{{track}} qulflangan.",
    layer_locked: "{{layer}} qulflangan. Tahrirlashdan oldin qulfdan chiqaring.",
    track_not_empty: "{{track}} da hali kliplar bor.",
    track_not_removable: "{{track}} zaxiralangan, uni olib tashlab bo'lmaydi.",
    link_locked_member:
      "«{{layer}}» qulflangan «{{locked}}» klipi bilan bog'langan.",
    trim_edge_out_of_range:
      "«{{layer}}» ni {{time}} gacha qisqartirib bo'lmaydi — klip oralig'idan tashqarida.",
    split_outside_layer:
      "«{{layer}}» ni {{time}} da bo'lib bo'lmaydi — bu joy klipdan tashqarida.",
    transition_insufficient_handle:
      "«{{layer}}» da faqat {{available}} manba zaxirasi bor — bu o'tish uchun yetarli emas.",
    transition_restore_collision:
      "O'tishni olib tashlash uchun «{{layer}}» ni kesimga qaytarish kerak, lekin u joy hozir band.",
    transition_participants_share_link:
      "«{{from}}» va «{{to}}» bir bog'lanishda — birini sursangiz ikkinchisi ham suriladi, shuning uchun ustma-ust joy ochilmaydi. Avval bog'lanishni uzing.",
    transition_layers_not_adjacent:
      "O'tish qo'shish uchun «{{from}}» va «{{to}}» bir-biriga tegib turishi kerak.",
    // Ripple delete's four. Every one opens with the same four words, because
    // these lines are read in two places — the status bar after the fact, and a
    // greyed row's tooltip before it — and the shared opening is what makes the
    // tooltip legible as "this is why the ripple is off" rather than as a
    // sentence about a clip.
    ripple_inside_hole:
      "Siljitib o'chirish to'sildi: {{layer}} yopilayotgan oraliq ichida boshlanadi — uni tanlovga qo'shing yoki siljitmasdan o'chiring.",
    ripple_collision:
      "Siljitib o'chirish to'sildi: {{moving}} {{blocking}} ustiga tushadi.",
    ripple_link_straddles:
      "Siljitib o'chirish to'sildi: {{link}} bog'lanishi a'zolari kesimning ikki tomonida.",
    ripple_locked_layer:
      "Siljitib o'chirish to'sildi: {{layer}} qulflangan, lekin surilishi kerak.",
    // The gap's own refusal (ADR 0069): the span the renderer selected is no
    // longer a gap by the time the actor reads it — a clip moved into it, or
    // an edge moved. Same four-word opening as the ripple's, since it greys the
    // same row and lands on the same status bar.
    gap_not_found:
      "Siljitib o'chirish to'sildi: {{track}} dagi tanlangan bo'shliq endi yo'q.",
    fps_locked_by_content:
      "Kadr tezligi {{current}} fps bo'lib qoladi — taymlaynda hali {{layers}} ta klip bor.",
    fps_locked_by_content_history:
      "Kadr tezligi {{current}} fps bo'lib qoladi — bekor qilish tarixida hali kliplar bor (tozalash uchun loyihani qayta oching).",
  },
  language: {
    switch_label: "Til",
  },
  window_controls: {
    minimize: "Yig'ish",
    maximize: "Kattalashtirish",
    restore: "Avvalgi o'lcham",
    close: "Yopish",
  },
  transport: {
    preparing_audio: "Ovoz tayyorlanmoqda…",
    audio_failed: "Ovozni o'ynatib bo'lmadi",
    retry_playback: "Qayta o'ynatish",
    retry_playback_hint: "Qayta urinish uchun «O'ynatish»ni bosing.",
    cancel_playback: "O'ynatishni bekor qilish",
    play_pause_hint: "O'ynatish / pauza",
    to_start_hint: "Boshiga o'tish",
    to_end_hint: "Oxiriga o'tish",
    timecode_label: "Joriy vaqt",
    timecode_edit_hint: "Tahrirlash uchun bosing · Enter — o'tish · Esc — bekor qilish",
    dropped_frames_one:
      "O'ynatish paytida {{count}} kadr tushib qoldi — dekodlash ulgurmadi",
    dropped_frames_other:
      "O'ynatish paytida {{count}} kadr tushib qoldi — dekodlash ulgurmadi",
    late_frames_one:
      "O'ynatish paytida {{count}} kadr kechikdi — render to'xtab qoldi",
    late_frames_other:
      "O'ynatish paytida {{count}} kadr kechikdi — render to'xtab qoldi",
  },
  export: {
    cancelling: "Eksport bekor qilinmoqda…",
    action_failed: "Amalni yakunlab bo'lmadi. Texnik tafsilotlarni tekshirib, qayta urining.",
    pending_title: "Eksport e'tiboringizni talab qiladi",
    phase_prepare: "Media tayyorlanmoqda…",
    failure_hint: "Eksportni yakunlab bo'lmadi. Texnik tafsilotlarni tekshiring, muammoni hal qiling va qayta eksport qiling.",
    change_filename: "Fayl nomini o'zgartirish",
    keep_filename: "Asl fayl nomini qoldirish",
    new_filename: "Yangi fayl nomi",
    filename_hint: "Fayl kengaytmasini saqlang. Yangi nom qayta urinishda qo'llanadi.",
    retry_filename: "Qayta urinish uchun fayl nomi (kengaytmasi bilan; bo'sh qolsa, joriy nom qoladi)",
    plan_resources: "Eksport talablari tekshirilmoqda",
    wait_resources: "Boshqa jarayonlar resurslarni bo'shatishi kutilmoqda",
    wait_memory: "Xotira bo'shashi kutilmoqda",
    resource_budget: "Bu eksportga joriy chegaradan ko'proq xotira kerak, hatto buferni kamaytirganda ham. Sozlamalar > Unumdorlik bo'limida xotira chegarasini oshiring va qayta urining. Eksport sifati o'zgartirilmadi.",
    resource_pressure: "Bo'sh xotira kam. Boshqa dasturlarni yoping yoki xotira bo'shashini kuting, keyin qayta urining.",

    title: "Eksport",
    phase_encode: "Kodlash",
    starting: "Eksport boshlanmoqda…",
    preparing:
      "{{labels}} uchun optimallashtirilgan media tayyorlanmoqda — eksport avtomatik boshlanadi.",
    preparing_cancel: "Bekor qilish",
    failed_prepare:
      "{{labels}}ni eksportga tayyorlab bo'lmadi — fayl buzilgan yoki qo'llab-quvvatlanmaydi. Uni qayta qo'shib, yana urinib ko'ring.",
    failed_audio_fx:
      "«{{layer}}» klipidagi «{{effect}}» ovoz effekti: {{message}}",
    failed_audio_fx_chain: "«{{layer}}» klipidagi ovoz effektlari: {{message}}",
    no_video_material:
      "Eksport uchun video yo'q: tanlangan oraliqda ko'rinadigan klip yo'q.",
    no_audio_material:
      "Eksport uchun ovoz yo'q: tanlangan oraliqda ovoz yo'q.",
    progress_label:
      "{{percent}}% · kadr {{frame}} · {{fps}}fps · {{speed}}x",
    phase_finalize: "Yakunlanmoqda",
    finalize_sink: "Kodlovchi tugatilmoqda…",
    finalize_audio: "Ovoz tayyorlanmoqda…",
    prepare_audio: "Ovoz",
    retry_finalize: "Eksportni yakunlashga qayta urinish",
    discard_pending: "Eksportni bekor qilish",
    retry_hint: "Qayta kodlamasdan eksportni yakunlashga urinib ko'ring. Loyihani yopsangiz yoki bu eksportni bekor qilsangiz, uning vaqtinchalik fayllari o'chiriladi.",
    finalize_mux: "Natija fayli yozilmoqda…",
    complete: "{{path}} ga eksport qilindi",
    failed: "Eksport bajarilmadi: {{detail}}",
    resource_unavailable: "Eksportni yakunlash uchun resurslar yetarli emas. Boshqa jarayonlar tugashini kuting va qayta urining. Yana xato bo'lsa, Sozlamalar > Unumdorlik bo'limida xotira chegarasini oshiring.",
    open_settings: "Sozlamalarni ochish",
    technical_details: "Texnik tafsilotlar",
    dismiss: "Yopish",
    play: "O'ynatish",
    play_hint: "Eksport qilingan faylni «Render va o'ynatish» oynasida ochish.",
    // Named per OS the way Premiere / Resolve label it (see ExportPanel's
    // REVEAL_KEY); Linux has no single file manager to name, and does not
    // select the file (main/openPath.ts), so its label promises less.
    reveal_windows: "Explorer'da ko'rsatish",
    reveal_mac: "Finder'da ko'rsatish",
    reveal_linux: "Jildda ko'rsatish",
    reveal_hint: "Eksport qilingan fayl joylashgan jildni ochish.",
    render_play_title: "Lahza Studio — Render va o'ynatish",
    notify_done_title: "Eksport tugadi",
    notify_done_body: "{{path}} ga saqlandi",
    notify_failed_title: "Eksport bajarilmadi",
    notify_failed_body: "{{detail}}",
  },
  export_presets: {
    default_badge: "Standart",
    set_default: "Standart qilib belgilash",
    is_default: "Yangi loyihalar uchun standart",
    empty_short: "Hali shaxsiy andozalar yo'q",
    "preset": "Andoza",
    "builtins": "Tayyor andozalar",
    "personal": "Mening andozalarim",
    "builtin_match": "Loyihaga mos",
    "builtin_hd": "720p HD gorizontal",
    "builtin_fullhd": "1080p Full HD gorizontal",
    "builtin_uhd": "4K UHD gorizontal",
    "name": "Andoza nomi",
    "save": "Saqlash",
    "save_as": "Andoza sifatida saqlash…",
    "rename": "Nomini o'zgartirish…",
    "delete": "O'chirish",
    "custom": "Maxsus",
    "modified_badge": "(o'zgartirilgan)",
    "restore": "Tiklash",
    "update": "Andozani yangilash",
    "save_failed": "Andozani saqlab bo'lmadi. Nomi takrorlanmasligini va andoza hali mavjudligini tekshirib, qayta urining.",
    "duplicate_name": "Bunday nomli andoza allaqachon bor.",
    "invalid": "Eksport sozlamalarini tekshiring: {{reason}}"
},
  export_dialog: {
    file_exists: "Bunday nomli fayl allaqachon bor",
    use_available_name: "«{{name}}» nomini ishlatish",
    path_check_failed: "Bunday nomli fayl bor-yo'qligini tekshirib bo'lmadi.",
    check_again: "Qayta tekshirish",
    overwrite_completed: "Eksportda bir xil nomli fayllarni avtomatik almashtirish",
    overwrite_save_failed: "Almashtirish sozlamasini saqlab bo'lmadi. Qayta urinib ko'ring.",
    title: "Eksport sozlamalari",
    cat_general: "Umumiy",
    cat_video: "Video",
    cat_audio: "Ovoz",
    cat_subtitle: "Subtitr",
    subtitle_placeholder: "Subtitr eksporti tez orada qo'shiladi.",
    content: "Eksport tarkibi",
    include_video: "Videoni qo'shish",
    include_audio: "Ovozni qo'shish",
    content_none: "Eksport uchun kamida video yoki ovozni tanlang.",
    video_excluded:
      "Bu eksportga video kirmaydi. Uni qo'shish uchun «Umumiy» bo'limida «Eksport tarkibi»ni o'zgartiring.",
    audio_excluded:
      "Bu eksportga ovoz kirmaydi. Uni qo'shish uchun «Umumiy» bo'limida «Eksport tarkibi»ni o'zgartiring.",
    resolution: "O'lcham (piksel)",
    fps: "Kadr tezligi",
    follow_comp: "Taymlayn bo'yicha",
    codec: "Kodek",
    container: "Konteyner / Muxer",
    encoder_engine: "Kodlash dvigateli",
    engine_auto: "Avtomatik",
    engine_native: "Mahalliy (FFmpeg)",
    engine_webcodecs: "WebCodecs",
    path_native: "Kodlovchi: mahalliy FFmpeg (to'liq boshqaruv, aniq rang teglari)",
    path_webcodecs: "Kodlovchi: WebCodecs (imkon bo'lsa, apparat orqali)",
    // Engine option labels + unavailable reason reuse settings.decode_engine_*
    // so preview and export read identically.
    decode_engine: "Dekodlash dvigateli",
    decode_summary:
      "Dekodlash: {{originals}} ta manba asl fayldan, {{proxy}} ta yengil nusxadan (proxy)",
    checking_codec: "Kodek qo'llab-quvvatlanishi tekshirilmoqda…",
    codec_unsupported:
      "{{codec}} bu kompyuterda kodlanmaydi — boshqa kodek tanlang.",
    prores_profile: "ProRes profili",
    dnxhr_profile: "DNxHR profili",
    quality: "Sifat",
    quality_low: "Past",
    quality_medium: "O'rta",
    quality_high: "Yuqori",
    quality_custom: "Maxsus",
    target_bitrate: "Maqsadli bitreyt",
    max_bitrate: "Maksimal bitreyt",
    max_bitrate_unlimited:
      "Cho'qqi cheklanmagan — murakkab sahnalarda kodlovchi maqsaddan ancha oshib ketishi mumkin. Cheklash uchun maksimumni belgilang.",
    max_bitrate_below_target:
      "Maksimum kamida maqsadli bitreytga teng bo'lishi kerak. Undan past bo'lsa, kodlovchi maqsadni tashlab, faylni maksimumda chiqaradi.",
    buffer_size: "Bufer hajmi",
    buffer_size_auto:
      "Bufer chegaraga qarab belgilanadi (2×). Kichik bufer chegaraga qattiqroq amal qiladi, lekin sifat ko'proq o'zgaradi; kattasi erkinroq.",
    cbr_hint:
      "CBR bu bitreytni butun video davomida ushlab turadi: maksimum va minimum unga teng, shuning uchun sifat sahna murakkabligiga qarab o'zgaradi.",
    rate_constraints_native_only:
      "Maksimal bitreyt va bufer hajmi uchun mahalliy FFmpeg kodlovchisi kerak — WebCodecs faqat maqsadli bitreytni beradi.",
    mbps: "Mbps",
    mbit: "Mbit",
    rate_mode: "Bitreyt boshqaruvi",
    rate_vbr: "VBR (o'zgaruvchan)",
    rate_cbr: "CBR (doimiy)",
    rate_quality: "Sifat (CRF)",
    crf: "CRF",
    keyframe_interval: "Kalit kadr oralig'i",
    encoder_accel: "Video kodlovchi",
    encoder_auto: "Avtomatik (apparat afzal)",
    encoder_software: "Dasturiy",
    speed_preset: "Kodlovchi andozasi",
    preset_fast: "Tez",
    preset_medium: "O'rta",
    preset_slow: "Sekin (eng yaxshi sifat/hajm)",
    location: "Joylashuv",
    filename: "Fayl nomi",
    choose_location: "Saqlash jildini tanlang",
    browse: "Tanlash…",
    cancel: "Bekor qilish",
    export: "Eksport",
    range: "Oraliq",
    range_full: "Butun loyiha",
    range_marked: "Boshlanish/tugash oralig'i",
    range_marked_none:
      "Taymlaynda boshlanish/tugash nuqtalari belgilanmagan. Oraliqni tezkor amallar paneli yoki I / O tugmalari bilan belgilang.",
    range_custom: "Maxsus",
    range_in: "Boshi",
    range_out: "Oxiri",
    range_invalid:
      "Bu oraliq bo'sh yoki butunlay loyihadan tashqarida. Boshlanish va tugash nuqtalarini tekshiring.",
    audio_codec: "Ovoz kodeki",
    audio_bitrate: "Ovoz bitreyti",
    audio_channels: "Kanallar",
    audio_sample_rate: "Diskretlash chastotasi",
    channels_mono: "Mono",
    channels_stereo: "Stereo",
    bit_depth: "Bit chuqurligi",
    bit_depth_8: "8-bit",
    bit_depth_10: "10-bit (HEVC Main10 / AV1) — tajribaviy",
    bit_depth_hint: "Taymlaynda 10-bitli manbalar bor — 10-bitli natija ularning aniqligini saqlaydi.",
    bit_depth_experimental_warning:
      "10-bitli eksport tajribaviy. Ko'rish oynasi oddiy 8-bitda ko'rsatadi, shuning uchun ekrandagi ranglar va gradiyentlar yakuniy 10-bitli faylga mos kelmasligi mumkin — HDR / keng rang gammasini ko'rish hozircha veb-platformada imkonsiz. Bundan tashqari, u real vaqtdan ancha sekin ishlaydi va ba'zi manbalarda xato berishi yoki noto'g'ri natija chiqarishi mumkin.",
    experimental_title: "10-bitli eksport tajribaviy",
    experimental_body:
      "Bu funksiya hali tajribaviy va xato berishi yoki noto'g'ri natija chiqarishi mumkin:",
    experimental_point_preview:
      "Ko'rish oynasi 8-bit/SDR'da ko'rsatadi va haqiqiy 10-bitli natijaga mosligini kafolatlab bo'lmaydi — rang, gradiyentlar va HDR farq qilishi mumkin.",
    experimental_point_slow:
      "Dasturiy 10-bitli dekodlash real vaqtdan ancha sekin — 4K yoki uzun loyihalar juda sekin bo'lishi mumkin.",
    experimental_point_reliability:
      "Ba'zi manbalar (masalan, HEVC Main10 asl fayllari) qayta kodlanadi va kamroq ishonchli bo'lishi mumkin.",
    experimental_proceed: "Baribir eksport qilish",
    native_unavailable_fallback:
      "Mahalliy FFmpeg kodlovchisi mavjud emas. O'rniga WebCodecs kodlovchisi bilan eksport qilinsinmi? (Faqat bitreyt rejimi; rang teglari standart qiymatda.)",
    native_unavailable_no_fallback:
      "Mahalliy FFmpeg kodlovchisi mavjud emas va bu format uchun WebCodecs muqobili yo'q.",
  },
  app_notice: {
    dismiss: "Tushunarli",
    keyring_unavailable: {
      title: "Bulut API kalitlari shifrlanmagan",
      body: "Tizim kalitlar ombori (keyring) topilmadi, shuning uchun bulut API kalitlari diskka shifrlanmasdan saqlanadi (cloud_keys.json). Kalitlar omborini o'rnating (masalan, GNOME Keyring / KWallet) yoki foydalanuvchi ma'lumotlari jildini himoyalang.",
      action: "API kalit sozlamalarini ochish",
    },
    native_decode_unavailable: {
      title: "Mahalliy dekodlash dvigateli mavjud emas",
      body: "Mahalliy dekodlash komponenti (@weftcut/native-decode) yuklanmadi, shuning uchun ko'rish oynasi faqat WebCodecs dvigatelidan foydalanadi. Uni tiklash uchun dasturni qayta o'rnating.",
      action: "Dekodlash sozlamalarini ochish",
    },
    agent_skill_unavailable: {
      title: "AI yordamchi Skill'i yo'q",
      body: "Ulangan AI yordamchiga Lahza Studio bilan ishlashni o'rgatadigan Skill o'rnatilmadi, shuning uchun yordamchingizga beradigan narsa yo'q. Uni tiklash uchun dasturni qayta o'rnating.",
      action: "AI yordamchi sozlamalarini ochish",
    },
    agent_skill_stale: {
      title: "AI yordamchi Skill'i eskirgan",
      body: "Lahza Studio AI yordamchi Skill'ini yangilay olmadi, shuning uchun taklif qilinayotgan nusxa oldingi versiyadan qolgan. Undan foydalanadigan yordamchi bu versiyada endi yo'q vositalarni chaqirishi mumkin.",
      action: "AI yordamchi sozlamalarini ochish",
    },
  },
  // Codec-named optimization reasons, shown in Media Pool badge tooltips.
  import_proxy: {
    checking_one: "Bu klip tekshirilmoqda…",
    reason_undecodable: "{{codec}} · bu kompyuterda dekodlanmaydi",
    reason_transcode: "{{codec}} · qayta kodlash kerak",
    reason_10bit: "{{codec}} 10-bit/HDR · optimallashtirish kerak",
    reason_bridged: "{{codec}} · hozir ishlatsa bo'ladi, fonda optimallashtirilmoqda",
    failed: "Tayyorlash bajarilmadi — qayta urinish uchun qayta qo'shing",
    failed_log: "«{{label}}»ni optimallashtirib bo'lmadi — qayta urinish uchun uni qayta qo'shing.",
  },
  motif_stale: {
    title: "Motiflar siz joylashtirgandan keyin o'zgardi",
    entry: "v{{from}} → v{{to}} ({{n}} ta klip)",
    note: "Bu kliplar allaqachon joriy versiya bilan chiqadi — bu shunchaki eslatma.",
    dismiss: "Tushunarli",
  },
  connect: {
    blurb:
      "Tashqi AI yordamchini (agent) Lahza Studio'ning mahalliy MCP serveriga ulang — u loyihangizni to'g'ridan-to'g'ri o'qiy va tahrirlay oladi.",
    starting: "MCP server ishga tushmoqda…",
    copy: "Sozlamani nusxalash",
    copied: "Nusxalandi!",
    copy_prompt: "Sozlash so'rovini nusxalash",
    prompt_copied: "So'rov nusxalandi!",
    prompt_heading: "AI yordamchi o'zini o'zi sozlasin",
    prompt_blurb:
      "MCP'ni qo'llaydigan yordamchilar uchun: so'rovni chatga qo'ying — u MCP ulanishini sozlaydi va Skill'ni o'rnatadi. Skill har bir relizda yangilanadi, shuning uchun har yangilanishdan keyin qayta o'rnatish tavsiya etiladi.",
    manual_heading: "Inson ekaningizni tasdiqlang",
    skill_path_heading: "Skill jildi joylashuvi",
    skill_path_unavailable:
      "Ochiladigan Skill jildi yo'q — yuqoridagi «AI yordamchi o'zini o'zi sozlasin» bo'limiga qarang.",
    skill_stale:
      "Oldingi ishga tushirishdan qolgan nusxa ko'rsatilmoqda, u Lahza Studio'ning bu versiyasidan eskiroq bo'lishi mumkin.",
    skill_retry: "Qayta urinish",
    skill_retrying: "O'rnatilmoqda…",
    skill_fault: {
      not_built:
        "Bu ishlab chiqish yig'masida hali Skill tayyorlanmagan. «npm run build:skills» buyrug'ini bajarib, qayta ishga tushiring.",
      bundle_missing:
        "Lahza Studio'ning bu o'rnatmasi bilan Skill kelmagan. Uni tiklash uchun dasturni qayta o'rnating.",
      incomplete:
        "Lahza Studio bilan kelgan Skill to'liq emas. Uni tiklash uchun dasturni qayta o'rnating.",
      copy_failed:
        "Lahza Studio Skill'ni foydalanuvchi ma'lumotlari jildiga yoza olmadi. Diskdagi bo'sh joyni va jild ruxsatlarini tekshirib, qayta ishga tushiring.",
    },
    copy_path: "Yo'lni nusxalash",
    browse: "Ochish…",
    // The Browse button's tooltip — Windows' own Explorer wording, and true on
    // all three: the file manager comes up on the folder (selected where the
    // platform can — see main/openPath.ts).
    open_location: "Fayl joylashuvini ochish",
    agent_prompt: [
      "Men uchun Lahza Studio MCP serverini sozla. Sozlamani bevosita o'zgartir; faqat qadamlarni tasvirlab berma.",
      "",
      "Ulanish ma'lumotlari:",
      "- Server nomi: weftcut",
      "- Transport: streamable HTTP",
      "- URL: {{url}}",
      "- Authorization sarlavhasi: Bearer {{token}}",
      "",
      "Talablar:",
      "- Mijozingning rasmiy MCP sozlama formati va joylashuvidan foydalan.",
      "- Avval mavjud sozlamani tekshir va boshqa barcha sozlamalar hamda MCP serverlarni saqlab qol.",
      "- Faqat «weftcut» nomli MCP serverni qo'sh yoki yangila; butun sozlama faylini almashtirma.",
      "- Bearer tokenni maxfiy saqla va javobingda uni takrorlama.",
      "- Hosil bo'lgan sozlama sintaksisini tekshir. Agar mijozni qayta ishga tushirish kerak bo'lsa, menga ayt.",
      "- Qaysi faylni o'zgartirganingni va sozlama to'g'riligini xabar qil.",
    ].join("\n"),
    agent_prompt_stdio: [
      "Men uchun Lahza Studio MCP serverini sozla. Sozlamani bevosita o'zgartir; faqat qadamlarni tasvirlab berma.",
      "",
      "Ulanish ma'lumotlari:",
      "- Server nomi: weftcut",
      "- Transport: stdio (mahalliy buyruq)",
      "- Buyruq: {{command}}",
      "- Argumentlar: {{args}}",
      "- Muhit (env): ELECTRON_RUN_AS_NODE=1, WEFTCUT_USERDATA={{userData}}",
      "",
      "Talablar:",
      "- Mijozingning rasmiy MCP sozlama formati va joylashuvidan foydalan.",
      "- Avval mavjud sozlamani tekshir va boshqa barcha sozlamalar hamda MCP serverlarni saqlab qol.",
      "- Faqat «weftcut» nomli MCP serverni qo'sh yoki yangila; butun sozlama faylini almashtirma.",
      "- Buyruq, argumentlar va env qiymatlarini aynan berilganidek qoldir — ular shu kompyuterga xos yo'llar.",
      "- Hosil bo'lgan sozlama sintaksisini tekshir. Agar mijozni qayta ishga tushirish kerak bo'lsa, menga ayt.",
      "- Qaysi faylni o'zgartirganingni va sozlama to'g'riligini xabar qil.",
    ].join("\n"),
    // The second half of the setup prompt, appended after whichever MCP block
    // applies. It stands on its own so the message still reads when there is no
    // staged Skill folder to hand over and this half is left out.
    agent_prompt_skill: [
      "Keyin Lahza Studio Skill'ini o'rnat — bu dastur bilan birga keladigan foydalanish yo'riqnomasi.",
      "",
      "- «{{folder}}» jildini o'zingning skills jildingga nusxala, jild nomini weftcut qoldir. Claude Code uchun bu ~/.claude/skills/weftcut.",
      "- U yerda turgan har qanday nusxani almashtir; u Lahza Studio'ning eski versiyasiga tegishli.",
      "- Skill joyiga tushgach, uni bir marta o'qib chiq va Lahza Studio loyihasi ustida ishlaganda doim unga amal qil.",
      "- Uni qayerga o'rnatganingni xabar qil.",
    ].join("\n"),
    reveal: "Tokenni ko'rsatish",
    hide: "Tokenni yashirish",
    refresh: "Tokenni yangilash",
    refreshing: "Yangilanmoqda…",
    refresh_hint: "Yangi bearer token yaratib, uni saqlash",
    refresh_confirm:
      "Yangi bearer token yaratilsinmi? Joriy tokendan foydalanayotgan har bir AI yordamchining sozlamasini yangilash kerak bo'ladi.",
    token_note:
      "MCP so'rovlari tokenni o'z ichiga olishi shart, server esa faqat mahalliy foydalanish uchun ochiq. Token mcp_auth.json faylida saqlanadi — agar u oshkor bo'lsa, «Tokenni yangilash» orqali almashtiring.",
    snippets_heading: "Mijoz sozlamasi namunalari",
    stdio_note:
      "Bu sozlama uzoq vaqt amal qiladi: dasturni qayta ishga tushirish, port yoki token o'zgarishi hech qanday tahrir talab qilmaydi. AI yordamchilar Lahza Studio yopiq bo'lganda ham ulanib, uni o'zi ishga tushira oladi.",
    http_heading: "To'g'ridan-to'g'ri HTTP (kengaytirilgan)",
    http_note:
      "Ishlab turgan dasturga to'g'ridan-to'g'ri ulanadi. Dastur yopilganda ulanish uziladi, port yoki token o'zgarganda sozlama yaroqsiz bo'ladi. Mijozingiz stdio'ni qo'llamasa bo'lmasa, yuqoridagi sozlamadan foydalaning.",
    cli_note: "Yoki terminalda quyidagi buyruqni bajaring",
    copy_command: "Buyruqni nusxalash",
    tabs: {
      codex: "Codex",
      claude: "Claude",
      cursor: "Cursor",
      generic: "Umumiy",
    },
    hint: {
      codex: "~/.codex/config.toml fayliga qo'ying",
      claude: ".mcp.json (loyiha) yoki ~/.claude.json fayliga qo'ying",
      cursor: "~/.cursor/mcp.json yoki loyihaning .cursor/mcp.json fayliga qo'ying",
      generic:
        "Ulanish ma'lumotlari — har bir qiymatni to'ldirish uchun mijozingiz hujjatlariga qarang.",
    },
    hint_stdio: {
      codex: "~/.codex/config.toml fayliga qo'ying",
      claude: ".mcp.json (loyiha) yoki ~/.claude.json fayliga qo'ying",
      cursor: "~/.cursor/mcp.json yoki loyihaning .cursor/mcp.json fayliga qo'ying",
      generic:
        "Ulanish ma'lumotlari — har bir qiymatni to'ldirish uchun mijozingiz hujjatlariga qarang.",
    },
  },
  settings: {
    auto_install_updates_on_quit: "Dastur yopilganda mavjud yangilanishlarni avtomatik o'rnatish",
    auto_install_updates_on_quit_hint: "Yoqilganda yangilanishlar fonda yuklab olinadi va chiqishda o'rnatiladi. O'chirilganda yangilanishlar faqat «Yuklab olish va o'rnatish»ni tanlaganingizda yuklanadi.",
    layout_theme: "Joylashuv mavzusi",
    layout_theme_hint: "Tayyor matn o'lchamlari va oyna o'lchamlarini qo'llash. Keng joylashuvlar gorizontal bo'yicha ko'proq joy va biroz kattaroq matn beradi.",
    layout_theme_recommended: "Tavsiya etiladi",
    layout_theme_recommended_detail: "Bu ekranga mos: {{width}}×{{height}}, {{scale}}% masshtab",
    layout_themes: {
      '1080p-standard': "1080p · Standart",
      '1080p-wide': "1080p · Keng",
      '2k-standard': "2K (1440p) · Standart",
      '2k-wide': "2K (1440p) · Keng",
      '4k-standard': "4K · Standart",
      '4k-wide': "4K · Keng",
    },
    default_text_font: "Standart matn shrifti",
    default_text_font_hint: "Matn qo'shilganda ishlatiladigan standart shrift. Shriftlarni operatsion tizim orqali o'rnating, so'ng ro'yxatni yangilash uchun Lahza Studio'ni qayta ishga tushiring.",
    heading: "Sozlamalar",
    cat_general: "Umumiy",
    cat_project: "Loyiha",
    cat_keyboard: "Klaviatura",
    cat_speech: "Transkripsiya",
    cat_vlm: "Videoni tushunish",
    cat_agent: "AI yordamchi",
    project_scope_blurb:
      "Bu sahifadagi sozlamalar faqat joriy loyihaga taalluqli va loyiha fayli bilan birga saqlanadi.",
    preferences_heading: "Asosiy",
    reopen_on_launch: "Oxirgi loyihani avtomatik ochish",
    reopen_on_launch_hint:
      "Yoqilganda Lahza Studio boshlang'ich ekranni o'tkazib, oxirgi ishlatilgan loyihani avtomatik ochadi.",
    canvas_heading: "Kanvas",
    canvas_blurb:
      "Bu loyihaning tahrirlash va ko'rish o'lchami hamda taymlayn kadr tezligi.",
    canvas_lock: "Kanvas sozlamalarini qulflash",
    canvas_lock_hint:
      "Kanvas sozlamalari tahrir emas, loyiha sozlamasi — ularni bekor qilib bo'lmaydi.",
    canvas_resolution: "O'lcham (piksel)",
    canvas_resolution_custom: "Maxsus",
    canvas_custom_size: "Maxsus o'lcham",
    canvas_width: "Kenglik",
    canvas_height: "Balandlik",
    canvas_apply: "Qo'llash",
    canvas_fps: "Kadr tezligi",
    canvas_fps_hint:
      "Kadr tezligini faqat taymlaynida hech qachon kontent bo'lmagan loyihada o'zgartirish mumkin.",
    duration_heading: "Davomiylik",
    duration_blurb:
      "Davomiylik odatda oxirgi ko'rinadigan kadrgacha bo'ladi. Kontentdan uzunroq qat'iy vaqt kerak bo'lsa, uni uzaytiring.",
    pin_composition_duration: "Davomiylikni uzaytirish",
    pin_composition_duration_hint:
      "Uni quyidagi qiymatda ushlab turadi. Faqat ≥ {{floor}} (kontent oxiri) qilib belgilash mumkin.",
    composition_duration_label: "Davomiylik",
    composition_duration_below_floor: "≥ {{floor}} (kontent oxiri) bo'lishi kerak.",
    duration_wall_clock:
      "Bu tezlik non-drop-frame: {{tc}} real vaqtda {{wall}} ga teng.",
    content_end_wall_clock: "Kontent oxiri {{tc}} — {{wall}}.",
    timeline_heading: "Taymlayn",
    timeline_wheel_axis: "Sichqoncha g'ildiragi aylantiradi",
    timeline_wheel_axis_horizontal: "Vaqt bo'yicha (gorizontal)",
    timeline_wheel_axis_vertical: "Yo'laklar bo'yicha (vertikal)",
    timeline_wheel_axis_hint:
      "Shift+g'ildirak doim boshqa o'q bo'yicha aylantiradi. Ctrl+g'ildirak va Alt+g'ildirak kattalashtiradi.",
    auto_delete_empty_tracks: "Bo'sh yo'laklarni avtomatik o'chirish",
    auto_delete_empty_tracks_hint:
      "Oxirgi klipi ko'chirilgan yoki o'chirilgan yo'lakni olib tashlash. Bo'sh yo'laklarni saqlash uchun o'chiring; zaxiralangan va qulflangan yo'laklar doim qoladi. Barcha loyihalarga taalluqli.",
    tail_snap_enabled: "Kliplarni yopishtirish",
    tail_snap_enabled_hint:
      "Sudrash yoki qisqartirish paytida kliplarni yaqin klip chetlariga yoki o'ynatish ko'rsatkichiga yopishtirish.",
    tail_snap_strength: "Yopishish kuchi",
    tail_snap_strength_hint:
      "Ekran piksellarida o'lchanadi.",
    playback_heading: "O'ynatish",
    prefer_proxies: "Ko'rishda yengil nusxalarni (proxy) afzal ko'rish",
    prefer_proxies_hint:
      "Silliqroq aylantirish uchun yengil 720p nusxasi bor kliplarni ko'rish oynasida o'sha nusxa bilan o'ynatish. Eksport baribir asl fayldan foydalanadi.",
    decode_unsupported_generate_proxy: "Yengil nusxa (proxy) yaratish",
    keybindings_blurb:
      "Klaviatura tugmalari sozlamalari jadvalini boshqaring.",
    placeholder_set: "Kalitni almashtirish…",
    placeholder_unset: "API kalitini qo'ying",
    speech_blurb:
      "Ovoz va videodagi nutqni subtitr va media qidiruvi uchun matnga aylantiradi. Mahalliy modellar va onlayn xizmatlarni qo'llaydi.",
    speech_binary: "Dastur fayli",
    speech_model: "Model",
    speech_tokens: "Tokenlar",
    speech_device: "Qurilma",
    speech_threads: "Oqimlar",
    speech_browse: "Tanlash…",
    vlm_blurb:
      "AI mediangizni tushunishi va qidirishi uchun video kadrlarni tasvirlaydi. Mahalliy modellar va onlayn xizmatlarni qo'llaydi.",
    // Named for what it controls rather than for the wire field (`fps`): what a
    // user is choosing is how closely the model looks — so the unit has to ride
    // in the row, beside the number, or nothing on screen says what the count
    // counts.
    vlm_sampling: "Namuna",
    vlm_sampling_unit: "fps",
    vlm_sampling_hint:
      "Klip bo'ylab soniyasiga olinadigan kadrlar soni — ko'proq bo'lsa, aniqroq, lekin sekinroq.",
    vlm_focus: "E'tibor",
    vlm_focus_general: "Umumiy sahna",
    vlm_focus_shot_type: "Sahna turi va kamera",
    vlm_focus_hint:
      "Teglar nimaga ko'proq qaratiladi. Matnli tavsif har holda sahnani tasvirlaydi.",
    // Worded by VIEW rather than by the two controls beside it: the engine, the
    // model and the interface language key the same cache, and naming only these
    // two would leave a language switch looking like lost data.
    vlm_view_note:
      "Tavsiflar dvigatel, model, namuna, e'tibor va interfeys tili bo'yicha keshlanadi. Ulardan birini o'zgartirsangiz, boshqa tavsif ko'rinishiga o'tiladi, mavjudi esa saqlanadi — qaytsangiz, u joyida turadi.",
    vlm_mmproj: "Proyektor",
    vlm_endpoint_url: "URL",
    vlm_endpoint_model: "Model",
    content_whisper_runtime: "whisper.cpp dvigateli (v1.9.1)",
    content_whisper_model_base: "Whisper Base modeli (ko'p tilli)",
    content_funasr_runtime: "sherpa-onnx dvigateli (v1.13.4)",
    content_funasr_model_paraformer: "Paraformer-zh modeli (xitoy tili)",
    content_llama_mtmd_runtime: "llama.cpp dvigateli (b10103, Vulkan)",
    content_qwen3vl_model: "Qwen3-VL 4B modeli (Q4_K_M)",
    content_qwen3vl_mmproj: "Qwen3-VL ko'rish proyektori (F16)",
    content_prereq_msvc14:
      "Microsoft Visual C++ 2015–2022 x64 runtime kerak (odatda allaqachon o'rnatilgan bo'ladi).",
    prebake_motifs: "Motiflarni oldindan tayyorlash",
    prebake_motifs_hint:
      "Motif kadrlarini fonda diskka tayyorlab qo'yadi. O'ynatish silliqroq, qayta ochish bir zumda; loyiha keshida disk joyini egallaydi.",
    preview_heading: "Ko'rish oynasi",
    preview_snap_enabled: "Kanvasga yopishtirish",
    preview_snap_enabled_hint:
      "Ko'rish oynasida kliplarni ko'chirish yoki o'lchamini o'zgartirishda ularni kadr chetlari, markaz chiziqlari va boshqa kliplarga tekislash. Bekor qilish uchun Ctrl'ni bosib turing.",
    preview_snap_strength: "Yopishish kuchi",
    preview_snap_strength_hint:
      "Ekran piksellarida o'lchanadi.",
    decode_engine: "Dekodlash dvigateli",
    decode_engine_auto: "Avtomatik",
    decode_engine_auto_desc: "Har bir klip uchun eng mos dvigatelni tanlaydi",
    decode_engine_ffmpeg: "Standart",
    decode_engine_ffmpeg_tag: "ffmpeg",
    decode_engine_ffmpeg_desc: "Barcha formatlarni dekodlaydi, ranglar aniq",
    decode_engine_webcodecs: "Yengil",
    decode_engine_webcodecs_tag: "webcodecs",
    decode_engine_webcodecs_desc: "Resurslarni kamroq talab qiladi; kamroq formatlarni qo'llaydi; ranglar biroz farq qilishi mumkin",
    decode_engine_unavailable: "Standart dvigatel mavjud emas: {{reason}}",
    decode_engine_unavailable_suffix: "mavjud emas",
    playback_resolution: "O'ynatish sifati",
    playback_resolution_full: "To'liq",
    playback_resolution_half: "1/2",
    playback_resolution_quarter: "1/4",
    playback_resolution_smooth: "Silliq",
    playback_resolution_sharp: "Aniq",
    playback_resolution_export_note: "Eksport doim to'liq o'lchamda tayyorlanadi.",
    decode_unsupported_title: "Format qo'llab-quvvatlanmaydi",
    decode_unsupported_body:
      "Yengil dvigatel bu klipni dekodlay olmaydi. Uni o'ynatish uchun Standart dvigatelga o'ting.",
    decode_unsupported_switch: "Standartga o'tish",
    decode_unsupported_body_no_component:
      "Bu klip formati Yengil dvigatelda qo'llanmaydi, Standart dvigatel esa o'rnatilmagan.",
    data_location_heading: "Ma'lumotlar joylashuvi",
    data_location_blurb:
      "Lahza Studio katta fayllarini saqlaydigan joy. Motiflaringiz, qisman keshlar va yuklab olingan fayllar shu yerda saqlanadi.",
    data_location_current_label: "Joriy jild",
    data_location_fallback:
      "Zaxira joy — siz tanlagan jild mavjud emas edi, shuning uchun standart jild ishlatilmoqda.",
    data_location_change: "O'zgartirish…",
    data_location_open_folder: "Jildni ochish",
    data_location_working: "Tayyorlanmoqda…",
    data_location_phase_copy: "Fayllar nusxalanmoqda…",
    data_location_phase_verify: "Tekshirilmoqda…",
    data_location_phase_done: "Yakunlanmoqda…",
    data_location_progress_count: "{{copied}} / {{total}} ta fayl",
    data_location_success_copy:
      "Ma'lumotlaringiz {{path}} ga nusxalandi. Yangi joydan foydalanishni boshlash uchun Lahza Studio'ni qayta ishga tushiring.",
    data_location_success_adopt:
      "Lahza Studio {{path}} dagi mavjud ma'lumotlar jildidan foydalanadi. Qo'llash uchun qayta ishga tushiring.",
    data_location_restart: "Qo'llash uchun qayta ishga tushirish",
    data_location_error:
      "Ma'lumotlar jildini o'zgartirib bo'lmadi: {{message}} Ma'lumotlaringiz o'zgarishsiz qoldi.",
    data_location_cleanup_title: "Eski ma'lumotlar nusxasi o'chirilsinmi?",
    data_location_cleanup_body:
      "Lahza Studio endi yangi joyda ishlamoqda. {{path}} dagi oldingi nusxa endi ishlatilmaydi — joy bo'shatish uchun uni o'chiring yoki zaxira sifatida qoldiring.",
    data_location_cleanup_keep: "Qoldirish",
    data_location_cleanup_delete: "Eski nusxani o'chirish",
    data_location_cleanup_deleting: "O'chirilmoqda…",
  },
  keybindings: {
    add: "+ Qo'shish",
    no_binding: "(tugma belgilanmagan)",
    remove_hint: "Bu tugmani olib tashlash",
    reset: "Tiklash",
    reset_all: "Hammasini tiklash",
    export: "Eksport…",
    import: "Qo'shish…",
    export_title: "Klaviatura tugmalarini eksport qilish",
    import_title: "Klaviatura tugmalarini qo'shish",
    press_a_key: "Tugmani bosing…",
    conflict:
      "Bu tugma allaqachon {{action}} uchun belgilangan — avval uni olib tashlang.",
    reset_blocked:
      "Tiklab bo'lmaydi: {{chord}} {{action}} uchun belgilangan. Avval uni olib tashlang.",
  },
  colorpick: {
    pick: "Rang tanlash",
    hint_cancel: "Esc — bekor qilish",
    hint_screen: "S — ekrandan tanlash",
    screen_hint: "Ekran muzlatilgan · Tanlash uchun bosing yoki Enter · Strelka tugmalari — sozlash · Esc — bekor qilish",
    error_unsupported: "Bu ish stolida ekrandan rang tanlab bo'lmaydi. Muharrir ichida baribir tanlashingiz mumkin.",
    error_permission: "Muharrirdan tashqarida tanlash uchun tizim sozlamalarida ekranni yozishga ruxsat bering.",
    error_capture: "Ekranni olib bo'lmadi. Qayta urining yoki muharrir ichida tanlang.",
    error_effect_input: "O'ynatish ko'rsatkichida bu klipdan rang olib bo'lmaydi. Bekor qiling va ko'rinadigan kadrga o'ting yoki ekrandan tanlash uchun S ni bosing.",
    error_timeout: "Ekrandan tanlash vaqti tugadi. Qayta urining yoki muharrir ichida tanlang.",
  },
  effects: {
    heading: "Effektlar",
    empty: "Effektlarini tahrirlash uchun klipni tanlang.",
    add: "Effekt qo'shish",
    empty_chain: "Bu klipda hali effekt yo'q.",
    order_hint: "Yuqoridan pastga qo'llanadi.",
    drag_hint: "Tartibni o'zgartirish uchun sudrang",
    collapse: "{{name}}ni yig'ish",
    expand: "{{name}}ni yoyish",
    enable: "{{name}}ni yoqish/o'chirish",
    more: "{{name}} uchun boshqa amallar",
    move_up: "Yuqoriga",
    move_down: "Pastga",
    reset_params: "Parametrlarni tiklash",
    remove: "{{name}}ni olib tashlash",
    key_color: "Kalit rang",
    search_placeholder: "Effektlarni qidirish…",
    search_clear: "Qidiruvni tozalash",
    no_results: "Mos effekt topilmadi.",
    category: {
      blur: "Xiralashtirish",
      keying: "Fonni olib tashlash",
      color: "Rang",
      stylize: "Uslub",
      audio: "Ovoz",
    },
    audio: {
      select_region: "Hududni tanlash",
      select_region_too_short: "Bu klip filtr namuna oladigan eng qisqa hududdan ham qisqaroq.",
      source_in: "Manba boshi",
      source_out: "Manba oxiri",
      region_needed: "Namuna olish uchun klipda faqat shovqin bor hududni sudrab belgilang.",
      region_too_short: "Shovqin profilini aniqlash uchun namuna hududi juda qisqa.",
      region_offscreen: "Namuna hududi bu klip o'ynatadigan media qismidan tashqarida.",
      status: {
        pending: "Ishlanmoqda…",
        failed: "Xato: {{error}}",
      },
    },
    audio_denoise: {
      name: "Shovqinni kamaytirish",
      desc: "Doimiy fon shovqinini olib tashlash",
      params: {
        strength: "Kuchi",
        margin: "Sezgirlik",
        profile_in_us: "Namuna hududi boshi",
        profile_out_us: "Namuna hududi oxiri",
      },
    },
    blur: {
      name: "Xiralashtirish",
      desc: "Gauss bo'yicha yumshatish",
      params: { strength: "Kuchi" },
    },
    chromakey: {
      name: "Xromakey",
      desc: "Yashil/ko'k fonni olib tashlash",
      params: {
        keyR: "Kalit qizil",
        keyG: "Kalit yashil",
        keyB: "Kalit ko'k",
        balance: "Fon balansi",
        clipBlack: "Qora chegarasi",
        clipWhite: "Oq chegarasi",
        despill: "Rang to'kilishini tozalash",
        feather: "Chetni yumshatish",
        shrink: "Toraytirish",
        viewMatte: "Niqobni ko'rish",
      },
    },
    brightness: {
      name: "Yorqinlik",
      desc: "Ekspozitsiyani oshirish — qora qora bo'lib qoladi",
      params: { amount: "Miqdor" },
    },
    contrast: {
      name: "Kontrast",
      desc: "O'rta kulrang atrofida keskinlik",
      params: { amount: "Miqdor" },
    },
    saturation: {
      name: "To'yinganlik",
      desc: "Rang jadalligi, kulranggacha",
      params: { amount: "Miqdor" },
    },
    sharpen: {
      name: "Aniqlashtirish",
      desc: "Yumshoq yoki kichraytirilgan videoni tiniqlashtirish",
      params: { amount: "Miqdor" },
    },
  },
  property_panel: {
    // Spatial progress is a scalar track, displayed as a percentage.
    path_progress: "Yo'l bo'ylab harakat (%)",
    heading: "Xususiyatlar",
    empty: "Xususiyatlarini tahrirlash uchun klipni tanlang.",
    envelope: "Klip",
    timing: "Vaqt",
    flag_enabled: "Yoqilgan",
    source_media: "Manba: {{name}}",
    flag_disabled: "O'chirilgan",
    flag_locked: "Qulflangan",
    flag_unlocked: "Qulfdan chiqarilgan",
    track_locked_hint: "Yo'lak qulflangan. Klip vaqtini tahrirlash uchun qulfdan chiqaring.",
    appearance: "Ko'rinish",
    effects: "Effektlar",
    flip: "Aylantirish (ko'zgu)",
    horizontal: "Gorizontal",
    vertical: "Vertikal",
    fades: "Paydo bo'lish va so'nish",
    motif_management: "Motifni boshqarish",
    // A Motif `media` prop: pick a pool image, or a video and the frame to take.
    motif_media_none: "Rasm yo'q",
    motif_media_frame_at: "Kadr vaqti (s)",
    text_layout: "Matn qutisi va oraliqlar",
    text_outline: "Kontur",
    advanced: "Qo'shimcha",
    label: "Nomi",
    enabled: "Yoqilgan",
    audio_units_hint:
      "Ovoz tahrirlari aniq 48 kHz namunalarga tushadi, shuning uchun bu maydonlar kadrdan kichik vaqtlarni ko'rsatadi va qabul qiladi. Sudrash baribir kadrlarga yopishadi — maksimal kattalashtirishda namunalar 0.042 px kenglikda. Bir namuna siljitish uchun Alt+←/→, 1 ms uchun Alt+Shift+←/→ dan foydalaning.",
    t_start: "Boshlanish",
    t_start_hint: "Klipni davomiyligini saqlagan holda ko'chirish.",
    t_end: "Tugash",
    kind: "Turi",
    link_none: "Bog'lanmagan",
    link_of_one: "{{count}} ta klip bilan bog'langan",
    link_of_other: "{{count}} ta klip bilan bog'langan",
    // The Group section: the composition's own name, its frame size and length
    // (both read-only here — a Group's size is copied at pre-compose), and the
    // two navigation/structure buttons.
    group: "Guruh",
    group_name: "Nomi",
    group_size: "Guruh o'lchami",
    group_refs: "Havolalar",
    group_open: "Guruhni ochish",
    group_ungroup: "Guruhni tarqatish",
    // The media branch: what an imported file IS. Read-only — the pool's
    // context menu stays the one place its preview source is chosen.
    media_resolution: "O'lcham (piksel)",
    media_size: "Fayl hajmi",
    media_location: "Joylashuv",
    media_decode: "Dekodlash",
    media_codec: "Kodek",
    media_pix_fmt: "Piksel formati",
    media_color: "Rang",
    media_route_bypass: "Asl fayl",
    media_route_direct_export: "Asl fayl, ko'rish uchun yengil nusxa",
    media_route_proxied: "Yengil nusxa (proxy)",
    media_route_native_sw: "Mahalliy dasturiy dekodlash",
    media_proxy_ready: "yengil nusxa tayyor",
    media_proxy_pending: "yengil nusxa kutilmoqda",
    media_usage: "Qayerda ishlatilgan",
    media_unused: "Hech bir taymlaynda ishlatilmagan.",
    media_usage_go: "Shu klipga o'tish",
    locked: "Qulflangan",
    duration: "Davomiylik",
    multi_primary: "Asosiy klip «{{label}}» tahrirlanmoqda — {{count}} ta klip tanlangan; o'zgarishlar faqat shu klipga qo'llanadi.",
    text: "Matn",
    content: "Mazmun",
    font_family: "Shrift",
    font_size_px: "Shrift o'lchami (px)",
    text_reduced: "avtomatik {{px}} px gacha kichraytirildi",
    text_overflowing: "sig'madi — eng kami {{px}} px",
    text_box_mode: "Quti",
    text_box_mode_auto_width: "Avtomatik kenglik",
    text_box_mode_auto_height: "Avtomatik balandlik",
    text_box_mode_fixed: "Qat'iy",
    text_box_unmeasured:
      "Klipning chizilgan o'lchami kerak. O'ynatish ko'rsatkichini bu klip ustiga olib boring yoki ko'rish oynasida quti tutqichini sudrang.",
    text_box_w: "Quti kengligi",
    text_box_h: "Quti balandligi",
    text_box_h_hint:
      "Balandlik berilsa, matn qatorga o'tish o'rniga sig'adigan qilib kichraytiriladi — 8 px gacha.",
    align: "Gorizontal tekislash",
    align_left: "Chapga",
    align_center: "Markazga",
    align_right: "O'ngga",
    valign: "Vertikal tekislash",
    valign_top: "Yuqoriga",
    valign_middle: "O'rtaga",
    valign_bottom: "Pastga",
    line_height: "Qator balandligi (px)",
    line_height_hint: "0 = avtomatik — shriftning o'z qator o'lchamlari.",
    letter_spacing: "Harflar oralig'i (px)",
    // Width 0 is how the outline is removed; the colour row leaves with it.
    outline_width: "Kontur (px)",
    outline_width_hint: "0 = kontursiz.",
    outline_color: "Kontur rangi",
    color: "Rang",
    // `position` / `anchor` caption a MERGED axis row; `x` / `y` / `anchor_x`
    // / `anchor_y` stay as the per-axis accessible names inside it.
    position: "Joylashuv",
    x: "X",
    y: "Y",
    opacity: "Shaffoflik",
    media: "Media",
    audio: "Ovoz",
    scale_x: "O'lcham X",
    scale_y: "O'lcham Y",
    scale: "O'lcham",
    scale_link: "X/Y o'lchamini bog'lash (bir xil) — O'lcham Y O'lcham X ning nusxasiga aylanadi",
    scale_unlink: "X/Y o'lchamini ajratish",
    rotation: "Burish (°)",
    anchor: "Tayanch nuqta",
    anchor_x: "Tayanch nuqta X",
    anchor_y: "Tayanch nuqta Y",
    speed: "Tezlik",
    fade_in: "Paydo bo'lish",
    fade_out: "So'nish",
    fade_in_duration: "Paydo bo'lish davomiyligi",
    fade_out_duration: "So'nish davomiyligi",
    flip_h: "Gorizontal aylantirish",
    flip_v: "Vertikal aylantirish",
    width: "Kenglik",
    height: "Balandlik",
    gain_db: "Kuchaytirish (dB)",
    pan: "Panorama",
    role: "Vazifa",
    transform: "O'zgartirish",
    // The Pauses section, between the kind's own sections and Advanced.
    pauses: "Pauzalar",
    props: "Parametrlar",
    unknown_motif: "Noma'lum motif — uning parametrlarini bu yerda tahrirlab bo'lmaydi.",
    bake_warming: "Ko'rish tayyorlanmoqda… {{done}}/{{total}}",
    bake_preview_ready: "Ko'rish tayyor",
    bake_queued: "Navbatda… {{done}}/{{total}}",
    bake_paused: "To'xtatilgan… {{done}}/{{total}}",
    bake_retrying: "Qayta urinilmoqda… {{done}}/{{total}}",
    bake_pause_playback: "O'ynatish paytida fon jarayoni to'xtatiladi",
    bake_pause_memory: "Bo'sh resurslar kutilmoqda",
    bake_pause_capacity: "Vaqtinchalik kesh to'lgan; kesh hajmini oshiring",
    bake_pause_disk: "Yoziladigan kesh xotirasi kutilmoqda",
    bake_baking: "Oldindan tayyorlanmoqda… {{done}}/{{total}}",
    bake_error: "Oldindan tayyorlash bajarilmadi",
    motif_install: "O'rnatish",
    motif_delete: "O'chirish",
    motif_delete_confirm: "«{{id}}» motifi o'chirilsinmi? Joylashtirilgan kliplar mazmunini yo'qotadi.",
    motif_status: { builtin: "Tayyor", draft: "Qoralama", installed: "O'rnatilgan" },
    motif_edit: "Tahrirlash",
    motif_edit_fork: "Nusxalash va tahrirlash",
    motif_update: "Yangilash",
    motif_save_as_new: "Yangi sifatida saqlash",
    motif_discard: "Bekor qilish",
    motif_confirm: "Tasdiqlash",
    motif_cancel: "Bekor qilish",
    motif_update_confirm_one: "Bu loyihada 1 ta klipda ishlatilgan. Yangilash uni o'zgartiradi (boshqa loyihalar keyingi ochilishda yangilanadi).",
    motif_update_confirm_many: "Bu loyihada {{count}} ta klipda ishlatilgan. Yangilash ularning barchasini o'zgartiradi (boshqa loyihalar keyingi ochilishda yangilanadi).",
    motif_source: "Manba",
    motif_source_apply: "Qo'llash",
    motif_source_applying: "Qo'llanmoqda…",
    motif_source_hint: "Motifning HTML + manifest qismini tahrirlang, so'ng ko'rish oynasini yangilash uchun «Qo'llash»ni bosing.",
    transition: "O'tish",
    direction: "Yo'nalish",
    transition_delete: "O'tishni o'chirish",
  },
  captions: {
    title: "Subtitrlar",
    empty: "Subtitr yaratish uchun subtitr faylini qo'shing yoki klip matnini transkripsiya qiling.",
    style_heading: "Uslub",
    // The two words beside the number fields; the aria-label below says what 0
    // does, because the field has no visible way to.
    size_label: "O'lcham",
    outline_label: "Kontur",
    outline_width: "Kontur qalinligi (px), 0 — kontursiz",
    seek_to: "{{timecode}} dagi subtitrga o'tish",
  },
  // Clip-compute jobs: transcribe_clip / describe_clip (ADR 0120, ADR 0121).
  compute: {
    // One per key `phaseLabel` (shared/compute-jobs.ts) emits — tool-neutral,
    // for any surface that only has the phase. A queued job's reason is the
    // admission condition that is closed, said as what it waits FOR.
    phase: {
      queued: "Boshlanishini kutmoqda",
      queued_memory: "Xotira bo'shashini kutmoqda",
      queued_finalization: "Eksport tugashini kutmoqda",
      queued_budget: "Ishlov berish quvvatini kutmoqda",
      extracting: "Ajratib olinmoqda {{done}}/{{total}}",
      normalizing: "Ovoz balandligi tekislanmoqda",
      loading_model: "Model yuklanmoqda",
      inferring: "Model ishlamoqda",
      inferring_counted: "Model ishlamoqda {{done}}/{{total}}",
      applying: "Natijalar qo'llanmoqda",
    },
    // What job surfaces (the Activity row, the status bar, in-context
    // indicators) draw. They know the tool, so a phase can say what it does.
    // A resource refusal, summarized (`compute/computeRefusalMessage.ts`). {{task}} is
    // "Transcription" / "Description".
    refusal: {
      task_transcribe: "Matnga aylantirish",
      task_describe: "Tavsiflash",
      memory: "{{task}} boshlanmadi: kompyuterda xotira yetishmayapti. Boshqa dasturlarni yoping yoki xotira bo'shashini kuting, so'ng qayta urining. Takrorlansa, Sozlamalar → Unumdorlik bo'limida Xotira chegarasini o'zgartiring.",
      finalization: "{{task}} eksport tugashini kutmoqda. Eksport tugagach qayta urining.",
      budget: "{{task}} 60 s ichida boshlanmadi: ishlov berish quvvatini boshqa ishlar, masalan yengil nusxa (proxy) yaratish band qilgan. U tugagach qayta urining yoki Sozlamalar → Unumdorlik bo'limida Ishlov berish kuchi yoki Xotira chegarasini oshiring.",
      allowance: "{{task}} joriy Xotira chegarasi ruxsat berganidan ko'proq xotira talab qiladi. Sozlamalar → Unumdorlik bo'limida Xotira chegarasini oshiring, so'ng qayta urining.",
      queue: "Navbatda juda ko'p vazifa bor. Joriy ish tugagach qayta urining.",
      busy: "{{task}} uchun ishlov berish resurslari topilmadi. Birozdan so'ng qayta urining; takrorlansa, Sozlamalar → Unumdorlik bo'limini tekshiring.",
      open_settings: "Unumdorlik sozlamalarini ochish",
      details: "Texnik tafsilotlar",
    },
    ui: {
      // The budget wait names what holds the capacity: the derivatives pill
      // beside it is usually the answer.
      queued_budget_detail: "Ishlov berish quvvatini kutmoqda — uni yengil nusxa (proxy) yaratish kabi fon ishlari band qilgan",
      extracting_audio: "Ovoz ajratib olinmoqda",
      sampling_frames: "Kadrlar olinmoqda {{done}}/{{total}}",
      transcribing: "Matnga aylantirilmoqda",
      transcribing_percent: "Matnga aylantirilmoqda {{percent}}%",
      describing: "Tavsiflanmoqda",
      describing_counted: "Tavsiflanmoqda {{done}}/{{total}}",
      applying_captions: "Subtitrlar qo'shilmoqda",
      // In-context overlay over the source range a job reads.
      transcribing_range: "Bu qism matnga aylantirilmoqda…",
      describing_range: "Bu qism tavsiflanmoqda…",
      // The short form wherever the reason does not fit; the reason goes in
      // the title.
      waiting_short: "Resurslarni kutmoqda",
      waited: "{{duration}} kutilmoqda",
      // A working phase that has not changed (counts included) for a while.
      stalled: "{{duration}} davomida o'zgarish yo'q",
      stalled_hint: "Joriy bosqich anchadan beri jarayon haqida xabar bermadi. U hali ishlayotgan bo'lishi mumkin — uzun videoda har bir bosqich bir necha daqiqa olishi mumkin.",
      caller_disconnected: "So'ragan tomon uzildi — ish davom etmoqda",
      caller_disconnected_hint: "Buni so'ragan AI yordamchi (agent) endi ulanmagan. Ish davom etadi, qayta urinish uning natijasini oladi.",
      cancel: "Bekor qilish",
      cancel_transcribe: "Matnga aylantirishni bekor qilish",
      cancel_describe: "Tavsiflashni bekor qilish",
      cancelling: "Bekor qilinmoqda…",
      cancelled: "Bekor qilindi",
      cancel_failed: "Bekor qilib bo'lmadi: {{reason}}",
      // The status bar pill: one job is named by what it does, several are
      // counted. Its title lists every job, one per line.
      pill_transcribing: "Matnga aylantirilmoqda",
      pill_describing: "Tavsiflanmoqda",
      pill_many_one: "{{count}} ta klip vazifasi",
      pill_many_other: "{{count}} ta klip vazifasi",
      pill_many: "{{count}} ta klip vazifasi",
      pill_waiting_one: "{{count}} ta klip vazifasi kutmoqda",
      pill_waiting_other: "{{count}} ta klip vazifasi kutmoqda",
      pill_waiting: "{{count}} ta klip vazifasi kutmoqda",
      pill_line: "{{tool}} “{{clip}}”: {{phase}}",
      pill_line_unnamed: "{{tool}}: {{phase}}",
      pill_hint: "AI yordamchi panelini yoki jurnalni ochish uchun bosing",
      tool_transcribe: "Matnga aylantirish",
      tool_describe: "Tavsiflash",
      // Appended to the derivatives pill's title while a clip job waits on
      // the processing budget those jobs hold.
      derivatives_blocking: "Matnga aylantirish yoki tavsiflash bular tugashini kutmoqda.",
      // Durations, coarsest unit first, no leading zeros.
      duration_seconds: "{{s}} s",
      duration_minutes: "{{m}} daq {{s}} s",
      duration_hours: "{{h}} soat {{m}} daq",
      // Completion notice: a job the person started (or joined) ended while
      // they may be looking elsewhere.
      notice_transcribe_done_title: "Matnga aylantirish tugadi",
      notice_transcribe_done_body: "“{{clip}}” matnga aylantirildi.",
      notice_describe_done_title: "Tavsiflash tugadi",
      notice_describe_done_body: "“{{clip}}” tavsiflandi.",
      notice_transcribe_failed_title: "Matnga aylantirib bo'lmadi",
      notice_transcribe_failed_body: "“{{clip}}” ni matnga aylantirib bo'lmadi: {{reason}}",
      notice_describe_failed_title: "Tavsiflab bo'lmadi",
      notice_describe_failed_body: "“{{clip}}” ni tavsiflab bo'lmadi: {{reason}}",
      notice_transcribe_cancelled_body: "“{{clip}}” ni matnga aylantirish bekor qilindi.",
      notice_describe_cancelled_body: "“{{clip}}” ni tavsiflash bekor qilindi.",
      notice_transcribe_cancelled_title: "Matnga aylantirish bekor qilindi",
      notice_describe_cancelled_title: "Tavsiflash bekor qilindi",
      notice_dismiss: "Yopish",
    },
  },
  audio_roles: { dialogue: "Suhbat", music: "Musiqa", sfx: "Ovoz effektlari", voiceover: "Ovozli izoh" },
  mixer: {
    title: "Mikser",
    gain_db: "{{role}} kuchaytirish (dB)",
    gain_value: "{{value}} dB",
    gain_fader: "{{role}} kuchaytirish regulyatori",
    mute_hint: "{{role}} ovozini hamma joyda o'chirish",
    solo_hint: "Faqat {{role}} (qolganlari o'chadi)",
    implied_mute_badge: "O'chirilgan",
    implied_mute_hint: "Boshqa rol yakka tanlangani uchun {{role}} ovozi o'chgan",
    reset_hint: "{{role}} kuchaytirishini 0 dB ga qaytarish",
    db_scale: "dB shkalasi",
    role_meter: "{{role}} daraja o'lchagichi",
    master: "Umumiy",
    master_meter: "Umumiy chiqish o'lchagichi",
    master_rms: "RMS {{value}}",
    master_peak: "Cho'qqi {{value}} dB",
    peak_hold: "Cho'qqi {{value}} dB, tiklash uchun bosing",
  },
  motif_picker: {
    heading: "Motiflar",
    loading: "Motiflar yuklanmoqda…",
    empty: "Motiflar yo'q.",
    preview_heading: "Ko'rish oynasi",
    preview_canvas_size: "{{w}}×{{h}} kanvas",
    preview_loading: "Ko'rish oynasi yuklanmoqda…",
    props_heading: "Xususiyatlar",
    no_props: "(o'zgartiriladigan xususiyat yo'q)",
    timing_heading: "Vaqt",
    insert_at: "Qo'yish joyi",
    track_label: "Yo'lak",
    track_overlay_auto: "Yangi yo'lak (avtomatik)",
    duration_hint:
      "Klip uzunligi standart bo'yicha {{value}} (motifning standart davomiyligi). Boshqa uzunlik kerak bo'lsa, keyin taymlaynda qisqartiring.",
    add: "Taymlaynga qo'shish",
    adding: "Qo'shilmoqda…",
    new_button: "Yangi motif",
    import_button: "Motif qo'shish",
    export_button: "Motifni ZIP qilib eksport qilish",
    delete_button: "Motifni o'chirish",
    delete_confirm: "“{{name}}” ushbu qurilmadan o'chirilsinmi? Buni bekor qilib bo'lmaydi. Uni ishlatgan loyihalarda motif yo'qligi haqida belgi ko'rinadi.",
    cancel: "Bekor qilish",
    cover_unavailable: "Muqova mavjud emas",
    untitled_name: "Nomsiz motif",
    search_placeholder: "Motiflarni qidirish…",
    search_clear: "Qidiruvni tozalash",
    no_matches: "“{{query}}” bo'yicha motif topilmadi.",
    status: {
      draft: "Qoralama",
      installed: "O'rnatilgan",
      builtin: "Ichki",
    },
  },
  status_bar: {
    label: "Faoliyat jurnali",
    empty: "Hali faoliyat yo'q",
    toggle_label: "Jurnal",
    toggle_hint: "Faoliyat jurnalini ko'rsatish / yashirish",
    source_user: "Foydalanuvchi",
    source_agent: "AI yordamchi · {{client}}",
    source_system: "Tizim",
    error_badge_hint: "{{count}} ta xato — ko'rish uchun bosing",
    running_badge_hint: "{{count}} ta jarayon bajarilmoqda — ko'rish uchun bosing",
    announce_error_prefix: "Xato",
    links_off: "Bog'lanishlar o'chiq",
    links_off_hint: "Bog'lanishni chetlab o'tish yoqilgan (Alt+Shift+G): tahrirlar alohida kliplarga ta'sir qiladi",
  },
  system_status: {
    trigger: "Tizim {{count}}",
    trigger_hint: "{{count}} ta tizim holati e'tibor talab qiladi",
    title: "Tizim holati",
    summary: "{{count}} ta element e'tibor talab qiladi",
  },
  log: {
    level_filter: "Muhimlik filtri",
    level_all: "Hammasi",
    level_info: "Ma'lumot+",
    level_warn: "Ogohlantirish+",
    level_errorOnly: "Faqat xatolar",
    category_filter: "Turkum filtri",
    category_Shortcut: "Tezkor tugma",
    category_Mcp: "MCP",
    category_Job: "Vazifa",
    category_Export: "Eksport",
    category_Import: "Qo'shish",
    category_Project: "Loyiha",
    category_System: "Tizim",
    category_Agent: "AI yordamchi",
    source_filter: "Manba filtri",
    source_User: "Foydalanuvchi",
    source_Agent: "AI yordamchi",
    source_System: "Tizim",
    search_placeholder: "Xabarlar va tafsilotlarni qidirish…",
    autoscroll_on: "Avtomatik aylantirish: yoqiq",
    autoscroll_off: "Avtomatik aylantirish: o'chiq",
    autoscroll_hint: "Eng yangi yozuvga avtomatik aylantirishni yoqish/o'chirish",
    copy: "Nusxa olish",
    clear: "Tozalash",
    open_folder: "Jurnal papkasini ochish",
    open_folder_unavailable_hint: "Avval ish maydonini oching.",
    close: "Faoliyat jurnalini yopish",
    resize: "Konsol balandligini o'zgartirish",
    empty: "Joriy filtrlarga mos yozuv yo'q.",
    op_counter_hint: "Bu amalning holat o'zgarishlarini ochish",
    toggle_details: "Tafsilotlarni ko'rsatish/yashirish",
    showing_of: "{{shown}} / {{total}} ko'rsatilmoqda",
    op_state_Started: "Boshlandi",
    op_state_Ok: "Tayyor",
    op_state_Err: "Xato",
    export_started: "Eksport qilinmoqda: {{path}}",
    export_ok: "Eksport qilindi: {{path}}",
    export_failed: "Eksport qilib bo'lmadi: {{error}}",
    export_cancelled: "Eksport bekor qilindi",
    cleared: "Jurnal tozalandi",
    scale_layer_unavailable: "Bu klip o'lchamini o'zgartirib bo'lmaydi — ko'rish oynasi o'lchamlari mavjud emas yoki klip o'lchami nolga teng",
    center_layer_unstaged:
      "Ko'rish oynasi hali tayyorlamagan klipni markazga qo'yib bo'lmaydi — uning o'lchami noma'lum",
    cross_composition_copy:
      "Klipni boshqa taymlaynga nusxalab bo'lmaydi — u yerga ko'chirish uchun Alt ni qo'yib yuboring",
    paste_keyframes_no_target: "Kalit kadrlarni qo'yish uchun klip tanlang",
    paste_keyframes_skipped:
      "{{params}} o'tkazib yuborildi — tanlangan kliplarda bu parametr yo'q",
    auto_caption_started: "“{{clip}}” matnga aylantirilmoqda",
    // Several clips are counted, not listed: their names are in the Caption
    // Panel the moment the cues land, and a row that named six clips would be a
    // paragraph. The failure row names the ONE clip that matters.
    auto_caption_started_many: "{{count}} ta klip matnga aylantirilmoqda",
    auto_caption_done: "{{cues}} ta subtitr qo'shildi ({{engine}})",
    auto_caption_failed: "“{{clip}}” ni matnga aylantirib bo'lmadi: {{reason}}",
    // A cancelled job is not a failure: the clip is named, nothing else is said.
    auto_caption_cancelled: "“{{clip}}” ni matnga aylantirish bekor qilindi",
    auto_caption_quiet: "“{{clip}}” ovozi past. Matnga aylantirishda ba'zi so'zlar tushib qolishi yoki til noto'g'ri aniqlanishi mumkin.",
    auto_caption_level_unavailable: "“{{clip}}” ovoz balandligini tekshirib bo'lmadi.",
    auto_caption_normalize_requested: "Sizning so'rovingiz bo'yicha “{{clip}}” ning matnga aylantirish uchun nusxasi ovozi tekislanmoqda.",
    auto_caption_normalized: "“{{clip}}” ning matnga aylantirish nusxasi: +{{gain}} dB kuchaytirildi. Asl fayl va taymlayndagi ovoz balandligi o'zgarmadi.",
    shots_analyze_started: "“{{clip}}” dagi sahnalar tahlil qilinmoqda",
    // The CANDIDATE count, not a shot count: the scan's product is the
    // candidate list, and how many shots come out of it is whatever threshold
    // is read next.
    shots_analyze_done: "“{{clip}}” da {{candidates}} ta sahna nomzodi topildi",
    // Only reached when the failure is not a structured refusal — a refusal
    // carries its own key and closes the op under that instead.
    shots_analyze_failed: "“{{clip}}” sahnalarini tahlil qilib bo'lmadi: {{error}}",
    // The SPAN count both ways: it is what the pass costs (three ffmpeg
    // extracts each, for the spans no pass had measured) and what came back.
    shots_stats_started: "“{{clip}}” dagi {{spans}} ta sahna o'lchanmoqda",
    shots_stats_done: "“{{clip}}” dagi {{spans}} ta sahna o'lchandi",
    // Only reached when the failure is not a structured refusal, as above.
    shots_stats_failed:
      "“{{clip}}” dagi sahnalarni o'lchab bo'lmadi: {{error}}",
    // One Started row per verb rather than one with the verb interpolated: a
    // discard announces two counts, and a translated sentence cannot carry an
    // untranslated verb name. The Started rows say how much of the review went
    // out; the terminal rows say what came back, which for a discard is
    // survivors and not the boundaries it cut at.
    shots_apply_split_started: "“{{clip}}” {{cuts}} ta sahna chegarasidan bo'linmoqda",
    shots_apply_split_done: "“{{clip}}” {{segments}} ta bo'lakka bo'lindi",
    shots_apply_mark_started: "“{{clip}}” da {{cuts}} ta sahna chegarasi belgilanmoqda",
    shots_apply_mark_done:
      "“{{clip}}” ga {{markers}} ta sahna chegarasi belgisi qo'shildi",
    shots_apply_discard_started:
      "“{{clip}}” {{cuts}} ta sahna chegarasidan bo'linmoqda, {{discarded}} ta sahna olib tashlanadi",
    shots_apply_discard_done:
      "“{{clip}}” dan {{segments}} ta bo'lak qoldirildi, {{discarded}} tasi olib tashlandi",
    // Only reached when the failure is not a structured refusal — a refusal
    // closes the op under its own curated key instead.
    shots_apply_failed:
      "“{{clip}}” ga sahna kesimlarini qo'llab bo'lmadi: {{error}}",
    // Two terminal rows and not one with a flag, because the difference is what
    // the run COST: a cached hit billed nothing, and that is the fact worth
    // reading in the record.
    voiceover_started: "Ovozli izoh yaratilmoqda — {{chars}} ta belgi, {{voice}}",
    voiceover_done: "Ovozli izoh qo'shildi — {{chars}} ta belgi, {{voice}}",
    voiceover_done_cached:
      "Ovozli izoh qo'shildi — keshdagi ovoz ishlatildi, to'lov olinmadi",
    mark_pauses_started: "“{{clip}}” dagi pauzalar belgilanmoqda",
    // The COUNT is the whole point of the row: the marks land in the ruler's
    // lower half, which the user may not have been looking at.
    mark_pauses_done: "“{{clip}}” ga {{markers}} ta pauza belgisi qo'shildi",
    remove_pauses_started: "“{{clip}}” dan pauzalar olib tashlanmoqda",
    // The TOTAL beside the count, unlike the marking row's count alone: a
    // removal shortens the film, and how much it took out is what says how far
    // everything downstream moved. It is the sum of the CORES cut, not of the
    // pauses found — each one keeps its pad.
    remove_pauses_done:
      "“{{clip}}” dan {{removed}} ta pauza olib tashlandi, jami {{total}}",
    describe_started: "“{{clip}}” tavsiflanmoqda",
    // The engine AND the model, unlike the transcription row's engine alone:
    // one runtime serves several vision models here, so the engine tag on its
    // own does not say which weights answered.
    describe_done:
      "“{{clip}}” da {{segments}} ta qism tavsiflandi ({{engine}}, {{model}})",
    describe_cancelled: "“{{clip}}” ni tavsiflash bekor qilindi",
    // A resource refusal, summarized (`compute/computeRefusalMessage.ts`); the native
    // sentence stays in the row's details.
    describe_failed: "“{{clip}}” ni tavsiflab bo'lmadi: {{reason}}",
  },
  // Edit-stack row labels — one per `HISTORY_SUMMARY` entry in
  // main/state/history-labels.ts, which owns the English source text. The three
  // templated summaries (media.remove_cascade, audio.set_role_gain,
  // checkpoint.restore) take their `{{…}}` values from the entry's `label_args`;
  // history-labels.test.ts gates the placeholders against what each builder
  // actually supplies, so one can never render literally.
  history: {
    initial: "Boshlang'ich holat",
    layer: {
      add: "Klip qo'shildi",
      paste: "Klip qo'yildi",
      duplicate: "Klip nusxalandi",
      paste_multi: "{{count}} ta klip nusxalandi",
      enabled_multi: "{{count}} ta klip yoqildi",
      disabled_multi: "{{count}} ta klip o'chirildi",
      move: "Klip ko'chirildi",
      shift: "Kliplar surildi",
      move_to_new_track: "Yangi yo'lakka ko'chirildi",
      // The named form wins whenever the destination carries a stored label;
      // the unnamed one covers a derived `Group N` and the root, neither of
      // which main can name.
      move_to_composition: "{{count}} ta klip {{composition}} ga ko'chirildi",
      move_to_composition_unnamed: "{{count}} ta klip boshqa joyga ko'chirildi",
      restack: "Klip tartibi o'zgartirildi",
      trim: "Klip qisqartirildi",
      split: "Klip bo'lindi",
      split_by_shots: "Klip sahnalar bo'yicha bo'lindi",
      delete_multi: "Kliplar o'chirildi",
      ripple_delete: "Kliplar bo'shliqsiz o'chirildi",
      split_and_ripple: "Klip bo'lindi va bo'shliqlar yopildi",
      update: "Klip yangilandi",
      update_params: "Klip parametrlari yangilandi",
      keyframe_param: "Klip parametriga kalit kadr qo'yildi",
      keyframe_params: "Klip parametrlariga kalit kadr qo'yildi",
      keyframe_params_multi: "Bir nechta klip parametrlariga kalit kadr qo'yildi",
      scale_link: "O'lcham bog'landi",
      scale_unlink: "O'lcham bog'lanishi uzildi",
      separate_audio: "Ovoz ajratildi",
      add_av_pair: "Video/ovoz juftligi qo'shildi",
      rebind_motif: "Motif kliplari qayta bog'landi",
    },
    // A selected gap closed (ADR 0069): the subject is the gap, no clip went.
    gap: {
      close: "Bo'shliq yopildi",
    },
    track: {
      add: "Yo'lak qo'shildi",
      delete: "Yo'lak o'chirildi",
      move: "Yo'lak ko'chirildi",
      rename: "Yo'lak nomi o'zgartirildi",
      add_caption: "Subtitrlar qo'shildi",
    },
    marker: {
      add: "Belgi qo'shildi",
      add_shots: "Sahna belgilari qo'shildi",
      update: "Belgi yangilandi",
      remove: "Belgi o'chirildi",
      attach: "Belgi klipga bog'landi",
      detach: "Belgi klipdan ajratildi",
    },
    effect: {
      add: "Effekt qo'shildi",
      update: "Effekt yangilandi",
      reorder: "Effekt tartibi o'zgartirildi",
      remove: "Effekt o'chirildi",
    },
    transition: {
      add: "O'tish qo'shildi",
      update: "O'tish yangilandi",
      remove: "O'tish o'chirildi",
    },
    link: {
      create: "Bog'lanish yaratildi",
      dissolve: "Bog'lanish uzildi",
      add_members: "Bog'lanishga a'zolar qo'shildi",
      remove_members: "Bog'lanishdan a'zolar olib tashlandi",
    },
    group: {
      create: "{{count}} ta klip guruhlandi",
      add_members: "Guruhga {{count}} ta klip qo'shildi",
      ungroup: "Guruh tarqatildi",
      rename: "Guruh nomi o'zgartirildi",
    },
    composition: { delete: "Guruh o'chirildi" },
    caption: { restyle: "Subtitr uslubi o'zgartirildi", correct: "Subtitr matni tuzatildi", merge: "Subtitrlar birlashtirildi" },
    style: { restyle: "Loyiha uslubiga moslandi" },
    media: {
      remove_cascade:
        "{{media}} media va unga bog'liq {{count}} ta klip o'chirildi",
    },
    audio: { set_role_gain: "{{role}} roli kuchaytirishi o'rnatildi" },
    checkpoint: { restore: "“{{label}}” nazorat nuqtasiga qaytarildi" },
    review: { revert: "Ko'rib chiqilmagan o'zgarishlar bekor qilindi" },
  },
  // The History Panel's own chrome. The ROW text comes from `history.*` above
  // (main records the key at commit time); everything here is panel furniture.
  history_panel: {
    // No "empty" string: the stack always holds at least the `Initial` seed and
    // the read cannot fail, so the only rowless moment is before the first
    // fetch settles.
    loading: "Tarix yuklanmoqda…",
    // Eviction header. Non-interactive: those snapshots are gone, so there is
    // nothing to jump to.
    evicted_one: "{{count}} ta oldingi qadam endi mavjud emas",
    evicted_other: "{{count}} ta oldingi qadam endi mavjud emas",
    jump_hint: "Shu holatga o'tish",
    current_hint: "Joriy holat",
    redo_hint: "Oldinga, shu holatga o'tish",
    locked_hint: "Tarix qulflangan: {{reason}}",
    actor_user: "Siz",
    agent_client: "AI yordamchi: {{client}}",
    group_steps_one: "{{count}} ta qadam",
    group_steps_other: "{{count}} ta qadam",
    group_jump_hint: "Bu ishdan oldingi holatga o'tish",
    // Boundary case: eviction ate the run's predecessor, so no stack index
    // holds "before this run" any more.
    group_jump_unavailable: "Bu ishdan oldingi holat endi mavjud emas",
    expand_group: "Barcha qadamlarni ko'rsatish",
    collapse_group: "Qadamlarni yig'ish",
    // Joins entity names on a row and the counted phrases in a group header.
    list_separator: ", ",
    // Aggregate counting: `Split layer ×2, Added marker ×4`.
    aggregate_item: "{{label}} ×{{count}}",
    // ── Checkpoints (own section above the stack) ────────────────────────────
    checkpoints_title: "Nazorat nuqtalari",
    // Load-bearing, not chrome: checkpoints are absent from serialize.ts /
    // persistence.ts and `replace_state` clears them, so a user reading them as
    // durable saves loses work.
    checkpoints_note: "Faqat shu seans uchun — loyiha yopilganda nazorat nuqtalari o'chib ketadi.",
    checkpoint_create: "Yangi",
    checkpoint_create_hint: "Joriy holatni nazorat nuqtasi sifatida saqlash",
    checkpoint_create_title: "Yangi nazorat nuqtasi",
    checkpoint_create_confirm: "Yaratish",
    checkpoint_cancel: "Bekor qilish",
    checkpoint_label: "Nomi",
    checkpoint_label_placeholder: "Dastlabki montaj tayyor",
    checkpoint_restore: "Qaytarish",
    checkpoint_restore_hint: "Shu nazorat nuqtasidagi holatga qaytarish",
    checkpoint_delete: "O'chirish",
    checkpoint_delete_hint: "Bu nazorat nuqtasini o'chirish",
    checkpoint_delete_title: "Nazorat nuqtasini o'chirish",
    checkpoint_delete_body: "“{{label}}” nazorat nuqtasi o'chiriladi.",
    // Whose checkpoint this is. The destructive case is cross-actor: an agent
    // session's `Pre-agent:` checkpoint may be that session's only way back, and
    // nothing else in the dialog says the checkpoint isn't yours.
    checkpoint_delete_owner_user: "Bu nazorat nuqtasini siz yaratgansiz.",
    checkpoint_delete_owner_agent: "Bu nazorat nuqtasini “{{client}}” AI yordamchisi yaratgan.",
    checkpoint_delete_note: "Nazorat nuqtasini o'chirishni bekor qilib bo'lmaydi.",
    checkpoint_delete_confirm: "O'chirish",
    checkpoint_deleting: "O'chirilmoqda…",
  },
  // Display labels for Rust-side enum discriminants. Keep keys lowercase so
  // `t("kinds." + value.toLowerCase())` works directly.
  kinds: {
    // MediaKind / TrackKind
    video: "Video",
    audio: "Ovoz",
    image: "Rasm",
    subtitle: "Subtitr",
    // LayerParams discriminants
    videoclip: "Video",
    imageoverlay: "Rasm",
    text: "Matn",
    motif: "Motif",
    color: "Rang",
    compositionref: "Guruh",
    // Markers have no kind discriminant; the history panel's entity-label chain
    // uses this as their last rung so a blank-labelled marker never renders as a
    // raw uuid (main/state/history-labels.ts).
    marker: "Belgi",
  },
  // The voiceover dialog.
  transcription_input: {
    title: "Matnga aylantirishdan oldin ovozni tekshiring",
    quiet: "Bu kliplarning ovozi past. Matnga aylantirishda so'zlar tushib qolishi yoki til noto'g'ri aniqlanishi mumkin.",
    unavailable: "Bu kliplarning ovoz darajasini tekshirib bo'lmadi. Ularning to'lqin shakli hali tayyorlanayotgan bo'lishi mumkin.",
    unchanged: "«Asl ovoz balandligida davom etish» ovozni o'zgartirmasdan ishlatadi. Ikkala holatda ham media fayllaringiz va taymlayndagi ovoz balandligi o'zgarmaydi.",
    normalize_note: "«Tekislash va matnga aylantirish» faqat yuqoridagi past ovozli kliplarning shu safar uchun olingan nusxalarini o'zgartiradi. Maqsadli cho'qqi: −3 dBFS; eng ko'p kuchaytirish: 24 dB. Haqiqiy kuchaytirish qayta o'lchanadi va jurnalga yoziladi. Jimlik va tekshirilmagan kliplar asl balandlikda qoladi; fon shovqini ham balandroq bo'lishi mumkin.",
    estimate: "taxminiy kuchaytirish +{{gain}} dB",
    normalize: "Tekislash va matnga aylantirish",
    remedy: "Avval asl ovozni tekshirish uchun bekor qilishingiz mumkin. Matnga aylantirish asl fayldan o'qiydi; taymlayndagi ovoz balandligi va effektlar unga ta'sir qilmaydi.",
    cancel: "Bekor qilish",
    continue: "Asl ovoz balandligida davom etish",
  },
  voiceover: {
    title: "Ovozli izoh",
    script: "Matn",
    // Counter, always shown — an over-length script is refused here rather than
    // by the provider, so the number has to be visible before the limit is hit.
    script_count: "{{chars}} / {{max}} ta belgi",
    script_empty: "o'qiladigan matnni yozing",
    script_too_long: "Bitta ovozli izoh uchun {{max}} belgi chegarasidan {{over}} ta ortiq",
    voice: "Ovoz",
    speed: "Tezlik",
    track: "Yo'lak",
    placement: "Qayerga qo'yiladi",
    placement_append: "Hammasidan keyin",
    placement_append_desc: "{{time}} da, taymlayn oxiridan keyin boshlanadi.",
    placement_playhead: "O'ynatish ko'rsatkichida",
    placement_playhead_desc: "{{time}} da boshlanadi.",
    // Said before the button, not after the bill: this is the only entry in the
    // editor that spends money per use, and the cache is what makes a re-run of
    // the same script free.
    cost: "Yangi ovoz yaratish pullik so'rov. Xuddi shu matn, ovoz va tezlik uchun avval yaratilgan ovoz bepul qayta ishlatiladi.",
    cancel: "Bekor qilish",
    confirm: "Yaratish",
    running: "Yaratilmoqda…",
  },
  // The Pauses section of the Attribute Panel. Its home is a panel section and
  // not a dialog because tuning a threshold is something a person does WHILE
  // looking at the waveform and playing the clip (spec Decision 3), so the copy
  // here has to work in a narrow column beside the timeline rather than in a
  // form with room for hints.
  //
  // The UI word is PAUSE on every line here: a stretch of quiet inside speech
  // is what the feature is about, and the old noun collided with mute. The one
  // exception is the slider end below, where the phrase names the sound itself.
  pauses: {
    preset: "Andoza",
    preset_modified: "{{name}} · O'zgartirilgan",
    presets_builtin: "Ichki andozalar",
    presets_personal: "Mening andozalarim",
    presets_empty: "Hali saqlangan andoza yo'q",
    presets_loading: "Andozalar yuklanmoqda…",
    preset_save_as: "Andoza sifatida saqlash…",
    preset_update: "“{{name}}” ni yangilash",
    presets_manage: "Andozalarni boshqarish…",
    presets_scope: "Barcha loyihalarda mavjud. O'zgarishlar loyihaga allaqachon qo'llangan parametrlarga ta'sir qilmaydi.",
    preset_name: "Andoza nomi",
    preset_values: "Chegara {{thresholdDb}} dB · eng qisqa pauza {{minMs}} ms · har tomonda {{padMs}} ms qoldirish",
    preset_duplicate: "Bu nomli andoza allaqachon mavjud.",
    preset_save: "Saqlash",
    preset_cancel: "Bekor qilish",
    preset_done: "Tayyor",
    preset_rename: "Nomini o'zgartirish",
    preset_delete: "O'chirish",
    preset_rename_named: "“{{name}}” nomini o'zgartirish",
    preset_delete_named: "“{{name}}” ni o'chirish",
    preset_saved: "Andoza saqlandi",
    preset_deleted: "“{{name}}” o'chirildi. Joriy parametrlar o'zgarmadi.",
    preset_save_failed: "Andozalarni saqlab bo'lmadi: {{reason}}",
    parameters_save_failed: "Bu parametrlarni eslab qolib bo'lmadi: {{reason}}",
    threshold_hint: "Past qiymat faqat juda jim joylarni topadi. Yuqori qiymat xona shovqinini va past ovozli nutqni ham qamrab olishi mumkin.",
    noise_floor_pending: "Shovqin darajasi —",
    found_one: "1 ta pauza topildi",
    found_other: "{{count}} ta pauza topildi",
    result_detail: "{{removed}} olib tashlanadi · {{result}} qoladi",
    seconds: "{{value}} s",
    detect_failed: "Pauzalarni aniqlab bo'lmadi",
    // Named on the delegating clip, so the user knows the numbers are not about
    // the picture they selected.
    delegated: "Bog'langan “{{clip}}” ovozida o'lchandi",
    // Starting points, not modes: each sets the threshold and the minimum and
    // then gets out of the way. Named for the RECORDING, because that is what
    // the user knows about their own material — a dB figure is not.
    preset_speech: "Nutq / podkast",
    preset_noisy: "Shovqinli xona",
    preset_music: "Musiqa / atrof-muhit",
    // A readout rather than a fourth choice: it lights to say the two numbers
    // below are the user's own.
    preset_custom: "Maxsus",
    threshold: "Chegara",
    // Decibels and not amplitude, unlike the tool's own parameter: 0..1 is
    // linear on a logarithmic quantity, so one step of it is 6 dB at the bottom
    // of the range and 0.4 dB at the top. The section converts.
    db: "{{db}} dB",
    // Measured from the clip's own peaks, which is what makes Auto worth a
    // button: it knows something about this recording that the user does not.
    noise_floor: "Shovqin darajasi ≈ {{db}} dB",
    use_suggested: "Tavsiyani qo'llash",
    suggestion_hint: "Bu klipning shovqin darajasiga qarab chegarani {{db}} dB ga qo'yish va pauzalarni qayta aniqlash.",
    suggestion_pending: "To'lqin shakli o'lchangach, tavsiya etilgan chegara paydo bo'ladi.",
    min_length: "Eng qisqa pauza",
    min_length_hint: "Pauza deb hisoblanishi uchun ovoz kamida shuncha vaqt chegaradan past bo'lishi kerak.",
    // “Keep”, not “pad” or “trim”: the number is what SURVIVES on each side of a
    // pause, and a removal that erased them outright makes speech breathless.
    pad: "Har tomonda qoldirish",
    pad_hint: "Pauzalarni olib tashlashda tabiiyroq kesim uchun har tomonda shuncha vaqt qoldiriladi. Bu pauza belgilariga ta'sir qilmaydi.",
    unit_ms: "ms",
    // Three numbers and no list: nobody confirms forty rows one by one. WHERE
    // the pauses are is answered by the bands on the clip, how it sounds by the
    // audition, and what it costs by this line.
    summary_one: "1 ta pauza · {{removed}} olib tashlanadi · natija {{result}}",
    summary_other: "{{count}} ta pauza · {{removed}} olib tashlanadi · natija {{result}}",
    none: "Joriy sozlamalarda pauza topilmadi",
    detecting: "To'lqin shakli o'qilmoqda…",
    // A state, not a failure: on a fresh import the peaks are still being
    // generated, and the section retries by itself once they are.
    waiting_waveform: "To'lqin shakli kutilmoqda…",
    // “Result”, because what plays is the stitched OUTCOME of a removal and not
    // the clip as it stands.
    audition: "Natijani tinglash",
    audition_stop: "Tinglashni to'xtatish",
    mark: "Pauzalarni belgilash",
    marking: "Belgilanmoqda…",
    remove: "Pauzalarni olib tashlash",
    removing: "Olib tashlanmoqda…",
    // The parameters are remembered per project, so there has to be a way back.
    reset: "Parametrlarni standart holatga qaytarish",
  },
  search: {
    placeholder: "Buyruqlar, media, kliplar, subtitrlar, tavsiflarni qidirish…",
    no_results: "“{{query}}” bo'yicha hech narsa topilmadi",
    group_command: "Buyruqlar",
    group_media: "Media",
    group_group: "Guruhlar",
    group_track: "Yo'laklar",
    group_clip: "Kliplar",
    group_caption: "Subtitrlar",
    group_marker: "Belgilar",
    group_description: "Tavsiflar",
    reveal_in_pool: "Media ro'yxatida ko'rsatish",
    unused: "Taymlaynda yo'q",
    missing_badge: "topilmadi",
    show_more: "Yana {{count}} tasini ko'rsatish…",
  },
  // Lahza panel: long Uzbek video → highlights → Reels (Lahza Studio engine).
  lahza_panel: {
    engine_checking: "Lahza dvigateli tekshirilmoqda…",
    engine_unavailable: "Bu o'rnatishda Lahza dvigateli yo'q. Lahza Studio'ni qayta o'rnating.",
    engine_stopped: "Lahza dvigateli to'xtadi.",
    engine_starting: "Lahza dvigateli ishga tushmoqda…",
    engine_ready: "Lahza dvigateli {{version}} tayyor — internetsiz o'zbekcha nutqni aniqlash va eng yaxshi lahzalarni topish.",
    engine_failed: "Lahza dvigatelida xato: {{error}}",
    retry: "Dvigatelni qayta ishga tushirish",
    analyze: "Videoni tahlil qilish…",
    pick_video: "Tahlil qilish uchun uzun videoni tanlang",
    video_files: "Video va ovoz fayllari",
    lite: "Tezkor (AI modelsiz)",
    lite_hint: "Eng yaxshi lahzalarni faqat ovoz va matnga qarab topadi, kompyuterdagi til modelisiz. Tezroq ishlaydi.",
    job: "Lahza vazifasi",
    job_queued: "Navbatda…",
    job_running: "{{stage}} — {{percent}}%",
    job_done: "Tayyor.",
    job_failed: "Xato yuz berdi.",
    job_cancelled: "Bekor qilindi.",
    cancel: "Bekor qilish",
    refresh: "Yangilash",
    videos: "Tahlil qilingan videolar",
    no_videos: "Hali hech qanday video tahlil qilinmagan. Eng yaxshi lahzalarni topish uchun podkast yoki intervyuni tahlil qiling.",
    episode_analyzing: "tahlil qilinmoqda",
    episode_ready: "tayyor",
    episode_failed: "xato",
    highlights: "Eng yaxshi lahzalar",
    no_highlights: "Bu videoda yaxshi lahza topilmadi.",
    untitled: "Nomsiz lahza",
    clip_meta: "{{seconds}} s · ball {{score}}",
    place: "Taymlaynga qo'yish",
    place_hint: "Bu lahzani taymlaynga 9:16 Reels shaklida, so'zma-so'z o'zbekcha subtitrlar bilan qo'yadi. Bekor qilish mumkin.",
    placed: "{{count}} ta video bo'lagi va {{cues}} ta subtitr qo'yildi.",
    export: "Reels sifatida saqlash…",
    export_hint: "Tayyor 1080×1920 Reels videoni o'zbekcha subtitrlar, SRT fayl va muqova bilan saqlaydi.",
    pick_folder: "Saqlash uchun papkani tanlang",
    exported: "Saqlandi: {{path}}",
    guide_title: "Qanday ishlaydi",
    guide_1: "1. «Videoni tahlil qilish…» tugmasini bosing va uzun videoni tanlang (podkast, intervyu, dars).",
    guide_2: "2. Lahza videoni tinglab chiqadi: o'zbekcha nutq matnga aylanadi va eng yaxshi lahzalar topiladi.",
    guide_3: "3. Lahzani tanlang: tahrirlash uchun «Taymlaynga qo'yish», tayyor video uchun «Reels sifatida saqlash…».",
    time_hint: "Tahlil internetsiz, shu kompyuterning o'zida bajariladi. Bir soatlik video biroz vaqt oladi — bu orada boshqa ish qilishingiz mumkin.",
    stage: {
      ingest: "Video o'qilmoqda",
      vad: "Nutq qidirilmoqda",
      asr: "Nutq matnga aylantirilmoqda",
      normalize: "Matn tozalanmoqda",
      align: "Har bir so'z vaqtga moslanmoqda",
      diarize: "Gapiruvchilar ajratilmoqda",
      sentences: "Gaplar tuzilmoqda",
      signals: "Qiziqarlilik baholanmoqda",
      highlight: "Eng yaxshi lahzalar qidirilmoqda",
      llm: "AI lahzalarni tanlamoqda",
      plan: "Montaj tayyorlanmoqda",
      render: "Video tayyorlanmoqda",
      download: "Yuklab olinmoqda",
    },
  },
};

export default uzUZ;
