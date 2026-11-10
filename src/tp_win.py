# -*- coding: utf-8 -*-
"""
TouchpadRescue Win32 层
=======================
不依赖任何 GUI 框架，直接用 ctypes 建分层窗口 + 托盘 + 全局热键。
窗口内容全部由 Pillow 渲染成位图后贴上去。
"""
from __future__ import annotations

import ctypes
import os
import tempfile
from ctypes import wintypes

from PIL import Image

# ---------------------------------------------------------------- 常量

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_QUIT = 0x0012
WM_PAINT = 0x000F
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_MOUSELEAVE = 0x02A3
WM_KEYDOWN = 0x0100
WM_TIMER = 0x0113
WM_HOTKEY = 0x0312
WM_SETTINGCHANGE = 0x001A
WM_APP = 0x8000
WM_TRAY = WM_APP + 1
WM_DPICHANGED = 0x02E0

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0
AC_SRC_ALPHA = 1
BI_RGB = 0
DIB_RGB_COLORS = 0

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
SW_SHOW = 5

SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOREDRAW = 0x0008
SWP_NOACTIVATE = 0x0010

VK_ESCAPE = 0x1B
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x01, 0x02, 0x04
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
MF_STRING, MF_SEPARATOR, MF_CHECKED, MF_GRAYED = 0x0000, 0x0800, 0x0008, 0x0001
SM_CXSCREEN, SM_CYSCREEN = 0, 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
IDC_ARROW = 32512
IDC_HAND = 32649
IDC_SIZEALL = 32646
WM_SETCURSOR = 0x0020

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)


# ---------------------------------------------------------------- 结构

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [("hdc", wintypes.HDC), ("fErase", wintypes.BOOL),
                ("rcPaint", wintypes.RECT), ("fRestore", wintypes.BOOL),
                ("fIncUpdate", wintypes.BOOL), ("rgbReserved", ctypes.c_byte * 32)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER),
                ("bmiColors", wintypes.DWORD * 3)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte),
                ("AlphaFormat", ctypes.c_ubyte)]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD), ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD), ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


class TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("hwndTrack", wintypes.HWND), ("dwHoverTime", wintypes.DWORD)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD), ("pt", wintypes.POINT)]


# ---------------------------------------------------------------- API 声明

user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPVOID]
user32.LoadCursorW.restype = wintypes.HANDLE
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int
user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT),
    ctypes.POINTER(wintypes.SIZE), wintypes.HDC, ctypes.POINTER(wintypes.POINT),
    wintypes.DWORD, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD,
]
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = LRESULT
user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
user32.SetTimer.restype = ctypes.c_size_t
user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
user32.KillTimer.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.GetKeyState.argtypes = [ctypes.c_int]
user32.GetKeyState.restype = ctypes.c_short
user32.TrackMouseEvent.argtypes = [ctypes.POINTER(TRACKMOUSEEVENT)]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND,
                               wintypes.UINT, wintypes.UINT]
user32.SetCapture.argtypes = [wintypes.HWND]
user32.SetCapture.restype = wintypes.HWND
user32.ReleaseCapture.argtypes = []
user32.ReleaseCapture.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.TrackPopupMenu.argtypes = [
    wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, wintypes.HWND, ctypes.c_void_p,
]
user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.SetCursor.argtypes = [wintypes.HANDLE]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL
user32.GetCursorPos.restype = wintypes.BOOL
user32.LoadImageW.restype = wintypes.HANDLE
user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                              ctypes.c_int, ctypes.c_int, wintypes.UINT]

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD,
]
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]

shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]


# ---------------------------------------------------------------- 工具

def get_scale() -> float:
    """界面缩放比例。优先用 GetDpiForSystem（高 DPI 显示器才准），
    GetDeviceCaps 在 DPI-aware 进程里只返回 96，不可靠。"""
    try:
        dpi = user32.GetDpiForSystem()
        if dpi and dpi > 48:
            return max(1.0, dpi / 96.0)
    except Exception:
        pass
    try:
        hdc = user32.GetDC(None)
        dpi = gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        user32.ReleaseDC(None, hdc)
        return max(1.0, dpi / 96.0)
    except Exception:
        return 1.0


def make_hicon(img: Image.Image, path_hint: str = "icon") -> int:
    """把 PIL 图存成 ico 再加载为 HICON。"""
    d = os.path.join(tempfile.gettempdir(), "TouchpadRescue")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{path_hint}.ico")
    sizes = [(16, 16), (20, 20), (24, 24), (32, 32), (48, 48), (64, 64)]
    img.save(path, format="ICO", sizes=sizes)
    h = user32.LoadImageW(None, path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
    return h


# ---------------------------------------------------------------- 基础窗口

class LayeredWindow:
    """分层窗口：内容由 render() 返回的 RGBA 图决定。"""

    _class_atom = None
    _class_name = "TouchpadRescueLayered"
    _instances: dict = {}
    _global_wndproc = None

    def __init__(self, w: int, h: int, scale: float = 1.0, title: str = "TouchpadRescue"):
        self.logical_w = w
        self.logical_h = h
        self.scale = scale
        self.title = title
        self.hwnd = None
        self.draggable = True          # 空白区域可拖动整个窗口
        self._drag_origin = None       # (mouse_x, mouse_y, win_x, win_y)
        self._drag_moved = False
        self._last_img = None
        self._placed = False
        self.visible = False
        self._hover = ""
        self._tracking = False
        self._mem_dc = None
        self._mem_bmp = None
        self._mem_bits = None
        self._mem_size = (0, 0)
        self.on_click = None      # (x_logical, y_logical) -> None
        self.on_hover = None      # (hover_id) -> None
        self.on_key = None        # (vk) -> None
        self.on_message = None    # (msg, wparam, lparam) -> bool
        self._create()

    # -- 全局窗口过程（按 hwnd 分发到实例）
    @staticmethod
    def _dispatch(hwnd, msg, wparam, lparam):
        inst = LayeredWindow._instances.get(hwnd)
        if inst is None:
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        try:
            return inst._proc(hwnd, msg, wparam, lparam)
        except Exception:
            # 同一个异常只记一次，避免回调里刷屏拖死消息循环
            cls = LayeredWindow
            if cls._err_count < 5:
                cls._err_count += 1
                import traceback
                traceback.print_exc()
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    _err_count = 0

    def _proc(self, hwnd, msg, wparam, lparam):
        if self.on_message is not None:
            if self.on_message(msg, wparam, lparam):
                return 0

        if msg == WM_MOUSEMOVE:
            # 拖动中：必须用「屏幕绝对坐标」算位移。
            # WM_MOUSEMOVE 的 lparam 是相对窗口客户区的，窗口一移动原点就跟着变，
            # 用它算 delta 会形成正反馈 —— 窗口抖成筛子。
            if self._drag_origin:
                pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                sx0, sy0, wx, wy = self._drag_origin
                dx, dy = pt.x - sx0, pt.y - sy0
                if not self._drag_moved and (abs(dx) > 3 or abs(dy) > 3):
                    self._drag_moved = True
                if self._drag_moved:
                    self._move_to(wx + dx, wy + dy)
                return 0

            if not self._tracking:
                tme = TRACKMOUSEEVENT()
                tme.cbSize = ctypes.sizeof(tme)
                tme.dwFlags = 0x00000002  # TME_LEAVE
                tme.hwndTrack = hwnd
                user32.TrackMouseEvent(ctypes.byref(tme))
                self._tracking = True
            x = ctypes.c_short(lparam & 0xFFFF).value / self.scale
            y = ctypes.c_short((lparam >> 16) & 0xFFFF).value / self.scale

            hv = self.hit_test(x, y)
            if hv != self._hover:
                self._hover = hv
                self.repaint()
            return 0

        if msg == WM_LBUTTONDOWN:
            x = ctypes.c_short(lparam & 0xFFFF).value / self.scale
            y = ctypes.c_short((lparam >> 16) & 0xFFFF).value / self.scale
            if self.draggable and not self.hit_test(x, y):
                pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                # 记的是屏幕坐标 + 窗口当时的左上角
                self._drag_origin = (pt.x, pt.y, self._x, self._y)
                self._drag_moved = False
                user32.SetCapture(hwnd)
            return 0

        if msg == WM_MOUSELEAVE:
            self._tracking = False
            if self._drag_origin:
                return 0      # 拖动中窗口在动，别重绘，否则和拖动互相拉扯
            if self._hover:
                self._hover = ""
                self.repaint()
            return 0

        if msg == WM_LBUTTONUP:
            if self._drag_origin:
                user32.ReleaseCapture()
                was_moved = self._drag_moved
                self._drag_origin = None
                self._drag_moved = False
                if was_moved:
                    # 拖到屏幕外找不回来就糟了，夹回工作区
                    if self._last_img is not None:
                        w, h = self._last_img.size
                        nx, ny = self._clamp_to_work_area(self._x, self._y, w, h)
                        if (nx, ny) != (self._x, self._y):
                            self._move_to(nx, ny)
                    return 0          # 拖动结束，不算点击
            x = ctypes.c_short(lparam & 0xFFFF).value / self.scale
            y = ctypes.c_short((lparam >> 16) & 0xFFFF).value / self.scale
            if self.on_click:
                self.on_click(x, y)
            return 0

        if msg == WM_SETCURSOR:
            if (lparam & 0xFFFF) == 1:   # HTCLIENT
                pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                cx = (pt.x - self._x) / self.scale
                cy = (pt.y - self._y) / self.scale
                hv = self.hit_test(cx, cy)
                if hv:
                    user32.SetCursor(user32.LoadCursorW(None, ctypes.c_void_p(IDC_HAND)))
                elif self.draggable:
                    user32.SetCursor(user32.LoadCursorW(None, ctypes.c_void_p(IDC_SIZEALL)))
                return 1
            return 0

        if msg == WM_KEYDOWN:
            if self.on_key:
                self.on_key(wparam)
            return 0

        if msg == WM_DESTROY:
            self.hwnd = None
            return 0

        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # -- 子类可覆盖
    def hit_test(self, x: float, y: float) -> str:
        return ""

    def render(self) -> Image.Image:
        raise NotImplementedError

    # -- 创建
    def _create(self):
        hinst = kernel32.GetModuleHandleW(None)
        if LayeredWindow._class_atom is None:
            LayeredWindow._global_wndproc = WNDPROC(LayeredWindow._dispatch)
            wc = WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(wc)
            wc.style = 0
            wc.lpfnWndProc = LayeredWindow._global_wndproc
            wc.hInstance = hinst
            wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(IDC_ARROW))
            wc.lpszClassName = self._class_name
            LayeredWindow._class_atom = user32.RegisterClassExW(ctypes.byref(wc))
        w = int(self.logical_w * self.scale)
        h = int(self.logical_h * self.scale)
        ex = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
        self.hwnd = user32.CreateWindowExW(ex, self._class_name, self.title,
                                           WS_POPUP, 0, 0, w, h,
                                           None, None, hinst, None)
        LayeredWindow._instances[self.hwnd] = self

    # -- 绘制
    def _ensure_mem(self, w, h):
        if self._mem_size == (w, h) and self._mem_dc:
            return
        if self._mem_dc:
            gdi32.DeleteObject(self._mem_bmp)
            gdi32.DeleteDC(self._mem_dc)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h     # 自上而下
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        bits = ctypes.c_void_p()
        dc = gdi32.CreateCompatibleDC(None)
        bmp = gdi32.CreateDIBSection(dc, ctypes.byref(bmi), DIB_RGB_COLORS,
                                     ctypes.byref(bits), None, 0)
        gdi32.SelectObject(dc, bmp)
        self._mem_dc, self._mem_bmp, self._mem_bits = dc, bmp, bits
        self._mem_size = (w, h)

    def present(self, img: Image.Image, x: int | None = None, y: int | None = None):
        if not self.hwnd:
            return
        self._last_img = img
        w, h = img.size
        self._ensure_mem(w, h)
        data = img.tobytes("raw", "BGRA")
        ctypes.memmove(self._mem_bits, data, len(data))

        if x is None or y is None:
            x = (user32.GetSystemMetrics(SM_CXSCREEN) - w) // 2
            y = (user32.GetSystemMetrics(SM_CYSCREEN) - h) // 2
            x, y = self._clamp_to_work_area(x, y, w, h)

        hdc_screen = user32.GetDC(None)
        pt_dst = wintypes.POINT(int(x), int(y))
        pt_src = wintypes.POINT(0, 0)
        size = wintypes.SIZE(w, h)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(self.hwnd, hdc_screen, ctypes.byref(pt_dst),
                                   ctypes.byref(size), self._mem_dc,
                                   ctypes.byref(pt_src), 0, ctypes.byref(blend),
                                   ULW_ALPHA)
        user32.ReleaseDC(None, hdc_screen)

    def _clamp_to_work_area(self, x, y, w, h):
        rect = wintypes.RECT()
        if user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
            if x + w > rect.right:
                x = rect.right - w
            if y + h > rect.bottom:
                y = rect.bottom - h
            x = max(rect.left, x)
            y = max(rect.top, y)
        return x, y

    def repaint(self):
        if self.hwnd and self.visible:
            self.present(self.render(), self._x, self._y)

    def _move_to(self, x: int, y: int):
        """
        拖动时移动窗口：用 SetWindowPos 而不是重新 UpdateLayeredWindow。
        UpdateLayeredWindow 每帧都要重新上传整张位图（这里 904×592×4 ≈ 2.1MB），
        拖动时会明显滞后；SetWindowPos 只是告诉 DWM 挪位置，内容跟着走，开销极小。
        """
        self._x, self._y = int(x), int(y)
        if self.hwnd:
            user32.SetWindowPos(self.hwnd, None, self._x, self._y, 0, 0,
                                SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
                                | SWP_NOREDRAW)

    _x: int = 0
    _y: int = 0

    def show(self, x=None, y=None, activate=True):
        if not self.hwnd:
            return
        img = self.render()
        w, h = img.size
        if x is None and y is None:
            if self._placed:
                # 记住上次拖到的位置
                x, y = self._x, self._y
            else:
                x = (user32.GetSystemMetrics(SM_CXSCREEN) - w) // 2
                y = (user32.GetSystemMetrics(SM_CYSCREEN) - h) // 2
        x, y = self._clamp_to_work_area(int(x), int(y), w, h)
        self._x, self._y = x, y
        self._placed = True
        self.present(img, x, y)
        self.visible = True
        user32.ShowWindow(self.hwnd, SW_SHOW if activate else SW_SHOWNOACTIVATE)
        if activate:
            user32.SetForegroundWindow(self.hwnd)

    def hide(self):
        if self.hwnd:
            user32.ShowWindow(self.hwnd, SW_HIDE)
        self.visible = False
        self._hover = ""

    def destroy(self):
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            LayeredWindow._instances.pop(self.hwnd, None)
            self.hwnd = None


# ---------------------------------------------------------------- 托盘

class TrayIcon:
    def __init__(self, hwnd: int, imgs: dict, tooltip: str = "TouchpadRescue"):
        self.hwnd = hwnd
        self.imgs = imgs            # {"on": PIL, "off": PIL}
        self.tooltip = tooltip
        self._hicon = {}
        self._added = False
        for k, im in imgs.items():
            self._hicon[k] = make_hicon(im, f"tray_{k}")

    def _data(self, key: str) -> NOTIFYICONDATAW:
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self._hicon.get(key) or self._hicon.get("on")
        nid.szTip = self.tooltip[:127]
        return nid

    def add(self, key="on"):
        nid = self._data(key)
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        self._added = True

    def update(self, key="on", tooltip: str | None = None):
        if tooltip:
            self.tooltip = tooltip
        nid = self._data(key)
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def remove(self):
        if not self._added:
            return
        nid = self._data("on")
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        self._added = False


# ---------------------------------------------------------------- 热键

VK_MAP = {
    "A": 0x41, "B": 0x42, "C": 0x43, "D": 0x44, "E": 0x45, "F": 0x46, "G": 0x47,
    "H": 0x48, "I": 0x49, "J": 0x4A, "K": 0x4B, "L": 0x4C, "M": 0x4D, "N": 0x4E,
    "O": 0x4F, "P": 0x50, "Q": 0x51, "R": 0x52, "S": 0x53, "T": 0x54, "U": 0x55,
    "V": 0x56, "W": 0x57, "X": 0x58, "Y": 0x59, "Z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
    "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
}


def parse_hotkey(spec: str):
    """'Ctrl+Alt+P' -> (modifiers, vk)"""
    mods = 0
    key = None
    for part in spec.replace(" ", "").split("+"):
        low = part.lower()
        if low in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif low == "alt":
            mods |= MOD_ALT
        elif low == "shift":
            mods |= MOD_SHIFT
        elif low in ("win", "super"):
            mods |= MOD_WIN
        elif part.upper() in VK_MAP:
            key = VK_MAP[part.upper()]
    if key is None:
        key = VK_MAP["P"]
    return mods, key


class Hotkey:
    def __init__(self, hwnd: int, hotkey_id: int = 1):
        self.hwnd = hwnd
        self.id = hotkey_id
        self.current = None

    def register(self, spec: str) -> bool:
        self.unregister()
        mods, vk = parse_hotkey(spec)
        ok = bool(user32.RegisterHotKey(self.hwnd, self.id, mods | MOD_NOREPEAT, vk))
        if ok:
            self.current = spec
        return ok

    def unregister(self):
        if self.current:
            user32.UnregisterHotKey(self.hwnd, self.id)
            self.current = None


# ---------------------------------------------------------------- 消息循环

def run_message_loop():
    msg = MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
