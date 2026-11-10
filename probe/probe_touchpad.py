"""
探测：这台机器上触摸板开关的可行控制路径。
只做读取 + 一次注册表写入实验，输出结构化结论。
"""
import ctypes
import sys
import winreg
from ctypes import wintypes

PTP_KEY = r"Software\Microsoft\Windows\CurrentVersion\PrecisionTouchPad\Status"

WM_SETTINGCHANGE = 0x001A
HWND_BROADCAST = 0xFFFF
SMTO_ABORTIFHUNG = 0x0002


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def read_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PTP_KEY) as k:
            v, t = winreg.QueryValueEx(k, "Enabled")
            return v, t
    except FileNotFoundError:
        return None, None
    except OSError as e:
        return f"ERR:{e}", None


def write_enabled(value: int):
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, PTP_KEY, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "Enabled", 0, winreg.REG_DWORD, value)


def broadcast_change():
    res = wintypes.DWORD()
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST, WM_SETTINGCHANGE, 0,
        ctypes.c_wchar_p("Software\\Microsoft\\Windows\\CurrentVersion\\PrecisionTouchPad"),
        SMTO_ABORTIFHUNG, 1000, ctypes.byref(res)
    )


# ---------- HID 能力探测 ----------
GUID_DEVINTERFACE_HID = "{4D1E55B2-F16F-11CF-88CB-001111000030}"


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID),
                ("Flags", wintypes.DWORD), ("Reserved", ctypes.POINTER(wintypes.ULONG))]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size", wintypes.ULONG), ("VendorID", wintypes.USHORT),
                ("ProductID", wintypes.USHORT), ("VersionNumber", wintypes.USHORT)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", wintypes.USHORT), ("UsagePage", wintypes.USHORT),
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
                ("NumberFeatureDataIndices", wintypes.USHORT)]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [("UsagePage", wintypes.USHORT), ("ReportID", ctypes.c_ubyte),
                ("IsAlias", ctypes.c_ubyte), ("BitField", wintypes.USHORT),
                ("LinkCollection", wintypes.USHORT), ("LinkUsage", wintypes.USHORT),
                ("LinkUsagePage", wintypes.USHORT), ("IsRange", ctypes.c_ubyte),
                ("IsStringRange", ctypes.c_ubyte), ("IsDesignatorRange", ctypes.c_ubyte),
                ("IsAbsolute", ctypes.c_ubyte), ("HasNull", ctypes.c_ubyte),
                ("Reserved", ctypes.c_ubyte), ("BitSize", wintypes.USHORT),
                ("ReportCount", wintypes.USHORT), ("Reserved2", wintypes.USHORT * 5),
                ("UnitsExp", wintypes.ULONG), ("Units", wintypes.ULONG),
                ("LogicalMin", ctypes.c_long), ("LogicalMax", ctypes.c_long),
                ("PhysicalMin", ctypes.c_long), ("PhysicalMax", ctypes.c_long),
                ("UsageMin", wintypes.USHORT), ("UsageMax", wintypes.USHORT),
                ("StringMin", wintypes.USHORT), ("StringMax", wintypes.USHORT),
                ("DesignatorMin", wintypes.USHORT), ("DesignatorMax", wintypes.USHORT),
                ("DataIndexMin", wintypes.USHORT), ("DataIndexMax", wintypes.USHORT)]


def hid_guid() -> GUID:
    g = GUID()
    ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(GUID_DEVINTERFACE_HID), ctypes.byref(g))
    return g


def enumerate_hid():
    setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
    hid = ctypes.WinDLL("hid", use_last_error=True)

    setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
    setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_wchar_p,
                                              wintypes.HWND, wintypes.DWORD]

    g = hid_guid()
    DIGCF_PRESENT = 0x02
    DIGCF_DEVICEINTERFACE = 0x10
    hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(g), None, None,
                                         DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if hdev == ctypes.c_void_p(-1).value:
        print("SetupDiGetClassDevs 失败")
        return []

    out = []
    did = SP_DEVICE_INTERFACE_DATA()
    did.cbSize = ctypes.sizeof(did)
    i = 0
    while setupapi.SetupDiEnumDeviceInterfaces(ctypes.c_void_p(hdev), None, ctypes.byref(g), i,
                                               ctypes.byref(did)):
        need = wintypes.DWORD()
        setupapi.SetupDiGetDeviceInterfaceDetailW(ctypes.c_void_p(hdev), ctypes.byref(did),
                                                  None, 0, ctypes.byref(need), None)
        if need.value:
            buf = ctypes.create_string_buffer(need.value)
            ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = (
                8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6)
            if setupapi.SetupDiGetDeviceInterfaceDetailW(
                    ctypes.c_void_p(hdev), ctypes.byref(did), buf, need.value,
                    ctypes.byref(need), None):
                path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
                out.append(path)
        i += 1
    setupapi.SetupDiDestroyDeviceInfoList(ctypes.c_void_p(hdev))
    return out


def probe_one(hid, path):
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 1
    FILE_SHARE_WRITE = 2
    OPEN_EXISTING = 3
    k32 = ctypes.windll.kernel32
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [ctypes.c_wchar_p, wintypes.DWORD, wintypes.DWORD,
                                ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]

    hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
    hid.HidD_GetPreparsedData.restype = wintypes.BYTE
    hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
    hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
    hid.HidP_GetCaps.restype = ctypes.c_long
    hid.HidP_GetValueCaps.argtypes = [ctypes.c_int, ctypes.POINTER(HIDP_VALUE_CAPS),
                                      ctypes.POINTER(wintypes.ULONG), ctypes.c_void_p]
    hid.HidP_GetValueCaps.restype = ctypes.c_long

    INVALID = ctypes.c_void_p(-1).value
    h = k32.CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                        FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
    if h == INVALID:
        h = k32.CreateFileW(path, 0, FILE_SHARE_READ | FILE_SHARE_WRITE,
                            None, OPEN_EXISTING, 0, None)
        if h == INVALID:
            return None
    try:
        attrs = HIDD_ATTRIBUTES()
        attrs.Size = ctypes.sizeof(attrs)
        if not hid.HidD_GetAttributes(h, ctypes.byref(attrs)):
            return None
        pp = ctypes.c_void_p()
        if not hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
            return None
        try:
            caps = HIDP_CAPS()
            hid.HidP_GetCaps(pp, ctypes.byref(caps))
            res = {"path": path, "vid": attrs.VendorID, "pid": attrs.ProductID,
                   "usage": caps.Usage, "usage_page": caps.UsagePage,
                   "feature_len": caps.FeatureReportByteLength,
                   "input_len": caps.InputReportByteLength,
                   "features": []}
            n = caps.NumberFeatureValueCaps
            if n:
                arr = (HIDP_VALUE_CAPS * n)()
                cnt = wintypes.ULONG(n)
                if hid.HidP_GetValueCaps(2, arr, ctypes.byref(cnt), pp) == 0:  # 2 = HidP_Feature
                    for k in range(cnt.value):
                        c = arr[k]
                        res["features"].append({
                            "usage_page": hex(c.UsagePage),
                            "usage_min": hex(c.UsageMin), "usage_max": hex(c.UsageMax),
                            "report_id": c.ReportID, "bit_size": c.BitSize,
                            "logical": (c.LogicalMin, c.LogicalMax),
                        })
            return res
        finally:
            hid.HidD_FreePreparsedData(pp)
    finally:
        k32.CloseHandle(h)


def main():
    print("=" * 60)
    print("管理员:", is_admin())
    v, t = read_enabled()
    print(f"当前 PrecisionTouchPad\\Status\\Enabled = {v} (type={t})")
    print()

    print("--- HID 接口枚举 ---")
    paths = enumerate_hid()
    hid = ctypes.WinDLL("hid", use_last_error=True)
    found = []
    for p in paths:
        if "GXTP7863" in p.upper():
            r = probe_one(hid, p)
            if r:
                found.append(r)
    for r in found:
        print(f"路径: {r['path']}")
        print(f"  VID/PID: {r['vid']:04X}/{r['pid']:04X}  TLC UsagePage/Usage: "
              f"{hex(r['usage_page'])}/{hex(r['usage'])}  FeatureLen={r['feature_len']}")
        for f in r["features"]:
            print(f"    feature: page={f['usage_page']} usage={f['usage_min']}..{f['usage_max']} "
                  f"reportId={f['report_id']} bits={f['bit_size']} logical={f['logical']}")
    print(f"共 {len(found)} 个触摸板 TLC")
    print()

    # 写入实验
    if len(sys.argv) > 1 and sys.argv[1] == "enable":
        print("--- 实验：写 Enabled=1 + 广播 WM_SETTINGCHANGE ---")
        write_enabled(1)
        broadcast_change()
        v2, _ = read_enabled()
        print(f"写入后读回: {v2}")
    else:
        print("(加参数 enable 执行写入实验)")


if __name__ == "__main__":
    main()
