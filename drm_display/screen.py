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
    screen.show_image(bgr_img)               # scales + centres an OpenCV image
"""

import numpy as np

from .drm_display import DRMDisplay
from .fb_display import FBDisplay
from .db_display import DBDisplay

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False


class Screen:
    def __init__(self, device=None, width=1920, height=1080):
        self.device = device
        self.screen_width = width
        self.screen_height = height
        self._last_image = None
        self._init_display()

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
                self.display = DisplayClass(device_path, self.screen_width, self.screen_height)
                self.screen_width = self.display.screen_width
                self.screen_height = self.display.screen_height
                print(f"Display: {device_path} ({self.screen_width}x{self.screen_height})")
                return
            except Exception as e:
                print(f"  {device_path}: {e}")

        raise RuntimeError("No suitable display backend found.")

    # ── public API ────────────────────────────────────────────────────────────

    def show(self, canvas):
        """Send a (H, W, 4) BGRA uint8 NumPy array to the display."""
        self._last_image = canvas
        self.display.send_full_image(canvas)

    def clear(self):
        """Fill the display with black."""
        self.display.clear()

    def get_screen_size(self):
        """Return (width, height)."""
        return self.screen_width, self.screen_height

    def copy(self):
        """Return a copy of the last shown frame, or None if nothing shown yet."""
        if self._last_image is None:
            return None
        return self._last_image.copy()

    def close(self):
        self.display.close()

    def show_image(self, img, img2=None):
        """Scale and centre an OpenCV BGR/BGRA image on the screen.

        Requires opencv-python (``pip install opencv-python``).
        If *img2* is supplied, both images are placed side-by-side first.
        """
        if not _CV2_AVAILABLE:
            raise RuntimeError("show_image() requires opencv-python: pip install opencv-python")

        if img2 is not None:
            img = self._side_by_side(img, img2)

        img_h, img_w = img.shape[:2]

        if img_w > img_h:  # landscape
            scale = min(self.screen_height / img_h, self.screen_width / img_w)
        else:              # portrait
            scale = min(self.screen_width / img_w, self.screen_height / img_h)

        if scale < 1:
            img = cv2.resize(
                img,
                (int(img_w * scale), int(img_h * scale)),
                interpolation=cv2.INTER_LANCZOS4,
            )

        img_h, img_w = img.shape[:2]
        pad_x = max(0, (self.screen_width  - img_w) // 2)
        pad_y = max(0, (self.screen_height - img_h) // 2)

        canvas = np.zeros((self.screen_height, self.screen_width, 4), dtype=np.uint8)
        if img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
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
