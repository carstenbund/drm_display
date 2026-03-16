# drm-display

Python display library for Linux — write NumPy image arrays directly to a
screen without a compositor, X server, or Wayland session.

Initially designed for Raspberry PI as DRM setup for kiosk mode.

Designed for **embedded systems, CVM/KVM virtual machines, single-board
computers, and headless servers with an attached display** where the traditional
`/dev/fb0` framebuffer is not exposed (or should not be used) because the
driver stack has moved to the modern DRM/KMS subsystem.

```python
from drm_display import Screen
import numpy as np

screen = Screen()               # auto-detects the best available backend
w, h   = screen.get_screen_size()

canvas = np.zeros((h, w, 4), dtype=np.uint8)
canvas[:, :, 2] = 255          # BGRA — red fill
screen.show(canvas)
```

---

## Features

- **Three backends, one interface** — `Screen` probes devices in priority order
  and selects the best one automatically; fall back is always graceful
- **DRM/KMS backend** — direct access to `/dev/dri/cardN` via `libdrm`,
  works with modern virtio-gpu, vmwgfx, vc4, i915, amdgpu, and any other
  KMS-capable driver; no compositor required
- **Smart mode selection** — reads the connector's advertised mode list and
  picks the preferred mode automatically; accepts explicit `width`/`height`
  for custom LCD panels that don't enumerate EDID modes
- **Legacy framebuffer backend** — pure-Python `/dev/fb0` access via
  `numpy.memmap`; zero C dependencies, kept for compatibility
- **Headless / in-memory backend** — numpy buffer that always succeeds;
  useful for unit testing and CI pipelines
- **OpenCV integration** — `Screen.show_image()` scales and centres any
  BGR/BGRA OpenCV image to fit the display, with optional side-by-side layout
- **Partial updates** — `send_partial_image(patch, x, y)` blits a sub-region
  without touching the rest of the framebuffer
- **`drm-list-modes` CLI** — built-in diagnostic tool: checks kernel modules,
  master-lock status, connector modes, and framebuffer devices in one pass

---

## Why DRM/KMS instead of /dev/fb0?

Modern Linux GPU drivers (including virtio-gpu used by QEMU/KVM, and vc4 used
by Raspberry Pi OS) register as **DRM/KMS** devices and expose a display
through `/dev/dri/cardN`.  They may also expose a compatibility `/dev/fb0`
node, but it is often read-only, absent, or explicitly disabled by the
distribution.

If you are seeing errors like `Permission denied on /dev/fb0` or
`/dev/fb0: No such file or directory` on a machine that clearly has a working
display, the driver has moved to DRM.  This package handles that transparently.

---

## Backend comparison

| Backend | Class | Device | C build | Dependency | Use when |
|---|---|---|---|---|---|
| DRM/KMS | `DRMDisplay` | `/dev/dri/cardN` | required | `libdrm` | Modern drivers, CVM/KVM, SBC |
| Framebuffer | `FBDisplay` | `/dev/fb0` | none | numpy only | Legacy kernels, compatibility |
| Headless | `DBDisplay` | *(in-memory)* | none | numpy only | Testing, CI, no display |

---

## Installation

### Option 1 — PyPI (recommended)

```bash
pip install drm-display
```

`pip install` automatically compiles the small C helper (`drm_display.c`) for
the DRM backend using your system's `libdrm`.

**System prerequisites for the DRM backend:**

| Distribution | Command |
|---|---|
| Debian / Ubuntu | `apt install gcc libdrm-dev` |
| Fedora / RHEL | `dnf install gcc libdrm-devel` |
| Alpine | `apk add gcc musl-dev libdrm-dev` |
| Arch | `pacman -S gcc libdrm` |

`pkg-config libdrm` is used when available; otherwise the common include
paths `/usr/include/libdrm` and `/usr/include/drm` are tried in order.

If `libdrm` or `gcc` is absent the package still installs — `FBDisplay` and
`DBDisplay` work without the C build step.

### Option 2 — Editable install from source

```bash
git clone https://github.com/carstenbund/drm_display.git
cd drm_display
pip install -e .        # compiles libdrm_display.so in-place
```

Local changes to Python files take effect immediately.
Re-run `pip install -e .` (or `make`) after changing `drm_display.c`.

### Option 3 — Compile the C helper manually

```bash
make                                          # auto via pkg-config
make CFLAGS_EXTRA="-I/opt/custom/include"     # custom include path
make CC=aarch64-linux-gnu-gcc                 # cross-compile
make info                                     # show resolved flags
```

---

## Quick start

### `Screen` — automatic backend selection (recommended)

```python
from drm_display import Screen
import numpy as np

# Auto-detect: tries card0 → card1 → /dev/fb0 → headless
screen = Screen()

# Force a specific device
screen = Screen(device="/dev/dri/card0")

# Custom LCD with no EDID — pass explicit size
screen = Screen(device="/dev/dri/card0", width=800, height=480)

w, h = screen.get_screen_size()     # actual size after init

# Send a frame (BGRA uint8, shape (h, w, 4))
canvas = np.zeros((h, w, 4), dtype=np.uint8)
canvas[:, :, 1] = 128              # mid-green
screen.show(canvas)

# Get the last shown frame
last = screen.copy()

screen.clear()
screen.close()
```

### OpenCV image display

```python
import cv2
from drm_display import Screen

screen = Screen()
img = cv2.imread("photo.jpg")       # BGR, any size

screen.show_image(img)              # scales + centres automatically

# Side-by-side comparison
img2 = cv2.imread("photo2.jpg")
screen.show_image(img, img2)
```

`show_image()` requires `opencv-python`.  Install it with:

```bash
pip install opencv-python
```

---

## Low-level backends

Use these directly when you need explicit control over the device or mode.

### DRMDisplay — DRM/KMS

```python
from drm_display import DRMDisplay
import numpy as np

# Auto mode: driver picks the preferred resolution
drm = DRMDisplay(device="/dev/dri/card0")

# Explicit size: finds matching mode in connector list;
# if none found, uses connector's preferred mode for set_crtc
# and creates the framebuffer at the requested size
# (panel does internal scaling — common on custom DSI/LVDS screens)
drm = DRMDisplay(device="/dev/dri/card0", width=800, height=480)

w = drm.screen_width
h = drm.screen_height

canvas = np.zeros((h, w, 4), dtype=np.uint8)
drm.send_full_image(canvas)             # full-screen blit

patch  = np.zeros((100, 200, 4), dtype=np.uint8)
patch[:, :, 2] = 255
drm.send_partial_image(patch, x=50, y=50)  # blit a region

drm.cleanup()   # or just let __del__ handle it
```

On init, `DRMDisplay` prints every mode the connector advertises — useful when
diagnosing custom panel issues:

```
Connector reports 2 mode(s):
  1920x1080@60 [preferred] (1920x1080)
   1280x720@60             (1280x720)
Auto-selected mode 1920x1080@60
Framebuffer: 1920x1080
```

### FBDisplay — legacy /dev/fb0

```python
from drm_display import FBDisplay

fb = FBDisplay("/dev/fb0")          # resolution auto-detected from sysfs
print(fb.screen_width, fb.screen_height)

fb.send_full_image(canvas)
fb.clear()
fb.close()
```

No C build, no `libdrm` — just `numpy`.

### DBDisplay — headless buffer

```python
from drm_display import DBDisplay

db = DBDisplay(width=1280, height=720)
db.send_full_image(canvas)
db.send_partial_image(patch, x=10, y=10)

# Access the backing buffer directly
last_frame = db.fb.copy()          # shape (720, 1280, 4)
```

Always succeeds regardless of what hardware is present.  Ideal for unit tests:

```python
def test_rendering():
    display = DBDisplay(width=320, height=240)
    render_something(display)
    assert display.fb[120, 160, 2] == 255   # check a pixel
```

---

## `drm-list-modes` — display diagnostic tool

After `pip install`, a `drm-list-modes` command is available system-wide.
It reports everything relevant to display availability in one pass — no more
assembling answers from `lsmod`, `ls /dev/dri`, and `ls /dev/fb*` separately.

```
── Kernel modules ──────────────────────────────────────────────
  DRM core:
    drm                  loaded    (DRM subsystem)
    drm_kms_helper       loaded    (KMS helpers)
  Virtual / CVM / KVM:
    virtio_gpu           loaded    (virtio-GPU (QEMU/KVM))

── DRM devices ─────────────────────────────────────────────────
  /dev/dri/card0  [driver: virtio_gpu]
    Master: ⚠ locked by pid 1234 (Xorg)
    Connector 1: Virtual-1       [connected]  527 x 296 mm
      * 1920x1080 @  60 Hz   (1920x1080)
        1280x720  @  60 Hz   (1280x720)

── Framebuffer devices (/dev/fb*) ──────────────────────────────
  /dev/fb0  [driver: virtio_gpu  DRM-backed]  1920x1080
    in use by pid 1234 (Xorg)

── Summary ─────────────────────────────────────────────────────
  Suggested usage:
  DRMDisplay('/dev/dri/card0') — has modes but master is locked;
    stop the compositor first, or use FBDisplay if a DRM-backed fb is free
```

### What it checks

| Section | What is reported |
|---|---|
| **Kernel modules** | Which DRM core, GPU driver, and framebuffer modules are loaded — grouped by role (CVM/KVM, desktop GPU, embedded SBC, legacy fb) |
| **DRM devices** | Driver name, DRM master lock (names the locking process by scanning `/proc/*/fdinfo`), all connectors with connection status and physical size, all modes with preferred marker |
| **Framebuffer devices** | Always shown even when no DRM devices exist — driver name, DRM-backed vs legacy, physical size, in-use status |
| **Summary** | Plain-English recommended call: `DRMDisplay(...)`, `FBDisplay(...)`, or explicit `width`/`height` for panels with no EDID |

### Usage

```bash
drm-list-modes                        # scan everything
drm-list-modes /dev/dri/card0         # specific device only
python -m drm_display.list_modes      # run without installing
```

Exit codes: `0` = at least one usable device found, `1` = nothing usable,
`2` = fatal error (libdrm missing).

---

## Custom LCD panels

Custom DSI and LVDS panels attached to embedded SBCs often do not expose EDID
data, so the DRM connector reports zero modes.  `DRMDisplay` handles this:

```python
# Pass explicit size — DRMDisplay will use whatever mode the CRTC has
# and create the framebuffer at the requested size.
# The panel does internal scaling (common on DSI/LVDS screens).
drm = DRMDisplay(device="/dev/dri/card0", width=480, height=800)
```

If the connector does enumerate modes and the requested size matches one of
them exactly, that mode is used for `drmModeSetCrtc`.  If there is no exact
match, the preferred mode (or first listed mode) is used for the CRTC call
while the framebuffer is still created at the requested size.

Run `drm-list-modes` first to see what your connector actually reports — it
saves a lot of guesswork.

---

## How it works

```
Screen()
  │
  ├─ try /dev/dri/card0  ──►  DRMDisplay
  │     open device
  │     drmModeGetResources
  │     find connected connector
  │     select best mode (preferred flag → first → explicit size)
  │     create dumb framebuffer
  │     drmModeSetCrtc with selected mode
  │     ▼
  │   send_full_image(canvas)
  │     mmap framebuffer
  │     memcpy row-by-row (supports partial updates)
  │
  ├─ try /dev/fb0  ──►  FBDisplay
  │     numpy.memmap(device, shape=(h, w, 4))
  │     canvas slice assignment
  │
  └─ dummy  ──►  DBDisplay
        numpy.zeros(shape=(h, w, 4))
        always succeeds
```

The DRM backend compiles a small C helper (`drm_display.c`) that wraps
`libdrm` ioctl calls.  The Python layer uses `ctypes` to call it — no
Python C extension build system required, no ABI compatibility issues.

---

## Requirements

- **Python** 3.8+
- **numpy** (installed automatically)
- **gcc** + **libdrm-dev** — required only for `DRMDisplay`; the package
  installs and `FBDisplay`/`DBDisplay` work without it
- **opencv-python** — optional, required only for `Screen.show_image()`
- Linux with a KMS-capable GPU for `DRMDisplay`
- User must be in the `video` group (or run as root) to open `/dev/dri/cardN`

---

## Troubleshooting

**`Failed to open device` / Permission denied**
```bash
sudo usermod -aG video $USER   # then log out and back in
# or run once as root to verify the device works
```

**`No connected connector found`**
The display cable is not plugged in, or the driver does not see the panel.
Run `drm-list-modes` to see the raw connector state.

**`Failed to set CRTC` on a custom panel**
The connector likely reports zero modes (no EDID).  Pass `width=` and
`height=` explicitly:
```python
DRMDisplay("/dev/dri/card0", width=800, height=480)
```

**`libdrm_display.so` not found**
The C helper was not compiled.  Run `pip install -e .` (editable) or `make`
from the repo root.  Check that `gcc` and `libdrm-dev` are installed first.

**DRM device exists but all operations fail**
A compositor (X11, Wayland) may hold the DRM master lock.
```bash
drm-list-modes    # shows which process holds master
```

---

## Build from source — publishing

```bash
pip install build twine
python -m build
twine upload --repository testpypi dist/*   # smoke-test on TestPyPI first
twine upload dist/*                          # publish to PyPI
```

---

## License

MIT
