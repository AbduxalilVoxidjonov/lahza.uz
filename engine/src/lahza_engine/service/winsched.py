"""Windows: foydalanuvchi darajasidagi Task Scheduler vazifasi (`\\Lahza\\Engine`), kirishda ishga tushadi.

Nega HKCU `Run` emas: Task Scheduler `RestartOnFailure` (qulashda qayta ishga tushirish) va
`MultipleInstancesPolicy=IgnoreNew` (ikkinchi nusxa yo'q) beradi; `Run` kaliti bularni bermaydi.
Zaxira sifatida `run_key_command` (qo'lda) - hujjatda (docs/12 3.3).

Manba: Task Scheduler Schema (learn.microsoft.com/windows/win32/taskschd/task-scheduler-schema):
LogonTrigger.UserId, Principal.LogonType=InteractiveToken, RunLevel=LeastPrivilege (admin kerak emas),
Settings.RestartOnFailure, ExecutionTimeLimit=PT0S (cheklovsiz); `schtasks /Create /XML` UTF-16 faylni kutadi.
Bu kod macOS'da faqat generatsiya darajasida testlanadi - haqiqiy Windows'da qo'lda sinov (docs/12 3.3).
"""

from __future__ import annotations

import getpass
import os
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

from lahza_engine.service import WINDOWS_TASK_NAME
from lahza_engine.service.spec import SERVE_ARGS, ServiceSpec

TASK_NS = "http://schemas.microsoft.com/windows/2004/02/mit/task"
RESTART_COUNT = 3
RESTART_INTERVAL = "PT1M"
LOGON_DELAY = "PT15S"


def current_user(environ: dict[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    user = env.get("USERNAME") or getpass.getuser()
    dom = env.get("USERDOMAIN")
    return f"{dom}\\{user}" if dom else user


def env_file(spec: ServiceSpec) -> Path:
    return spec.state_dir / "service-env.json"


def task_xml_path(spec: ServiceSpec) -> Path:
    return spec.state_dir / "lahza-engine-task.xml"


def task_arguments(spec: ServiceSpec) -> list[str]:
    args = [*spec.program[1:], *SERVE_ARGS]
    if spec.env:
        args += ["--env-file", str(env_file(spec))]
    return args


def build_task_xml(spec: ServiceSpec, user: str | None = None) -> str:
    user = user or current_user()
    command = escape(spec.program[0])
    arguments = escape(subprocess.list2cmdline(task_arguments(spec)))
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="{TASK_NS}">
  <RegistrationInfo>
    <Author>{escape(user)}</Author>
    <Description>Lahza Engine: Adobe plaginlari uchun lokal engine (faqat 127.0.0.1). lahza uninstall-service bilan o'chiriladi.</Description>
    <URI>{escape(WINDOWS_TASK_NAME)}</URI>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{escape(user)}</UserId>
      <Delay>{LOGON_DELAY}</Delay>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{escape(user)}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>{RESTART_INTERVAL}</Interval>
      <Count>{RESTART_COUNT}</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{command}</Command>
      <Arguments>{arguments}</Arguments>
      <WorkingDirectory>{escape(str(spec.data_dir))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def install_commands(xml_path: Path) -> list[list[str]]:
    return [["schtasks", "/Create", "/TN", WINDOWS_TASK_NAME, "/XML", str(xml_path), "/F"],
            ["schtasks", "/Run", "/TN", WINDOWS_TASK_NAME]]


def uninstall_commands() -> list[list[str]]:
    # /End xatosi e'tiborsiz (vazifa ishlamayotgan bo'lishi mumkin).
    return [["schtasks", "/End", "/TN", WINDOWS_TASK_NAME],
            ["schtasks", "/Delete", "/TN", WINDOWS_TASK_NAME, "/F"]]


def status_command() -> list[str]:
    return ["schtasks", "/Query", "/TN", WINDOWS_TASK_NAME, "/FO", "LIST", "/V"]


def run_key_command(spec: ServiceSpec) -> list[str]:
    """Zaxira (Task Scheduler taqiqlangan korporativ muhit): HKCU Run qiymati. Qayta ishga tushirish yo'q."""
    value = subprocess.list2cmdline([spec.program[0], *task_arguments(spec)])
    return ["reg", "add", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run", "/v", "LahzaEngine",
            "/t", "REG_SZ", "/d", value, "/f"]
