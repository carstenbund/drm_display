# drm-display

Python bindings for Linux **DRM/KMS** display output — send NumPy image arrays
directly to `/dev/dri/cardN` without a compositor or X server.

## System requirements

- Linux with a KMS-capable GPU (most modern hardware)
- `libdrm` development headers: `apt install libdrm-dev` / `dnf install libdrm-devel`
- `gcc`
- Access to `/dev/dri/cardN` (add your user to the `video` group or run as root)

## Install

```bash
pip install drm-display
```

`pip install` compiles the small C helper (`drm_display.c`) against your
system's `libdrm` automatically.  `pkg-config libdrm` is used when available;
otherwise `/usr/include/libdrm` and `-ldrm` are assumed.

## Usage

```python
import numpy as np
from drm_display import DRMDisplay

display = DRMDisplay(device="/dev/dri/card0", width=1920, height=1080)

# BGRA uint8 NumPy array, shape (height, width, 4)
frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
frame[:, :, 2] = 255   # red screen (B=0, G=0, R=255, A=0)

display.send_full_image(frame)

# Partial update (blit a region at pixel offset x, y)
patch = np.zeros((100, 200, 4), dtype=np.uint8)
patch[:, :, 1] = 255   # green patch
display.send_partial_image(patch, x=50, y=50)
```

`DRMDisplay.__del__` frees DRM resources automatically; call `display.cleanup()`
explicitly if you need deterministic teardown.

## Build from source / editable install

```bash
git clone https://github.com/carstenbund/drm_display.git
cd drm_display
pip install -e .        # compiles libdrm_display.so in-place
```

Or compile the shared library manually:

```bash
gcc -shared -fPIC -o drm_display/libdrm_display.so \
    $(pkg-config --cflags libdrm) \
    drm_display/drm_display.c \
    $(pkg-config --libs libdrm)
```

## Publishing (maintainer notes)

```bash
python -m build
twine upload --repository testpypi dist/*   # test first
twine upload dist/*                          # publish to PyPI
```

## License

MIT
