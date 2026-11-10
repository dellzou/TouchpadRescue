# -*- coding: utf-8 -*-
"""
TouchpadRescue 视觉层
=====================
用 Pillow 离屏渲染成 RGBA 位图，再通过 UpdateLayeredWindow 贴到窗口上。
好处：真圆角、真阴影、逐像素透明，且不依赖任何 GUI 框架。

所有尺寸都是「逻辑像素」，渲染时按 DPI 缩放。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------- 版面常量

SHADOW = 24              # 卡片四周留出的阴影空间
CARD_W, CARD_H = 404, 248
CANVAS_W = CARD_W + SHADOW * 2
CANVAS_H = CARD_H + SHADOW * 2
RADIUS = 14

FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


# ---------------------------------------------------------------- 主题

@dataclass(frozen=True)
class Theme:
    dark: bool
    card: tuple
    border: tuple
    text: tuple
    subtext: tuple
    faint: tuple
    accent: tuple
    accent_hover: tuple
    accent_text: tuple
    ghost: tuple
    ghost_hover: tuple
    ghost_text: tuple
    ok: tuple
    warn: tuple
    danger: tuple
    track: tuple
    shadow_alpha: int


LIGHT = Theme(
    dark=False,
    card=(255, 255, 255, 255),
    border=(228, 231, 236, 255),
    text=(24, 28, 35, 255),
    subtext=(108, 116, 128, 255),
    faint=(150, 157, 168, 255),
    accent=(37, 99, 235, 255),
    accent_hover=(29, 78, 216, 255),
    accent_text=(255, 255, 255, 255),
    ghost=(243, 244, 246, 255),
    ghost_hover=(233, 235, 239, 255),
    ghost_text=(55, 62, 74, 255),
    ok=(16, 163, 127, 255),
    warn=(217, 119, 6, 255),
    danger=(220, 60, 60, 255),
    track=(209, 213, 219, 255),
    shadow_alpha=46,
)

DARK = Theme(
    dark=True,
    card=(32, 34, 38, 255),
    border=(52, 56, 63, 255),
    text=(240, 242, 245, 255),
    subtext=(154, 161, 172, 255),
    faint=(120, 127, 138, 255),
    accent=(59, 130, 246, 255),
    accent_hover=(37, 99, 235, 255),
    accent_text=(255, 255, 255, 255),
    ghost=(44, 47, 53, 255),
    ghost_hover=(54, 58, 65, 255),
    ghost_text=(214, 219, 226, 255),
    ok=(45, 190, 145, 255),
    warn=(234, 160, 46, 255),
    danger=(238, 96, 96, 255),
    track=(70, 75, 84, 255),
    shadow_alpha=120,
)

THEMES = {False: LIGHT, True: DARK}


def theme_for(dark: bool) -> Theme:
    return THEMES[bool(dark)]


# ---------------------------------------------------------------- 字体

_font_cache: dict = {}


def font(size: int, bold: bool = False):
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    candidates = (
        ["msyhbd.ttc", "msyh.ttc", "simhei.ttf"]
        if bold else
        ["msyh.ttc", "msyhl.ttc", "simhei.ttf"]
    )
    chosen = None
    for name in candidates:
        path = os.path.join(FONT_DIR, name)
        if os.path.exists(path):
            try:
                chosen = ImageFont.truetype(path, size)
                break
            except OSError:
                continue
    if chosen is None:
        chosen = ImageFont.load_default()
    _font_cache[key] = chosen
    return chosen


# ---------------------------------------------------------------- 绘制工具

def _rounded(img, box, radius, fill=None, outline=None, width=1):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _text(draw, xy, s, f, fill, anchor="la"):
    draw.text(xy, s, font=f, fill=fill, anchor=anchor)


def _shadow_layer(size, card_box, radius, alpha):
    """生成柔和外阴影。"""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(card_box, radius=radius, fill=(0, 0, 0, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(14))
    return layer


# ---------------------------------------------------------------- 图标

def _draw_app_icon(img, box):
    """程序图标：圆角方块 + 触控板轮廓 + 双指。"""
    x0, y0, x1, y1 = box
    w = x1 - x0
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=int(w * 0.28), fill=(37, 99, 235, 255))
    pad = w * 0.24
    tr = (int(x0 + pad), int(y0 + pad), int(x1 - pad), int(y1 - pad * 1.05))
    d.rounded_rectangle(tr, radius=int(w * 0.09),
                        outline=(255, 255, 255, 235), width=max(2, int(w * 0.055)))
    cx = (x0 + x1) / 2
    dot_r = w * 0.048
    for dx in (-w * 0.10, w * 0.10):
        d.ellipse([cx + dx - dot_r, y1 - pad * 1.45 - dot_r,
                   cx + dx + dot_r, y1 - pad * 1.45 + dot_r],
                  fill=(255, 255, 255, 235))


def _draw_status_dot(draw, cx, cy, r, color):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)


# ---------------------------------------------------------------- 主面板

@dataclass
class PanelState:
    enabled: bool | None      # True 开启 / False 关闭 / None 未知
    busy: bool = False
    message: str = ""
    level: str = "ok"         # ok / warn / error
    admin: bool = True
    hotkey: str = "Ctrl+Alt+P"
    hover: str = ""


BTN_PRIMARY_BOX = (22, 168, 206, 208)   # 相对卡片左上
BTN_GHOST_BOX = (216, 168, 382, 208)
BTN_CLOSE_BOX = (364, 16, 390, 42)


def render_panel(th: Theme, st: PanelState, scale: float = 1.0) -> Image.Image:
    W, H = int(CANVAS_W * scale), int(CANVAS_H * scale)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def F(size, bold=False):
        return font(max(8, int(round(size * scale))), bold)

    card = [int(v * scale) for v in
            (SHADOW, SHADOW, SHADOW + CARD_W, SHADOW + CARD_H)]
    r = int(RADIUS * scale)

    # 阴影
    img.alpha_composite(
        _shadow_layer((W, H), card, r, th.shadow_alpha))

    # 卡片
    _rounded(img, card, r, fill=th.card, outline=th.border, width=max(1, int(scale)))

    d = ImageDraw.Draw(img)
    ox, oy = card[0], card[1]

    def P(x, y):
        return (ox + int(x * scale), oy + int(y * scale))

    # 图标 + 标题
    icon_box = [P(22, 18)[0], P(22, 18)[1], P(52, 48)[0], P(22, 48)[1]]
    _draw_app_icon(img, icon_box)
    _text(d, P(62, 23), "触摸板救援", F(15, bold=True), th.text)
    _text(d, P(62, 44), "Touchpad Rescue", F(9.5), th.faint)

    # 关闭按钮
    cb = [ox + int(BTN_CLOSE_BOX[0] * scale), oy + int(BTN_CLOSE_BOX[1] * scale),
          ox + int(BTN_CLOSE_BOX[2] * scale), oy + int(BTN_CLOSE_BOX[3] * scale)]
    if st.hover == "close":
        _rounded(img, cb, int(8 * scale), fill=th.ghost)
    cxm = (cb[0] + cb[2]) // 2
    cym = (cb[1] + cb[3]) // 2
    arm = int(5 * scale)
    lw = max(1, int(1.6 * scale))
    d.line([cxm - arm, cym - arm, cxm + arm, cym + arm], fill=th.subtext, width=lw)
    d.line([cxm - arm, cym + arm, cxm + arm, cym - arm], fill=th.subtext, width=lw)

    # 状态区
    dot_color = th.ok if st.enabled else th.danger
    label = "触摸板已开启" if st.enabled else "触摸板已关闭"
    if st.enabled is None:
        dot_color, label = th.warn, "状态未知"

    _draw_status_dot(d, ox + int(29 * scale), oy + int(88 * scale),
                     int(4.5 * scale), dot_color)
    _text(d, P(42, 76), label, F(19, bold=True), th.text)

    sub = st.message or ("现在就能用触摸板操作" if st.enabled
                         else "按快捷键或下方按钮立即恢复触控")
    if st.busy and not st.message:
        sub = "正在重新加载触摸板设备…"
    color = th.subtext
    if st.level == "error":
        color = th.danger
    elif st.level == "warn":
        color = th.warn
    _text(d, P(22, 114), _ellipsize(sub, F(12), CARD_W - 44, scale), F(12), color)

    # 主按钮
    pb = [ox + int(BTN_PRIMARY_BOX[0] * scale), oy + int(BTN_PRIMARY_BOX[1] * scale),
          ox + int(BTN_PRIMARY_BOX[2] * scale), oy + int(BTN_PRIMARY_BOX[3] * scale)]
    pfill = th.accent_hover if st.hover == "primary" else th.accent
    _rounded(img, pb, int(9 * scale), fill=pfill)
    ptext = "关闭触摸板" if st.enabled else "开启触摸板"
    _text(d, ((pb[0] + pb[2]) // 2, (pb[1] + pb[3]) // 2), ptext,
          F(13, bold=True), th.accent_text, anchor="mm")

    # 次按钮
    gb = [ox + int(BTN_GHOST_BOX[0] * scale), oy + int(BTN_GHOST_BOX[1] * scale),
          ox + int(BTN_GHOST_BOX[2] * scale), oy + int(BTN_GHOST_BOX[3] * scale)]
    gfill = th.ghost_hover if st.hover == "ghost" else th.ghost
    _rounded(img, gb, int(9 * scale), fill=gfill)
    _text(d, ((gb[0] + gb[2]) // 2, (gb[1] + gb[3]) // 2), "设置",
          F(13, bold=True), th.ghost_text, anchor="mm")

    # 页脚
    foot = f"{st.hotkey} 一键切换"
    if not st.admin:
        foot += "  ·  未提权，功能受限"
    _text(d, P(22, 220), foot, F(10), th.faint)

    return img


def _ellipsize(text: str, f, max_w: float, scale: float) -> str:
    """粗略截断，避免文字溢出卡片。"""
    limit = max_w * scale
    if f.getlength(text) <= limit:
        return text
    ell = "…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if f.getlength(text[:mid] + ell) <= limit:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + ell


# ---------------------------------------------------------------- 托盘图标

def render_tray_icon(enabled: bool, dark: bool, size: int = 32) -> Image.Image:
    """托盘小图标：圆角方块 + 触控板轮廓，关闭时加一道斜杠。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    base = (37, 99, 235, 255) if enabled else (140, 148, 160, 255)
    d.rounded_rectangle([1, 1, size - 1, size - 1], radius=int(size * 0.28), fill=base)
    pad = size * 0.26
    d.rounded_rectangle([pad, pad, size - pad, size - pad * 0.9],
                        radius=int(size * 0.08),
                        outline=(255, 255, 255, 240), width=max(1, int(size * 0.07)))
    if not enabled:
        d.line([size * 0.24, size * 0.76, size * 0.76, size * 0.24],
               fill=(255, 255, 255, 245), width=max(2, int(size * 0.11)))
    return img


# ---------------------------------------------------------------- 设置界面

SET_CARD_W, SET_CARD_H = 460, 372
SET_CANVAS_W = SET_CARD_W + SHADOW * 2
SET_CANVAS_H = SET_CARD_H + SHADOW * 2

SET_HITBOXES = {
    "close":         (412, 16, 440, 44),
    "theme_system":  (24, 96, 90, 128),
    "theme_light":   (96, 96, 162, 128),
    "theme_dark":    (168, 96, 234, 128),
    "hotkey":        (326, 168, 436, 200),
    "autostart":     (358, 232, 412, 260),
}


@dataclass
class SettingsState:
    theme_mode: str = "system"
    hotkey: str = "Ctrl+Alt+P"
    autostart: bool = True
    recording: bool = False
    admin: bool = True
    has_task: bool = False
    device_name: str = ""
    hover: str = ""


def render_settings(th: Theme, st: SettingsState, scale: float = 1.0) -> Image.Image:
    W_, H_ = int(SET_CANVAS_W * scale), int(SET_CANVAS_H * scale)
    img = Image.new("RGBA", (W_, H_), (0, 0, 0, 0))

    def F(size, bold=False):
        return font(max(8, int(round(size * scale))), bold)

    card = [int(v * scale) for v in
            (SHADOW, SHADOW, SHADOW + SET_CARD_W, SHADOW + SET_CARD_H)]
    img.alpha_composite(_shadow_layer((W_, H_), card, int(RADIUS * scale), th.shadow_alpha))
    _rounded(img, card, int(RADIUS * scale), fill=th.card, outline=th.border,
             width=max(1, int(scale)))

    d = ImageDraw.Draw(img)
    ox, oy = card[0], card[1]

    def P(x, y):
        return (ox + int(x * scale), oy + int(y * scale))

    def BOX(b):
        return (ox + int(b[0] * scale), oy + int(b[1] * scale),
                ox + int(b[2] * scale), oy + int(b[3] * scale))

    def sep(y):
        d.line([P(24, y), P(SET_CARD_W - 24, y)], fill=th.track,
               width=max(1, int(scale)))

    # 标题
    _text(d, P(24, 20), "设置", F(17, bold=True), th.text)
    _text(d, P(72, 26), "Touchpad Rescue", F(9.5), th.faint)

    # 关闭
    cb = BOX(SET_HITBOXES["close"])
    if st.hover == "close":
        _rounded(img, cb, int(8 * scale), fill=th.ghost)
    cxm, cym = (cb[0] + cb[2]) // 2, (cb[1] + cb[3]) // 2
    arm, lw = int(5 * scale), max(1, int(1.6 * scale))
    d.line([cxm - arm, cym - arm, cxm + arm, cym + arm], fill=th.subtext, width=lw)
    d.line([cxm - arm, cym + arm, cxm + arm, cym - arm], fill=th.subtext, width=lw)
    sep(62)

    # 主题
    _text(d, P(24, 74), "外观主题", F(12), th.subtext)
    modes = [("theme_system", "跟随系统"), ("theme_light", "浅色"), ("theme_dark", "深色")]
    for key, label in modes:
        b = BOX(SET_HITBOXES[key])
        selected = (st.theme_mode == key.split("_")[1])
        if selected:
            fill, tcolor = th.accent, th.accent_text
        else:
            fill = th.ghost_hover if st.hover == key else th.ghost
            tcolor = th.ghost_text
        _rounded(img, b, int(8 * scale), fill=fill)
        _text(d, ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2), label,
              F(11.5, bold=selected), tcolor, anchor="mm")

    # 热键
    _text(d, P(24, 150), "全局快捷键", F(12), th.subtext)
    hk_box = BOX(SET_HITBOXES["hotkey"])
    hk_fill = th.accent if st.recording else (th.ghost_hover if st.hover == "hotkey" else th.ghost)
    _rounded(img, hk_box, int(8 * scale), fill=hk_fill)
    hk_text = "请按键…" if st.recording else "修改"
    hk_color = th.accent_text if st.recording else th.ghost_text
    _text(d, ((hk_box[0] + hk_box[2]) // 2, (hk_box[1] + hk_box[3]) // 2),
          hk_text, F(11.5, bold=True), hk_color, anchor="mm")
    _text(d, P(24, 172), st.hotkey, F(14, bold=True), th.text)
    sep(214)

    # 开机自启
    _text(d, P(24, 234), "开机自启", F(12), th.subtext)
    _text(d, P(24, 254), "登录后自动常驻，异常退出会被拉起", F(10.5), th.faint)
    sw = BOX(SET_HITBOXES["autostart"])
    track_h = int(22 * scale)
    track_w = int(44 * scale)
    tx = sw[2] - track_w
    ty = (sw[1] + sw[3]) // 2 - track_h // 2
    track_box = (tx, ty, tx + track_w, ty + track_h)
    _rounded(img, track_box, track_h // 2,
             fill=th.accent if st.autostart else th.track)
    dot_r = int(8 * scale)
    dot_cx = tx + (track_w - dot_r * 2 - int(3 * scale)) if st.autostart else tx + int(3 * scale)
    dot_cy = ty + track_h // 2 - dot_r
    d.ellipse([dot_cx, dot_cy, dot_cx + dot_r * 2, dot_cy + dot_r * 2],
              fill=(255, 255, 255, 255) if st.autostart else (245, 246, 248, 255))
    sep(290)

    # 运行信息
    perm = "管理员权限" if st.admin else "普通权限（功能受限）"
    perm_color = th.ok if st.admin else th.warn
    _text(d, P(24, 308), "权限", F(11), th.faint)
    _text(d, P(80, 308), perm, F(11, bold=True), perm_color)

    dev = st.device_name or "未检测到触摸板"
    _text(d, P(24, 330), "设备", F(11), th.faint)
    _text(d, P(80, 330), _ellipsize(dev, F(11), 340, scale), F(11), th.subtext)

    task = "自启任务正常" if st.has_task else "自启任务未注册"
    _text(d, P(24, 352), "守护", F(11), th.faint)
    _text(d, P(80, 352), task, F(11), th.ok if st.has_task else th.faint)

    return img
