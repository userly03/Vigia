#!/usr/bin/env python3
"""
Maury-valida: ¿cuánto se equivoca un modelo de corrientes frente a boyas a la deriva REALES?

Mide el error vectorial de la corriente superficial de los reanálisis de Copernicus Marine contra las boyas del Global
Drifter Program (NOAA, CC BY 4.0, medidas horarias) en el Mar del Norte y el Báltico/Kattegat, y lo compara con la
tolerancia que el Vigía ASUME (0,4 kn). Es lo que convierte esa suposición en un número medido.

    pip install -r scripts/requirements-maury.txt        # y: copernicusmarine login   (lo hace la persona, no el script)
    python3 scripts/maury_valida.py --trabajo /tmp/maury --salida backend/mares/apps/cables/validacion_datos/maury_valida.json

LÍMITES, que el resultado repite:
  - Se valida el MODELO de Copernicus, no el de Open-Meteo (no se puede consultar su histórico de 1993-2019).
  - Las boyas con ancla flotante («drogue») miden ~15 m de profundidad; el modelo se toma en superficie (y a ~15 m en
    el Báltico). Las que perdieron el ancla miden la superficie MÁS el arrastre del viento; no se separa aquí.
  - Mar del Norte: modelo horario (incluye mareas) contra boya horaria; además, la boya promediada en 3 h contra el modelo
    en un instante («actual») y contra el modelo promediado en esas 3 h («ventana»). Báltico: medias diarias (≥ 12 h).
  - Pocas boyas (decenas) y concentradas en unos pocos años: el resultado es indicativo, no definitivo.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

ERDDAP = ('https://data.pmel.noaa.gov/generic/erddap/tabledap/gdp_hourly_velocities.csv'
          '?ID,time,latitude,longitude,ve,vn,drogue_lost_date,typebuoy&longitude>={lo0}&longitude<={lo1}&latitude>={la0}&latitude<={la1}&time>=1993-01-01')
GLOBAL_DIARIO = 'cmems_mod_glo_phy_my_0.083deg_P1D-m'
TOL_KN = 0.4                      # la tolerancia base que asume Vigía (deriva.py: TOL_BASE_KN)
KN = 1.0 / 0.514444               # m/s → nudos
REGIONES = {
    # nombre: (caja lat/lon, dataset, variables, ¿horario?, ¿con profundidad?)
    'MarNorte': ((51, 61, -4, 9), 'cmems_mod_nws_phy-uv_my_7km-2D_PT1H-i', ('uo', 'vo'), True, False),
    'Baltico': ((53, 66, 9, 31), 'cmems_mod_bal_phy_my_P1D-m', ('uo', 'vo'), False, True),
    # Resto del mundo: reanálisis global de 1/12° con medias diarias (sin mareas) contra la media diaria de la boya.
    'Mediterraneo': ((30, 46, -6, 36), GLOBAL_DIARIO, ('uo', 'vo'), False, True),
    # Mismas boyas que 'Mediterraneo' pero con el reanálisis REGIONAL de 4,2 km: ¿mejora al modelo global de 1/12°?
    'Mediterraneo_regional': ((30, 46, -6, 36), 'cmems_mod_med_phy-cur_my_4.2km_P1D-m', ('uo', 'vo'), False, True),
    'MarRojo_Golfo': ((12, 30, 32, 60), GLOBAL_DIARIO, ('uo', 'vo'), False, True),
    'Peru': ((-20, 0, -85, -70), GLOBAL_DIARIO, ('uo', 'vo'), False, True),
    'Taiwan': ((20, 28, 117, 125), GLOBAL_DIARIO, ('uo', 'vo'), False, True),
}
POR_DEFECTO = 'MarNorte,Baltico'
MARGEN = 0.3


def bajar_boyas(trabajo: Path, region: str) -> pd.DataFrame:
    """Boyas con datos dentro de la caja de la región (se guarda en caché por región)."""
    ruta = trabajo / f'gdp_{region.removesuffix("_regional")}.csv'      # el modelo regional usa las mismas boyas
    if not ruta.exists():
        la0, la1, lo0, lo1 = REGIONES[region][0]
        print(f'Descargando boyas de NOAA (ERDDAP) para {region}…')
        with urllib.request.urlopen(ERDDAP.format(la0=la0, la1=la1, lo0=lo0, lo1=lo1), timeout=280) as r, open(ruta, 'wb') as f:
            f.write(r.read())
    d = pd.read_csv(ruta, skiprows=[1], parse_dates=['time', 'drogue_lost_date'])
    d = d.dropna(subset=['ve', 'vn'])
    perdida = d.drogue_lost_date.fillna(pd.Timestamp('2100-01-01', tz='UTC'))
    d['con_ancla'] = d.time < perdida
    return d


def modelo_para(boya: pd.DataFrame, region: str, trabajo: Path):
    """
    Descarga el modelo en la caja y fechas de UNA boya (en esa región) y devuelve (ruta, None), o (None, motivo).
    Se reutiliza un archivo ya descargado. NO abre el archivo: netCDF4/HDF5 no es seguro entre hilos; se abre en el principal.
    """
    import copernicusmarine as cm
    (_, dataset, variables, _horario, con_prof) = (None, *REGIONES[region][1:])
    t0, t1 = boya.time.min(), boya.time.max()
    nombre = f'{region}_{int(boya.ID.iloc[0])}.nc'
    destino = trabajo / 'modelo' / nombre
    if destino.exists() and destino.stat().st_size > 0:
        return destino, None
    kw = dict(dataset_id=dataset, variables=list(variables), output_directory=str(trabajo / 'modelo'), output_filename=nombre,
              minimum_longitude=float(boya.longitude.min() - MARGEN), maximum_longitude=float(boya.longitude.max() + MARGEN),
              minimum_latitude=float(boya.latitude.min() - MARGEN), maximum_latitude=float(boya.latitude.max() + MARGEN),
              start_datetime=t0.tz_convert(None).isoformat(), end_datetime=(t1.tz_convert(None) + pd.Timedelta(days=1)).isoformat(),
              overwrite=True, disable_progress_bar=True)
    if con_prof:
        kw.update(minimum_depth=0.0, maximum_depth=16.0)
    try:
        cm.subset(**kw)
    except Exception as exc:                                    # noqa: BLE001 — se cuenta y se informa, no se oculta
        return None, f'{type(exc).__name__}: {str(exc)[:80]}'
    return destino, None


def _modelo_en(ds: xr.Dataset, t, la: float, lo: float, z, tol: pd.Timedelta):
    """(uo, vo) del modelo en un instante y punto, o None si no hay dato."""
    try:
        s = ds.sel(time=t, method='nearest', tolerance=tol)
        if z is not None:
            s = s.sel(depth=z, method='nearest')
        s = s.interp(latitude=la, longitude=lo)
        uo, vo = float(s.uo), float(s.vo)
    except (KeyError, ValueError):
        return None
    return None if math.isnan(uo) or math.isnan(vo) else (uo, vo)


def errores(boya: pd.DataFrame, ds: xr.Dataset, region: str) -> list[dict]:
    """
    Error vectorial (m/s) entre boya y modelo. Modos:
      · 'dia'      (Báltico) media diaria de la boya contra la media diaria del modelo.
      · 'hora'     (Mar del Norte) boya horaria contra modelo del mismo instante.
      · 'actual'   boya promediada 3 h (como la velocidad que ajustamos a un buque) contra el modelo en UN instante
                   —lo que hace hoy Vigía—.
      · 'ventana'  la misma boya de 3 h contra el modelo PROMEDIADO en esas 3 h —la mejora propuesta—.
    """
    horario, con_prof = REGIONES[region][3], REGIONES[region][4]
    out: list[dict] = []
    b = boya.sort_values('time').copy()
    ident = int(boya.ID.iloc[0])

    def fila(modo, prof, anc, uo, vo, r):
        out.append({'region': region, 'modo': modo, 'prof': prof, 'con_ancla': bool(anc), 'id': ident,
                    'err': math.hypot(uo - r['ve'], vo - r['vn']), 'vel_boya': math.hypot(r['ve'], r['vn']),
                    'err_u': uo - r['ve'], 'err_v': vo - r['vn']})

    if not horario:
        b['dia'] = b.time.dt.floor('D').dt.tz_convert(None) + pd.Timedelta(hours=12)
        g = b.groupby(['dia', 'con_ancla']).agg(ve=('ve', 'mean'), vn=('vn', 'mean'), latitude=('latitude', 'mean'),
                                                longitude=('longitude', 'mean'), n=('ve', 'size')).reset_index()
        g = g[g.n >= 12]
        for prof_nombre, z in (('superficie', 0.5), ('15 m', 15.0)):
            for _, r in g.iterrows():
                m = _modelo_en(ds, r.dia, r.latitude, r.longitude, z, pd.Timedelta(hours=13))
                if m:
                    fila('dia', prof_nombre, r.con_ancla, m[0], m[1], r)
        return out

    b['t'] = b.time.dt.tz_convert(None)
    h = pd.Timedelta(hours=1)
    # ventana centrada de 3 h con pasos horarios completos (sin huecos)
    b = b.set_index('t')
    b3 = b[['ve', 'vn']].rolling('3h', center=True, min_periods=3).mean()
    b3['latitude'], b3['longitude'], b3['con_ancla'] = b['latitude'], b['longitude'], b['con_ancla']
    for t, r in b.iterrows():
        m = _modelo_en(ds, t, r.latitude, r.longitude, None, h)
        if m:
            fila('hora', 'superficie', r.con_ancla, m[0], m[1], r)
    for t, r in b3.dropna(subset=['ve']).iloc[::3].iterrows():           # una de cada 3 h: ventanas casi independientes
        puntos = [_modelo_en(ds, t + k * h, r.latitude, r.longitude, None, h) for k in (-1, 0, 1)]
        if None in puntos:
            continue
        fila('actual', 'superficie', r.con_ancla, puntos[1][0], puntos[1][1], r)
        fila('ventana', 'superficie', r.con_ancla, sum(p[0] for p in puntos) / 3, sum(p[1] for p in puntos) / 3, r)
    return out


def resumen(filas: pd.DataFrame) -> dict:
    e, v = filas.err * KN, filas.vel_boya * KN
    return {
        'n_puntos': int(len(filas)), 'n_boyas': int(filas.id.nunique()),
        'error_mediano_kn': round(float(e.median()), 3), 'error_p90_kn': round(float(e.quantile(0.9)), 3),
        'rmse_kn': round(float(math.sqrt((e ** 2).mean())), 3),
        'sesgo_este_kn': round(float(filas.err_u.mean() * KN), 3), 'sesgo_norte_kn': round(float(filas.err_v.mean() * KN), 3),
        'dentro_de_tolerancia_pct': round(float((e <= TOL_KN).mean() * 100), 1),
        'rapidez_mediana_boya_kn': round(float(v.median()), 3),
        'error_si_modelo_fuera_cero_kn': round(float(v.median()), 3),   # lo que se erraría diciendo «no hay corriente»
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--trabajo', default='/tmp/maury')
    ap.add_argument('--salida', default='backend/mares/apps/cables/validacion_datos/maury_valida.json')
    ap.add_argument('--max-boyas', type=int, default=0, help='0 = todas (para pruebas rápidas)')
    ap.add_argument('--hilos', type=int, default=4)
    ap.add_argument('--regiones', default=POR_DEFECTO, help=f"lista separada por comas o 'todas'; disponibles: {', '.join(REGIONES)}")
    ap.add_argument('--por-region', type=int, default=12, help='boyas por región (las de más datos); 0 = todas (muy lento)')
    ap.add_argument('--dias', type=int, default=40, help='máximo de días por boya (los primeros en la región)')
    a = ap.parse_args()
    trabajo = Path(a.trabajo)
    (trabajo / 'modelo').mkdir(parents=True, exist_ok=True)

    nombres = list(REGIONES) if a.regiones == 'todas' else a.regiones.split(',')
    partes = []
    for nombre in nombres:
        x = bajar_boyas(trabajo, nombre)
        x['region'] = nombre
        partes.append(x)
    d = pd.concat(partes, ignore_index=True)
    trabajos = []
    for reg in nombres:
        gs = sorted(((r, g) for (r, _i), g in d.groupby(['region', 'ID']) if r == reg), key=lambda x: -len(x[1]))
        for r, g in (gs[:a.por_region] if a.por_region else gs):
            g = g.sort_values('time')
            trabajos.append((r, g[g.time < g.time.iloc[0] + pd.Timedelta(days=a.dias)]))   # se acota para no pedir meses de modelo
    if a.max_boyas:
        trabajos = trabajos[:a.max_boyas]
    print(f'{len(trabajos)} boyas-región a comparar ({d.ID.nunique()} boyas, {len(d)} datos horarios)')

    filas: list[dict] = []
    fallos: dict[str, int] = {}

    def una(args):
        region, g = args
        ruta, motivo = modelo_para(g, region, trabajo)
        return (region, g, ruta, motivo)

    with ThreadPoolExecutor(max_workers=a.hilos) as ex:
        for k, (region, g, ruta, motivo) in enumerate(ex.map(una, trabajos), 1):
            if ruta is None:
                fallos[motivo] = fallos.get(motivo, 0) + 1
            else:
                with xr.open_dataset(ruta) as ds:
                    ds.load()
                    filas += errores(g, ds, region)
            if k % 10 == 0:
                print(f'  {k}/{len(trabajos)} · {len(filas)} comparaciones · {sum(fallos.values())} fallos')

    df = pd.DataFrame(filas)
    res: dict = {}
    if len(df):
        for (reg, modo, prof, anc), g in df.groupby(['region', 'modo', 'prof', 'con_ancla']):
            res[f"{reg} · {modo} · modelo a {prof} · boya {'con ancla (~15 m)' if anc else 'sin ancla (sup.+viento)'}"] = resumen(g)
    salida = {
        'generado': datetime.now(timezone.utc).isoformat(), 'tolerancia_asumida_kn': TOL_KN,
        'resultados': res, 'boyas_sin_modelo': fallos,
        'fuentes': ['Boyas: Global Drifter Program hourly, NOAA AOML (CC BY 4.0), doi:10.25921/x46c-3620',
                    'Modelos: Copernicus Marine, ' + ', '.join(v[1] for v in REGIONES.values())],
        'limites': ['Se valida el modelo de Copernicus, no el de Open-Meteo', 'Pocas boyas, pocos años',
                    'Profundidades distintas entre boya con ancla (15 m) y modelo de superficie',
                    'Boyas sin ancla incluyen arrastre del viento, no separado'],
    }
    Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(a.salida).write_text(json.dumps(salida, indent=2, ensure_ascii=False), encoding='utf-8')
    for k, v in res.items():
        print(f"\n{k}\n  {v}")
    print(f'\nGuardado en {a.salida}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
