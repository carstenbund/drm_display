import ctypes
import os
import numpy as np
import time

DRM_DISPLAY_MODE_LEN = 32

class drmModeModeInfo(ctypes.Structure):
    _fields_ = [
        ("clock", ctypes.c_uint32),
        ("hdisplay", ctypes.c_uint16),
        ("hsync_start", ctypes.c_uint16),
        ("hsync_end", ctypes.c_uint16),
        ("htotal", ctypes.c_uint16),
        ("hskew", ctypes.c_uint16),
        ("vdisplay", ctypes.c_uint16),
        ("vsync_start", ctypes.c_uint16),
        ("vsync_end", ctypes.c_uint16),
        ("vtotal", ctypes.c_uint16),
        ("vscan", ctypes.c_uint16),
        ("vrefresh", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("name", ctypes.c_char * DRM_DISPLAY_MODE_LEN)
    ]

class drmModeRes(ctypes.Structure):
    _fields_ = [
        ("count_fbs",        ctypes.c_int),
        ("fb_id_ptr",        ctypes.POINTER(ctypes.c_uint32)),
        ("count_crtcs",      ctypes.c_int),
        ("crtc_id_ptr",      ctypes.POINTER(ctypes.c_uint32)),
        ("count_connectors", ctypes.c_int),
        ("connector_id_ptr", ctypes.POINTER(ctypes.c_uint32)),
        ("count_encoders",   ctypes.c_int),
        ("encoder_id_ptr",   ctypes.POINTER(ctypes.c_uint32)),
        ("min_width",        ctypes.c_uint32),
        ("max_width",        ctypes.c_uint32),
        ("min_height",       ctypes.c_uint32),
        ("max_height",       ctypes.c_uint32),
    ]

class drmModeConnector(ctypes.Structure):
    _fields_ = [
        ("connector_id", ctypes.c_uint32),
        ("encoder_id", ctypes.c_uint32),
        ("connector_type", ctypes.c_uint32),
        ("connector_type_id", ctypes.c_uint32),
        ("connection", ctypes.c_uint32),
        ("mmWidth", ctypes.c_uint32),
        ("mmHeight", ctypes.c_uint32),
        ("subpixel", ctypes.c_uint32),
        ("count_modes", ctypes.c_uint32),
        ("modes", ctypes.POINTER(drmModeModeInfo)),
        ("count_props", ctypes.c_uint32),
        ("props", ctypes.POINTER(ctypes.c_uint32)),
        ("prop_values", ctypes.POINTER(ctypes.c_uint64)),
        ("count_encoders", ctypes.c_uint32),
        ("encoders", ctypes.POINTER(ctypes.c_uint32)),
    ]

class drmModeEncoder(ctypes.Structure):
    _fields_ = [
        ("encoder_id", ctypes.c_uint32),
        ("encoder_type", ctypes.c_uint32),
        ("crtc_id", ctypes.c_uint32),
        ("possible_crtcs", ctypes.c_uint32),
        ("possible_clones", ctypes.c_uint32),
    ]

class drmModeCrtc(ctypes.Structure):
    _fields_ = [
        ("crtc_id", ctypes.c_uint32),
        ("buffer_id", ctypes.c_uint32),
        ("x", ctypes.c_uint32),
        ("y", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("mode_valid", ctypes.c_int),
        ("mode", drmModeModeInfo),
        ("gamma_size", ctypes.c_int),
    ]

class FramebufferInfo(ctypes.Structure):
    _fields_ = [("fb_id", ctypes.c_uint32),
                ("handle", ctypes.c_uint32),
                ("pitch", ctypes.c_uint32),
                ("size", ctypes.c_uint32),
                ("width", ctypes.c_uint32),
                ("height", ctypes.c_uint32)]

class DRMDisplay:
    def __init__(self, device="/dev/dri/card0", width=None, height=None):
        base_path = os.path.dirname(__file__)
        lib_path = os.path.join(base_path, "libdrm_display.so")
        self.lib = ctypes.CDLL(lib_path)

        self.lib.open_device.argtypes = [ctypes.c_char_p]
        self.lib.open_device.restype = ctypes.c_int

        self.lib.create_framebuffer.argtypes = [ctypes.c_int, ctypes.c_uint32, ctypes.c_uint32]
        self.lib.create_framebuffer.restype = FramebufferInfo

        self.lib.send_to_fb.argtypes = [
            ctypes.c_int,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32
        ]
        self.lib.send_to_fb.restype = None

        self.lib.dirty_fb.argtypes = [ctypes.c_int, ctypes.c_uint32]
        self.lib.dirty_fb.restype  = None

        self.lib.set_crtc_with_mode.argtypes = [
            ctypes.c_int,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.POINTER(drmModeModeInfo),
        ]
        self.lib.set_crtc_with_mode.restype = ctypes.c_int

        self.lib.get_connector.argtypes = [ctypes.c_int, ctypes.POINTER(drmModeRes)]
        self.lib.get_connector.restype = ctypes.POINTER(drmModeConnector)

        self.lib.get_encoder.argtypes = [ctypes.c_int, ctypes.POINTER(drmModeConnector)]
        self.lib.get_encoder.restype = ctypes.POINTER(drmModeEncoder)

        self.lib.get_crtc.argtypes = [ctypes.c_int, ctypes.POINTER(drmModeEncoder)]
        self.lib.get_crtc.restype = ctypes.POINTER(drmModeCrtc)

        self.lib.get_resources.argtypes = [ctypes.c_int]
        self.lib.get_resources.restype = ctypes.POINTER(drmModeRes)

        self.lib.free_resources.argtypes = [ctypes.POINTER(drmModeRes)]
        self.lib.free_resources.restype = None

        self.lib.free_connector.argtypes = [ctypes.POINTER(drmModeConnector)]
        self.lib.free_connector.restype = None

        self.lib.free_encoder.argtypes = [ctypes.POINTER(drmModeEncoder)]
        self.lib.free_encoder.restype = None

        self.lib.free_crtc.argtypes = [ctypes.POINTER(drmModeCrtc)]
        self.lib.free_crtc.restype = None

        self.fd = self.lib.open_device(device.encode('utf-8'))
        if self.fd < 0:
            raise RuntimeError("Failed to open device")
        print("Opened DRM device:", device)

        self.res = self.lib.get_resources(self.fd)
        if not self.res:
            raise RuntimeError("Failed to get DRM resources")

        self.conn = self.lib.get_connector(self.fd, self.res)
        if not self.conn:
            self.lib.free_resources(self.res)
            raise RuntimeError("No connected connector found")

        self.enc = self.lib.get_encoder(self.fd, self.conn)
        if not self.enc:
            self.lib.free_connector(self.conn)
            self.lib.free_resources(self.res)
            raise RuntimeError("Failed to get encoder")

        self.crtc = self.lib.get_crtc(self.fd, self.enc)
        if not self.crtc:
            self.lib.free_encoder(self.enc)
            self.lib.free_connector(self.conn)
            self.lib.free_resources(self.res)
            raise RuntimeError("Failed to get CRTC")

        # -- mode selection ---------------------------------------------------
        # Read all modes the connector advertises and pick the best one.
        #
        # Priority when width/height are given (custom LCD override):
        #   1. Exact match in connector mode list
        #   2. Fall back to preferred/first connector mode and warn
        #
        # Priority when width/height are None (auto from driver):
        #   1. Mode flagged DRM_MODE_TYPE_PREFERRED
        #   2. First mode in the list (drivers usually sort by preference)
        #   3. If no modes at all: raise a clear error
        DRM_MODE_TYPE_PREFERRED = 1 << 3

        conn = self.conn.contents
        n_modes = conn.count_modes
        modes = [conn.modes[i] for i in range(n_modes)]

        print(f"Connector reports {n_modes} mode(s):")
        for m in modes:
            flag = " [preferred]" if m.type & DRM_MODE_TYPE_PREFERRED else ""
            print(f"  {m.hdisplay}x{m.vdisplay}@{m.vrefresh}{flag} ({m.name.decode()})")

        selected_mode = None

        if width is not None and height is not None:
            # User explicitly requested a size — try to find an exact match.
            for m in modes:
                if m.hdisplay == width and m.vdisplay == height:
                    selected_mode = m
                    print(f"Mode matched requested size {width}x{height}")
                    break
            if selected_mode is None and modes:
                # No exact match — use the connector's preferred/first mode.
                # The framebuffer will still be created at the requested size;
                # some panels (DSI/LVDS) accept this and do internal scaling.
                for m in modes:
                    if m.type & DRM_MODE_TYPE_PREFERRED:
                        selected_mode = m
                        break
                if selected_mode is None:
                    selected_mode = modes[0]
                print(
                    f"Warning: no connector mode for {width}x{height}. "
                    f"Using connector mode {selected_mode.hdisplay}x{selected_mode.vdisplay} "
                    f"with framebuffer {width}x{height} — panel may do internal scaling."
                )
        else:
            # Auto: use preferred mode or first available.
            for m in modes:
                if m.type & DRM_MODE_TYPE_PREFERRED:
                    selected_mode = m
                    break
            if selected_mode is None and modes:
                selected_mode = modes[0]
            if selected_mode is None:
                self.lib.free_crtc(self.crtc)
                self.lib.free_encoder(self.enc)
                self.lib.free_connector(self.conn)
                self.lib.free_resources(self.res)
                raise RuntimeError(
                    "Connector reports no modes. "
                    "Pass width= and height= explicitly for custom LCD panels."
                )
            width  = selected_mode.hdisplay
            height = selected_mode.vdisplay
            print(f"Auto-selected mode {width}x{height}@{selected_mode.vrefresh}")

        self._mode = selected_mode  # keep alive for ctypes pointer

        # -- framebuffer + CRTC -----------------------------------------------
        self.fb_info = self.lib.create_framebuffer(self.fd, width, height)
        if not self.fb_info.fb_id:
            self.lib.free_crtc(self.crtc)
            self.lib.free_encoder(self.enc)
            self.lib.free_connector(self.conn)
            self.lib.free_resources(self.res)
            raise RuntimeError("Failed to create framebuffer")

        self.screen_width  = self.fb_info.width
        self.screen_height = self.fb_info.height
        print(f"Framebuffer: {self.screen_width}x{self.screen_height}")

        mode_ptr = ctypes.pointer(self._mode)
        if self.lib.set_crtc_with_mode(
            self.fd,
            self.crtc.contents.crtc_id,
            self.fb_info.fb_id,
            conn.connector_id,
            mode_ptr,
        ) != 0:
            self.lib.free_crtc(self.crtc)
            self.lib.free_encoder(self.enc)
            self.lib.free_connector(self.conn)
            self.lib.free_resources(self.res)
            raise RuntimeError("Failed to set CRTC")

    def clear(self):
        blank = np.zeros((self.screen_height, self.screen_width, 4), dtype=np.uint8)
        self.send_full_image(blank)

    def send_full_image(self, data):
        data_ptr = data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
        self.lib.send_to_fb(self.fd, self.fb_info.handle, self.fb_info.size, data_ptr, self.fb_info.width, self.fb_info.height, 0, 0, self.fb_info.pitch)
        self.lib.dirty_fb(self.fd, self.fb_info.fb_id)

    def send_partial_image(self, data, x, y):
        height, width, _ = data.shape
        data_ptr = data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
        self.lib.send_to_fb(self.fd, self.fb_info.handle, self.fb_info.size, data_ptr, width, height, x, y, self.fb_info.pitch)
        self.lib.dirty_fb(self.fd, self.fb_info.fb_id)

    def cleanup(self):
        if hasattr(self, 'crtc') and self.crtc:
            self.lib.free_crtc(self.crtc)
            self.crtc = None
        if hasattr(self, 'enc') and self.enc:
            self.lib.free_encoder(self.enc)
            self.enc = None
        if hasattr(self, 'conn') and self.conn:
            self.lib.free_connector(self.conn)
            self.conn = None
        if hasattr(self, 'res') and self.res:
            self.lib.free_resources(self.res)
            self.res = None

    def close(self):
        self.cleanup()

    def __del__(self):
        self.cleanup()

if __name__ == "__main__":
    drm_display = DRMDisplay(device="/dev/dri/card0", width=1024, height=600)
    print("DRM Display initialized successfully")

    # Create a test image (red screen)
    test_image = np.zeros((600, 1024, 4), dtype=np.uint8)
    test_image[:, :, 0] = 255  # Red channel

    # Send the full image to the display
    print(f"set up image to send {test_image.shape}")
    drm_display.send_full_image(test_image)
    print("Sent full image to display")

