# -*- coding: utf-8 -*-
"""
TouchpadRescue 应用主体
=======================
托盘常驻 + 全局热键 + 一键重载触摸板。
所有耗时操作（设备重载约 1 秒）走后台线程，界面不卡。
"""
from __future__ import annotations

import ctypes
import os
import sys
import threading
import traceback
from ctypes import wintypes

import tp_config as C
import tp_core as core
import tp_ui as ui
import tp_win as W

user32 = W.user32

WM_APP_RESULT = W.WM_APP + 2
WM_NULL = 0x0000
TIMER_HIDE = 1
TIMER_RETRY = 2

ID_TOGGLE = 1001
ID_SHOW = 1002
ID_SETTINGS = 1003
ID_AUTOSTART = 1004
ID_QUIT = 1005
ID_OPEN_SETTINGS_WIN = 1006


# ---------------------------------------------------------------- 主面板

class Panel(W.LayeredWindow):
    def __init__(self, app: "App"):
        suffix = "-dev" if os.environ.get("TR_DEV") else ""
        super().__init__(ui.CANVAS_W, ui.CANVAS_H, app.scale,
                         title=f"TouchpadRescue{suffix}")
        self.app = app
        self.on_click = self._click
        self.on_message = self._msg
        self.on_key = self._key

    def render(self):
        app = self.app
        st = ui.PanelState(
            enabled=app.enabled,
            busy=app.busy,
            message=app.message,
            level=app.level,
            admin=app.admin,
            hotkey=app.cfg.get("hotkey", "Ctrl+Alt+P"),
            hover=self._hover,
        )
        return ui.render_panel(app.theme, st, app.scale)

    def hit_test(self, x, y):
        cx, cy = x - ui.SHADOW, y - ui.SHADOW
        if _inside(cx, cy, ui.BTN_PRIMARY_BOX):
            return "primary"
        if _inside(cx, cy, ui.BTN_GHOST_BOX):
            return "ghost"
        if _inside(cx, cy, ui.BTN_CLOSE_BOX):
            return "close"
        return ""

    def _click(self, x, y):
        hv = self.hit_test(x, y)
        if os.environ.get("TR_DEBUG"):
            print(f"[click] x={x:.1f} y={y:.1f} hit={hv!r} scale={self.scale}",
                  flush=True)
        if hv == "primary":
            self.app.toggle()
        elif hv == "ghost":
            self.app.open_settings()
        elif hv == "close":
            self.hide()
            user32.KillTimer(self.hwnd, TIMER_HIDE)

    def _key(self, vk):
        if vk == W.VK_ESCAPE:
            self.hide()
            user32.KillTimer(self.hwnd, TIMER_HIDE)

    def _msg(self, msg, wparam, lparam):
        return self.app.handle_message(msg, wparam, lparam)


def _inside(x, y, box) -> bool:
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


# ---------------------------------------------------------------- 设置面板

class SettingsWin(W.LayeredWindow):
    def __init__(self, app: "App"):
        super().__init__(ui.SET_CANVAS_W, ui.SET_CANVAS_H, app.scale,
                         title="TouchpadRescueSettings")
        self.app = app
        self.recording = False
        self.on_click = self._click
        self.on_key = self._key
        self.on_message = self._msg

    def render(self):
        st = ui.SettingsState(
            theme_mode=self.app.cfg.get("theme", "system"),
            hotkey=self.app.cfg.get("hotkey", "Ctrl+Alt+P"),
            autostart=bool(self.app.cfg.get("autostart", True)),
            recording=self.recording,
            admin=self.app.admin,
            has_task=self.app.task_ok,
            device_name=self.app.device_name,
            hover=self._hover,
        )
        return ui.render_settings(self.app.theme, st, self.app.scale)

    def hit_test(self, x, y):
        cx, cy = x - ui.SHADOW, y - ui.SHADOW
        for key, box in ui.SET_HITBOXES.items():
            if _inside(cx, cy, box):
                return key
        return ""

    def _click(self, x, y):
        hv = self.hit_test(x, y)
        if not hv:
            return
        app = self.app
        if hv == "close":
            self.hide()
        elif hv == "theme_system":
            app.set_theme("system")
        elif hv == "theme_light":
            app.set_theme("light")
        elif hv == "theme_dark":
            app.set_theme("dark")
        elif hv == "autostart":
            app.toggle_autostart()
        elif hv == "hotkey":
            self.recording = True
            self.repaint()
        self.repaint()

    def _key(self, vk):
        if not self.recording:
            if vk == W.VK_ESCAPE:
                self.hide()
            return
        if vk == W.VK_ESCAPE:
            self.recording = False
            self.repaint()
            return
        mods = 0
        if user32.GetKeyState(0x11) & 0x8000:
            mods |= W.MOD_CONTROL
        if user32.GetKeyState(0x12) & 0x8000:
            mods |= W.MOD_ALT
        if user32.GetKeyState(0x10) & 0x8000:
            mods |= W.MOD_SHIFT
        if (user32.GetKeyState(0x5B) & 0x8000) or (user32.GetKeyState(0x5C) & 0x8000):
            mods |= W.MOD_WIN

        name = _vk_name(vk)
        if not name or not mods:
            return
        parts = []
        if mods & W.MOD_CONTROL:
            parts.append("Ctrl")
        if mods & W.MOD_ALT:
            parts.append("Alt")
        if mods & W.MOD_SHIFT:
            parts.append("Shift")
        if mods & W.MOD_WIN:
            parts.append("Win")
        parts.append(name)
        spec = "+".join(parts)
        if self.app.set_hotkey(spec):
            self.recording = False
            self.repaint()

    def _msg(self, msg, wparam, lparam):
        return self.app.handle_message(msg, wparam, lparam)


_VK_NAMES = {
    0x70: "F1", 0x71: "F2", 0x72: "F3", 0x73: "F4", 0x74: "F5", 0x75: "F6",
    0x76: "F7", 0x77: "F8", 0x78: "F9", 0x79: "F10", 0x7A: "F11", 0x7B: "F12",
    0x20: "Space", 0xC0: "`", 0xBD: "-", 0xBB: "=", 0xDB: "[", 0xDD: "]",
    0xBA: ";", 0xDE: "'", 0xBC: ",", 0xBE: ".", 0xBF: "/", 0xDC: "\\",
}


def _vk_name(vk: int):
    if 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    if vk in _VK_NAMES:
        return _VK_NAMES[vk]
    return None


# ---------------------------------------------------------------- 应用

class App:
    def __init__(self, argv: list[str]):
        self.argv = argv
        self.cfg = C.load_config()
        self.scale = W.get_scale()
        self.dark = C.resolve_dark(self.cfg)
        self.theme = ui.theme_for(self.dark)
        self.admin = core.is_admin()

        self.busy = False
        self.message = ""
        self.level = "ok"
        self.enabled = core.get_enabled() == 1
        self.devices = []
        self.device_name = ""
        self.task_ok = C.task_exists()
        self._result = None

        # 启动自检：修正上次异常退出可能留下的禁用设备
        self._discover()
        if self.admin and self.devices:
            try:
                core.ensure_devices_enabled([d.instance_id for d in self.devices])
            except Exception:
                pass

        self.panel = Panel(self)
        self.settings_win = None
        self.hwnd = self.panel.hwnd

        tray_imgs = {
            "on": ui.render_tray_icon(True, self.dark, 32),
            "off": ui.render_tray_icon(False, self.dark, 32),
        }
        self.tray = W.TrayIcon(self.hwnd, tray_imgs, self._tray_tip())
        self.tray.add("on" if self.enabled else "off")

        self.hotkey = W.Hotkey(self.hwnd)
        self._register_hotkey()

        if self.cfg.get("autostart") and self.admin and not self.task_ok:
            # 放到后台做：装任务要调 schtasks，万一被安全软件拦了
            # 也不能影响主程序启动和热键响应。
            threading.Thread(target=self._ensure_autostart, daemon=True).start()

    def _ensure_autostart(self):
        try:
            ok, msg = C.install_autostart(self.cfg)
            self.task_ok = ok
            if not ok:
                self.message = "自启注册失败，可在设置里重试"
                self.level = "warn"
                self.refresh()
        except Exception:
            traceback.print_exc()

    # -- 基础
    def _discover(self):
        try:
            self.devices = core.find_touchpad_devices()
        except Exception:
            self.devices = []
        self.device_name = self.devices[0].friendly_name if self.devices else ""

    def _tray_tip(self) -> str:
        state = "已开启" if self.enabled else "已关闭"
        return f"触摸板救援 · 触摸板{state}"

    def _register_hotkey(self):
        spec = self.cfg.get("hotkey", "Ctrl+Alt+P")
        if self.hotkey.register(spec):
            return
        for fb in ("Ctrl+Alt+Shift+P", "Ctrl+Alt+F10"):
            if self.hotkey.register(fb):
                self.cfg["hotkey"] = fb
                C.save_config(self.cfg)
                return
        self.message = "热键被占用，请到设置里换一个"
        self.level = "warn"

    # -- 界面刷新
    def refresh(self):
        key = "on" if self.enabled else "off"
        try:
            self.tray.update(key, self._tray_tip())
        except Exception:
            pass
        if self.panel.visible:
            self.panel.repaint()
        if self.settings_win and self.settings_win.visible:
            self.settings_win.repaint()

    def show_panel(self, auto_hide=True):
        self.panel.show()
        user32.KillTimer(self.hwnd, TIMER_HIDE)
        if auto_hide:
            ms = int(self.cfg.get("panel_timeout_ms", 3500))
            user32.SetTimer(self.hwnd, TIMER_HIDE, ms, None)

    def hide_panel(self):
        self.panel.hide()
        user32.KillTimer(self.hwnd, TIMER_HIDE)

    def open_settings(self):
        if self.settings_win is None:
            self.settings_win = SettingsWin(self)
        self.task_ok = C.task_exists()
        self.hide_panel()
        self.settings_win.show()

    # -- 业务动作
    def toggle(self):
        if self.busy:
            return
        if os.environ.get("TR_DEBUG"):
            import tempfile
            with open(os.path.join(tempfile.gettempdir(), "tr_toggle.log"), "a",
                      encoding="utf-8") as f:
                f.write("---- toggle ----\n" + "".join(traceback.format_stack()))
        target = not self.enabled
        self.busy = True
        self.message = ""
        self.level = "ok"
        self.refresh()
        threading.Thread(target=self._worker, args=(target,), daemon=True).start()

    def apply(self, enable: bool):
        if self.busy:
            return
        self.busy = True
        self.message = ""
        self.level = "ok"
        self.refresh()
        threading.Thread(target=self._worker, args=(enable,), daemon=True).start()

    def _worker(self, target: bool):
        try:
            if not self.devices:
                self._discover()
            r = core.apply_state(target, self.devices or None)
            self._result = (target, r.ok, r.message, r.level)
        except Exception as e:
            self._result = (target, False, f"操作异常：{e}", "error")
            traceback.print_exc()
        try:
            ok = user32.PostMessageW(self.hwnd, WM_APP_RESULT, 0, 0)
            if os.environ.get("TR_DEBUG"):
                print(f"[worker] result={self._result} post={ok} hwnd={self.hwnd}",
                      flush=True)
        except Exception:
            traceback.print_exc()

    def _finish(self):
        if os.environ.get("TR_DEBUG"):
            print(f"[finish] result={self._result}", flush=True)
        if not self._result:
            return
        target, ok, msg, level = self._result
        self._result = None
        self.busy = False
        if ok:
            self.enabled = bool(target)
        self.message = msg
        self.level = level
        self.refresh()
        if self.panel.visible:
            user32.KillTimer(self.hwnd, TIMER_HIDE)
            user32.SetTimer(self.hwnd, TIMER_HIDE,
                            int(self.cfg.get("panel_timeout_ms", 3500)), None)

    # -- 设置项
    def set_theme(self, mode: str):
        self.cfg["theme"] = mode
        C.save_config(self.cfg)
        self.dark = C.resolve_dark(self.cfg)
        self.theme = ui.theme_for(self.dark)
        try:
            self.tray.imgs = {
                "on": ui.render_tray_icon(True, self.dark, 32),
                "off": ui.render_tray_icon(False, self.dark, 32),
            }
            self.tray = W.TrayIcon(self.hwnd, self.tray.imgs, self._tray_tip())
            self.tray.add("on" if self.enabled else "off")
        except Exception:
            pass
        self.refresh()

    def set_hotkey(self, spec: str) -> bool:
        old = self.cfg.get("hotkey", "Ctrl+Alt+P")
        if self.hotkey.register(spec):
            self.cfg["hotkey"] = spec
            C.save_config(self.cfg)
            self.message = f"快捷键已改为 {spec}"
            self.level = "ok"
            self.refresh()
            return True
        self.hotkey.register(old)
        self.message = f"{spec} 被其它程序占用"
        self.level = "warn"
        if self.settings_win:
            self.settings_win.repaint()
        return False

    def toggle_autostart(self):
        if not self.admin:
            self.message = "需要管理员权限才能修改自启"
            self.level = "warn"
            return
        if self.cfg.get("autostart"):
            ok, _ = C.remove_autostart()
            if ok:
                self.cfg["autostart"] = False
                C.save_config(self.cfg)
                self.task_ok = False
        else:
            ok, _ = C.install_autostart(self.cfg)
            if ok:
                self.cfg["autostart"] = True
                C.save_config(self.cfg)
                self.task_ok = True
        if self.settings_win:
            self.settings_win.repaint()

    # -- 托盘菜单
    def _tray_menu(self):
        menu = user32.CreatePopupMenu()
        label = "关闭触摸板" if self.enabled else "开启触摸板"
        user32.AppendMenuW(menu, W.MF_STRING, ID_TOGGLE, label)
        user32.AppendMenuW(menu, W.MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, W.MF_STRING, ID_SHOW, "显示面板")
        user32.AppendMenuW(menu, W.MF_STRING | (W.MF_GRAYED if False else 0),
                           ID_SETTINGS, "设置…")
        auto_flag = W.MF_CHECKED if self.cfg.get("autostart") else 0
        user32.AppendMenuW(menu, W.MF_STRING | auto_flag, ID_AUTOSTART, "开机自启")
        user32.AppendMenuW(menu, W.MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, W.MF_STRING, ID_QUIT, "退出")

        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenu(menu, W.TPM_RIGHTBUTTON | W.TPM_RETURNCMD,
                                    pt.x, pt.y, 0, self.hwnd, None)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)
        return cmd

    def on_menu(self, cmd: int):
        if cmd == ID_TOGGLE:
            self.toggle()
            if not self.panel.visible:
                self.show_panel()
        elif cmd == ID_SHOW:
            self.show_panel(auto_hide=False)
        elif cmd == ID_SETTINGS:
            self.open_settings()
        elif cmd == ID_AUTOSTART:
            self.cfg["autostart"] = not self.cfg.get("autostart")
            C.save_config(self.cfg)
            if self.cfg["autostart"]:
                ok, _ = C.install_autostart(self.cfg)
                self.task_ok = ok
            else:
                C.remove_autostart()
                self.task_ok = False
        elif cmd == ID_QUIT:
            self.quit()

    # -- 消息
    def handle_message(self, msg, wparam, lparam) -> bool:
        if msg == W.WM_HOTKEY and wparam == self.hotkey.id:
            self.toggle()
            if self.cfg.get("show_panel_on_hotkey", True) and not self.panel.visible:
                self.show_panel()
            return True

        if msg == W.WM_TRAY:
            ev = lparam & 0xFFFF
            if ev in (W.WM_LBUTTONUP,):
                if self.panel.visible:
                    self.hide_panel()
                else:
                    self.show_panel(auto_hide=False)
                return True
            if ev == W.WM_RBUTTONUP:
                cmd = self._tray_menu()
                if cmd:
                    self.on_menu(cmd)
                return True
            return True

        if msg == W.WM_TIMER:
            if wparam == TIMER_HIDE:
                user32.KillTimer(self.hwnd, TIMER_HIDE)
                self.hide_panel()
            return True

        if msg == WM_APP_RESULT:
            self._finish()
            return True

        if msg == W.WM_SETTINGCHANGE:
            if self.cfg.get("theme") == "system":
                new_dark = C.system_is_dark()
                if new_dark != self.dark:
                    self.dark = new_dark
                    self.theme = ui.theme_for(new_dark)
                    self.refresh()
            return True

        return False

    # -- 退出
    def quit(self):
        try:
            self.hotkey.unregister()
        except Exception:
            pass
        try:
            self.tray.remove()
        except Exception:
            pass
        user32.PostQuitMessage(0)

    def run(self, show_on_start: bool):
        if show_on_start:
            self.show_panel(auto_hide=False)
        W.run_message_loop()


# ---------------------------------------------------------------- 入口

def _single_instance() -> bool:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    name = "Local\\TouchpadRescue-SingleInstance"
    if os.environ.get("TR_DEV"):
        # 调试实例用独立互斥量，方便和正在运行的正式实例共存
        name += "-dev"
    h = kernel32.CreateMutexW(None, False, name)
    if not h:
        return True
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        return False
    return True


def _set_dpi_aware():
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def _crash_log(exc_text: str):
    """窗口模式没有控制台，异常必须落盘，否则出问题无从查起。"""
    try:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "TouchpadRescue")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "crash.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"\n===== {__import__('datetime').datetime.now()} =====\n")
            f.write(exc_text)
    except Exception:
        pass


def main():
    try:
        return _main()
    except Exception:
        _crash_log(traceback.format_exc())
        raise


def _main():
    _set_dpi_aware()
    if not _single_instance():
        print("已经在运行")
        return 1
    autostart = "--autostart" in sys.argv
    app = App(sys.argv)
    app.run(show_on_start=not autostart)
    return 0


if __name__ == "__main__":
    sys.exit(main())
