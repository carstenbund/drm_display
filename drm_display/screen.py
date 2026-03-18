"""
screen.py — unified display interface that auto-detects available backends.

Priority order:
  1. /dev/dri/card0  (DRM/KMS — preferred, works with modern CVM/KVM drivers)
  2. /dev/dri/card1  (second DRM card)
  3. /dev/fb0        (legacy framebuffer — kept for compatibility)
  4. dummy           (headless numpy buffer — always succeeds)

Usage::

    from drm_display import Screen
    import numpy as np

    screen = Screen()                         # auto-detect
    screen = Screen(device="/dev/dri/card0")  # force a specific backend

    canvas = np.zeros((screen.screen_height, screen.screen_width, 4), dtype=np.uint8)
    screen.show(canvas)
    screen.show_image(img_array)             # scales + centres any (h,w,3/4) array
"""

import numpy as np

from .drm_display import DRMDisplay
from .fb_display import FBDisplay
from .db_display import DBDisplay



def _numpy_resize(img, new_h, new_w):
    """Area-average downscale — pure numpy, no extra dependencies.

    Uses np.add.reduceat for vectorised block averaging: one pass over rows,
    one pass over columns.  Fast enough for display-rate use on small systems.
    """
    src_h, src_w = img.shape[:2]
    row_cuts = np.round(np.linspace(0, src_h, new_h + 1)).astype(int)
    col_cuts = np.round(np.linspace(0, src_w, new_w + 1)).astype(int)

    # Average rows into new_h bands
    tmp = np.add.reduceat(img.astype(np.float32), row_cuts[:-1], axis=0)
    tmp /= np.diff(row_cuts)[:, None, None]

    # Average columns into new_w bands
    tmp = np.add.reduceat(tmp, col_cuts[:-1], axis=1)
    tmp /= np.diff(col_cuts)[None, :, None]

    return np.clip(tmp, 0, 255).astype(np.uint8)


class Screen:
    def __init__(self, device=None, canvas_width=None, canvas_height=None):
        self.device = device
        self._last_image = None
        self._init_display()
        # Canvas is the painter's render resolution — independent of the
        # physical display.  Defaults to screen size so existing code that
        # treats them as the same keeps working.
        self.canvas_width  = canvas_width  or self.screen_width
        self.canvas_height = canvas_height or self.screen_height

    def _init_display(self):
        candidates = [
            ("/dev/dri/card0", DRMDisplay),
            ("/dev/dri/card1", DRMDisplay),
            ("/dev/fb0",       FBDisplay),
            ("dummy",          DBDisplay),
        ]
        for device_path, DisplayClass in candidates:
            if self.device and self.device != device_path:
                continue
            try:
                # Always let the backend auto-detect the display resolution.
                self.display = DisplayClass(device_path, None, None)
                self.screen_width  = self.display.screen_width
                self.screen_height = self.display.screen_height
                print(f"Display: {device_path} ({self.screen_width}x{self.screen_height})")
                return
            except Exception as e:
                print(f"  {device_path}: {e}")

        raise RuntimeError("No suitable display backend found.")

    # ── public API ────────────────────────────────────────────────────────────

    def show(self, canvas):
        """Send a (H, W, 4) BGRA uint8 array sized to the *screen* directly."""
        self._last_image = canvas
        self.display.send_full_image(canvas)

    def show_canvas(self, canvas, fmt="BGRA"):
        """Send a painter canvas to the screen.

        If canvas_size == screen_size the array is blitted directly.
        Otherwise it is scaled and centred via show_image(), so the
        painter is free to render at any resolution or aspect ratio.

        *fmt* is passed to show_image() when scaling is needed; it is
        ignored for direct blits (canvas must already be BGRA uint8).
        """
        if canvas.shape[1] == self.screen_width and canvas.shape[0] == self.screen_height:
            self.show(canvas)
        else:
            self.show_image(canvas, fmt=fmt)

    def clear(self):
        """Fill the display with black."""
        self.display.clear()

    def get_screen_size(self):
        """Return physical display (width, height)."""
        return self.screen_width, self.screen_height

    def get_canvas_size(self):
        """Return the painter canvas (width, height)."""
        return self.canvas_width, self.canvas_height

    def copy(self):
        """Return a copy of the last shown frame, or None if nothing shown yet."""
        if self._last_image is None:
            return None
        return self._last_image.copy()

    def close(self):
        self.display.close()
        self._last_image = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def show_image(self, img, img2=None, fmt="BGR"):
        """Scale and centre a (H, W, 3|4) uint8 NumPy image on the screen.

        *fmt* specifies the channel order of the input array.  The image is
        always converted to BGRA before being sent to the display hardware
        (DRM framebuffers expect XRGB8888 little-endian, i.e. BGRX in memory).

        Supported *fmt* values: ``"BGR"`` (default), ``"RGB"``,
        ``"BGRA"``, ``"RGBA"``.

        Downscaling uses a vectorised numpy area-average — no extra
        dependencies beyond numpy.

        If *img2* is supplied both images are placed side-by-side first.
        """
        if img2 is not None:
            img = self._side_by_side(img, img2)

        img_h, img_w = img.shape[:2]

        if img_w > img_h:  # landscape
            scale = min(self.screen_height / img_h, self.screen_width / img_w)
        else:              # portrait
            scale = min(self.screen_width / img_w, self.screen_height / img_h)

        if scale < 1:
            img = _numpy_resize(img, max(1, int(img_h * scale)),
                                     max(1, int(img_w * scale)))

        img_h, img_w = img.shape[:2]
        pad_x = max(0, (self.screen_width  - img_w) // 2)
        pad_y = max(0, (self.screen_height - img_h) // 2)

        # Normalise to BGRA (canonical internal layout for DRM/fb backends)
        fmt = fmt.upper()
        if fmt == "RGB":
            alpha = np.full((*img.shape[:2], 1), 255, dtype=np.uint8)
            img = np.concatenate([img[:, :, ::-1], alpha], axis=2)  # RGB→BGR + A
        elif fmt == "RGBA":
            img = img[:, :, [2, 1, 0, 3]]  # RGBA → BGRA
        elif fmt == "BGR":
            alpha = np.full((*img.shape[:2], 1), 255, dtype=np.uint8)
            img = np.concatenate([img, alpha], axis=2)
        elif fmt == "BGRA":
            pass  # already canonical
        else:
            raise ValueError(f"Unknown fmt={fmt!r}; expected one of: BGR, RGB, BGRA, RGBA")

        canvas = np.zeros((self.screen_height, self.screen_width, 4), dtype=np.uint8)
        canvas[pad_y:pad_y + img_h, pad_x:pad_x + img_w] = img
        self.show(canvas)

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _side_by_side(img1, img2):
        """Place two images side by side, padding the shorter one."""
        h = max(img1.shape[0], img2.shape[0])
        ch = img1.shape[2] if img1.ndim == 3 else 1

        def _pad(im):
            ph = h - im.shape[0]
            pad = np.zeros((ph, im.shape[1], ch), dtype=im.dtype)
            return np.vstack([im, pad])

        i1 = _pad(img1) if img1.shape[0] < h else img1
        i2 = _pad(img2) if img2.shape[0] < h else img2
        return np.hstack([i1, i2])
