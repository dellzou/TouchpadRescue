# -*- coding: utf-8 -*-
"""
拖动质量检测：真实按住鼠标拖，逐帧记录窗口位置，判断有无抖动/延迟。

判定标准：
  1. 单调性 —— 拖动过程中窗口 x/y 不应出现反向移动（回退即抖动）
  2. 跟随度 —— 最终位移应约等于鼠标位移
  3. 稳定性 —— 每帧位移应接近恒定，忽大忽小说明有反馈震荡

注意：本脚本使用真实鼠标事件（SetCursorPos + mouse_event），
      只在卡片空白区操作，不触碰键盘。
"""
import ctypes
import sys
import time
from ctypes import wintypes

u = ctypes.windll.user32
u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
u.FindWindowW.restype = wintypes.HWND
u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]

SHADOW = 24
START = (250, 62)      # 卡片内空白点（逻辑）
DELTA = (-200, -150)   # 向左上拖，避开边界
STEPS = 25
SCALE = 2.0

hwnd = u.FindWindowW("TouchpadRescueLayered", "TouchpadRescue")
if not hwnd:
    sys.exit("窗口未找到")
if not u.IsWindowVisible(hwnd):
    sys.exit("窗口不可见，先让它显示出来")


def rect():
    r = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top


x0, y0 = rect()
print(f"起始窗口位置: ({x0}, {y0})")

# 按下点（屏幕物理坐标）
px = int(x0 + (START[0] + SHADOW) * SCALE)
py = int(y0 + (START[1] + SHADOW) * SCALE)
u.SetCursorPos(px, py)
time.sleep(0.15)


def cursor():
    p = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


print(f"按下前光标: {cursor()}  设定值: ({px}, {py})")
u.SetForegroundWindow(hwnd)
time.sleep(0.25)
u.mouse_event(0x0002, 0, 0, 0, 0)      # LEFTDOWN
time.sleep(0.08)
print(f"按下后光标: {cursor()}")
print(f"按下后窗口: {rect()}")

positions = []
for i in range(1, STEPS + 1):
    cx = int(px + (DELTA[0] * SCALE) * i / STEPS)
    cy = int(py + (DELTA[1] * SCALE) * i / STEPS)
    u.SetCursorPos(cx, cy)
    time.sleep(0.018)
    positions.append(rect())

time.sleep(0.1)
print(f"抬起前光标: {cursor()}")
u.mouse_event(0x0004, 0, 0, 0, 0)      # LEFTUP
time.sleep(0.35)

x1, y1 = rect()
print(f"结束窗口位置: ({x1}, {y1})")
print(f"光标实际位移: ({cursor()[0] - px}, {cursor()[1] - py})")

# ---- 分析
xs = [p[0] for p in positions]
ys = [p[1] for p in positions]

# 回退 = 与拖动方向相反的位移（往哪边拖都适用）
sx = 1 if DELTA[0] >= 0 else -1
sy = 1 if DELTA[1] >= 0 else -1
back_x = sum(1 for a, b in zip(xs, xs[1:]) if (b - a) * sx < 0)
back_y = sum(1 for a, b in zip(ys, ys[1:]) if (b - a) * sy < 0)

deltas_x = [b - a for a, b in zip(xs, xs[1:])]
deltas_y = [b - a for a, b in zip(ys, ys[1:])]


def spread(v):
    if not v:
        return 0
    return max(v) - min(v)


print()
print(f"采样帧数      : {len(positions)}")
print(f"窗口实际位移  : ({x1 - x0}, {y1 - y0})   期望约 ({DELTA[0]*SCALE:.0f}, {DELTA[1]*SCALE:.0f})")
print(f"x 回退次数    : {back_x}   y 回退次数: {back_y}   (0 = 无抖动)")
print(f"单帧位移波动  : x={spread(deltas_x)}px  y={spread(deltas_y)}px  (越小越平稳)")
print()
print(f"x 轨迹: {xs[:12]}{' ...' if len(xs) > 12 else ''}")
print(f"y 轨迹: {ys[:12]}{' ...' if len(ys) > 12 else ''}")

ok = back_x == 0 and back_y == 0
print()
print("RESULT:", "PASS 无抖动" if ok else f"FAIL 检测到回退 (x={back_x}, y={back_y})")
