"""Real QGIS acceptance tests and OSGeo4W headless bootstrap."""

import os
import ctypes
import uuid
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if not os.environ.get("QGIS_CUSTOM_CONFIG_PATH"):
    _profile = (
        Path(__file__).resolve().parents[2]
        / "scratch"
        / ("mpyy-profile-" + uuid.uuid4().hex)
    )
    _profile.mkdir(parents=True)
    os.environ["QGIS_CUSTOM_CONFIG_PATH"] = str(_profile)
_DLL_HANDLES = []
if os.name == "nt" and hasattr(os, "add_dll_directory"):
    prefix = Path(os.environ.get("QGIS_PREFIX_PATH", ""))
    root = Path(os.environ.get("OSGEO4W_ROOT", ""))
    qt = "qt5" if prefix.name.endswith("ltr") else "qt6"
    os.environ["PATH"] = (
        os.pathsep.join(
            str(p) for p in (prefix / "bin", root / "apps" / qt / "bin", root / "bin")
        )
        + os.pathsep
        + os.environ.get("PATH", "")
    )
    for folder in (root / "bin", root / "apps" / qt / "bin", prefix / "bin"):
        if folder.is_dir():
            _DLL_HANDLES.append(os.add_dll_directory(str(folder.resolve())))
    # Explicitly select OSGeo4W Qt before third-party sitecustomize DLL paths.
    # Only when the DLL is really there: with OSGEO4W_ROOT and QGIS_PREFIX_PATH
    # unset -- a plain interpreter importing this package for a qgis-free test --
    # `root` and `prefix` collapse to "." and this load would raise
    # FileNotFoundError on a cwd-relative path, taking the whole run down.
    _qt_core = root / "apps" / qt / "bin" / (
        "Qt5Core.dll" if qt == "qt5" else "Qt6Core.dll"
    )
    if _qt_core.is_file():
        _QT_CORE = ctypes.WinDLL(str(_qt_core))
    os.environ.setdefault("QT_QPA_FONTDIR", str(Path(os.environ["WINDIR"]) / "Fonts"))
