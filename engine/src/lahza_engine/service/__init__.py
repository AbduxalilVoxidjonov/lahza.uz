"""Mustaqil "Lahza Engine" servisi (ADB-7, docs/12 3.3-bo'lim).

Lahza Studio ochilmagan holda ham Adobe plaginlari engine'ga ulana olishi uchun engine foydalanuvchi
darajasida avtomatik ishga tushiriladi:

* macOS - LaunchAgent `~/Library/LaunchAgents/uz.lahza.engine.plist` (`launchd.py`);
* Windows - Task Scheduler vazifasi `\\Lahza\\Engine`, kirishda (`winsched.py`).

Servis `lahza serve --service` ni ishga tushiradi: bu `--discovery` (qat'iy portlar 47600-47602, faqat
127.0.0.1, `<data_dir>/engine.json` + token) va qo'shimcha himoyalar (`runtime.py`): ikkinchi nusxa
ishga tushmaydi, tez-tez qulashda qayta ishga tushirish to'xtatiladi. Desktop ilova sidecar'i tirik
servisni topsa, o'z engine'ini ko'tarmaydi - unga ulanadi (`runtime.attach`).
"""

from __future__ import annotations

APP_IDENTIFIER = "uz.lahza.studio"
"""Desktop ilovaning bundle identifikatori (`app/src-tauri/tauri.conf.json` -> `identifier`)."""

SERVICE_LABEL = APP_IDENTIFIER.rsplit(".", 1)[0] + ".engine"
"""launchd Label: ilova identifikatorining reverse-domain prefiksi (`uz.lahza`) + `.engine`."""

WINDOWS_TASK_NAME = "\\Lahza\\Engine"
"""Task Scheduler'dagi vazifa yo'li (foydalanuvchi vazifasi, `Lahza` papkasida)."""

SERVICE_DIR = "service"
"""`<data_dir>/service/` - servis holati (start jurnali, Windows env/XML nusxasi). Uninstall o'chiradi."""

__all__ = ["APP_IDENTIFIER", "SERVICE_DIR", "SERVICE_LABEL", "WINDOWS_TASK_NAME"]
