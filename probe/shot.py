# -*- coding: utf-8 -*-
"""抓屏，用于验证窗口真实渲染效果。"""
import sys
import time

from PIL import ImageGrab

delay = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
out = sys.argv[2] if len(sys.argv) > 2 else "shot.png"
time.sleep(delay)
img = ImageGrab.grab(all_screens=True)
img.save(out)
print("saved", out, img.size)
