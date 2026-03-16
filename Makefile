# Makefile for drm_display/libdrm_display.so
#
# Targets:
#   make            - build using pkg-config (auto-detects include/lib paths)
#   make BACKEND=fb - framebuffer /dev/fb0 stub (no libdrm needed)
#   make clean      - remove compiled artifacts
#   make install    - copy .so into the Python package for dev use
#
# Override variables at the command line, e.g.:
#   make CFLAGS_EXTRA="-I/opt/vc/include" LDFLAGS_EXTRA="-L/opt/vc/lib"

CC      ?= gcc
SRC     := drm_display/drm_display.c
OUT     := drm_display/libdrm_display.so
BACKEND ?= drm

# ── DRM/KMS backend (default) ────────────────────────────────────────────────
# Tries pkg-config first; falls back to well-known include paths.
ifeq ($(BACKEND),drm)

PKGCFG_OK := $(shell pkg-config --exists libdrm 2>/dev/null && echo yes)

ifeq ($(PKGCFG_OK),yes)
  DRM_CFLAGS  := $(shell pkg-config --cflags libdrm)
  DRM_LDFLAGS := $(shell pkg-config --libs   libdrm)
else
  # Raspbian / older Ubuntu use /usr/include/libdrm
  # Fedora/RHEL use /usr/include/drm
  LIBDRM_INC  := $(firstword $(foreach d,\
                    /usr/include/libdrm \
                    /usr/include/drm \
                    /usr/local/include/libdrm,\
                    $(wildcard $(d)/xf86drmMode.h)))
  ifeq ($(LIBDRM_INC),)
    $(error Cannot find xf86drmMode.h. Install libdrm-dev / libdrm-devel)
  endif
  DRM_CFLAGS  := -I$(dir $(LIBDRM_INC))
  DRM_LDFLAGS := -ldrm
endif

CFLAGS  := -shared -fPIC $(DRM_CFLAGS)  $(CFLAGS_EXTRA)
LDFLAGS := $(DRM_LDFLAGS) $(LDFLAGS_EXTRA)
endif

# ── Framebuffer stub (BACKEND=fb, no libdrm) ──────────────────────────────
# Useful on older kernels or VM environments that still expose /dev/fb0.
# Expects drm_display/drm_display_fb.c (a separate FB implementation).
ifeq ($(BACKEND),fb)
SRC     := drm_display/drm_display_fb.c
CFLAGS  := -shared -fPIC $(CFLAGS_EXTRA)
LDFLAGS := $(LDFLAGS_EXTRA)
endif

# ─────────────────────────────────────────────────────────────────────────────

.PHONY: all clean install info

all: $(OUT)
	@echo "Built $(OUT)"

$(OUT): $(SRC)
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f $(OUT)

install: $(OUT)
	@echo "$(OUT) is already in place — 'pip install -e .' or run Python from repo root."

info:
	@echo "BACKEND  : $(BACKEND)"
	@echo "CC       : $(CC)"
	@echo "SRC      : $(SRC)"
	@echo "OUT      : $(OUT)"
	@echo "CFLAGS   : $(CFLAGS)"
	@echo "LDFLAGS  : $(LDFLAGS)"
