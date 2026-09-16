"""Render the real Qt workbench without opening a visible native window."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

os.environ["QT_QPA_PLATFORM"] = "windows"
from qgis.core import QgsApplication, Qgis
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont, QFontDatabase, QPalette

from ..dock import MPYYDock
from .test_gui_qgis import APP, Interface


def render(widget, path):
    widget.ensurePolished()
    widget.layout().activate()
    APP.processEvents()
    if not widget.grab().save(str(path)):
        raise RuntimeError("Could not save screenshot: " + str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--before-source")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    fonts = Path(__file__).resolve().parents[1] / "resources" / "fonts"
    QFontDatabase.addApplicationFont(str(fonts / "DejaVuSans.ttf"))
    original_palette = QPalette(APP.palette())
    snapshots = []
    if args.before_source:
        spec = importlib.util.spec_from_file_location("planx_mpyy_studio._before_gui", args.before_source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        APP.setFont(QFont("DejaVu Sans", 10))
        before = module.MPYYDock(Interface())
        before.resize(440, 800)
        for index, title in ((0, "Previous workspace screen"), (3, "Previous analysis screen")):
            before.tabs.setCurrentIndex(index)
            name = "before_" + str(index) + ".png"
            render(before, output / name)
            snapshots.append({"file": name, "title": title, "theme": "light", "width": 440, "font_pt": 10})
        before.close()
        before.deleteLater()
    for dark in (False, True):
        palette = QPalette(original_palette)
        roles = {
            QPalette.ColorRole.Window: "#242424" if dark else "#F4F4F4",
            QPalette.ColorRole.Base: "#171717" if dark else "#FFFFFF",
            QPalette.ColorRole.Button: "#303030" if dark else "#FFFFFF",
            QPalette.ColorRole.WindowText: "#F2F2F2" if dark else "#202020",
            QPalette.ColorRole.Text: "#F2F2F2" if dark else "#202020",
            QPalette.ColorRole.ButtonText: "#F2F2F2" if dark else "#202020",
        }
        for role, color in roles.items():
            palette.setColor(role, QColor(color))
        APP.setPalette(palette)
        for font_pt in (10, 15):
            APP.setFont(QFont("DejaVu Sans", font_pt))
            dock = MPYYDock(Interface())
            for width in (360, 600):
                dock.resize(width, 860)
                for view in ("start", "tools", "workspace", "style", "density", "activity"):
                    if view == "start":
                        dock.tabs.setCurrentIndex(0)
                    elif view == "tools":
                        dock.focus_tool_search()
                        dock.tool_search.setText("erisilebilirlik senaryolarini karsilastir")
                    elif view in {"workspace", "style", "density"}:
                        tool_id = {"workspace": "create_workspace", "style": "style_and_forms",
                                   "density": "estimate_plan_capacity"}[view]
                        dock.show_inline_form(tool_id)
                    else:
                        dock.status.setText("Örnek sonuç\nSatır 1: inceleme bulgusu\nSatır 2: açıklayıcı ayrıntı")
                        dock.tabs.setCurrentIndex(2)
                    theme = "dark" if dark else "light"
                    name = f"{theme}_{font_pt}pt_{width}_{view}.png"
                    render(dock, output / name)
                    titles = {'start': 'Başlangıç', 'tools': 'Araçlar', 'workspace': 'Çalışma alanı',
                              'style': 'Katman stili', 'density': 'Kapasite', 'activity': 'İşlem Kaydı'}
                    snapshots.append({"file": name, "title": titles[view], "theme": 'Koyu' if dark else 'Açık',
                                      "width": dock.width(), "font_pt": font_pt})
            dock.dispose_ui()
            dock.close()
            dock.deleteLater()
            APP.processEvents()
    payload = {"qgis_version": Qgis.QGIS_VERSION, "snapshots": snapshots,
               "scope": "Real Qt rendering; no claim of a full assistive-technology audit."}
    (output / "qa.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    cards = "\n".join(
        f'<figure><a href="{row["file"]}"><img src="{row["file"]}" loading="lazy" alt="{row["title"]} {row["theme"]} {row["width"]}px {row["font_pt"]}pt"></a>'
        f'<figcaption>{row["title"]} · {row["theme"]} · {row["width"]}px · {row["font_pt"]}pt</figcaption></figure>'
        for row in snapshots
    )
    (output / "index.html").write_text(
        '<!doctype html><html lang="tr"><meta charset="utf-8"><title>MPYY Studio Arayüz İncelemesi</title>'
        '<style>body{font:16px system-ui;margin:24px;background:#f3f5f7;color:#202020}'
        'main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}'
        'figure{margin:0;padding:12px;background:white;border:1px solid #adb5bd}img{width:100%;height:auto}'
        'figcaption{margin-top:12px}</style><h1>MPYY Studio Arayüz İncelemesi</h1>'
        '<p>Dar/geniş panel, normal/büyük yazı ve açık/koyu paletlerde gerçek QGIS arayüz görüntüleri.</p>'
        '<main>' + cards + '</main></html>', encoding="utf-8",
    )
    print("Rendered", len(snapshots), "real Qt snapshots:", output)


if __name__ == "__main__":
    main()
