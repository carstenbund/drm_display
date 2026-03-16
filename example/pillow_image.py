"""
Example: display an image file with Pillow (auto-scaled to screen).

Usage:
    python example/pillow_image.py photo.jpg
"""

import sys
import numpy as np
from PIL import Image
from drm_display import Screen

path = sys.argv[1] if len(sys.argv) > 1 else "image.jpg"

screen = Screen()
w, h = screen.get_screen_size()

img = Image.open(path).convert("RGBA")
img = img.resize((w, h), Image.LANCZOS)

frame = np.array(img, dtype=np.uint8)
# Pillow gives RGBA; DRM expects BGRA — swap R and B
frame[:, :, [0, 2]] = frame[:, :, [2, 0]]

screen.show(frame)
input(f"{path} — press Enter to quit...")
screen.clear()
screen.close()
