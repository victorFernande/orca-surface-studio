"""Orca Surface Studio. Legacy import identity retained for existing installs."""

__version__ = "0.12.0"

try:
    import orca as _native_orca
except ImportError:
    _native_orca = None

if _native_orca is not None:
    from . import plugin as _plugin
