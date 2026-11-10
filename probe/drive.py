# -*- coding: utf-8 -*-
"""
用窗口消息驱动界面测试：直接 PostMessage(WM_LBUTTONUP)，不碰系统键盘。
用法: drive.py <x_logical> <y_logical> <out.png>
坐标相对窗口左上角（逻辑像素），会自动按 2.0 的 DPI 缩放转物理坐标。
"""
import ctypes
import sys
import time
from ctypes import wintypes

from PIL import ImageGrab

u = ctypes.windll.user32
u.FindWindowW.restype = wintypes.HWND
u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                           wintypes.WPARAM, wintypes.LPARAM]

WM_LBUTTONUP = 0x0202
SCALE = 2.0

x_log = int(sys.argv[1])
y_log = int(sys.argv[2])
out = sys.argv[3] if len(sys.argv) > 3 else "shot_drive.png"
cls = sys.argv[4] if len(sys.argv) > 4 else "TouchpadRescueLayered"

hwnd = u.FindWindowW(cls, "TouchpadRescue")
print("hwnd:", hwnd, "visible:", bool(u.IsWindowVisible(hwnd)) if hwnd else None)
if not hwnd:
    sys.exit("window not found")

px = int(x_log * SCALE)
py = int(y_log * SCALE)
lparam = (py << 16) | px
u.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
print(f"posted click at logical ({x_log},{y_log}) -> physical ({px},{py})")

time.sleep(0.7)
ImageGrab.grab().save(out)
print("saved", out)
