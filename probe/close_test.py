# -*- coding: utf-8 -*-
"""验证关闭按钮：热键唤出面板 -> 点右上角 X -> 确认窗口隐藏。
注意：本进程不设 DPI 感知，GetWindowRect 返回的是虚拟坐标，
虚拟坐标下窗口尺寸正好等于逻辑尺寸，所以直接用逻辑坐标偏移即可。
"""
import ctypes
import sys
import time
from ctypes import wintypes

from PIL import ImageGrab

u = ctypes.windll.user32
try:
    u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass
u.FindWindowW.restype = wintypes.HWND
u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]

SCALE = 2.0
SHADOW = 24
CLOSE_BOX = (364, 16, 390, 42)


def show_via_hotkey():
    KEYS = [0x11, 0x12, 0x50]
    for k in KEYS:
        u.keybd_event(k, 0, 0, 0)
        time.sleep(0.03)
    time.sleep(0.08)
    for k in reversed(KEYS):
        u.keybd_event(k, 0, 0, 0x0002)
        time.sleep(0.03)


show_via_hotkey()
time.sleep(0.8)

hwnd = u.FindWindowW("TouchpadRescueLayered", "TouchpadRescue")
print("hwnd:", hwnd)
if not hwnd:
    sys.exit("window not found")
print("visible before:", bool(u.IsWindowVisible(hwnd)))

r = wintypes.RECT()
u.GetWindowRect(hwnd, ctypes.byref(r))
print("rect:", r.left, r.top, r.right, r.bottom,
      "size:", r.right - r.left, r.bottom - r.top)

sx = r.left + int(((CLOSE_BOX[0] + CLOSE_BOX[2]) / 2 + SHADOW) * SCALE)
sy = r.top + int(((CLOSE_BOX[1] + CLOSE_BOX[3]) / 2 + SHADOW) * SCALE)
print("click at:", sx, sy)

u.SetCursorPos(sx, sy)
time.sleep(0.2)
u.mouse_event(0x0002, 0, 0, 0, 0)
time.sleep(0.06)
u.mouse_event(0x0004, 0, 0, 0, 0)
time.sleep(0.6)

print("visible after click:", bool(u.IsWindowVisible(hwnd)))
ImageGrab.grab().save(sys.argv[1] if len(sys.argv) > 1 else "shot_close.png")
print("saved")
