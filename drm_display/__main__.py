from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("drm-display")
except PackageNotFoundError:
    __version__ = "unknown"

print(f"drm-display {__version__}")
