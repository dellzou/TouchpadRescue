"""验证：用 CfgMgr32 API 重载触摸板设备（替代 pnputil 子进程）。"""
import ctypes
import time
import winreg
from ctypes import wintypes

LOG = r"D:\WorkBuddy\本地电脑状况检查\TouchpadRescue\probe\api_test.log"
PTP = r"Software\Microsoft\Windows\CurrentVersion\PrecisionTouchPad\Status"
IDS = [r"HID\GXTP7863&COL02\5&1BE1D8CC&0&0001", r"ACPI\GXTP7863\4&497DC3C&0"]

lines = []


def log(s):
    lines.append(s)


cfg = ctypes.WinDLL("cfgmgr32", use_last_error=True)
CFG_SUCCESS = 0
CM_LOCATE_DEVNODE_NORMAL = 0
CM_DISABLE_UI_NOT_OK = 0x00000004

cfg.CM_Locate_DevNodeW.argtypes = [ctypes.POINTER(wintypes.ULONG),
                                   ctypes.c_wchar_p, wintypes.ULONG]
cfg.CM_Locate_DevNodeW.restype = wintypes.ULONG
cfg.CM_Disable_DevNode.argtypes = [wintypes.ULONG, wintypes.ULONG]
cfg.CM_Disable_DevNode.restype = wintypes.ULONG
cfg.CM_Enable_DevNode.argtypes = [wintypes.ULONG, wintypes.ULONG]
cfg.CM_Enable_DevNode.restype = wintypes.ULONG
cfg.CM_Get_Device_IDW.argtypes = [wintypes.ULONG, ctypes.c_wchar_p, wintypes.ULONG, wintypes.ULONG]
cfg.CM_Get_Device_IDW.restype = wintypes.ULONG


def set_enabled(v):
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, PTP, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "Enabled", 0, winreg.REG_DWORD, v)


def get_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PTP) as k:
            return winreg.QueryValueEx(k, "Enabled")[0]
    except OSError:
        return None


def restart(devid):
    dn = wintypes.ULONG()
    rc = cfg.CM_Locate_DevNodeW(ctypes.byref(dn), devid, CM_LOCATE_DEVNODE_NORMAL)
    log(f"  locate rc={rc} devinst={dn.value}")
    if rc != CFG_SUCCESS:
        return False
    rc = cfg.CM_Disable_DevNode(dn.value, CM_DISABLE_UI_NOT_OK)
    log(f"  disable rc={rc}")
    time.sleep(0.6)
    rc2 = cfg.CM_Enable_DevNode(dn.value, 0)
    log(f"  enable rc={rc2}")
    return rc == CFG_SUCCESS and rc2 == CFG_SUCCESS


try:
    log(f"admin={bool(ctypes.windll.shell32.IsUserAnAdmin())}")
    log(f"before Enabled={get_enabled()}")
    set_enabled(1)
    log(f"after set Enabled={get_enabled()}")
    for devid in IDS:
        log(f"restart {devid}")
        ok = restart(devid)
        log(f"  => {ok}")
        time.sleep(0.8)
    time.sleep(1)
    log(f"final Enabled={get_enabled()}")
    log("INPUT-PROMPT: 请现在摸一下触摸板")
except Exception as e:
    log(f"EXC {type(e).__name__}: {e}")
finally:
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
