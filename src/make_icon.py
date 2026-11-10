# -*- coding: utf-8 -*-
"""生成应用图标 assets/app.ico"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tp_ui as U

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
os.makedirs(out_dir, exist_ok=True)

img = U.render_tray_icon(True, False, 256)
path = os.path.join(out_dir, "app.ico")
img.save(path, format="ICO", sizes=[(16, 16), (20, 20), (24, 24), (32, 32),
                                    (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)])
print("saved", os.path.abspath(path))

png = os.path.join(out_dir, "app.png")
img.save(png)
print("saved", png)
