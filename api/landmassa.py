import io
import math
import requests
from PIL import Image

PDOK_WMTS = "https://service.pdok.nl/brt/achtergrondkaart/wmts/v2_0/grijs/EPSG:3857/{z}/{x}/{y}.png"
TILE_GROOTTE = 256  # px per tile


def _lon_lat_naar_tile(lon, lat, zoom):
    """Bereken OSM/WMTS tile x,y voor een lon/lat coordinaat."""
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    lat_rad = math.radians(lat)
    y = int((1 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2 * n)
    return x, y


def _tile_naar_lon_lat(tx, ty, zoom):
    """Linkerbovenhoek van een tile als (lon, lat)."""
    n = 2 ** zoom
    lon = tx / n * 360 - 180
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ty / n)))
    lat = math.degrees(lat_rad)
    return lon, lat


def haal_achtergrond_wms(bbox, breedte=800, hoogte=400, zoom=11, callback=None):
    """
    Haalt achtergrondkaart op via PDOK BRT WMTS (grijs thema).
    Stitcht meerdere 256px tiles samen en crop naar exacte bbox.
    bbox: (lonMin, latMin, lonMax, latMax) WGS84
    Geeft PIL Image RGB terug op (breedte × hoogte).
    """
    lonMin, latMin, lonMax, latMax = bbox

    if callback:
        callback("Achtergrond (land/water) ophalen van PDOK WMTS...")

    # Bereken tile bereik voor bbox
    tx_min, ty_max = _lon_lat_naar_tile(lonMin, latMin, zoom)  # SW hoek
    tx_max, ty_min = _lon_lat_naar_tile(lonMax, latMax, zoom)  # NE hoek

    nx = tx_max - tx_min + 1
    ny = ty_max - ty_min + 1

    if callback:
        callback(f"Achtergrond: {nx * ny} tiles ophalen (zoom {zoom})...")

    # Canvas voor alle tiles
    canvas_b = nx * TILE_GROOTTE
    canvas_h = ny * TILE_GROOTTE
    canvas = Image.new("RGB", (canvas_b, canvas_h), (200, 200, 200))

    headers = {"User-Agent": "WaddenKaartGenerator/1.0 (BKOS-NUI project)"}

    for ty in range(ty_min, ty_max + 1):
        for tx in range(tx_min, tx_max + 1):
            url = PDOK_WMTS.format(z=zoom, x=tx, y=ty)
            try:
                resp = requests.get(url, timeout=15, headers=headers)
                if resp.status_code == 200:
                    tile = Image.open(io.BytesIO(resp.content)).convert("RGB")
                    px = (tx - tx_min) * TILE_GROOTTE
                    py = (ty - ty_min) * TILE_GROOTTE
                    canvas.paste(tile, (px, py))
            except Exception:
                pass  # laat grijze placeholder staan

    # Bepaal pixel-offsets voor exacte bbox crop
    # Linkerbovenhoek van de tile-canvas in lon/lat
    canvas_lon_min, canvas_lat_max = _tile_naar_lon_lat(tx_min, ty_min, zoom)
    canvas_lon_max, canvas_lat_min = _tile_naar_lon_lat(tx_max + 1, ty_max + 1, zoom)

    canvas_lon_bereik = canvas_lon_max - canvas_lon_min
    canvas_lat_bereik = canvas_lat_max - canvas_lat_min  # N→Z = positief

    # Pixel-offset van gewenste bbox binnen canvas
    links  = int((lonMin - canvas_lon_min) / canvas_lon_bereik * canvas_b)
    rechts = int((lonMax - canvas_lon_min) / canvas_lon_bereik * canvas_b)
    boven  = int((canvas_lat_max - latMax) / canvas_lat_bereik * canvas_h)
    onder  = int((canvas_lat_max - latMin) / canvas_lat_bereik * canvas_h)

    # Clip naar canvas grenzen
    links  = max(0, min(links, canvas_b - 1))
    rechts = max(links + 1, min(rechts, canvas_b))
    boven  = max(0, min(boven, canvas_h - 1))
    onder  = max(boven + 1, min(onder, canvas_h))

    uitsnede = canvas.crop((links, boven, rechts, onder))
    resultaat = uitsnede.resize((breedte, hoogte), Image.LANCZOS)

    if callback:
        callback(f"Achtergrond opgehaald: {nx}×{ny} tiles → {breedte}×{hoogte} px")

    return resultaat
