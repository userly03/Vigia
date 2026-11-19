'use client';

// Globo 3D del Vigía (MapLibre GL, proyección de globo).
// Capas, de abajo arriba: zonas escuchadas · cables (resplandor + núcleo + pulsos de datos) · amarres · buques · alertas.

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { BuqueFeature, BuqueProps, CablesGeoJSON, Zona } from '@/lib/cables';
import { COLOR_ESTADO, COLOR_NIVEL, TONOS_CABLE, proyectar, type PruebaDeriva } from '@/lib/cables';

export interface GlobeHandle {
  flyTo(lng: number, lat: number, zoom?: number): void;
}

/** `n` = buques reales vistos en la zona; `sim` = buques simulados (rotulados aparte). */
export type ZonaConteo = Zona & { n: number; sim: number };

interface Props {
  /** Avisa si la vista 3D se interrumpió (p. ej. el navegador perdió el contexto gráfico) y cuando se recupera (null). */
  onProblema?: (mensaje: string | null) => void;
  cables: CablesGeoJSON | null;
  amarres: GeoJSON.FeatureCollection | null;
  buques: BuqueFeature[];
  zonas: ZonaConteo[];
  /** Cables con al menos un buque en alerta ALTO/MEDIO: se dibujan en rojo y parpadean. */
  cablesEnAlerta: string[];
  cableSeleccionado: string | null;
  /** Vectores de la prueba de deriva pasiva del buque seleccionado (lo observado y lo que haría el agua). */
  prueba: { lng: number; lat: number; datos: PruebaDeriva } | null;
  /** Replay: posición y rastro de los buques con atención en el instante elegido (null = apagado). */
  replay: GeoJSON.FeatureCollection | null;
  onBuque(p: BuqueProps & { lng: number; lat: number }): void;
  onCable(c: { slug: string; nombre: string; longitud_km: number | null }): void;
  onVacio(): void;
}

const ESRI_OSCURO = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}';
const VACIO: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };

const ESTILO: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    base: {
      type: 'raster', tiles: [ESRI_OSCURO], tileSize: 256, maxzoom: 16,
      attribution: 'Mapa © Esri',
    },
  },
  layers: [
    { id: 'fondo', type: 'background', paint: { 'background-color': '#020611' } },
    { id: 'base', type: 'raster', source: 'base', paint: { 'raster-opacity': 0.8, 'raster-brightness-max': 0.7, 'raster-saturation': -0.4 } },
  ],
};

// Secuencia que desplaza un guion a lo largo de la línea: da la sensación de paquetes de datos viajando por el cable.
const GUIONES: number[][] = [
  [0, 4, 3], [0.5, 4, 2.5], [1, 4, 2], [1.5, 4, 1.5], [2, 4, 1], [2.5, 4, 0.5], [3, 4, 0],
  [0, 0.5, 3, 3.5], [0, 1, 3, 3], [0, 1.5, 3, 2.5], [0, 2, 3, 2], [0, 2.5, 3, 1.5], [0, 3, 3, 1], [0, 3.5, 3, 0.5],
];

function flecha(color: string): ImageData {
  const s = 40;
  const c = document.createElement('canvas');
  c.width = c.height = s;
  const g = c.getContext('2d')!;
  g.translate(s / 2, s / 2);
  g.beginPath();
  g.moveTo(0, -14); g.lineTo(9, 11); g.lineTo(0, 6); g.lineTo(-9, 11); g.closePath();
  g.lineWidth = 2.5;
  g.strokeStyle = 'rgba(2,6,17,0.95)';
  g.stroke();
  g.fillStyle = color;
  g.fill();
  return g.getImageData(0, 0, s, s);
}

const porTono = (campo: string): maplibregl.ExpressionSpecification =>
  ['match', ['get', campo], 0, TONOS_CABLE[0], 1, TONOS_CABLE[1], 2, TONOS_CABLE[2], 3, TONOS_CABLE[3], 4, TONOS_CABLE[4], 5, TONOS_CABLE[5], TONOS_CABLE[0]];

const porNivel: maplibregl.ExpressionSpecification =
  ['match', ['get', 'alerta'], 'ALTO', COLOR_NIVEL.ALTO, 'MEDIO', COLOR_NIVEL.MEDIO, COLOR_NIVEL.BAJO];

const esAlerta: maplibregl.ExpressionSpecification = ['match', ['get', 'alerta'], ['ALTO', 'MEDIO'], true, false];

const ancho = (k: number): maplibregl.ExpressionSpecification =>
  ['interpolate', ['linear'], ['zoom'], 0, 0.5 * k, 4, 1.1 * k, 8, 2 * k, 12, 3.2 * k];

function cajaARecta(z: Zona): GeoJSON.Feature<GeoJSON.LineString> {
  const [[a, b], [c, d]] = z.caja;
  return {
    type: 'Feature', properties: { nombre: z.nombre, cubierta: false },
    geometry: { type: 'LineString', coordinates: [[b, a], [d, a], [d, c], [b, c], [b, a]] },
  };
}

const GlobeMap = forwardRef<GlobeHandle, Props>(function GlobeMap(props, ref) {
  const contenedor = useRef<HTMLDivElement>(null);
  const mapaRef = useRef<maplibregl.Map | null>(null);
  const propsRef = useRef(props);
  propsRef.current = props;
  const ultimaInteraccion = useRef(0);
  const etiquetas = useRef<maplibregl.Marker[]>([]);
  const [listo, setListo] = useState(false);

  useImperativeHandle(ref, () => ({
    flyTo(lng, lat, zoom = 5) {
      ultimaInteraccion.current = performance.now();
      mapaRef.current?.flyTo({ center: [lng, lat], zoom, pitch: zoom > 4 ? 40 : 0, speed: 0.9, essential: true });
    },
  }), []);

  // ── creación del mapa (una sola vez) ────────────────────────────────────────
  useEffect(() => {
    if (!contenedor.current || mapaRef.current) return;
    const map = new maplibregl.Map({
      container: contenedor.current, style: ESTILO, center: [8, 33], zoom: 2.05, minZoom: 0.8, maxZoom: 13,
      attributionControl: false, dragRotate: true, pitchWithRotate: true,
    });
    mapaRef.current = map;
    map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: 'Cables © TeleGeography' }), 'bottom-right');
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
    map.addControl(new maplibregl.GlobeControl(), 'top-right');

    // Si el navegador pierde el contexto gráfico (muchas pestañas, poca memoria de vídeo), el mapa se ve vacío: se avisa y, al
    // recuperarse, se vuelven a enviar los datos (el aviso «listo» se reinicia para que los efectos de datos corran de nuevo).
    // OJO: al destruir un mapa, MapLibre pierde el contexto A PROPÓSITO; eso no es una avería (por eso `destruido`).
    let destruido = false;
    const lienzo = map.getCanvas();
    lienzo.addEventListener('webglcontextlost', (e) => {
      if (destruido) return;
      e.preventDefault(); setListo(false);
      propsRef.current.onProblema?.('La vista 3D se interrumpió (el navegador perdió el contexto gráfico). Intentando recuperarla…');
    });
    lienzo.addEventListener('webglcontextrestored', () => {
      if (destruido) return;
      propsRef.current.onProblema?.(null); setListo(true);
    });

    const tocar = () => { ultimaInteraccion.current = performance.now(); };
    (['mousedown', 'touchstart', 'wheel'] as const).forEach((ev) => map.on(ev, tocar));

    let raf = 0;

    map.on('load', () => {
      map.setProjection({ type: 'globe' });
      map.setSky({
        'sky-color': '#01030a', 'horizon-color': '#0b3a8c', 'fog-color': '#0a1c46',
        'sky-horizon-blend': 0.55, 'horizon-fog-blend': 0.8, 'fog-ground-blend': 0.9,
        'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1, 5, 1, 8, 0],
      });

      (['transito', 'lento', 'parado', 'atracado'] as const).forEach((e) =>
        map.addImage(`flecha-${e}`, flecha(COLOR_ESTADO[e]), { pixelRatio: 2 }));

      (['cables', 'amarres', 'buques', 'zonas', 'prueba', 'replay'] as const).forEach((s) => map.addSource(s, { type: 'geojson', data: VACIO }));

      map.addLayer({
        id: 'zonas-linea', type: 'line', source: 'zonas',
        paint: { 'line-color': ['case', ['get', 'cubierta'], '#38bdf8', '#ef4444'], 'line-width': 1, 'line-opacity': 0.45, 'line-dasharray': [2, 3] },
      });
      map.addLayer({ id: 'cables-brillo2', type: 'line', source: 'cables', layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': porTono('tono'), 'line-width': ancho(7), 'line-blur': 8, 'line-opacity': 0.12 } });
      map.addLayer({ id: 'cables-brillo', type: 'line', source: 'cables', layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': porTono('tono'), 'line-width': ancho(3.2), 'line-blur': 3, 'line-opacity': 0.3 } });
      map.addLayer({ id: 'cables-nucleo', type: 'line', source: 'cables', layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': porTono('tono'), 'line-width': ancho(1), 'line-opacity': 0.95 } });
      map.addLayer({ id: 'cables-pulso', type: 'line', source: 'cables',
        paint: { 'line-color': '#ffffff', 'line-width': ancho(1.1), 'line-opacity': 0.8, 'line-dasharray': GUIONES[0] } });
      map.addLayer({ id: 'cables-alerta-brillo', type: 'line', source: 'cables', filter: ['==', ['get', 'slug'], ''],
        paint: { 'line-color': COLOR_NIVEL.ALTO, 'line-width': ancho(7), 'line-blur': 6, 'line-opacity': 0.5 } });
      map.addLayer({ id: 'cables-alerta', type: 'line', source: 'cables', filter: ['==', ['get', 'slug'], ''],
        paint: { 'line-color': '#ff7a8a', 'line-width': ancho(1.8), 'line-opacity': 1 } });
      map.addLayer({ id: 'cables-sel', type: 'line', source: 'cables', filter: ['==', ['get', 'slug'], ''],
        paint: { 'line-color': '#ffffff', 'line-width': ancho(2.4), 'line-opacity': 0.95 } });

      map.addLayer({ id: 'amarres', type: 'circle', source: 'amarres', minzoom: 2,
        paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 2, 1.2, 8, 3.5], 'circle-color': '#a5f3fc', 'circle-opacity': 0.75,
          'circle-stroke-width': 0.6, 'circle-stroke-color': '#020611' } });

      map.addLayer({ id: 'buques-halo', type: 'circle', source: 'buques', filter: esAlerta,
        paint: { 'circle-radius': 6, 'circle-color': porNivel, 'circle-opacity': 0.3, 'circle-blur': 0.9 } });
      map.addLayer({ id: 'buques-circulos', type: 'circle', source: 'buques', maxzoom: 5,
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 0, 2, 3, 3.2, 5, 4.6],
          'circle-stroke-width': 0.8, 'circle-stroke-color': '#020611',
          'circle-color': ['match', ['get', 'estado'], 'transito', COLOR_ESTADO.transito, 'lento', COLOR_ESTADO.lento, 'parado', COLOR_ESTADO.parado, COLOR_ESTADO.atracado],
          'circle-opacity': ['case', ['get', 'simulado'], 0.65, 0.95],
        } });
      map.addLayer({ id: 'buques-flechas', type: 'symbol', source: 'buques', minzoom: 5,
        layout: {
          'icon-image': ['match', ['get', 'estado'], 'transito', 'flecha-transito', 'lento', 'flecha-lento', 'parado', 'flecha-parado', 'flecha-atracado'],
          'icon-rotate': ['coalesce', ['get', 'cog'], 0],
          // OJO: con alineación 'map' y rumbo variable, la proyección de globo NO dibuja las flechas (medido: 0 de 3 811). Se usa 'viewport'
          // y se resta el giro del mapa (evento 'rotate') para que apunten hacia donde navega el barco aunque se gire la vista.
          'icon-rotation-alignment': 'viewport',
          'icon-size': ['interpolate', ['linear'], ['zoom'], 5, 0.85, 12, 1.5], 'icon-allow-overlap': true, 'icon-ignore-placement': true,
        }, paint: { 'icon-opacity': ['case', ['get', 'simulado'], 0.7, 1] } });
      const ajustarRumbo = () => map.setLayoutProperty('buques-flechas', 'icon-rotate', ['-', ['coalesce', ['get', 'cog'], 0], map.getBearing()]);
      map.on('rotate', ajustarRumbo);
      map.addLayer({ id: 'buques-anillo', type: 'circle', source: 'buques', filter: esAlerta,
        paint: { 'circle-radius': 6, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': porNivel, 'circle-stroke-width': 1.6, 'circle-stroke-opacity': 0.9 } });

      map.addLayer({ id: 'prueba-pista', type: 'line', source: 'prueba', filter: ['==', ['get', 'tipo'], 'pista'],
        paint: { 'line-color': '#f8fafc', 'line-width': 1.4, 'line-opacity': 0.55 } });
      map.addLayer({ id: 'prueba-pista-pt', type: 'circle', source: 'prueba', filter: ['==', ['get', 'tipo'], 'pista-pt'],
        paint: { 'circle-radius': 2.2, 'circle-color': '#f8fafc', 'circle-opacity': 0.9 } });
      map.addLayer({ id: 'prueba-esp', type: 'line', source: 'prueba', filter: ['==', ['get', 'tipo'], 'esp'],
        paint: { 'line-color': '#22d3ee', 'line-width': 2.2, 'line-dasharray': [2, 1.5], 'line-opacity': 0.95 } });
      map.addLayer({ id: 'prueba-obs', type: 'line', source: 'prueba', filter: ['==', ['get', 'tipo'], 'obs'],
        paint: { 'line-color': '#ffffff', 'line-width': 2.6, 'line-opacity': 1 } });
      map.addLayer({ id: 'prueba-puntas', type: 'circle', source: 'prueba', filter: ['all', ['==', ['geometry-type'], 'Point'], ['in', ['get', 'tipo'], ['literal', ['obs', 'esp']]]],
        paint: { 'circle-radius': 4, 'circle-color': ['match', ['get', 'tipo'], 'esp', '#22d3ee', '#ffffff'], 'circle-stroke-width': 1.5, 'circle-stroke-color': '#020611' } });

      // replay: rastro y posición de los buques con atención en el instante elegido
      const colorReplay = ['match', ['get', 'nivel'], 'ALTO', '#ff3b5c', 'MEDIO', '#ffb020', 'BAJO', '#7dd3fc', '#38bdf8'] as unknown as maplibregl.ExpressionSpecification;
      map.addLayer({ id: 'replay-rastro', type: 'line', source: 'replay', filter: ['==', ['get', 'tipo'], 'rastro'],
        layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': colorReplay, 'line-width': 2, 'line-opacity': 0.8 } });
      map.addLayer({ id: 'replay-pos', type: 'circle', source: 'replay', filter: ['==', ['get', 'tipo'], 'pos'],
        paint: { 'circle-radius': 5.5, 'circle-color': colorReplay, 'circle-stroke-width': 1.8, 'circle-stroke-color': '#ffffff' } });

      // interacción
      const capasBuque = ['buques-circulos', 'buques-flechas', 'buques-halo'];
      [...capasBuque, 'cables-nucleo'].forEach((id) => {
        map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
        map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
      });
      map.on('click', (e) => {
        ultimaInteraccion.current = performance.now();
        const b = map.queryRenderedFeatures(e.point, { layers: capasBuque })[0];
        if (b) {
          const [lng, lat] = (b.geometry as GeoJSON.Point).coordinates;
          const props = { ...(b.properties as Record<string, unknown>) };
          // MapLibre aplana los objetos anidados a texto JSON: se vuelve a leer
          if (typeof props.prueba === 'string') { try { props.prueba = JSON.parse(props.prueba); } catch { delete props.prueba; } }
          propsRef.current.onBuque({ ...(props as unknown as BuqueProps), lng, lat });
          return;
        }
        const r = 7;
        const c = map.queryRenderedFeatures([[e.point.x - r, e.point.y - r], [e.point.x + r, e.point.y + r]], { layers: ['cables-nucleo'] })[0];
        if (c) {
          const p = c.properties as { slug: string; nombre: string; longitud_km: number | null };
          propsRef.current.onCable({ slug: p.slug, nombre: p.nombre, longitud_km: p.longitud_km ?? null });
          return;
        }
        propsRef.current.onVacio();
      });

      // animación: rotación lenta, pulsos de datos, anillos de alerta
      let previo = performance.now();
      let ultGuion = 0;
      let ultAnillo = 0;
      const tick = (t: number) => {
        raf = requestAnimationFrame(tick);
        const dt = Math.min(0.1, (t - previo) / 1000);
        previo = t;
        if (document.hidden) return;
        if (t - ultimaInteraccion.current > 12_000 && map.getZoom() < 2.6 && !map.isMoving()) {
          const c = map.getCenter();
          map.jumpTo({ center: [c.lng + 2.2 * dt, c.lat] });
        }
        if (t - ultGuion > 90) {
          ultGuion = t;
          map.setPaintProperty('cables-pulso', 'line-dasharray', GUIONES[Math.floor(t / 90) % GUIONES.length]);
        }
        if (t - ultAnillo > 50) {
          ultAnillo = t;
          const fase = (t % 1700) / 1700;
          // los radios escalan con el zoom: a escala global un anillo de 20 px taparía regiones enteras
          map.setPaintProperty('buques-anillo', 'circle-radius', ['interpolate', ['linear'], ['zoom'], 0, 2 + fase * 4, 4, 4 + fase * 9, 8, 7 + fase * 18]);
          map.setPaintProperty('buques-anillo', 'circle-stroke-opacity', 0.95 * (1 - fase));
          const respira = 0.5 + 0.5 * Math.sin(t / 380);
          map.setPaintProperty('buques-halo', 'circle-radius', ['interpolate', ['linear'], ['zoom'], 0, 2.5 + respira, 4, 6 + respira * 2, 8, 11 + respira * 3]);
          map.setPaintProperty('cables-alerta-brillo', 'line-opacity', 0.35 + 0.3 * (0.5 + 0.5 * Math.sin(t / 300)));
        }
      };
      raf = requestAnimationFrame(tick);
      setListo(true);
    });

    return () => {
      destruido = true;
      cancelAnimationFrame(raf);
      etiquetas.current.forEach((m) => m.remove());
      mapaRef.current = null;
      map.remove();
      setListo(false);      // un mapa nuevo (recarga en caliente, doble montaje) debe volver a recibir todos los datos
    };
  }, []);

  // ── datos ───────────────────────────────────────────────────────────────────
  const fuente = (id: string) => mapaRef.current?.getSource(id) as maplibregl.GeoJSONSource | undefined;

  useEffect(() => { if (listo && props.cables) fuente('cables')?.setData(props.cables); }, [listo, props.cables]);
  useEffect(() => { if (listo && props.amarres) fuente('amarres')?.setData(props.amarres); }, [listo, props.amarres]);
  useEffect(() => {
    if (listo) fuente('buques')?.setData({ type: 'FeatureCollection', features: props.buques });
  }, [listo, props.buques]);

  useEffect(() => {
    const m = mapaRef.current;
    if (!listo || !m) return;
    const f: maplibregl.FilterSpecification = ['in', ['get', 'slug'], ['literal', props.cablesEnAlerta.length ? props.cablesEnAlerta : ['']]];
    m.setFilter('cables-alerta', f);
    m.setFilter('cables-alerta-brillo', f);
  }, [listo, props.cablesEnAlerta]);

  useEffect(() => {
    const m = mapaRef.current;
    if (!listo || !m) return;
    m.setFilter('cables-sel', ['==', ['get', 'slug'], props.cableSeleccionado ?? '']);
  }, [listo, props.cableSeleccionado]);

  // replay: el instante elegido por el control (o apagado)
  useEffect(() => {
    if (!listo) return;
    fuente('replay')?.setData(props.replay ?? VACIO);
  }, [listo, props.replay]);

  // prueba de deriva pasiva: lo observado (blanco) y lo que haría el agua (cian punteado), proyectados 3 h
  useEffect(() => {
    if (!listo) return;
    const pr = props.prueba;
    if (!pr) { fuente('prueba')?.setData(VACIO); return; }
    const { lng, lat, datos: d } = pr;
    const o = proyectar(lng, lat, d.obs_ve, d.obs_vn, 3);
    const e = proyectar(lng, lat, d.esp_ve, d.esp_vn, 3);
    fuente('prueba')?.setData({
      type: 'FeatureCollection',
      features: [
        { type: 'Feature', properties: { tipo: 'esp' }, geometry: { type: 'LineString', coordinates: [[lng, lat], e] } },
        { type: 'Feature', properties: { tipo: 'obs' }, geometry: { type: 'LineString', coordinates: [[lng, lat], o] } },
        ...(d.pista.length > 1 ? [{ type: 'Feature' as const, properties: { tipo: 'pista' }, geometry: { type: 'LineString' as const, coordinates: d.pista } }] : []),
        ...d.pista.map((c) => ({ type: 'Feature' as const, properties: { tipo: 'pista-pt' }, geometry: { type: 'Point' as const, coordinates: c } })),
        { type: 'Feature', properties: { tipo: 'esp' }, geometry: { type: 'Point', coordinates: e } },
        { type: 'Feature', properties: { tipo: 'obs' }, geometry: { type: 'Point', coordinates: o } },
      ],
    });
  }, [listo, props.prueba]);

  // zonas: rectángulos coloreados según haya o no señal + etiquetas con el recuento
  useEffect(() => {
    const m = mapaRef.current;
    if (!listo || !m) return;
    fuente('zonas')?.setData({
      type: 'FeatureCollection',
      features: props.zonas.map((z) => ({ ...cajaARecta(z), properties: { nombre: z.nombre, cubierta: z.n > 0 } })),
    });
    etiquetas.current.forEach((mk) => mk.remove());
    etiquetas.current = props.zonas.map((z) => {
      const [[a, b], [c, d]] = z.caja;
      const real = z.n > 0;
      const sim = !real && z.sim > 0;
      const color = real ? '#bae6fd' : sim ? '#d8b4fe' : '#fca5a5';
      const borde = real ? 'rgba(56,189,248,.35)' : sim ? 'rgba(192,132,252,.45)' : 'rgba(239,68,68,.45)';
      const el = document.createElement('div');
      el.style.cssText = `font:600 10px/1.2 ui-sans-serif,system-ui;letter-spacing:.08em;text-transform:uppercase;white-space:nowrap;padding:2px 6px;border-radius:4px;`
        + `pointer-events:none;color:${color};background:rgba(2,6,17,.7);border:1px solid ${borde};`;
      el.textContent = real ? `${z.nombre} · ${z.n}` : sim ? `${z.nombre} · simulado ${z.sim}` : `${z.nombre} · sin señal`;
      return new maplibregl.Marker({ element: el, anchor: 'bottom' }).setLngLat([(b + d) / 2, Math.max(a, c)]).addTo(m);
    });
  }, [listo, props.zonas]);

  return <div ref={contenedor} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} aria-label="Globo con cables submarinos y buques" />;
});

export default GlobeMap;
