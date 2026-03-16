"""
Example: basic Screen usage.

Run from the repo root after 'pip install -e .':
    python example/screen.py
"""

import numpy as np
from drm_display import Screen

screen = Screen()                                   # auto-detects best backend
w, h = screen.get_screen_size()

# -- solid colour fill --------------------------------------------------------
red = np.zeros((h, w, 4), dtype=np.uint8)
red[:, :, 2] = 255                                  # BGRA: R channel
screen.show(red)

input("Red screen — press Enter to continue...")

# -- gradient -----------------------------------------------------------------
canvas = np.zeros((h, w, 4), dtype=np.uint8)
canvas[:, :, 0] = np.linspace(0, 255, w, dtype=np.uint8)  # blue L→R
canvas[:, :, 1] = np.linspace(0, 255, h, dtype=np.uint8).reshape(h, 1)
screen.show(canvas)

input("Gradient — press Enter to quit...")
screen.clear()
screen.close()
