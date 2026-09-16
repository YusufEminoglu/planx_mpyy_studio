"""PlanX MPYY Studio QGIS entry point."""


def classFactory(iface):
    from .main_plugin import PlanXMPYYStudioPlugin

    return PlanXMPYYStudioPlugin(iface)
