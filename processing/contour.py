import numpy as np
from contourpy import contour_generator
from config import DIEPTE_NIVEAUS_CM


def nap_naar_lat_cm(grid_nap_m, lat_offset_cm):
    """
    Converteert NAP hoogte (m float) naar diepte t.o.v. LAT (cm).
    Resultaat:
      positief  = ONDER LAT = altijd water (diepte in cm)
      negatief  = BOVEN LAT = land of droogvallend gebied
    lat_offset_cm: negatief getal, bijv. -175 (LAT is 175 cm onder NAP)
    """
    grid_nap_cm = grid_nap_m * 100
    return -(grid_nap_cm - lat_offset_cm)


def bereken_contourlijnen(lons, lats, diepte_lat_cm_grid, niveaus_cm=None, callback=None):
    """
    Berekent contourlijnen via contourpy (Marching Squares).
    lons: 1D array lengte W
    lats: 1D array lengte H
    diepte_lat_cm_grid: 2D array (H, W), positief = water onder LAT
    niveaus_cm: lijst van diepteniveaus in cm t.o.v. LAT
    Geeft terug: dict {niveau_cm: [[(lon, lat), ...], ...]}
    """
    if niveaus_cm is None:
        niveaus_cm = DIEPTE_NIVEAUS_CM

    # contourpy verwacht lats stijgend
    if len(lats) > 1 and lats[0] > lats[-1]:
        lats = lats[::-1]
        diepte_lat_cm_grid = diepte_lat_cm_grid[::-1, :]

    cgen = contour_generator(x=lons, y=lats, z=diepte_lat_cm_grid)

    resultaat = {}
    totaal = len(niveaus_cm)

    for i, niveau in enumerate(niveaus_cm):
        if callback and i % 20 == 0:
            callback(f"Contourlijnen berekenen: {i}/{totaal} niveaus...")
        try:
            lijnen = cgen.lines(niveau)
            if lijnen:
                resultaat[niveau] = [
                    [(pt[0], pt[1]) for pt in lijn]
                    for lijn in lijnen
                    if len(lijn) >= 2
                ]
        except Exception:
            pass

    if callback:
        callback(f"Contourlijnen klaar: {sum(len(v) for v in resultaat.values())} lijnen")

    return resultaat


def maak_dieptekaart_rgba(lons, lats, diepte_lat_cm_grid, lat_offset_cm=-175,
                           getij_cm=0, breedte=800, hoogte=400):
    """
    Maakt een RGBA uint8 array (hoogte×breedte×4) voor alpha-compositing
    over een achtergrondkaart (PDOK WMS).

    Diepteformule:
      effectieve_diepte = diepte_lat_cm + (getij_cm - lat_offset_cm)
      > 0  = water (diepte in cm)
      < 0  = droog (hoogte boven huidig waterpeil in cm)

    Nautisch kleurenschema (semi-transparant over WMS):
      land/dijk (> 2m boven water)  : beige, alpha 160
      droogval  (0..2m boven water) : zandgeel, alpha 180
      0-1m water                    : lichtturquoise, alpha 190
      1-3m water                    : lichtblauw, alpha 200
      3-6m water                    : middenblauw, alpha 210
      > 6m water                    : donkerblauw, alpha 220
    """
    # Resample naar schermgrootte
    rij_idx = np.linspace(0, diepte_lat_cm_grid.shape[0] - 1, hoogte).astype(int)
    kol_idx = np.linspace(0, diepte_lat_cm_grid.shape[1] - 1, breedte).astype(int)
    grid = diepte_lat_cm_grid[np.ix_(rij_idx, kol_idx)]

    nan_masker = np.isnan(grid)

    # Effectieve diepte bij huidig getij
    # water_boven_lat: hoeveel cm de waterstand boven LAT staat bij huidig getij
    water_boven_lat = getij_cm - lat_offset_cm   # bijv. 0 - (-175) = 175 cm bij getij=0
    eff = grid + water_boven_lat                  # > 0 = water; < 0 = droog

    rgba = np.zeros((hoogte, breedte, 4), dtype=np.uint8)

    # Land / dijk: > 200cm boven huidig waterpeil
    m = (~nan_masker) & (eff < -200)
    rgba[m] = (210, 190, 145, 160)

    # Droogvallend: 0..200cm boven waterpeil (wadplaten e.d.)
    m = (~nan_masker) & (eff >= -200) & (eff < 0)
    rgba[m] = (235, 215, 160, 185)

    # 0–100 cm water (zeer ondiep)
    m = (~nan_masker) & (eff >= 0) & (eff < 100)
    rgba[m] = (160, 220, 210, 190)

    # 100–300 cm water (ondiep)
    m = (~nan_masker) & (eff >= 100) & (eff < 300)
    rgba[m] = (80, 160, 210, 200)

    # 300–600 cm water (medium)
    m = (~nan_masker) & (eff >= 300) & (eff < 600)
    rgba[m] = (40, 100, 175, 210)

    # > 600 cm water (diep)
    m = (~nan_masker) & (eff >= 600)
    rgba[m] = (15, 50, 130, 220)

    # NaN = volledig transparant (WMS achtergrond schijnt door)
    rgba[nan_masker] = (0, 0, 0, 0)

    return rgba


# Achterwaartse compatibiliteit voor export-code die nog RGB verwacht
def maak_dieptekaart_array(lons, lats, diepte_lat_cm_grid, lat_offset_cm=-175,
                            getij_cm=0, breedte=800, hoogte=400):
    rgba = maak_dieptekaart_rgba(lons, lats, diepte_lat_cm_grid,
                                  lat_offset_cm=lat_offset_cm,
                                  getij_cm=getij_cm,
                                  breedte=breedte, hoogte=hoogte)
    return rgba[:, :, :3]
