from .drm_display import DRMDisplay
from .fb_display import FBDisplay
from .db_display import DBDisplay
from .screen import Screen

from importlib.metadata import version, PackageNotFoundError
try:
    __version__ = version("drm-display")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["Screen", "DRMDisplay", "FBDisplay", "DBDisplay", "__version__"]
