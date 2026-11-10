# -*- coding: utf-8 -*-
"""渲染预览：把浅色/深色 × 开启/关闭 四种状态拼成一张图，用于视觉校对。"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image

import tp_ui as U

SCALE = 2


def make(th, enabled, hover="", busy=False, message="", level="ok"):
    st = U.PanelState(enabled=enabled, busy=busy, message=message,
                      level=level, admin=True, hover=hover)
    return U.render_panel(th, st, SCALE)


def main():
    tiles = [
        make(U.LIGHT, True),
        make(U.LIGHT, False),
        make(U.LIGHT, False, hover="primary"),
        make(U.DARK, True),
        make(U.DARK, False),
    ]
    w, h = tiles[0].size
    pad = 16
    sheet = Image.new("RGBA", (w * 2 + pad * 3, h * 3 + pad * 4), (235, 237, 240, 255))
    for i, t in enumerate(tiles):
        col, row = i % 2, i // 2
        sheet.alpha_composite(t, (pad + col * (w + pad), pad + row * (h + pad)))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "probe", "preview_panel.png")
    sheet.save(out)
    print("saved", os.path.abspath(out), sheet.size)

    # 托盘图标放大预览
    tray = Image.new("RGBA", (160, 80), (240, 242, 245, 255))
    tray.alpha_composite(U.render_tray_icon(True, False, 64), (10, 8))
    tray.alpha_composite(U.render_tray_icon(False, False, 64), (86, 8))
    out2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "probe", "preview_tray.png")
    tray.save(out2)
    print("saved", os.path.abspath(out2))

    # 设置页
    s1 = U.render_settings(U.LIGHT, U.SettingsState(
        theme_mode="system", hotkey="Ctrl+Alt+P", autostart=True,
        admin=True, has_task=True, device_name="符合 HID 标准的触摸板"), SCALE)
    s2 = U.render_settings(U.DARK, U.SettingsState(
        theme_mode="dark", hotkey="Ctrl+Alt+P", autostart=True,
        admin=False, has_task=False, device_name="符合 HID 标准的触摸板"), SCALE)
    sw, sh = s1.size
    sheet2 = Image.new("RGBA", (sw * 2 + pad * 3, sh + pad * 2), (235, 237, 240, 255))
    sheet2.alpha_composite(s1, (pad, pad))
    sheet2.alpha_composite(s2, (pad * 2 + sw, pad))
    out3 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "probe", "preview_settings.png")
    sheet2.save(out3)
    print("saved", os.path.abspath(out3), sheet2.size)


if __name__ == "__main__":
    main()
