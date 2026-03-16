#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <string.h>
#include <libdrm/drm.h>
#include <libdrm/drm_mode.h>
#include <xf86drm.h>
#include <xf86drmMode.h>

#define EXPORT __attribute__((visibility("default")))

struct framebuffer_info {
    uint32_t fb_id;
    uint32_t handle;
    uint32_t pitch;
    uint32_t size;
    uint32_t width;
    uint32_t height;
};

EXPORT int open_device(const char *device) {
    int fd = open(device, O_RDWR | O_CLOEXEC);
    if (fd < 0) {
        perror("open");
        return -1;
    }
    return fd;
}

EXPORT struct framebuffer_info create_framebuffer(int fd, uint32_t width, uint32_t height) {
    struct framebuffer_info fb_info = {0};
    struct drm_mode_create_dumb create = {};
    create.width = width;
    create.height = height;
    create.bpp = 32;  // 32 bits per pixel (ARGB format)

    if (ioctl(fd, DRM_IOCTL_MODE_CREATE_DUMB, &create) < 0) {
        perror("DRM_IOCTL_MODE_CREATE_DUMB");
        return fb_info;
    }

    fb_info.handle = create.handle;
    fb_info.pitch = create.pitch;
    fb_info.size = create.size;
    fb_info.width = create.width;
    fb_info.height = create.height;

    struct drm_mode_map_dumb map = {};
    map.handle = create.handle;

    if (ioctl(fd, DRM_IOCTL_MODE_MAP_DUMB, &map) < 0) {
        perror("DRM_IOCTL_MODE_MAP_DUMB");
        return fb_info;
    }

    void *fb_ptr = mmap(0, create.size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, map.offset);
    if (fb_ptr == MAP_FAILED) {
        perror("mmap");
        return fb_info;
    }

    memset(fb_ptr, 0x00, create.size);  // Clear framebuffer to black initially

    struct drm_mode_fb_cmd cmd = {};
    cmd.width = create.width;
    cmd.height = create.height;
    cmd.pitch = create.pitch;
    cmd.bpp = create.bpp;
    cmd.depth = 24;
    cmd.handle = create.handle;

    if (ioctl(fd, DRM_IOCTL_MODE_ADDFB, &cmd) < 0) {
        perror("DRM_IOCTL_MODE_ADDFB");
        return fb_info;
    }

    fb_info.fb_id = cmd.fb_id;
    return fb_info;
}

EXPORT void send_to_fb(int fd, uint32_t handle, uint32_t size, uint8_t *data, uint32_t width, uint32_t height, uint32_t x, uint32_t y, uint32_t fb_pitch) {
    struct drm_mode_map_dumb map = {};
    map.handle = handle;

    if (ioctl(fd, DRM_IOCTL_MODE_MAP_DUMB, &map) < 0) {
        perror("DRM_IOCTL_MODE_MAP_DUMB");
        return;
    }

    void *fb_ptr = mmap(0, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, map.offset);
    if (fb_ptr == MAP_FAILED) {
        perror("mmap");
        return;
    }

    for (uint32_t row = 0; row < height; row++) {
        memcpy((uint8_t *)fb_ptr + (y + row) * fb_pitch + x * 4, data + row * width * 4, width * 4);
    }

    munmap(fb_ptr, size);
}

EXPORT int set_crtc(int fd, drmModeCrtc *crtc, uint32_t fb_id, drmModeConnector *conn) {
    if (drmModeSetCrtc(fd, crtc->crtc_id, fb_id, 0, 0, &conn->connector_id, 1, &crtc->mode) != 0) {
        perror("drmModeSetCrtc");
        return -1;
    }
    return 0;
}

EXPORT drmModeConnector* get_connector(int fd, drmModeRes *res) {
    drmModeConnector *conn = NULL;
    for (int i = 0; i < res->count_connectors; i++) {
        conn = drmModeGetConnector(fd, res->connectors[i]);
        if (conn->connection == DRM_MODE_CONNECTED) {
            break;
        }
        drmModeFreeConnector(conn);
        conn = NULL;
    }
    return conn;
}

EXPORT drmModeEncoder* get_encoder(int fd, drmModeConnector *conn) {
    return drmModeGetEncoder(fd, conn->encoder_id);
}

EXPORT drmModeCrtc* get_crtc(int fd, drmModeEncoder *enc) {
    return drmModeGetCrtc(fd, enc->crtc_id);
}

EXPORT drmModeRes* get_resources(int fd) {
    return drmModeGetResources(fd);
}

EXPORT void free_resources(drmModeRes *res) {
    drmModeFreeResources(res);
}

EXPORT void free_connector(drmModeConnector *conn) {
    drmModeFreeConnector(conn);
}

EXPORT void free_encoder(drmModeEncoder *enc) {
    drmModeFreeEncoder(enc);
}

EXPORT void free_crtc(drmModeCrtc *crtc) {
    drmModeFreeCrtc(crtc);
}

