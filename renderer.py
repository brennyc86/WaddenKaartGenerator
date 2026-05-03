import math
import numpy as np
from PIL import Image, ImageDraw
from processing.contour import nap_naar_lat_cm, maak_dieptekaart_rgba
from config import KLEUR_VAARWEG, KLEUR_BOEI_ROOD, KLEUR_BOEI_GROEN, KLEUR_BOEI_GEEL, KLEUR_PIJL, BOEI_TYPE

KAART_B = 800
KAART_H = 400


def _lon_lat_naar_px(lon, lat, bbox, rotatie_graden=0):
    lonMin, latMin, lonMax, latMax = bbox
    nx = (lon - lonMin) / (lonMax - lonMin)
    ny = 1.0 - (lat - latMin) / (latMax - latMin)

    if rotatie_graden != 0:
        rad = math.radians(rotatie_graden)
        cx, cy = 0.5, 0.5
        dx, dy = nx - cx, ny - cy
        nx = cx + dx * math.cos(rad) - dy * math.sin(rad)
        ny = cy + dx * math.sin(rad) + dy * math.cos(rad)

    return int(nx * KAART_B), int(ny * KAART_H)


def _boei_kleur(boei_type):
    if boei_type == BOEI_TYPE["groen_spits"]:
        return KLEUR_BOEI_GROEN
    elif boei_type == BOEI_TYPE["rood_stomp"]:
        return KLEUR_BOEI_ROOD
    elif boei_type == BOEI_TYPE["geel"]:
        return KLEUR_BOEI_GEEL
    elif boei_type == BOEI_TYPE["zwart"]:
        return (30, 30, 30)
    elif boei_type == BOEI_TYPE["wit"]:
        return (240, 240, 240)
    return (180, 180, 180)


def teken_kaart(
    bathymetrie_grid=None,
    lons=None,
    lats=None,
    bbox=None,
    rotatie_graden=0,
    getij_cm=0,
    lat_offset_cm=-175,
    achtergrond_img=None,
    vaarwegen=None,
    boeien=None,
    stroming=None,
    tijdstap_index=12,
    toon_vaarwegen=True,
    toon_boeien=True,
    toon_stroming=True,
    toon_windroos=True,
    diepgang_cm=120,
    buffer_cm=50,
):
    """
    Rendert een 800x400 PIL Image RGB met alle lagen:
      1. Achtergrond: PDOK WMS (land/IJsselmeer/Afsluitdijk) of donkerblauw
      2. Dieptekaart: RGBA semi-transparant over achtergrond
      3. Vaarwegen, boeien, stromingspijlen
      4. Windroos + legenda + diepgang-indicator
    """
    # ── Laag 1: achtergrond (WMS of donkerblauw) ─────────────────────────────
    if achtergrond_img is not None:
        if achtergrond_img.size != (KAART_B, KAART_H):
            achtergrond_img = achtergrond_img.resize((KAART_B, KAART_H), Image.LANCZOS)
        canvas = achtergrond_img.copy().convert("RGBA")
    else:
        canvas = Image.new("RGBA", (KAART_B, KAART_H), (20, 40, 80, 255))

    # ── Laag 2: dieptekaart (RGBA semi-transparant) ──────────────────────────
    if bathymetrie_grid is not None and lons is not None and bbox is not None:
        diepte_grid = nap_naar_lat_cm(bathymetrie_grid, lat_offset_cm)
        rgba_arr = maak_dieptekaart_rgba(
            lons, lats, diepte_grid,
            lat_offset_cm=lat_offset_cm,
            getij_cm=getij_cm,
            breedte=KAART_B, hoogte=KAART_H,
        )
        canvas = Image.alpha_composite(canvas, Image.fromarray(rgba_arr, "RGBA"))

    img = canvas.convert("RGB")
    draw = ImageDraw.Draw(img)

    # ── Laag 3: vaarwegen ────────────────────────────────────────────────────
    if toon_vaarwegen and vaarwegen and bbox:
        for lijn in vaarwegen:
            if len(lijn) < 2:
                continue
            pixels = [_lon_lat_naar_px(lon, lat, bbox, rotatie_graden)
                      for lon, lat in lijn]
            pixels = [(x, y) for x, y in pixels
                      if -50 <= x <= KAART_B + 50 and -50 <= y <= KAART_H + 50]
            if len(pixels) >= 2:
                draw.line(pixels, fill=KLEUR_VAARWEG, width=2)

    # ── Laag 4: boeien ───────────────────────────────────────────────────────
    if toon_boeien and boeien and bbox:
        for boei in boeien:
            x, y = _lon_lat_naar_px(boei["lon"], boei["lat"], bbox, rotatie_graden)
            if 0 <= x < KAART_B and 0 <= y < KAART_H:
                kleur = _boei_kleur(boei["type"])
                draw.ellipse((x - 3, y - 3, x + 3, y + 3),
                             fill=kleur, outline=(0, 0, 0))

    # ── Laag 5: stromingspijlen ──────────────────────────────────────────────
    if toon_stroming and stroming and bbox:
        from processing.stroomatlas import stroming_op_tijdstip
        for lon, lat, velu, velv in stroming_op_tijdstip(stroming, tijdstap_index):
            x, y = _lon_lat_naar_px(lon, lat, bbox, rotatie_graden)
            if not (0 <= x < KAART_B and 0 <= y < KAART_H):
                continue
            snelheid = math.sqrt(velu ** 2 + velv ** 2)
            if snelheid < 0.05:
                continue
            schaal = min(20 * snelheid, 30)
            richting_rad = math.atan2(velu, velv) + math.radians(rotatie_graden)
            dx = schaal * math.sin(richting_rad)
            dy = -schaal * math.cos(richting_rad)
            x2, y2 = int(x + dx), int(y + dy)
            draw.line((x, y, x2, y2), fill=KLEUR_PIJL, width=2)
            draw.ellipse((x2 - 2, y2 - 2, x2 + 2, y2 + 2), fill=KLEUR_PIJL)

    # ── Laag 6: windroos ─────────────────────────────────────────────────────
    if toon_windroos:
        _teken_windroos(draw, rotatie_graden)

    # ── Laag 7: diepgang-indicator + legenda ─────────────────────────────────
    min_diepte_cm = diepgang_cm + buffer_cm
    draw.rectangle((5, KAART_H - 20, 175, KAART_H - 4), fill=(0, 0, 0))
    draw.text((8, KAART_H - 18), f"Min.diepte: {min_diepte_cm} cm", fill=(255, 255, 180))

    _teken_legenda(draw)

    return img


def _teken_windroos(draw, rotatie_graden):
    cx, cy = KAART_B - 35, 35
    r = 20
    rad = math.radians(-rotatie_graden)
    nx = cx + r * math.sin(rad)
    ny = cy - r * math.cos(rad)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(180, 180, 180), width=1)
    draw.line((cx, cy, int(nx), int(ny)), fill=(220, 60, 60), width=2)
    draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=(200, 200, 200))
    draw.text((int(nx) - 4, int(ny) - 12), "N", fill=(220, 60, 60))


def _teken_legenda(draw):
    items = [
        ((210, 190, 145), "Land/dijk"),
        ((235, 215, 160), "Droogval"),
        ((160, 220, 210), "< 1m"),
        ((80,  160, 210), "1-3m"),
        ((40,  100, 175), "3-6m"),
        ((15,   50, 130), "> 6m"),
    ]
    x0 = KAART_B - 90
    y0 = KAART_H - 6 - len(items) * 14
    draw.rectangle((x0 - 4, y0 - 4, KAART_B - 3, KAART_H - 24), fill=(0, 0, 0))
    for i, (kleur, label) in enumerate(items):
        y = y0 + i * 14
        draw.rectangle((x0, y, x0 + 10, y + 10), fill=kleur)
        draw.text((x0 + 13, y), label, fill=(220, 220, 220))
