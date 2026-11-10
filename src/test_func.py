"""功能闭环测试：开启 -> 关闭 -> 开启，检查每步注册表与设备状态。"""
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tp_core as core

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "probe", "func_test.log")
lines = []


def log(s):
    lines.append(str(s))


try:
    log(f"admin={core.is_admin()}")
    devs = core.find_touchpad_devices()
    log(f"devices={[d.instance_id for d in devs]}")
    log(f"start Enabled={core.get_enabled()}")

    t0 = time.time()
    r = core.apply_state(True, devs)
    log(f"apply(True) -> ok={r.ok} msg={r.message} reg={core.get_enabled()} in {(time.time()-t0)*1000:.0f}ms")
    time.sleep(1.2)

    t0 = time.time()
    r = core.apply_state(False, devs)
    log(f"apply(False) -> ok={r.ok} msg={r.message} reg={core.get_enabled()} in {(time.time()-t0)*1000:.0f}ms")
    time.sleep(1.2)

    t0 = time.time()
    r = core.apply_state(True, devs)
    log(f"apply(True) -> ok={r.ok} msg={r.message} reg={core.get_enabled()} in {(time.time()-t0)*1000:.0f}ms")
    log(f"final Enabled={core.get_enabled()}")
except Exception as e:
    import traceback
    log("EXC " + traceback.format_exc())
finally:
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
