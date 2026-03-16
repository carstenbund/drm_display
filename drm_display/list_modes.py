"""
drm-list-modes — diagnose DRM/KMS and framebuffer display availability.

Sections reported:
  1. Kernel modules   — which DRM / fb modules are loaded
  2. DRM devices      — driver, master-lock status, connectors, modes
  3. Framebuffer devs — /dev/fb*, backing driver, in-use status
  4. Summary          — plain-English recommendation

Usage:
    drm-list-modes                        # full scan
    drm-list-modes /dev/dri/card0         # specific DRM device(s) only

Exit codes:  0 = at least one usable display found
             1 = nothing usable found
             2 = fatal error (libdrm missing, etc.)
"""

import ctypes
import ctypes.util
import glob
import os
import sys

# ═══════════════════════════════════════════════════════════════════════════ #
#  Constants                                                                  #
# ═══════════════════════════════════════════════════════════════════════════ #

DRM_MODE_TYPE_PREFERRED = 1 << 3
DRM_MODE_CONNECTED      = 1
DRM_DISPLAY_MODE_LEN    = 32

_CONNECTOR_TYPE = {
    0: "Unknown",   1: "VGA",       2: "DVI-I",    3: "DVI-D",
    4: "DVI-A",     5: "Composite", 6: "S-Video",  7: "LVDS",
    8: "Component", 9: "DIN",      10: "DP",       11: "HDMI-A",
   12: "HDMI-B",  13: "TV",       14: "eDP",      15: "Virtual",
   16: "DSI",     17: "DPI",      18: "Writeback", 19: "SPI",
   20: "USB",
}

# Modules to probe — grouped by role.
# Tuple: (module_name, description)
_MODULE_GROUPS = {
    "DRM core": [
        ("drm",              "DRM subsystem"),
        ("drm_kms_helper",   "KMS helpers"),
    ],
    "Virtual / CVM / KVM": [
        ("virtio_gpu",       "virtio-GPU (QEMU/KVM)"),
        ("vmwgfx",           "VMware SVGA"),
        ("vboxvideo",        "VirtualBox"),
        ("bochs_drm",        "QEMU Bochs VGA"),
        ("simpledrm",        "SimpleDRM (EFI/VESA fallback)"),
    ],
    "Desktop GPU": [
        ("i915",             "Intel"),
        ("amdgpu",           "AMD (GCN+)"),
        ("radeon",           "AMD (legacy)"),
        ("nouveau",          "NVIDIA (open)"),
        ("ast",              "ASPEED (server BMC)"),
    ],
    "Embedded / SBC": [
        ("vc4",              "Raspberry Pi (VC4/VC6)"),
        ("v3d",              "Raspberry Pi GPU"),
        ("sun4i_drm",        "Allwinner"),
        ("msm",              "Qualcomm"),
        ("etnaviv",          "Vivante"),
        ("panfrost",         "ARM Mali (Midgard+)"),
        ("lima",             "ARM Mali (Utgard)"),
        ("imx_drm",          "NXP i.MX"),
        ("exynos_drm",       "Samsung Exynos"),
        ("rockchip_drm",     "Rockchip"),
        ("meson",            "Amlogic"),
    ],
    "Framebuffer (legacy)": [
        ("fb",               "fbdev core"),
        ("fbcon",            "fbcon (fb console)"),
        ("vesafb",           "VESA framebuffer"),
        ("uvesafb",          "userspace VESA fb"),
        ("simplefb",         "Simple framebuffer (DT)"),
        ("efifb",            "EFI framebuffer"),
    ],
}

# ═══════════════════════════════════════════════════════════════════════════ #
#  ctypes structures                                                          #
# ═══════════════════════════════════════════════════════════════════════════ #

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

# ═══════════════════════════════════════════════════════════════════════════ #
#  libdrm loading + setup                                                     #
# ═══════════════════════════════════════════════════════════════════════════ #

def _load_libdrm():
    for name in ("libdrm.so.2", "libdrm.so"):
        try:
            lib = ctypes.CDLL(name)
            lib.drmModeGetResources.argtypes  = [ctypes.c_int]
            lib.drmModeGetResources.restype   = ctypes.POINTER(_Res)
            lib.drmModeFreeResources.argtypes = [ctypes.POINTER(_Res)]
            lib.drmModeFreeResources.restype  = None
            lib.drmModeGetConnector.argtypes  = [ctypes.c_int, ctypes.c_uint32]
            lib.drmModeGetConnector.restype   = ctypes.POINTER(_Connector)
            lib.drmModeFreeConnector.argtypes = [ctypes.POINTER(_Connector)]
            lib.drmModeFreeConnector.restype  = None
            lib.drmSetMaster.argtypes         = [ctypes.c_int]
            lib.drmSetMaster.restype          = ctypes.c_int
            lib.drmDropMaster.argtypes        = [ctypes.c_int]
            lib.drmDropMaster.restype         = ctypes.c_int
            return lib
        except OSError:
            pass
    return None  # caller handles missing libdrm gracefully

# ═══════════════════════════════════════════════════════════════════════════ #
#  Kernel module helpers                                                      #
# ═══════════════════════════════════════════════════════════════════════════ #

def _loaded_modules():
    """Return set of currently loaded module names (from /proc/modules)."""
    loaded = set()
    try:
        with open("/proc/modules") as f:
            for line in f:
                name = line.split()[0]
                loaded.add(name)
    except OSError:
        pass
    return loaded


def print_modules(loaded):
    print("── Kernel modules ──────────────────────────────────────────────")
    any_relevant = False
    for group, entries in _MODULE_GROUPS.items():
        group_lines = []
        for mod, desc in entries:
            if mod in loaded:
                group_lines.append(f"    {mod:<22} loaded    ({desc})")
                any_relevant = True
        if group_lines:
            print(f"  {group}:")
            for line in group_lines:
                print(line)
    if not any_relevant:
        print("  (no DRM or framebuffer modules detected in /proc/modules)")
    print()

# ═══════════════════════════════════════════════════════════════════════════ #
#  DRM master-lock detection                                                  #
# ═══════════════════════════════════════════════════════════════════════════ #

def _find_master_holder(device):
    """Scan /proc/*/fdinfo for the process holding DRM master on *device*.

    Returns (pid, comm) or None.  Requires read access to /proc — may return
    None on permission-restricted systems even if master is held.
    """
    try:
        dev_rdev = os.stat(device).st_rdev
    except OSError:
        return None

    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        pid = entry.name
        fd_dir      = f"/proc/{pid}/fd"
        fdinfo_dir  = f"/proc/{pid}/fdinfo"
        try:
            for fd_entry in os.scandir(fd_dir):
                try:
                    if os.stat(fd_entry.path).st_rdev != dev_rdev:
                        continue
                    with open(f"{fdinfo_dir}/{fd_entry.name}") as fi:
                        info = fi.read()
                    if "drm-master:\tyes" in info or "drm-master: yes" in info:
                        comm = open(f"/proc/{pid}/comm").read().strip()
                        return (int(pid), comm)
                except OSError:
                    pass
        except (OSError, PermissionError):
            pass
    return None


def _check_master(lib, fd, device):
    """Return (status_str, locked: bool).

    status_str examples:
      "available"
      "locked by pid 1234 (Xorg)"
      "locked (holder unknown — run as root for details)"
      "unknown (drmSetMaster not available)"
    """
    if lib is None:
        return "unknown (libdrm not loaded)", False

    ret = lib.drmSetMaster(fd)
    if ret == 0:
        lib.drmDropMaster(fd)
        return "available", False

    # Failed — someone holds the master.
    holder = _find_master_holder(device)
    if holder:
        pid, comm = holder
        return f"locked by pid {pid} ({comm})", True
    else:
        return "locked (holder unknown — run as root for details)", True

# ═══════════════════════════════════════════════════════════════════════════ #
#  sysfs helpers                                                              #
# ═══════════════════════════════════════════════════════════════════════════ #

def _sysfs_driver(sysfs_device_path):
    """Read the driver name from a sysfs device path (via 'driver' symlink)."""
    driver_link = os.path.join(sysfs_device_path, "driver")
    try:
        target = os.readlink(driver_link)
        return os.path.basename(target)
    except OSError:
        return None


def _drm_driver(card_name):
    """Return driver name for a DRM card (e.g. 'card0') via sysfs."""
    sysfs = f"/sys/class/drm/{card_name}/device"
    drv = _sysfs_driver(sysfs)
    if drv:
        return drv
    # Fallback: check the modalias or uevent
    try:
        uevent = open(f"{sysfs}/uevent").read()
        for line in uevent.splitlines():
            if line.startswith("DRIVER="):
                return line.split("=", 1)[1]
    except OSError:
        pass
    return "unknown"

# ═══════════════════════════════════════════════════════════════════════════ #
#  DRM device section                                                         #
# ═══════════════════════════════════════════════════════════════════════════ #

def report_drm_device(lib, device):
    """Print full info for one DRM device. Returns True if usable."""
    card_name = os.path.basename(device)
    driver    = _drm_driver(card_name)

    try:
        fd = os.open(device, os.O_RDWR | os.O_CLOEXEC)
    except PermissionError:
        print(f"  {device}  [driver: {driver}]")
        print("    ✗ Permission denied — add user to 'video' group or run as root")
        return False
    except OSError as e:
        print(f"  {device}  [{e.strerror}]")
        return False

    master_status, locked = _check_master(lib, fd, device)
    master_tag = "⚠ " if locked else "✓ "
    print(f"  {device}  [driver: {driver}]")
    print(f"    Master: {master_tag}{master_status}")

    usable = False
    try:
        if lib is None:
            print("    (libdrm not available — cannot read connectors)")
        else:
            res_ptr = lib.drmModeGetResources(fd)
            if not res_ptr:
                print("    (drmModeGetResources failed — module may not support KMS)")
            else:
                res = res_ptr.contents
                n   = res.count_connectors
                for i in range(n):
                    conn_ptr = lib.drmModeGetConnector(fd, res.connectors[i])
                    if not conn_ptr:
                        continue
                    c         = conn_ptr.contents
                    type_name = _CONNECTOR_TYPE.get(c.connector_type, "Unknown")
                    full_name = f"{type_name}-{c.connector_type_id}"
                    connected = c.connection == DRM_MODE_CONNECTED
                    status    = "connected" if connected else "disconnected"

                    size_str = ""
                    if connected and c.mmWidth and c.mmHeight:
                        size_str = f"  {c.mmWidth} x {c.mmHeight} mm"

                    print(f"    Connector {i+1}: {full_name:<14} [{status}]{size_str}")

                    n_modes = c.count_modes
                    if n_modes == 0:
                        msg = ("no modes — driver may need explicit width/height"
                               if connected else "no modes")
                        print(f"      ({msg})")
                    else:
                        for j in range(n_modes):
                            m        = c.modes[j]
                            marker   = "*" if (m.type & DRM_MODE_TYPE_PREFERRED) else " "
                            name_str = m.name.decode(errors="replace")
                            print(f"      {marker} {m.hdisplay:5}x{m.vdisplay:<5}"
                                  f" @ {m.vrefresh:3} Hz   ({name_str})")
                        if connected:
                            usable = True

                    lib.drmModeFreeConnector(conn_ptr)
                lib.drmModeFreeResources(res_ptr)
    finally:
        os.close(fd)

    return usable

# ═══════════════════════════════════════════════════════════════════════════ #
#  Framebuffer section                                                        #
# ═══════════════════════════════════════════════════════════════════════════ #

def _fb_driver(fb_name):
    """Return driver name for /dev/fbN via sysfs."""
    sysfs = f"/sys/class/graphics/{fb_name}/device"
    drv = _sysfs_driver(sysfs)
    if drv:
        return drv
    # Some fb devices (drm_fb_helper) expose a 'device' symlink into a DRM device.
    # Walk up to find the DRM driver name.
    try:
        target = os.readlink(sysfs)
        # target e.g. ../../../0000:00:07.0 — try one level up for driver
        parent = os.path.join(sysfs, "..", "driver")
        drv = os.path.basename(os.readlink(parent))
        return drv
    except OSError:
        pass
    return "unknown"


def _fb_is_drm_backed(fb_name):
    """Return True if this framebuffer is provided by a DRM/KMS driver."""
    # DRM fb helper exposes a symlink: /sys/class/graphics/fbN/device ->
    # the DRM device (e.g. ../../../card0).  Check if that resolves to a
    # path under /sys/class/drm/.
    try:
        sysfs_dev = f"/sys/class/graphics/{fb_name}/device"
        real = os.path.realpath(sysfs_dev)
        # Also check: does a matching /sys/class/drm/cardN exist?
        for drm_entry in glob.glob("/sys/class/drm/card*"):
            drm_real = os.path.realpath(os.path.join(drm_entry, "device"))
            if real == drm_real:
                return True
    except OSError:
        pass
    # Fallback: check the driver name against known DRM drivers
    drv = _fb_driver(fb_name)
    drm_drivers = {
        "virtio_gpu", "vmwgfx", "vboxvideo", "bochs_drm", "simpledrm",
        "i915", "amdgpu", "radeon", "nouveau", "ast", "vc4",
        "sun4i_drm", "msm", "etnaviv", "panfrost", "lima",
        "imx_drm", "exynos_drm", "rockchip_drm", "meson",
    }
    return drv in drm_drivers


def _fb_size(fb_name):
    """Return (width, height) from sysfs virtual_size, or (None, None)."""
    try:
        with open(f"/sys/class/graphics/{fb_name}/virtual_size") as f:
            w, h = f.read().strip().split(",")
            return int(w), int(h)
    except (OSError, ValueError):
        return None, None


def _fb_holders(fb_dev):
    """Return list of (pid, comm) for processes with fb_dev open."""
    holders = []
    try:
        dev_rdev = os.stat(fb_dev).st_rdev
    except OSError:
        return holders

    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        pid = entry.name
        try:
            for fd_entry in os.scandir(f"/proc/{pid}/fd"):
                try:
                    if os.stat(fd_entry.path).st_rdev == dev_rdev:
                        comm = open(f"/proc/{pid}/comm").read().strip()
                        holders.append((int(pid), comm))
                        break
                except OSError:
                    pass
        except (OSError, PermissionError):
            pass
    return holders


def report_framebuffers():
    """Print info about all /dev/fb* devices. Returns list of free fb paths."""
    fb_devs = sorted(glob.glob("/dev/fb*"))
    free_fbs = []

    if not fb_devs:
        print("  (no /dev/fb* devices found)")
        return free_fbs

    for fb_dev in fb_devs:
        fb_name  = os.path.basename(fb_dev)
        driver   = _fb_driver(fb_name)
        drm_back = _fb_is_drm_backed(fb_name)
        w, h     = _fb_size(fb_name)
        size_str = f"  {w}x{h}" if w else ""
        backing  = "DRM-backed" if drm_back else "legacy fbdev"
        holders  = _fb_holders(fb_dev)

        if holders:
            procs    = ", ".join(f"pid {p} ({c})" for p, c in holders)
            use_str  = f"in use by {procs}"
        else:
            use_str  = "free"
            free_fbs.append(fb_dev)

        print(f"  {fb_dev}  [driver: {driver}  {backing}]{size_str}")
        print(f"    {use_str}")

    return free_fbs

# ═══════════════════════════════════════════════════════════════════════════ #
#  Summary                                                                    #
# ═══════════════════════════════════════════════════════════════════════════ #

def print_summary(drm_results, free_fbs, loaded_modules):
    """drm_results: list of (device, usable, locked)"""
    print("── Summary ─────────────────────────────────────────────────────")

    usable_drm    = [(d, lk) for d, ok, lk in drm_results if ok]
    locked_drm    = [(d, lk) for d, ok, lk in drm_results if lk]
    no_modes_drm  = [(d, lk) for d, ok, lk in drm_results if not ok and not lk]

    recommendations = []

    if usable_drm:
        for dev, locked in usable_drm:
            if locked:
                recommendations.append(
                    f"  DRMDisplay('{dev}') — has modes but master is locked;\n"
                    f"    stop the compositor first, or use FBDisplay if a DRM-backed fb is free"
                )
            else:
                recommendations.append(f"  DRMDisplay('{dev}') — ready")

    if no_modes_drm:
        for dev, _ in no_modes_drm:
            recommendations.append(
                f"  DRMDisplay('{dev}', width=W, height=H) — no modes reported;\n"
                f"    pass explicit size for custom LCD panels"
            )

    if free_fbs:
        for fb in free_fbs:
            recommendations.append(f"  FBDisplay('{fb}') — framebuffer available")

    if not drm_results and not free_fbs:
        print("  ✗ No display devices found at all.")
        # Check for likely causes
        if "drm" not in loaded_modules:
            print("  → 'drm' module not loaded. Try: modprobe drm")
        if not glob.glob("/dev/dri/*"):
            print("  → /dev/dri/ is empty. GPU driver may not be loaded.")
        return

    if recommendations:
        print("  Suggested usage:")
        for r in recommendations:
            print(r)
    else:
        print("  ✗ No immediately usable display found.")
        if locked_drm:
            print("  → DRM devices exist but all are locked by a compositor.")
            print("    Stop X11/Wayland, or use FBDisplay if /dev/fb* is available.")
        if not free_fbs and glob.glob("/dev/fb*"):
            print("  → Framebuffers exist but are all in use.")

# ═══════════════════════════════════════════════════════════════════════════ #
#  Entry point                                                                #
# ═══════════════════════════════════════════════════════════════════════════ #

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    # ── modules ──────────────────────────────────────────────────────────────
    loaded = _loaded_modules()
    print_modules(loaded)

    # ── libdrm ───────────────────────────────────────────────────────────────
    lib = _load_libdrm()
    if lib is None:
        print("Note: libdrm not found — connector/mode info unavailable.")
        print("  Install: apt install libdrm2  /  dnf install libdrm\n")

    # ── DRM devices ──────────────────────────────────────────────────────────
    drm_devices = argv if argv else sorted(glob.glob("/dev/dri/card*"))

    print("── DRM devices ─────────────────────────────────────────────────")
    drm_results = []  # (device, usable, locked)
    if not drm_devices:
        print("  (no /dev/dri/card* devices found)")
        if "drm" not in loaded:
            print("  → 'drm' kernel module is not loaded")
        if "virtio_gpu" not in loaded and "i915" not in loaded and "amdgpu" not in loaded:
            print("  → no GPU driver module detected in /proc/modules")
    else:
        for dev in drm_devices:
            # Pre-check master status without consuming a slot in drm_results
            locked_pre = False
            try:
                fd_pre = os.open(dev, os.O_RDWR | os.O_CLOEXEC)
                _, locked_pre = _check_master(lib, fd_pre, dev)
                os.close(fd_pre)
            except OSError:
                pass
            usable = report_drm_device(lib, dev)
            drm_results.append((dev, usable, locked_pre))
            print()

    # ── framebuffer devices ──────────────────────────────────────────────────
    print("── Framebuffer devices (/dev/fb*) ──────────────────────────────")
    free_fbs = report_framebuffers()
    print()

    # ── summary ──────────────────────────────────────────────────────────────
    print_summary(drm_results, free_fbs, loaded)

    any_usable = any(ok for _, ok, _ in drm_results) or bool(free_fbs)
    sys.exit(0 if any_usable else 1)


if __name__ == "__main__":
    main()
