# drm-display

Render NumPy image arrays directly to a Linux display using DRM/KMS —
no X11, Wayland, or `/dev/fb0` required.

Designed for Raspberry Pi, embedded systems, virtual machines, and headless
servers with no connected display.

```python
from drm_display import Screen
import numpy as np

screen = Screen()               # auto-detects best backend
w, h   = screen.get_screen_size()

canvas = np.zeros((h, w, 4), dtype=np.uint8)
canvas[:, :, 2] = 255          # BGRA — red

screen.show(canvas)
```

---

## Why this exists

On modern Linux systems (including Raspberry Pi OS), displays are no longer
reliably exposed via `/dev/fb0`.  Instead, they are managed through the
DRM/KMS subsystem (`/dev/dri/cardN`).

This creates problems:

- `/dev/fb0` is missing or read-only
- X11 / Wayland is overkill for simple display tasks
- Direct rendering becomes unnecessarily complex

**drm-display solves this by providing a simple NumPy-to-screen pipeline**,
with automatic backend selection and graceful fallback.

If you are seeing errors like `Permission denied on /dev/fb0` or
`/dev/fb0: No such file or directory` on a machine that clearly has a working
display, the driver has moved to DRM.  This package handles that transparently.

---

## Features

- **One interface, multiple backends** —
  Automatically selects the best available display method
- **DRM/KMS backend (primary)** —
  Direct rendering via `/dev/dri/cardN` using libdrm;
  works with vc4 (Raspberry Pi), virtio-gpu, vmwgfx, i915, amdgpu, ...
- **Framebuffer fallback (`/dev/fb0`)** —
  Pure Python, no C dependencies
- **Headless backend** —
  Always succeeds — ideal for testing and CI
- **NumPy-first design** —
  Send raw `(H, W, 4)` uint8 arrays directly
- **Explicit channel handling** —
  `show_image(img, fmt="BGR")` converts BGR, RGB, BGRA, or RGBA
  to the canonical BGRA layout before blitting — no ambiguity
- **Partial updates** —
  Update subregions without rewriting the full frame
- **Context manager support** —
  `with Screen() as s:` for safe, automatic cleanup
- **Smart mode selection** —
  Reads the connector's mode list and picks the preferred mode automatically;
  accepts explicit `width`/`height` for custom LCD panels without EDID
- **Built-in diagnostics** —
  `drm-list-modes` shows devices, connectors, modes, and lock state

---

## When to use drm-display

This library is ideal if you want to:

- Render directly to a screen without a desktop environment
- Build kiosk systems on Raspberry Pi
- Display NumPy / OpenCV output without GUI frameworks
- Run inside VMs (virtio-gpu, vmwgfx)
- Work on embedded Linux systems with modern GPU drivers

## When NOT to use it

`drm-display` is a thin surface over DRM/KMS: one buffer, one frame, no state.
It is not intended for:

- Wayland / X11 integration
- Hardware-accelerated rendering (OpenGL, Vulkan)

Use a full graphics stack for those.

Layers, compositing, and interaction are a level up rather than out of scope.
[`drm-screen`](https://github.com/carstenbund/drm_screen) builds on this library
and adds:

- Persistent named layers -- position, z-order, visibility, opacity
- Z-ordered alpha compositing into a single frame
- Hit-testing and a pointer overlay for touch/mouse input
- A pluggable renderer: numpy by default, with an optional `lvgl` backend

```bash
pip install drm-screen
```

---

## Raspberry Pi

Works out of the box on modern Raspberry Pi OS (Bullseye / Bookworm) using
the DRM/KMS driver.  Make sure KMS is enabled in `/boot/config.txt`:

```
dtoverlay=vc4-kms-v3d
```

Typical use cases:

- Fullscreen HDMI output without X/Wayland
- Kiosk displays
- Camera / CV pipelines (OpenCV -> screen)
- Lightweight dashboards

If `/dev/fb0` is missing or unusable, this library automatically switches
to DRM.

---

## Installation

### Quick install

```bash
pip install drm-display
```

`pip install` automatically compiles the small C helper (`drm_display.c`) for
the DRM backend using your system's `libdrm`.  If `gcc` or `libdrm` is absent
the package still installs — `FBDisplay` and `DBDisplay` work without the C
build step.

### Requirements for DRM backend

| Distribution | Command |
|---|---|
| Debian / Ubuntu | `apt install gcc libdrm-dev` |
| Fedora / RHEL | `dnf install gcc libdrm-devel` |
| Alpine | `apk add gcc musl-dev libdrm-dev` |
| Arch | `pacman -S gcc libdrm` |

### Editable install from source

```bash
git clone https://github.com/carstenbund/drm_display.git
cd drm_display
pip install -e .        # compiles libdrm_display.so in-place
```

Local changes to Python files take effect immediately.
Re-run `pip install -e .` (or `make`) after changing `drm_display.c`.

### Compile the C helper manually

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

# Auto-detect: tries card0 -> card1 -> /dev/fb0 -> headless
with Screen() as screen:
    w, h = screen.get_screen_size()

    canvas = np.zeros((h, w, 4), dtype=np.uint8)
    canvas[:, :, 1] = 128    # mid-green in BGRA
    screen.show(canvas)
```

Other construction patterns:

```python
screen = Screen(device="/dev/dri/card0")              # force a specific device
screen = Screen(device="/dev/dri/card0", width=800, height=480)  # custom LCD, no EDID
screen = Screen()                                      # true auto-detect (width/height from mode)
```

### Displaying an image array

`show_image()` accepts any `(H, W, 3|4)` uint8 NumPy array.  Specify the
input channel order with `fmt=` — the image is always converted to BGRA
before blitting (DRM framebuffers use XRGB8888 little-endian, i.e. BGRX
in memory).

```python
from drm_display import Screen

with Screen() as screen:
    # OpenCV (BGR by default)
    screen.show_image(cv2_frame, fmt="BGR")

    # Pillow / imageio / matplotlib (RGB)
    screen.show_image(pil_array, fmt="RGB")

    # Side-by-side comparison
    screen.show_image(left, img2=right, fmt="BGR")
```

Supported formats: `"BGR"` (default), `"RGB"`, `"BGRA"`, `"RGBA"`.

Downscaling uses a vectorised numpy area-average; no OpenCV or Pillow needed.

---

## Backend comparison

| Backend | Class | Device | C build | Dependency | Use when |
|---|---|---|---|---|---|
| DRM/KMS | `DRMDisplay` | `/dev/dri/cardN` | required | `libdrm` | Modern drivers, CVM/KVM, SBC |
| Framebuffer | `FBDisplay` | `/dev/fb0` | none | numpy only | Legacy kernels, compatibility |
| Headless | `DBDisplay` | *(in-memory)* | none | numpy only | Testing, CI, no display |

---

## Low-level backends

Use these directly when you need explicit control over the device or mode.

### DRMDisplay — DRM/KMS

```python
from drm_display import DRMDisplay
import numpy as np

# Auto mode: driver picks the preferred resolution
drm = DRMDisplay(device="/dev/dri/card0")

# Explicit size for custom DSI/LVDS panels without EDID
drm = DRMDisplay(device="/dev/dri/card0", width=800, height=480)

w = drm.screen_width
h = drm.screen_height

canvas = np.zeros((h, w, 4), dtype=np.uint8)
drm.send_full_image(canvas)             # full-screen blit

patch  = np.zeros((100, 200, 4), dtype=np.uint8)
patch[:, :, 2] = 255
drm.send_partial_image(patch, x=50, y=50)  # blit a region

drm.close()    # restores previous CRTC, destroys FB, closes device
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

Input validation enforces `(H, W, 4)` uint8 C-contiguous arrays and
bounds-checks partial updates before writing.

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
    Master: locked by pid 1234 (Xorg)
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
  |
  +-- try /dev/dri/card0  -->  DRMDisplay
  |     open device
  |     drmModeGetResources
  |     find connected connector
  |     select best mode (preferred flag -> first -> explicit size)
  |     create dumb framebuffer
  |     drmModeSetCrtc with selected mode
  |     v
  |   send_full_image(canvas)
  |     mmap framebuffer
  |     memcpy row-by-row (supports partial updates)
  |   close()
  |     restore previous CRTC state
  |     remove framebuffer + destroy dumb buffer
  |     close device fd
  |
  +-- try /dev/fb0  -->  FBDisplay
  |     numpy.memmap(device, shape=(h, w, 4))
  |     canvas slice assignment
  |
  +-- dummy  -->  DBDisplay
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

Changes:

0.1.10  Packaging: the project had no author at all -- pyproject carried no
        authors field, so both Author and Author-email were empty on PyPI.
0.1.9   Point at drm-screen for layers, compositing, and pointer input
        rather than listing them as out of scope.  Record release
        history back to 0.1.5.
0.1.8   Publish sdist only -- the previous py3-none-any wheel carried an
        aarch64 .so and was installed on every platform.  Stop shipping the
        compiled library in the sdist.  Say plainly when libdrm_display.so is
        missing or built for another architecture, instead of a raw OSError.
        Fix resolution mismatch crash and double-free in init error paths.
0.1.7   never released
0.1.6   Fixes from API review
0.1.5   drm-list-modes segfault and AttributeError; DRMDisplay.clear();
        Screen.close() across all backends; call drmModeDirtyFB after each
        write so the framebuffer is visible on vmwgfx
0.1.3   Cleanup README.md
0.1.2   added Screen handler class, removed CV2 and Pillow dependencies. 
0.1.0   initial

---

## License

MIT
