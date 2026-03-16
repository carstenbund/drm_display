class Screen(object):
    def __init__(self, device=None, width=1080, height=1080):
        self.display = device
        self.device = device
        self.screen_width = width
        self.screen_height = height
        self._init_display()

    def _init_display(self):
        drivers = [
            ('/dev/dri/card0', DRMDisplay),
            ('/dev/dri/card1', DRMDisplay),
            ('/dev/fb0', FBDisplay),
            ('dummy', DBDisplay),
        ]
        for device_path, DisplayClass in drivers:
            if self.device and self.device != device_path:
                print(f"! {self.device} != {device_path}")
                continue
            try:
                self.display = DisplayClass(device_path, self.screen_width, self.screen_height)
                self.screen_width = self.display.screen_width
                self.screen_height = self.display.screen_height
                print(f"Initialized display using {device_path}")
                print(f"{self.display}, {self.screen_width}, {self.screen_height}")
                break
            except RuntimeError as e:
                print(f"Failed to initialize display with {device_path}: {e}")
                self.display = None
        if not self.display:
            raise RuntimeError("No suitable display driver found.")

    def clear(self):
        black_canvas = np.zeros((self.screen_height, self.screen_width, 4), dtype=np.uint8)
        self.display.send_full_image(black_canvas)

    def get_screen_size(self):
        return self.screen_width, self.screen_height

    def copy(self):
        return self.lastImage.copy()

    def show(self, canvas):
        self.lastImage = canvas
        self.display.send_full_image(canvas)

    def show_image(self, img, img2=None):
        if img2 is not None:
            img = self.adjust_two_images(img, img2)

        img_height, img_width = img.shape[:2]

        if img_width > img_height:  # Landscape
            scale = min(self.screen_height / img_height, self.screen_width / img_width)
        else:  # Portrait
            scale = min(self.screen_width / img_width, self.screen_height / img_height)

        if scale < 1:
            img = cv2.resize(img, (int(img_width * scale), int(img_height * scale)),
                             interpolation=cv2.INTER_LANCZOS4)

        img_height, img_width = img.shape[:2]
        pad_lx = max(0, (self.screen_width - img_width) // 2)
        pad_uy = max(0, (self.screen_height - img_height) // 2)

        canvas = np.zeros((self.screen_height, self.screen_width, 4), dtype=np.uint8)
        canvas[pad_uy:pad_uy + img_height, pad_lx:pad_lx + img_width] = cv2.cvtColor(img, cv2.COLOR_RGB2RGBA)
        self.show(canvas)
