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
        ("fb_id_ptr", ctypes.POINTER(ctypes.c_uint32)),
        ("crtc_id_ptr", ctypes.POINTER(ctypes.c_uint32)),
        ("connector_id_ptr", ctypes.POINTER(ctypes.c_uint32)),
        ("encoder_id_ptr", ctypes.POINTER(ctypes.c_uint32)),
        ("count_fbs", ctypes.c_uint32),
        ("count_crtcs", ctypes.c_uint32),
        ("count_connectors", ctypes.c_uint32),
        ("count_encoders", ctypes.c_uint32),
        ("min_width", ctypes.c_uint32),
        ("max_width", ctypes.c_uint32),
        ("min_height", ctypes.c_uint32),
        ("max_height", ctypes.c_uint32),
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
    def __init__(self, device="/dev/dri/card0", width=1024, height=600):
        #self.lib = ctypes.CDLL(os.path.abspath("libdrm_display.so"))
        base_path = os.path.dirname(__file__)
        # Construct the absolute path to the shared library
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

        self.lib.set_crtc.argtypes = [
            ctypes.c_int, 
            ctypes.POINTER(drmModeCrtc), 
            ctypes.c_uint32, 
            ctypes.POINTER(drmModeConnector)
        ]
        self.lib.set_crtc.restype = ctypes.c_int

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

        #time.sleep(5)  # Add a delay to ensure device initialization

        #print("Calling get_resources...")
        self.res = self.lib.get_resources(self.fd)
        if not self.res:
            print("get_resources returned None")
            print("Device file descriptor:", self.fd)
            raise RuntimeError("Failed to get DRM resources")
        #print("Successfully obtained DRM resources")
        #print("Resources count_fbs:", self.res.contents.count_fbs)
        #print("Resources count_crtcs:", self.res.contents.count_crtcs)
        #print("Resources count_connectors:", self.res.contents.count_connectors)
        #print("Resources count_encoders:", self.res.contents.count_encoders)

        self.conn = self.lib.get_connector(self.fd, self.res)
        if not self.conn:
            self.lib.free_resources(self.res)
            raise RuntimeError("No connected connector found")
        #print("Successfully obtained DRM connector")
        #print("Connector ID:", self.conn.contents.connector_id)
        #print("Connector encoder ID:", self.conn.contents.encoder_id)
        #print("Connector type:", self.conn.contents.connector_type)
        #print("Connector type ID:", self.conn.contents.connector_type_id)
        #print("Connector connection:", self.conn.contents.connection)
        #print("Connector mmWidth:", self.conn.contents.mmWidth)
        #print("Connector mmHeight:", self.conn.contents.mmHeight)
        #print("Connector subpixel:", self.conn.contents.subpixel)
        #print("Connector count_modes:", self.conn.contents.count_modes)
        #print("Connector count_props:", self.conn.contents.count_props)
        #print("Connector count_encoders:", self.conn.contents.count_encoders)

        self.enc = self.lib.get_encoder(self.fd, self.conn)
        if not self.enc:
            self.lib.free_connector(self.conn)
            self.lib.free_resources(self.res)
            raise RuntimeError("Failed to get encoder")
        #print("Successfully obtained DRM encoder")
        #print("Encoder ID:", self.enc.contents.encoder_id)
        #print("Encoder type:", self.enc.contents.encoder_type)
        #print("Encoder CRTC ID:", self.enc.contents.crtc_id)
        #print("Encoder possible CRTCs:", self.enc.contents.possible_crtcs)
        #print("Encoder possible clones:", self.enc.contents.possible_clones)

        self.crtc = self.lib.get_crtc(self.fd, self.enc)
        if not self.crtc:
            self.lib.free_encoder(self.enc)
            self.lib.free_connector(self.conn)
            self.lib.free_resources(self.res)
            raise RuntimeError("Failed to get CRTC")
        #print("Successfully obtained DRM CRTC")
        #print("CRTC ID:", self.crtc.contents.crtc_id)
        #print("CRTC buffer ID:", self.crtc.contents.buffer_id)
        #print("CRTC x:", self.crtc.contents.x)
        #print("CRTC y:", self.crtc.contents.y)
        #print("CRTC width:", self.crtc.contents.width)
        #print("CRTC height:", self.crtc.contents.height)
        #print("CRTC mode valid:", self.crtc.contents.mode_valid)
        #print("CRTC mode clock:", self.crtc.contents.mode.clock)
        #print("CRTC mode hdisplay:", self.crtc.contents.mode.hdisplay)
        #print("CRTC mode vdisplay:", self.crtc.contents.mode.vdisplay)
        #print("CRTC mode vrefresh:", self.crtc.contents.mode.vrefresh)

        self.fb_info = self.lib.create_framebuffer(self.fd, width, height)
        if not self.fb_info.fb_id:
            self.lib.free_crtc(self.crtc)
            self.lib.free_encoder(self.enc)
            self.lib.free_connector(self.conn)
            self.lib.free_resources(self.res)
            raise RuntimeError("Failed to create framebuffer")
        print("Successfully created framebuffer")
        #print("Framebuffer ID:", self.fb_info.fb_id)
        #print("Framebuffer handle:", self.fb_info.handle)
        #print("Framebuffer pitch:", self.fb_info.pitch)
        #print("Framebuffer size:", self.fb_info.size)
        print("Framebuffer width:", self.fb_info.width)
        print("Framebuffer height:", self.fb_info.height)

        if self.lib.set_crtc(
            self.fd, 
            self.crtc, 
            self.fb_info.fb_id, 
            self.conn
        ) != 0:
            self.lib.free_crtc(self.crtc)
            self.lib.free_encoder(self.enc)
            self.lib.free_connector(self.conn)
            self.lib.free_resources(self.res)
            raise RuntimeError("Failed to set CRTC")
        #print("Successfully set CRTC")

    def send_full_image(self, data):
        data_ptr = data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
        self.lib.send_to_fb(self.fd, self.fb_info.handle, self.fb_info.size, data_ptr, self.fb_info.width, self.fb_info.height, 0, 0, self.fb_info.pitch)

    def send_partial_image(self, data, x, y):
        height, width, _ = data.shape
        data_ptr = data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
        self.lib.send_to_fb(self.fd, self.fb_info.handle, self.fb_info.size, data_ptr, width, height, x, y, self.fb_info.pitch)

    def cleanup(self):
        if hasattr(self, 'crtc') and self.crtc:
            self.lib.free_crtc(self.crtc)
        if hasattr(self, 'enc') and self.enc:
            self.lib.free_encoder(self.enc)
        if hasattr(self, 'conn') and self.conn:
            self.lib.free_connector(self.conn)
        if hasattr(self, 'res') and self.res:
            self.lib.free_resources(self.res)

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

