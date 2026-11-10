# -*- coding: utf-8 -*-
"""验证窗口可拖动：向空白区投递 DOWN -> MOVE -> UP，比较窗口位置。"""
import ctypes
import sys
import time
from ctypes import wintypes

u = ctypes.windll.user32
try:
    u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass
u.FindWindowW.restype = wintypes.HWND
u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

WM_LBUTTONDOWN, WM_MOUSEMOVE, WM_LBUTTONUP = 0x0201, 0x0200, 0x0202
MK_LBUTTON = 0x0001
SCALE = 2.0

hwnd = u.FindWindowW("TouchpadRescueLayered", "TouchpadRescue")
if not hwnd:
    sys.exit("no window")


def rect():
    r = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top


def lp(x_log, y_log):
    return (int(y_log * SCALE) << 16) | int(x_log * SCALE)


before = rect()
print("before:", before)

# 从标题区右侧空白处（非按钮）按下
u.PostMessageW(hwnd, WM_LBUTTONDOWN, 0, lp(250, 62))
time.sleep(0.12)
# 分几步移动，模拟真实拖动
for step in (1, 2, 3):
    u.PostMessageW(hwnd, WM_MOUSEMOVE, MK_LBUTTON, lp(250 + step * 35, 62 + step * 20))
    time.sleep(0.06)
u.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp(355, 122))
time.sleep(0.4)

after = rect()
print("after :", after)
dx, dy = after[0] - before[0], after[1] - before[1]
print(f"moved: ({dx}, {dy})  期望约 (210, 120)")
print("RESULT:", "PASS" if abs(dx - 210) < 30 and abs(dy - 120) < 30 else "FAIL")
