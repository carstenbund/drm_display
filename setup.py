"""
Custom build logic for drm-display.

Compiles drm_display.c into libdrm_display.so using libdrm headers/libs
discovered via pkg-config (falls back to common paths if pkg-config is absent).
"""
import os
import subprocess
import sys
from setuptools import setup
from setuptools.command.build_py import build_py as _BuildPy
from setuptools.command.develop import develop as _Develop


def _pkg_config(lib):
    """Return (cflags, ldflags) for a pkg-config library, or sensible defaults."""
    try:
        cflags = subprocess.check_output(
            ["pkg-config", "--cflags", lib], stderr=subprocess.DEVNULL
        ).decode().split()
        ldflags = subprocess.check_output(
            ["pkg-config", "--libs", lib], stderr=subprocess.DEVNULL
        ).decode().split()
        return cflags, ldflags
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ["-I/usr/include/libdrm"], ["-ldrm"]


def compile_libdrm_display(dest_dir):
    """Compile drm_display.c -> libdrm_display.so in dest_dir."""
    src = os.path.join(os.path.dirname(__file__), "drm_display", "drm_display.c")
    out = os.path.join(dest_dir, "libdrm_display.so")
    os.makedirs(dest_dir, exist_ok=True)

    cflags, ldflags = _pkg_config("libdrm")
    cmd = ["gcc", "-shared", "-fPIC", "-o", out] + cflags + [src] + ldflags
    print(f"Building {out} ...")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)


class BuildPy(_BuildPy):
    """Compile the C library as part of a normal build/install."""

    def run(self):
        super().run()
        dest = os.path.join(self.build_lib, "drm_display")
        compile_libdrm_display(dest)


class Develop(_Develop):
    """Compile the C library in-place for editable/develop installs."""

    def run(self):
        super().run()
        src_pkg = os.path.join(os.path.dirname(__file__), "drm_display")
        compile_libdrm_display(src_pkg)


setup(
    cmdclass={
        "build_py": BuildPy,
        "develop": Develop,
    },
)
