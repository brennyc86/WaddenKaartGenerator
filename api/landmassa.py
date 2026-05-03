import io
import requests
from PIL import Image

PDOK_WMS = "https://service.pdok.nl/brt/achtergrondkaart/wms/v2_0"


def haal_achtergrond_wms(bbox, breedte=800, hoogte=400, callback=None):
    """
    Haalt een achtergrondkaart op van PDOK BRT (land, water, IJsselmeer,
    Afsluitdijk, eilanden — alles visueel correct).
    bbox: (lonMin, latMin, lonMax, latMax) WGS84
    Geeft een PIL.Image RGB terug op (breedte x hoogte).
    """
    lonMin, latMin, lonMax, latMax = bbox

    if callback:
        callback("Achtergrond (land/water) ophalen van PDOK WMS...")

    # WMS 1.3.0 met EPSG:4326: axis order is LAT,LON in bbox
    params = {
        "SERVICE":     "WMS",
        "VERSION":     "1.3.0",
        "REQUEST":     "GetMap",
        "LAYERS":      "standaard",
        "STYLES":      "grijs",
        "CRS":         "EPSG:4326",
        "BBOX":        f"{latMin},{lonMin},{latMax},{lonMax}",
        "WIDTH":       str(breedte),
        "HEIGHT":      str(hoogte),
        "FORMAT":      "image/png",
        "TRANSPARENT": "FALSE",
    }

    try:
        resp = requests.get(PDOK_WMS, params=params, timeout=30)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        if callback:
            callback(f"Achtergrond opgehaald: {img.size[0]}×{img.size[1]} px")
        return img
    except Exception as e:
        raise RuntimeError(f"Fout bij ophalen achtergrond WMS: {e}") from e
