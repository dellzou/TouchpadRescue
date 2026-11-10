# -*- coding: utf-8 -*-
"""
TouchpadRescue 核心引擎
=======================
负责：读写触摸板开关偏好、枚举触摸板 HID 设备、重载设备使其立即生效。

原理：
    Windows 的精密触摸板开关只是把偏好写进
    HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\PrecisionTouchPad\\Status\\Enabled，
    驱动并不会实时重读。所以必须让 HID 设备重新加载一次，
    驱动初始化时才会读这个值 —— 这是整套方案的关键。

可靠性约定：
    - 禁用设备后必须保证重新启用，用 try/finally 兜底；
    - 程序启动时做一次设备自检，修复上次异常退出遗留的禁用状态。
"""
from __future__ import annotations

import ctypes
import time
import winreg
from ctypes import wintypes
from dataclasses import dataclass

# ---------------------------------------------------------------- 常量

PTP_STATUS_KEY = r"Software\Microsoft\Windows\CurrentVersion\PrecisionTouchPad\Status"

GUID_DEVCLASS_HIDCLASS = "{745A17A0-74D3-11D0-B6FE-00A0C90F57DA}"
GUID_DEVINTERFACE_HID = "{4D1E55B2-F16F-11CF-88CB-001111000030}"

DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10

CFG_SUCCESS = 0
CR_SUCCESS = 0
CM_LOCATE_DEVNODE_NORMAL = 0
CM_DISABLE_UI_NOT_OK = 0x00000004

USAGE_PAGE_DIGITIZER = 0x0D
USAGE_TOUCH_PAD = 0x05

# HidP_GetCaps 的成功码（HIDP_STATUS_SUCCESS），不是 0
HIDP_STATUS_SUCCESS = 0x00110000

# 设备友好名关键字（多语言，尽量兜住）
TOUCHPAD_NAME_HINTS = (
    "touchpad", "touch pad", "precision touchpad",
    "触摸板", "觸控板", "터치패드", "タッチパッド", "тачпад",
)


# ---------------------------------------------------------------- 结构体

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.POINTER(wintypes.ULONG)),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.POINTER(wintypes.ULONG)),
    ]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", wintypes.ULONG),
        ("VendorID", wintypes.USHORT),
        ("ProductID", wintypes.USHORT),
        ("VersionNumber", wintypes.USHORT),
    ]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wintypes.USHORT),
        ("UsagePage", wintypes.USHORT),
        ("InputReportByteLength", wintypes.USHORT),
        ("OutputReportByteLength", wintypes.USHORT),
        ("FeatureReportByteLength", wintypes.USHORT),
        ("Reserved", wintypes.USHORT * 17),
        ("NumberLinkCollectionNodes", wintypes.USHORT),
        ("NumberInputButtonCaps", wintypes.USHORT),
        ("NumberInputValueCaps", wintypes.USHORT),
        ("NumberInputDataIndices", wintypes.USHORT),
        ("NumberOutputButtonCaps", wintypes.USHORT),
        ("NumberOutputValueCaps", wintypes.USHORT),
        ("NumberOutputDataIndices", wintypes.USHORT),
        ("NumberFeatureButtonCaps", wintypes.USHORT),
        ("NumberFeatureValueCaps", wintypes.USHORT),
        ("NumberFeatureDataIndices", wintypes.USHORT),
    ]


# ---------------------------------------------------------------- 库句柄

_setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
_hid = ctypes.WinDLL("hid", use_last_error=True)
_cfg = ctypes.WinDLL("cfgmgr32", use_last_error=True)
_k32 = ctypes.windll.kernel32

_k32.CreateFileW.restype = wintypes.HANDLE
_k32.CreateFileW.argtypes = [
    ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD,
    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_k32.CloseHandle.restype = wintypes.BOOL

_setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
_setupapi.SetupDiGetClassDevsW.argtypes = [
    ctypes.POINTER(GUID), ctypes.c_wchar_p, wintypes.HWND, wintypes.DWORD,
]
_setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

_setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID),
    wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
]
_setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p,
    wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(SP_DEVINFO_DATA),
]

_setupapi.SetupDiGetDeviceRegistryPropertyW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA), wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
_setupapi.SetupDiEnumDeviceInfo.argtypes = [
    ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(SP_DEVINFO_DATA),
]

_hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
_hid.HidD_GetPreparsedData.restype = wintypes.BYTE
_hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
_hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
_hid.HidP_GetCaps.restype = ctypes.c_long

_cfg.CM_Locate_DevNodeW.argtypes = [
    ctypes.POINTER(wintypes.ULONG), ctypes.c_wchar_p, wintypes.ULONG,
]
_cfg.CM_Locate_DevNodeW.restype = wintypes.ULONG
_cfg.CM_Disable_DevNode.argtypes = [wintypes.ULONG, wintypes.ULONG]
_cfg.CM_Disable_DevNode.restype = wintypes.ULONG
_cfg.CM_Enable_DevNode.argtypes = [wintypes.ULONG, wintypes.ULONG]
_cfg.CM_Enable_DevNode.restype = wintypes.ULONG
_cfg.CM_Get_Device_IDW.argtypes = [
    wintypes.ULONG, ctypes.c_wchar_p, wintypes.ULONG, wintypes.ULONG,
]
_cfg.CM_Get_Device_IDW.restype = wintypes.ULONG

INVALID_HANDLE = ctypes.c_void_p(-1).value


# ---------------------------------------------------------------- 基础

def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def get_enabled():
    """读取开关偏好：1 开启 / 0 关闭 / None 不存在"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PTP_STATUS_KEY) as k:
            return int(winreg.QueryValueEx(k, "Enabled")[0])
    except FileNotFoundError:
        return None
    except OSError:
        return None


def set_enabled(value: int) -> bool:
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, PTP_STATUS_KEY,
                                0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "Enabled", 0, winreg.REG_DWORD, int(value))
        return True
    except OSError:
        return False


def _guid(text: str) -> GUID:
    g = GUID()
    ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(g))
    return g


def _open_hid(path: str):
    """打开 HID 设备接口，先试读写，失败退只读。"""
    GENERIC_READ, GENERIC_WRITE = 0x80000000, 0x40000000
    SHARE = 3
    OPEN_EXISTING = 3
    h = _k32.CreateFileW(path, GENERIC_READ | GENERIC_WRITE, SHARE,
                         None, OPEN_EXISTING, 0, None)
    if h == INVALID_HANDLE:
        h = _k32.CreateFileW(path, 0, SHARE, None, OPEN_EXISTING, 0, None)
    return h


def _hid_tlc_usage(path: str):
    """返回 (usage_page, usage)；不是 HID 设备返回 None。"""
    h = _open_hid(path)
    if h == INVALID_HANDLE:
        return None
    try:
        pp = ctypes.c_void_p()
        if not _hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
            return None
        try:
            caps = HIDP_CAPS()
            if _hid.HidP_GetCaps(pp, ctypes.byref(caps)) != HIDP_STATUS_SUCCESS:
                return None
            return (caps.UsagePage, caps.Usage)
        finally:
            _hid.HidD_FreePreparsedData(pp)
    finally:
        _k32.CloseHandle(h)


# ---------------------------------------------------------------- 设备枚举

@dataclass
class TouchpadDevice:
    instance_id: str          # 例如 HID\GXTP7863&COL02\5&1BE1D8CC&0&0001
    friendly_name: str
    is_touchpad_tlc: bool     # 是否为 Digitizer/TouchPad 顶层集合


def list_hid_devices() -> list[TouchpadDevice]:
    """枚举所有 HID 设备，标出哪些是触摸板。"""
    out: list[TouchpadDevice] = []
    g = _guid(GUID_DEVINTERFACE_HID)
    hdev = _setupapi.SetupDiGetClassDevsW(
        ctypes.byref(g), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if not hdev or hdev == INVALID_HANDLE:
        return out
    try:
        did = SP_DEVICE_INTERFACE_DATA()
        did.cbSize = ctypes.sizeof(did)
        seen = set()
        i = 0
        while _setupapi.SetupDiEnumDeviceInterfaces(
                hdev, None, ctypes.byref(g), i, ctypes.byref(did)):
            i += 1
            need = wintypes.DWORD()
            _setupapi.SetupDiGetDeviceInterfaceDetailW(
                hdev, ctypes.byref(did), None, 0, ctypes.byref(need), None)
            if not need.value:
                continue
            buf = ctypes.create_string_buffer(need.value)
            # cbSize 字段：x64 为 8，x86 为 6
            ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = (
                8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6)
            devinfo = SP_DEVINFO_DATA()
            devinfo.cbSize = ctypes.sizeof(devinfo)
            if not _setupapi.SetupDiGetDeviceInterfaceDetailW(
                    hdev, ctypes.byref(did), buf, need.value,
                    ctypes.byref(need), ctypes.byref(devinfo)):
                continue
            path = ctypes.wstring_at(ctypes.addressof(buf) + 4)

            name = _device_friendly_name(hdev, devinfo)
            idbuf = ctypes.create_unicode_buffer(260)
            if _cfg.CM_Get_Device_IDW(devinfo.DevInst, idbuf, 260, 0) != CR_SUCCESS:
                continue
            instance_id = idbuf.value
            if instance_id in seen:
                continue
            seen.add(instance_id)

            usage = _hid_tlc_usage(path)
            is_tp = bool(usage and usage[0] == USAGE_PAGE_DIGITIZER
                         and usage[1] == USAGE_TOUCH_PAD)
            out.append(TouchpadDevice(instance_id, name, is_tp))
        return out
    finally:
        _setupapi.SetupDiDestroyDeviceInfoList(hdev)


def _device_friendly_name(hdev, devinfo) -> str:
    """取友好名，取不到退回设备描述。"""
    for prop in (0x0C, 0x00):  # SPDRP_FRIENDLYNAME, SPDRP_DEVICEDESC
        buf = ctypes.create_unicode_buffer(512)
        need = wintypes.DWORD()
        if _setupapi.SetupDiGetDeviceRegistryPropertyW(
                hdev, ctypes.byref(devinfo), prop, None,
                ctypes.byref(buf), ctypes.sizeof(buf), ctypes.byref(need)):
            if buf.value:
                return buf.value
    return ""


def find_touchpad_devices() -> list[TouchpadDevice]:
    """
    找出触摸板设备。
    优先认 HID 顶层集合（Digitizer/TouchPad），这才是 Windows 认的精密触摸板；
    名称匹配作为兜底。
    """
    devices = list_hid_devices()
    strict = [d for d in devices if d.is_touchpad_tlc]
    if strict:
        return strict
    loose = []
    for d in devices:
        low = d.friendly_name.lower()
        if any(h in low for h in TOUCHPAD_NAME_HINTS):
            loose.append(d)
    return loose


# ---------------------------------------------------------------- 设备重载

def _locate(instance_id: str):
    dn = wintypes.ULONG()
    rc = _cfg.CM_Locate_DevNodeW(ctypes.byref(dn), instance_id, CM_LOCATE_DEVNODE_NORMAL)
    return (dn.value, rc)


def restart_device(instance_id: str, settle: float = 0.45) -> bool:
    """
    禁用并重新启用设备，让驱动重读开关状态。
    无论中间发生什么，都尽力保证设备最终是启用状态。
    """
    devinst, rc = _locate(instance_id)
    if rc != CR_SUCCESS:
        return False

    disabled = False
    try:
        if _cfg.CM_Disable_DevNode(devinst, CM_DISABLE_UI_NOT_OK) == CR_SUCCESS:
            disabled = True
            time.sleep(settle)
    finally:
        # 关键：哪怕上面抛异常，也要把设备开回来
        for attempt in range(3):
            rc2 = _cfg.CM_Enable_DevNode(devinst, 0)
            if rc2 == CR_SUCCESS:
                break
            time.sleep(0.3 * (attempt + 1))
    return disabled


def ensure_devices_enabled(instance_ids: list[str]) -> None:
    """启动自检：修正上次异常退出可能留下的禁用状态。幂等。"""
    for iid in instance_ids:
        devinst, rc = _locate(iid)
        if rc == CR_SUCCESS:
            _cfg.CM_Enable_DevNode(devinst, 0)


# ---------------------------------------------------------------- 对外动作

@dataclass
class Result:
    ok: bool
    message: str
    level: str = "ok"      # ok / warn / error


def apply_state(enable: bool, devices: list[TouchpadDevice] | None = None) -> Result:
    """
    设置触摸板开关并使其立即生效。
    返回结果里带过程信息，UI 可以直接展示。
    """
    target = 1 if enable else 0
    if not is_admin():
        # 没有管理员权限就别动注册表：写了也不会生效，
        # 反而会造成"显示已关闭、实际还能用"的假状态。
        return Result(False, "需要管理员权限才能切换触摸板", "error")

    if devices is None:
        devices = find_touchpad_devices()
    if not devices:
        set_enabled(target)
        return Result(False, "没有找到触摸板设备", "error")

    set_enabled(target)
    ok_count = 0
    for d in devices:
        if restart_device(d.instance_id):
            ok_count += 1
    if ok_count:
        return Result(True, "触摸板已开启" if enable else "触摸板已关闭")
    return Result(False, "重载触摸板设备失败", "error")


def status_text() -> str:
    v = get_enabled()
    if v == 1:
        return "已开启"
    if v == 0:
        return "已关闭"
    return "未知"
