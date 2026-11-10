# -*- coding: utf-8 -*-
"""
TouchpadRescue 配置与自启动
===========================
配置放 %APPDATA%\\TouchpadRescue\\config.json；
开机自启用任务计划（最高权限 + 登录触发 + 定期自检 + 失败重启）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import winreg

APP_NAME = "TouchpadRescue"
TASK_NAME = "TouchpadRescue"

CREATE_NO_WINDOW = 0x08000000

DEFAULT_CONFIG = {
    "hotkey": "Ctrl+Alt+P",
    "theme": "system",          # system / light / dark
    "autostart": True,
    "show_panel_on_hotkey": True,
    "panel_timeout_ms": 3500,
    "interval_check_minutes": 30,
}


# ---------------------------------------------------------------- 路径

def app_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def config_path() -> str:
    return os.path.join(app_dir(), "config.json")


def exe_path() -> str:
    """当前可执行文件路径；脚本方式运行时返回 pythonw + 脚本。"""
    if getattr(sys, "frozen", False):
        return sys.executable
    return sys.executable


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


# ---------------------------------------------------------------- 配置

def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg: dict) -> bool:
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- 系统主题

def system_is_dark() -> bool:
    key = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            v, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
            return int(v) == 0
    except OSError:
        return False


def resolve_dark(cfg: dict) -> bool:
    theme = cfg.get("theme", "system")
    if theme == "dark":
        return True
    if theme == "light":
        return False
    return system_is_dark()


# ---------------------------------------------------------------- 任务计划

TASK_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>TouchpadRescue - 触摸板救援常驻服务（提供全局热键与自愈）</Description>
    <URI>\\{task}</URI>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{user}</UserId>
      <Delay>PT8S</Delay>
    </LogonTrigger>
    <CalendarTrigger>
      <StartBoundary>2026-01-01T00:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <Repetition>
        <Interval>PT{interval}M</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{user}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>false</AllowHardTerminate>
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
    <DisallowStartOnRemoteAppSession>false</DisallowStartOnRemoteAppSession>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>2</Priority>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{command}</Command>
      <Arguments>--autostart</Arguments>
    </Exec>
  </Actions>
</Task>
"""


def current_user() -> str:
    domain = os.environ.get("USERDOMAIN", "")
    name = os.environ.get("USERNAME", "")
    return f"{domain}\\{name}" if domain else name


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           creationflags=CREATE_NO_WINDOW, timeout=25,
                           encoding="mbcs", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return -1, str(e)


def task_exists() -> bool:
    code, _ = _run(["schtasks", "/Query", "/TN", TASK_NAME])
    return code == 0


def install_autostart(cfg: dict | None = None) -> tuple[bool, str]:
    """创建/更新登录自启任务。需要管理员权限。"""
    cfg = cfg or load_config()
    command = exe_path()
    if not is_frozen():
        # 调试用：脚本方式运行时，用 pythonw 拉起同目录入口
        entry = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "TouchpadRescue.pyw")
        entry = os.path.abspath(entry)
        command = f'{sys.executable} "{entry}"'

    xml = TASK_XML.format(
        task=TASK_NAME,
        user=current_user(),
        interval=int(cfg.get("interval_check_minutes", 30)),
        command=command.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
    )
    tmp = os.path.join(tempfile.gettempdir(), "TouchpadRescue_task.xml")
    try:
        with open(tmp, "w", encoding="utf-16") as f:
            f.write(xml)
    except OSError as e:
        return False, f"写入任务定义失败：{e}"

    code, out = _run(["schtasks", "/Create", "/TN", TASK_NAME,
                      "/XML", tmp, "/F"])
    if code == 0:
        return True, "开机自启已启用"
    return False, f"注册自启任务失败（{code}）：{out.strip()[:200]}"


def remove_autostart() -> tuple[bool, str]:
    code, out = _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    if code == 0:
        return True, "开机自启已关闭"
    return False, f"删除任务失败（{code}）：{out.strip()[:200]}"


def start_task_now() -> None:
    _run(["schtasks", "/Run", "/TN", TASK_NAME])
