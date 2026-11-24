"""
utils/map_view.py

Zoom de mapas folium sin fit_bounds.

Streamlit dibuja los mapas de pestañas y expanders ocultos con tamaño 0;
en ese caso Leaflet calcula fit_bounds sobre un contenedor vacío y cae a
zoom mundial. Centrar con un zoom calculado desde los bounds evita el problema.
"""


def zoom_for_bounds(bx) -> int:
    """bx = [[sur, oeste], [norte, este]] → nivel de zoom aproximado."""
    (s, w), (n, e) = bx
    span = max(abs(n - s), abs(e - w))
    for limite, zoom in ((0.001, 18), (0.003, 17), (0.007, 16),
                         (0.015, 15), (0.03, 14), (0.07, 13), (0.15, 12)):
        if span < limite:
            return zoom
    return 11
