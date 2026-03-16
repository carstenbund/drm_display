import numpy as np


class DBDisplay:
    """Headless in-memory display backed by a NumPy array.

    Useful for testing, CI environments, or any context where no physical
    display device is available.  The last frame written is always accessible
    via ``display.fb``.
    """

    def __init__(self, device="dummy", width=1920, height=1080):
        self.screen_width = width
        self.screen_height = height
        self.fb = np.zeros((height, width, 4), dtype=np.uint8)

    def send_full_image(self, canvas):
        h, w = canvas.shape[:2]
        self.fb[:h, :w, :canvas.shape[2]] = canvas

    def send_partial_image(self, data, x, y):
        h, w = data.shape[:2]
        self.fb[y:y + h, x:x + w, :data.shape[2]] = data

    def clear(self):
        self.fb[:] = 0

    def close(self):
        pass
