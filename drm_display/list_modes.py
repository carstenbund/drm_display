"""
drm-list-modes — print every DRM connector and its available modes.

Usage:
    drm-list-modes              # scan all /dev/dri/card* devices
    drm-list-modes /dev/dri/card0 /dev/dri/card1

Output example:

    /dev/dri/card0
      Connector 1: HDMI-A-1  [connected]  527 x 296 mm
        * 1920x1080 @ 60 Hz   (1920x1080)    <- preferred
          1280x720  @ 60 Hz   (1280x720)
          1024x768  @ 60 Hz   (1024x768)
      Connector 2: DSI-1     [disconnected]
        (no modes)

Exit codes:  0 = ok,  1 = no DRM devices found,  2 = permission / open error
"""

import ctypes
import glob
import os
import sys

# --------------------------------------------------------------------------- #
#  ctypes structures (mirrors drm_display.py — kept local so this module is   #
#  usable standalone without building libdrm_display.so)                      #
# --------------------------------------------------------------------------- #

DRM_MODE_TYPE_PREFERRED = 1 << 3
DRM_MODE_CONNECTED      = 1

_CONNECTOR_TYPE = {
    0:  "Unknown", 1:  "VGA",    2:  "DVI-I",  3:  "DVI-D",
    4:  "DVI-A",   5:  "Composite", 6: "S-Video", 7: "LVDS",
    8:  "Component", 9: "DIN",   10: "DP",     11: "HDMI-A",
    12: "HDMI-B", 13: "TV",     14: "eDP",    15: "Virtual",
    16: "DSI",    17: "DPI",    18: "Writeback", 19: "SPI",
    20: "USB",
}

DRM_DISPLAY_MODE_LEN = 32

class _ModeInfo(ctypes.Structure):
    _fields_ = [
        ("clock",       ctypes.c_uint32),
        ("hdisplay",    ctypes.c_uint16),
        ("hsync_start", ctypes.c_uint16),
        ("hsync_end",   ctypes.c_uint16),
        ("htotal",      ctypes.c_uint16),
        ("hskew",       ctypes.c_uint16),
        ("vdisplay",    ctypes.c_uint16),
        ("vsync_start", ctypes.c_uint16),
        ("vsync_end",   ctypes.c_uint16),
        ("vtotal",      ctypes.c_uint16),
        ("vscan",       ctypes.c_uint16),
        ("vrefresh",    ctypes.c_uint32),
        ("flags",       ctypes.c_uint32),
        ("type",        ctypes.c_uint32),
        ("name",        ctypes.c_char * DRM_DISPLAY_MODE_LEN),
    ]

class _Res(ctypes.Structure):
    _fields_ = [
        ("fb_id_ptr",        ctypes.POINTER(ctypes.c_uint32)),
        ("crtc_id_ptr",      ctypes.POINTER(ctypes.c_uint32)),
        ("connector_id_ptr", ctypes.POINTER(ctypes.c_uint32)),
        ("encoder_id_ptr",   ctypes.POINTER(ctypes.c_uint32)),
        ("count_fbs",        ctypes.c_uint32),
        ("count_crtcs",      ctypes.c_uint32),
        ("count_connectors", ctypes.c_uint32),
        ("count_encoders",   ctypes.c_uint32),
        ("min_width",        ctypes.c_uint32),
        ("max_width",        ctypes.c_uint32),
        ("min_height",       ctypes.c_uint32),
        ("max_height",       ctypes.c_uint32),
    ]

class _Connector(ctypes.Structure):
    _fields_ = [
        ("connector_id",      ctypes.c_uint32),
        ("encoder_id",        ctypes.c_uint32),
        ("connector_type",    ctypes.c_uint32),
        ("connector_type_id", ctypes.c_uint32),
        ("connection",        ctypes.c_uint32),
        ("mmWidth",           ctypes.c_uint32),
        ("mmHeight",          ctypes.c_uint32),
        ("subpixel",          ctypes.c_uint32),
        ("count_modes",       ctypes.c_uint32),
        ("modes",             ctypes.POINTER(_ModeInfo)),
        ("count_props",       ctypes.c_uint32),
        ("props",             ctypes.POINTER(ctypes.c_uint32)),
        ("prop_values",       ctypes.POINTER(ctypes.c_uint64)),
        ("count_encoders",    ctypes.c_uint32),
        ("encoders",          ctypes.POINTER(ctypes.c_uint32)),
    ]


def _load_libdrm():
    for name in ("libdrm.so.2", "libdrm.so"):
        try:
            return ctypes.CDLL(name)
        except OSError:
            pass
    raise OSError(
        "libdrm not found. Install it with:\n"
        "  apt install libdrm2   (Debian/Ubuntu)\n"
        "  dnf install libdrm    (Fedora/RHEL)"
    )


def _setup(lib):
    lib.drmModeGetResources.argtypes  = [ctypes.c_int]
    lib.drmModeGetResources.restype   = ctypes.POINTER(_Res)
    lib.drmModeFreeResources.argtypes = [ctypes.POINTER(_Res)]
    lib.drmModeFreeResources.restype  = None

    lib.drmModeGetConnector.argtypes  = [ctypes.c_int, ctypes.c_uint32]
    lib.drmModeGetConnector.restype   = ctypes.POINTER(_Connector)
    lib.drmModeFreeConnector.argtypes = [ctypes.POINTER(_Connector)]
    lib.drmModeFreeConnector.restype  = None


def list_modes_for_device(lib, device):
    """Print connector/mode information for one DRM device path."""
    try:
        fd = os.open(device, os.O_RDWR | os.O_CLOEXEC)
    except PermissionError:
        print(f"{device}  [permission denied — try: sudo / add user to 'video' group]")
        return False
    except OSError as e:
        print(f"{device}  [{e.strerror}]")
        return False

    print(device)
    ok = True

    try:
        res_ptr = lib.drmModeGetResources(fd)
        if not res_ptr:
            print("  (no DRM resources — kernel module not loaded?)")
            ok = False
        else:
            res = res_ptr.contents
            n   = res.count_connectors

            for i in range(n):
                conn_id  = res.connectors[i]
                conn_ptr = lib.drmModeGetConnector(fd, conn_id)
                if not conn_ptr:
                    continue
                c = conn_ptr.contents

                type_name = _CONNECTOR_TYPE.get(c.connector_type, "Unknown")
                full_name = f"{type_name}-{c.connector_type_id}"
                connected = c.connection == DRM_MODE_CONNECTED

                if connected and c.mmWidth and c.mmHeight:
                    size_str = f"  {c.mmWidth} x {c.mmHeight} mm"
                else:
                    size_str = ""

                status = "connected" if connected else "disconnected"
                print(f"  Connector {i+1}: {full_name:<14} [{status}]{size_str}")

                n_modes = c.count_modes
                if n_modes == 0:
                    print("    (no modes reported)")
                else:
                    for j in range(n_modes):
                        m        = c.modes[j]
                        pref     = m.type & DRM_MODE_TYPE_PREFERRED
                        marker   = "*" if pref else " "
                        name_str = m.name.decode(errors="replace")
                        print(f"    {marker} {m.hdisplay:5}x{m.vdisplay:<5} @ {m.vrefresh:3} Hz"
                              f"   ({name_str})")

                lib.drmModeFreeConnector(conn_ptr)

            lib.drmModeFreeResources(res_ptr)
    finally:
        os.close(fd)

    return ok


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    devices = argv if argv else sorted(glob.glob("/dev/dri/card*"))

    if not devices:
        print("No DRM devices found under /dev/dri/. "
              "Is a GPU present and are kernel modules loaded?")
        sys.exit(1)

    try:
        lib = _load_libdrm()
    except OSError as e:
        print(f"Error: {e}")
        sys.exit(2)

    _setup(lib)

    any_ok = False
    for i, dev in enumerate(devices):
        if i:
            print()
        ok = list_modes_for_device(lib, dev)
        any_ok = any_ok or ok

    sys.exit(0 if any_ok else 2)


if __name__ == "__main__":
    main()
