import io
import numpy as np
import requests
import tifffile

# EMODnet Bathymetry WCS 1.0.0 — Europese marine databron
# Dekt Waddenzee, Noordzee en alle Europese zeeën
# Resolutie: ~115m (1/16 boogminuut), gratis, geen authenticatie
EMODNET_WCS = "https://ows.emodnet-bathymetry.eu/wcs"


def haal_bathymetrie_op(bbox, resolutie_m=200, callback=None):
    """
    Haalt bathymetrie+hoogte op van EMODnet Bathymetry WCS.
    bbox: (lonMin, latMin, lonMax, latMax) WGS84
    resolutie_m: gewenste rasterresolutie in meter
    Geeft terug: (grid_m, lons_1d, lats_1d)
      grid_m: 2D float32, positief = boven zeeniveau (land), negatief = water
    """
    lonMin, latMin, lonMax, latMax = bbox

    if callback:
        callback("Bathymetrie ophalen van EMODnet...")

    # Bereken uitvoergrootte voor gewenste resolutie
    lon_m = (lonMax - lonMin) * 70000   # ~m bij 53°N
    lat_m = (latMax - latMin) * 111000
    breedte = max(50, min(1500, int(lon_m / resolutie_m)))
    hoogte  = max(50, min(1500, int(lat_m / resolutie_m)))

    params = [
        ("service",       "WCS"),
        ("version",       "1.0.0"),
        ("request",       "GetCoverage"),
        ("coverage",      "emodnet:mean"),
        ("bbox",          f"{lonMin},{latMin},{lonMax},{latMax}"),
        ("crs",           "EPSG:4326"),
        ("response_crs",  "EPSG:4326"),
        ("format",        "GeoTIFF"),
        ("width",         str(breedte)),
        ("height",        str(hoogte)),
    ]

    try:
        resp = requests.get(EMODNET_WCS, params=params, timeout=120)
        resp.raise_for_status()

        with tifffile.TiffFile(io.BytesIO(resp.content)) as tif:
            data = tif.asarray().astype(np.float32)

        if data.ndim == 3:
            data = data[0]

        # Vervang nodata waarden
        nodata_masker = (data < -9000) | (data > 1e20)
        data[nodata_masker] = np.nan

        actuele_hoogte, actuele_breedte = data.shape
        lons = np.linspace(lonMin, lonMax, actuele_breedte)
        lats = np.linspace(latMax, latMin, actuele_hoogte)  # N→Z

        if callback:
            callback(f"Bathymetrie opgehaald: {actuele_breedte}×{actuele_hoogte} px"
                     f" (min {np.nanmin(data):.1f}m, max {np.nanmax(data):.1f}m)")

        return data, lons, lats

    except Exception as e:
        raise RuntimeError(f"Fout bij ophalen bathymetrie: {e}") from e
