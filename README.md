# drm-display

Python display library for Linux — sends NumPy image arrays to a screen
without a compositor or X server.

Three backends are included; `Screen` picks the best one automatically:

| Backend | Device | Notes |
|---|---|---|
| `DRMDisplay` | `/dev/dri/cardN` | DRM/KMS via `libdrm` — preferred, works with modern CVM/KVM drivers |
| `FBDisplay` | `/dev/fb0` | Legacy framebuffer via `numpy.memmap` — no C build required |
| `DBDisplay` | *(in-memory)* | Headless numpy buffer — always works, good for testing |

## Install

```bash
pip install drm-display
```

`pip install` compiles the small C helper for the DRM backend automatically.
Requirements: `gcc`, `libdrm-dev` (Debian/Ubuntu) or `libdrm-devel` (Fedora/RHEL).

If `libdrm` is unavailable the package still installs and `FBDisplay` /
`DBDisplay` work without it.

## Quick start — `Screen` (recommended)

```python
from drm_display import Screen
import numpy as np

screen = Screen()                         # auto-detects best backend
screen = Screen(device="/dev/dri/card0") # force a specific backend

w, h = screen.get_screen_size()

# BGRA uint8 array
canvas = np.zeros((h, w, 4), dtype=np.uint8)
canvas[:, :, 2] = 255                    # red fill
screen.show(canvas)

# Display a scaled & centred OpenCV image (requires opencv-python)
import cv2
img = cv2.imread("photo.jpg")
screen.show_image(img)

screen.close()
```

## Low-level backends

```python
from drm_display import DRMDisplay, FBDisplay, DBDisplay

# DRM/KMS
drm = DRMDisplay(device="/dev/dri/card0", width=1920, height=1080)
drm.send_full_image(canvas)          # full-screen blit
drm.send_partial_image(patch, x, y) # blit a region

# Framebuffer
fb = FBDisplay("/dev/fb0")           # size auto-detected from sysfs
fb.send_full_image(canvas)

# Headless
db = DBDisplay(width=1280, height=720)
db.send_full_image(canvas)
last_frame = db.fb.copy()
```

## Build from source / editable install

```bash
git clone https://github.com/carstenbund/drm_display.git
cd drm_display
pip install -e .        # compiles libdrm_display.so in-place
```

Or compile the shared library manually:

```bash
make                    # uses pkg-config
make CFLAGS_EXTRA="-I/opt/custom/include"   # override include path
make info               # show resolved flags
```

## Publishing (maintainer notes)

```bash
pip install build twine
python -m build
twine upload --repository testpypi dist/*   # test first
twine upload dist/*                          # publish to PyPI
```

## License

MIT
