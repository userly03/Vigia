'use client';

// Vigía: globo + panel de mando. Datos públicos y de solo lectura; el AIS se refresca cada 15 s.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Medido from './Medido';
import { MARCA } from '@/lib/marca';
import { etiquetaTiempo, featuresReplay, type ReplayResponse } from '@/lib/replay';
import GlobeMap, { type GlobeHandle, type ZonaConteo } from './GlobeMap';
import { construirInforme, construirRecibo, descargar, descargarComo } from '@/lib/recibo';
import {
  COLOR_ESTADO, COLOR_NIVEL, ETIQUETA_ESTADO, TEXTO_VEREDICTO, enZona, fetchAmarres, fetchBuques, fetchCables, fetchHistorialCable, fetchReplay, fetchSellos, type HistorialCable, type SellosResponse,
  type BuqueFeature, type BuqueProps, type BuquesResponse, type CablesGeoJSON, type Nivel,
} from '@/lib/cables';

const ORDEN: Record<Nivel, number> = { ALTO: 0, MEDIO: 1, BAJO: 2 };
const PANEL = 'rounded-xl border border-cyan-400/20 bg-[#030a18]/75 backdrop-blur-md shadow-[0_0_30px_-10px_rgba(34,211,238,0.35)]';

function Reloj() {
  const [t, setT] = useState('');
  useEffect(() => {
    const f = () => setT(new Date().toISOString().slice(11, 19));
    f();
    const id = setInterval(f, 1000);
    return () => clearInterval(id);
  }, []);
  return <span className="tabular-nums">{t} UTC</span>;
}

function Cifra({ etiqueta, valor, color, ayuda }: { etiqueta: string; valor: number | string; color?: string; ayuda?: string }) {
  return (
    <div className="px-3 py-2 text-center" title={ayuda}>
      <div className="text-xl font-bold tabular-nums leading-none" style={{ color: color ?? '#e2f6ff' }}>{valor}</div>
      <div className="mt-1 text-[9px] font-semibold uppercase tracking-[0.14em] text-cyan-200/55">{etiqueta}</div>
    </div>
  );
}

export default function Guardian() {
  const mapa = useRef<GlobeHandle>(null);
  const [cables, setCables] = useState<CablesGeoJSON | null>(null);
  const [amarres, setAmarres] = useState<GeoJSON.FeatureCollection | null>(null);
  const [resp, setResp] = useState<BuquesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cablesFallo, setCablesFallo] = useState(false);
  const [problemaGL, setProblemaGL] = useState<string | null>(null);
  const [leyenda, setLeyenda] = useState(false);
  const [invest, setInvest] = useState<{ slug: string; horas: number; datos: HistorialCable | null; cargando: boolean; error: boolean } | null>(null);
  const [selBuque, setSelBuque] = useState<(BuqueProps & { lng: number; lat: number }) | null>(null);
  const [selCable, setSelCable] = useState<{ slug: string; nombre: string; longitud_km: number | null } | null>(null);
  const [metodo, setMetodo] = useState(false);
  const [medido, setMedido] = useState(false);
  // replay de las últimas horas de los buques con atención
  const [replay, setReplay] = useState<ReplayResponse | null>(null);
  const [replayOn, setReplayOn] = useState(false);
  const [replayCarga, setReplayCarga] = useState(false);
  const [replayError, setReplayError] = useState(false);
  const [trans, setTrans] = useState(0);        // minutos transcurridos desde el inicio de la ventana
  const [play, setPlay] = useState(false);
  const totalMin = (replay?.horas ?? 3) * 60;
  const replayFC = useMemo(() => (replayOn && replay ? featuresReplay(replay, totalMin - trans) : null), [replayOn, replay, totalMin, trans]);
  useEffect(() => {
    if (!play) return;
    const id = setInterval(() => setTrans((t) => { const n = t + 2; if (n >= totalMin) { setPlay(false); return totalMin; } return n; }), 200);
    return () => clearInterval(id);
  }, [play, totalMin]);
  const alternarReplay = async () => {
    if (replayOn) { setReplayOn(false); setPlay(false); return; }
    setReplayOn(true); setReplayError(false); setReplayCarga(true);
    try {
      const d = await fetchReplay(3);
      setReplay(d); setTrans(0); setPlay(true);
      // la cámara va adonde están los buques del replay (mediana de sus últimas posiciones)
      const med = (v: number[]) => [...v].sort((a, b) => a - b)[Math.floor(v.length / 2)];
      const fin = d.buques.map((b) => b.pista[b.pista.length - 1]).filter(Boolean);
      if (fin.length) mapa.current?.flyTo(med(fin.map((m) => m[1])), med(fin.map((m) => m[2])), 4);
    } catch { setReplayError(true); } finally { setReplayCarga(false); }
  };
  const [sellos, setSellos] = useState<SellosResponse | null>(null);
  useEffect(() => { if (metodo && !sellos) fetchSellos().then(setSellos).catch(() => undefined); }, [metodo, sellos]);

  useEffect(() => {
    let vivo = true;
    // Los cables se piden con reintentos: antes, si la primera petición fallaba, el error lo borraba la siguiente consulta de barcos
    // que sí salía bien y los cables no volvían a pedirse nunca (se veían barcos sin cables).
    const temporizadores: ReturnType<typeof setTimeout>[] = [];
    const reintentar = <T,>(pedir: () => Promise<T>, ok: (d: T) => void, marcar: (fallo: boolean) => void) => {
      let espera = 2000;
      const intentar = () => pedir().then((d) => { if (vivo) { ok(d); marcar(false); } }).catch(() => {
        if (!vivo) return;
        marcar(true);
        temporizadores.push(setTimeout(intentar, espera));
        espera = Math.min(espera * 2, 30_000);
      });
      intentar();
    };
    reintentar(fetchCables, setCables, setCablesFallo);
    reintentar(fetchAmarres, setAmarres, () => undefined);
    const cargar = () =>
      fetchBuques()
        .then((r) => { if (vivo) { setResp(r); setError(null); } })
        .catch((e) => { if (vivo) setError(`AIS: ${e.message}`); });
    cargar();
    const id = setInterval(cargar, 15_000);
    return () => { vivo = false; clearInterval(id); temporizadores.forEach(clearTimeout); };
  }, []);

  const buques: BuqueFeature[] = useMemo(() => resp?.features ?? [], [resp]);

  const zonas: ZonaConteo[] = useMemo(() => (resp?.meta.zonas ?? []).map((z) => {
    let n = 0; let sim = 0;
    for (const f of buques) {
      const [lng, lat] = f.geometry.coordinates;
      if (enZona(lat, lng, z)) { if (f.properties.simulado) sim++; else n++; }
    }
    return { ...z, n, sim };
  }), [resp, buques]);

  const alertas = useMemo(() => buques
    .filter((f) => f.properties.alerta)
    .sort((a, b) => ORDEN[a.properties.alerta as Nivel] - ORDEN[b.properties.alerta as Nivel]
      || (b.properties.minutos ?? 0) - (a.properties.minutos ?? 0)
      || (a.properties.dist_m ?? 0) - (b.properties.dist_m ?? 0)), [buques]);

  const cablesEnAlerta = useMemo(() => Array.from(new Set(
    alertas.filter((f) => f.properties.alerta !== 'BAJO' && f.properties.cable).map((f) => f.properties.cable as string),
  )), [alertas]);

  const alAtencion = alertas.filter((f) => f.properties.alerta !== 'BAJO');
  const recorridos = (resp?.features ?? []).filter((f) => f.properties.recorrido_km && !f.properties.simulado).sort((a, b) => (b.properties.recorrido_km ?? 0) - (a.properties.recorrido_km ?? 0));
  const maxZona = Math.max(1, ...zonas.map((z) => z.n + z.sim));
  const sim = resp?.meta.simulados ?? 0;
  const reales = (resp?.meta.total ?? 0) - sim;

  const volar = useCallback((lng: number, lat: number, z = 8) => mapa.current?.flyTo(lng, lat, z), []);
  const investigar = async (slug: string, horas: number) => {
    setInvest({ slug, horas, datos: null, cargando: true, error: false });
    try { setInvest({ slug, horas, datos: await fetchHistorialCable(slug, horas), cargando: false, error: false }); }
    catch { setInvest({ slug, horas, datos: null, cargando: false, error: true }); }
  };
  useEffect(() => { setInvest(null); }, [selCable?.slug]);

  return (
    <div className="fixed inset-0 overflow-hidden bg-[#020611] text-slate-200">
      <GlobeMap
        ref={mapa}
        cables={cables} amarres={amarres} buques={buques} zonas={zonas}
        cablesEnAlerta={cablesEnAlerta} cableSeleccionado={selCable?.slug ?? null}
        replay={replayFC}
        onProblema={setProblemaGL}
        prueba={selBuque?.prueba ? { lng: selBuque.lng, lat: selBuque.lat, datos: selBuque.prueba } : null}
        onBuque={(p) => { setSelCable(null); setSelBuque(p); }}
        onCable={(c) => { setSelBuque(null); setSelCable(c); }}
        onVacio={() => { setSelBuque(null); setSelCable(null); }}
      />

      <div className="pointer-events-none absolute inset-0 flex flex-col p-3 sm:p-4">
        {/* ── cabecera ── */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className={`${PANEL} pointer-events-auto px-4 py-3`}>
            <div className="flex items-center gap-2.5">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-70" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-cyan-300" />
              </span>
              <h1 className="text-lg font-black tracking-[0.32em] text-white">{MARCA.nombreMayus}</h1>
            </div>
            <p className="mt-1 text-[11px] text-cyan-100/60">{MARCA.lema} · <Reloj /></p>
          </div>

          <div className={`${PANEL} pointer-events-auto flex divide-x divide-cyan-400/15 sm:mr-12`}>
            <Cifra etiqueta="Buques" valor={resp?.meta.total ?? '—'} ayuda="Barcos con posición reciente que estamos viendo ahora. Los simulados se avisan aparte." />
            <Cifra etiqueta="En corredor" valor={resp?.meta.en_corredor ?? '—'} color="#67e8f9" ayuda="Barcos a menos de 2 km de algún cable submarino (el «corredor» de vigilancia)." />
            <Cifra etiqueta="Atención alta" valor={resp?.meta.alertas.ALTO ?? '—'} color={COLOR_NIVEL.ALTO} ayuda="Barcos lentos o parados sobre un cable desde hace 60 min o más, o que se mueven despacio de un modo que el agua no explica. Es un aviso para mirar, no una acusación." />
            <Cifra etiqueta="Media" valor={resp?.meta.alertas.MEDIO ?? '—'} color={COLOR_NIVEL.MEDIO} ayuda="Barcos lentos o parados sobre un cable desde hace menos de 60 min, o a la deriva, o quietos durante horas." />
            <Cifra etiqueta="Silencios" valor={resp?.silencios.length ?? '—'} color="#c4b5fd" ayuda="Barcos que estaban en un corredor y dejaron de emitir su posición: pudieron apagar el AIS o salir del alcance de los receptores. Es un indicio, no una prueba." />
          </div>
        </div>

        {sim > 0 && (
          <div role="status" className="pointer-events-auto mt-2 w-fit rounded-md border border-fuchsia-400/50 bg-fuchsia-950/70 px-3 py-1.5 text-[11px] font-semibold tracking-wide text-fuchsia-200 backdrop-blur">
            ⚠ TRÁFICO SIMULADO — {sim} buques no son reales (nombres «SIM ·»){reales > 0 ? ` · ${reales} reales en pantalla` : ''}
          </div>
        )}
        {error && (
          <div role="alert" className="pointer-events-auto mt-2 w-fit rounded-md border border-red-400/50 bg-red-950/70 px-3 py-1.5 text-[11px] text-red-200 backdrop-blur">
            Sin conexión con la API ({error}). Se muestra el último dato recibido.
          </div>
        )}
        {cablesFallo && !cables && (
          <div role="alert" className="pointer-events-auto mt-2 w-fit rounded-md border border-amber-400/50 bg-amber-950/70 px-3 py-1.5 text-[11px] text-amber-200 backdrop-blur">
            No se pudieron cargar los cables todavía; reintentando…
          </div>
        )}
        {problemaGL && (
          <div role="alert" className="pointer-events-auto mt-2 w-fit rounded-md border border-amber-400/50 bg-amber-950/70 px-3 py-1.5 text-[11px] text-amber-200 backdrop-blur">
            {problemaGL}
          </div>
        )}

        <div className="mt-3 flex min-h-0 flex-1 flex-col justify-between gap-3 sm:flex-row sm:items-stretch">
          {/* ── columna izquierda: alertas ── */}
          <div className="flex min-h-0 w-full flex-col gap-3 sm:w-80">
            <section className={`${PANEL} pointer-events-auto flex min-h-0 flex-col`} aria-label="Alertas">
              <h2 title="Barcos lentos o parados sobre un cable, de mayor a menor atención. Pulsa uno para verlo en el mapa." className="border-b border-cyan-400/15 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-200/70">
                Atención · {alAtencion.length}{alertas.length > alAtencion.length ? ` (+${alertas.length - alAtencion.length} bajas)` : ''}
              </h2>
              <ul className="min-h-[9.5rem] max-h-[34vh] overflow-y-auto sm:max-h-[40vh]">
                {alAtencion.length === 0 && (
                  <li className="px-3 py-4 text-xs text-slate-400">Ningún buque lento o parado sobre un cable ahora mismo.</li>
                )}
                {alAtencion.slice(0, 40).map((f) => {
                  const p = f.properties;
                  const n = p.alerta as Nivel;
                  return (
                    <li key={p.mmsi}>
                      <button
                        onClick={() => { setSelCable(null); setSelBuque({ ...p, lng: f.geometry.coordinates[0], lat: f.geometry.coordinates[1] }); volar(f.geometry.coordinates[0], f.geometry.coordinates[1]); }}
                        className="flex w-full items-start gap-2.5 border-b border-white/5 px-3 py-2 text-left transition hover:bg-cyan-400/10"
                      >
                        <span className="mt-1 h-2 w-2 shrink-0 rounded-full" style={{ background: COLOR_NIVEL[n], boxShadow: `0 0 8px ${COLOR_NIVEL[n]}` }} />
                        <span className="min-w-0 flex-1">
                          <span className="flex items-center gap-1.5">
                            <span className="truncate text-xs font-semibold text-slate-100">{p.nombre || `MMSI ${p.mmsi}`}</span>
                            {p.simulado && <span className="rounded bg-fuchsia-500/25 px-1 text-[9px] font-bold text-fuchsia-200">SIM</span>}
                          </span>
                          <span className="block truncate text-[11px] text-slate-400">sobre {p.cable_nombre}</span>
                          <span className="block text-[10px] tabular-nums text-slate-500">
                            {n} · {p.minutos ?? 0} min · {p.sog != null ? `${p.sog} kn` : 's/d'} · {p.dist_m} m del cable
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>

            {(resp?.silencios.length ?? 0) > 0 && (
              <section className={`${PANEL} pointer-events-auto hidden sm:block`} aria-label="Silencios">
                <h2 title="Puede ser que el buque saliera del alcance de los receptores. Es un indicio." className="border-b border-cyan-400/15 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.2em] text-violet-200/80">Silencios en corredor ⓘ</h2>
                <ul className="max-h-[11vh] overflow-y-auto">
                  {resp!.silencios.slice(0, 6).map((s) => (
                    <li key={s.mmsi}>
                      <button onClick={() => volar(s.lng, s.lat)} className="w-full px-3 py-1.5 text-left transition hover:bg-violet-400/10">
                        <span className="block truncate text-xs text-slate-200">{s.nombre || `MMSI ${s.mmsi}`}</span>
                        <span className="block text-[10px] text-slate-500">{s.minutos_sin_senal} min sin señal · {s.cable_nombre}</span>
                      </button>
                    </li>
                  ))}
                </ul>
                
              </section>
            )}
            {recorridos.length > 0 && (
              <section className={`${PANEL} pointer-events-auto hidden sm:block`} aria-label="Recorridos largos">
                <h2 title="Informativo. En marcha dentro del corredor: no es una alerta, muchas rutas van paralelas a un cable. Se guarda en los sellos para compararlo después con fallos reales." className="border-b border-cyan-400/15 px-3 py-2 text-[10px] font-bold uppercase tracking-[0.2em] text-sky-200/80">Recorridos largos · {recorridos.length} ⓘ</h2>
                <ul className="max-h-[11vh] overflow-y-auto">
                  {recorridos.slice(0, 8).map((f) => {
                    const p = f.properties;
                    return (
                      <li key={p.mmsi}>
                        <button
                          onClick={() => { setSelCable(null); setSelBuque({ ...p, lng: f.geometry.coordinates[0], lat: f.geometry.coordinates[1] }); volar(f.geometry.coordinates[0], f.geometry.coordinates[1]); }}
                          className="w-full px-3 py-1.5 text-left transition hover:bg-sky-400/10"
                        >
                          <span className="block truncate text-xs text-slate-200">{p.nombre || `MMSI ${p.mmsi}`}</span>
                          <span className="block text-[10px] text-slate-500">{p.recorrido_km} km seguidos · {p.sog} kn · {p.cable_nombre}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
                
              </section>
            )}
          </div>

          {/* ── columna derecha: cobertura ── */}
          <div className="flex w-full flex-col justify-end gap-3 sm:w-72">

            <section className={`${PANEL} pointer-events-auto p-3`} aria-label="Cobertura del AIS">
              <h2 title="Regiones donde escuchamos barcos y cuántos vemos. «Sin señal» = ahí no hay receptores gratuitos: no vemos nada, aunque haya barcos." className="text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-200/70">Zonas escuchadas</h2>
              <ul className="mt-2 space-y-1.5">
                {zonas.map((z) => {
                  const total = z.n + z.sim;
                  const [[a, b], [c, d]] = z.caja;
                  return (
                    <li key={z.nombre}>
                      <button onClick={() => volar((b + d) / 2, (a + c) / 2, 4.2)} className="w-full text-left" title="Ir a la zona">
                        <div className="flex items-baseline justify-between text-[11px]">
                          <span className="truncate text-slate-300">{z.nombre}</span>
                          <span className={`tabular-nums ${z.n > 0 ? 'text-cyan-300' : z.sim > 0 ? 'text-fuchsia-300' : 'font-semibold text-red-400'}`}>
                            {z.n > 0 ? z.n : z.sim > 0 ? `sim ${z.sim}` : 'sin señal'}
                          </span>
                        </div>
                        <div className="mt-0.5 h-1 rounded bg-white/5">
                          <div className="h-1 rounded" style={{ width: `${(total / maxZona) * 100}%`, background: z.n > 0 ? '#22d3ee' : '#c084fc' }} />
                        </div>
                      </button>
                    </li>
                  );
                })}
                {zonas.length === 0 && <li className="text-xs text-slate-500">Esperando datos…</li>}
              </ul>
              <p className="mt-2 text-[9px] leading-snug text-slate-500">
                El AIS gratuito viene de estaciones en tierra: donde no hay receptores no se ve nada. «Sin señal» es falta de cobertura, no ausencia de barcos.
              </p>
            </section>
          </div>
        </div>

        {(selBuque || selCable) && (
          <section className={`${PANEL} pointer-events-auto absolute bottom-16 left-1/2 z-10 w-[min(22rem,92vw)] -translate-x-1/2 p-3`} aria-label="Detalle">
            {selBuque && (
              <>
                <div className="flex items-center justify-between gap-2">
                  <h3 className="truncate text-sm font-bold text-white">{selBuque.nombre || `MMSI ${selBuque.mmsi}`}</h3>
                  <button onClick={() => setSelBuque(null)} aria-label="Cerrar" className="text-slate-400 hover:text-white">✕</button>
                </div>
                {selBuque.simulado && <p className="mt-1 text-[10px] font-bold text-fuchsia-300">DATO SIMULADO</p>}
                <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
                  <dt className="text-slate-500">MMSI</dt><dd className="tabular-nums">{selBuque.mmsi}</dd>
                  <dt className="text-slate-500">Estado</dt><dd>{ETIQUETA_ESTADO[selBuque.estado]}</dd>
                  <dt className="text-slate-500">Velocidad</dt><dd className="tabular-nums">{selBuque.sog != null ? `${selBuque.sog} kn` : 's/d'}</dd>
                  <dt className="text-slate-500">Rumbo</dt><dd className="tabular-nums">{selBuque.cog != null ? `${Math.round(selBuque.cog)}°` : 's/d'}</dd>
                  {selBuque.cable_nombre && (<><dt className="text-slate-500">Cable</dt><dd className="truncate" title={selBuque.cable_nombre}>{selBuque.cable_nombre}</dd></>)}
                  {selBuque.dist_m != null && (<><dt className="text-slate-500">Distancia</dt><dd className="tabular-nums">{selBuque.dist_m} m</dd></>)}
                  {selBuque.alerta && (<><dt className="text-slate-500">Atención</dt><dd className="font-bold" style={{ color: COLOR_NIVEL[selBuque.alerta] }}>{selBuque.alerta} · {selBuque.minutos ?? 0} min</dd></>)}
                </dl>
                {selBuque.recorrido_km && (
                  <p className="mt-2 rounded border border-sky-400/25 bg-sky-950/30 px-2 py-1 text-[10px] text-sky-200">Lleva {selBuque.recorrido_km} km seguidos en marcha dentro del corredor (mínimo {resp?.meta.metodo.recorrido_min_km ?? 15}). Es informativo: muchas rutas van paralelas a un cable, y no se sabe si un arrastre a velocidad de navegación se vería así.</p>
                )}
                {(selBuque.inmovil_h ?? 0) >= (resp?.meta.metodo.inmovil_min_h ?? 3) && (
                  <p className="mt-2 rounded border border-sky-400/25 bg-sky-950/30 px-2 py-1 text-[10px] text-sky-200">Inmóvil desde hace {selBuque.inmovil_h} h (sin salir de {resp?.meta.metodo.inmovil_radio_m ?? 250} m): ni arrastra ni deriva, así que no pasa de MEDIO. Sigue siendo un fondeo o atraque sobre el corredor.</p>
                )}
                {selBuque.habitual && (
                  <p className="mt-2 rounded border border-sky-400/25 bg-sky-950/30 px-2 py-1 text-[10px] text-sky-200">Zona de estacionamiento habitual (puerto o rada): el nivel se rebaja salvo que se mueva sin que el agua lo explique.</p>
                )}
                {selBuque.prueba && (() => {
                  const pr = selBuque.prueba;
                  const v = TEXTO_VEREDICTO[pr.veredicto];
                  return (
                    <div className="mt-3 rounded-lg border border-white/10 bg-black/25 p-2.5">
                      <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-cyan-200/70">Prueba de deriva pasiva</p>
                      <p className="mt-1 text-xs font-bold" style={{ color: v.color }}>{v.titulo}</p>
                      <p className="text-[11px] leading-snug text-slate-300">{v.detalle}</p>
                      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[10px] tabular-nums">
                        <dt className="text-white">━ Observado</dt><dd>{pr.obs_kn} kn → {pr.obs_rumbo}°</dd>
                        <dt className="text-cyan-300">╌ Si fuera a la deriva</dt><dd>{pr.esp_kn} kn → {pr.esp_rumbo}°</dd>
                        <dt className="text-slate-500">Diferencia</dt><dd>{pr.residuo_kn} kn (tolerancia {pr.tol_kn}{pr.tol_base_kn && pr.tol_base_kn > 0.41 ? ' · el modelo de corrientes se equivoca más en esta región (medido con boyas)' : ''})</dd>
                        <dt className="text-slate-500">Corriente</dt><dd>{pr.corriente_kn} kn → {pr.corriente_hacia}°</dd>
                        <dt className="text-slate-500">Viento</dt><dd>{pr.viento_kn} kn desde {pr.viento_desde}°</dd>
                        <dt className="text-slate-500">Pista</dt><dd>{pr.muestras} posiciones en {pr.minutos} min</dd>
                      </dl>
                      {(pr.aprox_km ?? 0) > 0 && (
                        <p className="mt-1.5 rounded border border-amber-400/25 bg-amber-950/30 px-2 py-1 text-[10px] text-amber-200">La corriente es APROXIMADA: el modelo no tiene dato en este punto (costa) y se tomó la del agua más cercana, a {pr.aprox_km} km. Por eso la tolerancia es mayor.</p>
                      )}
                      <p className="mt-1.5 text-[9px] text-slate-500">En el mapa, los puntos son su pista real y las dos líneas muestran 3 h de movimiento.</p>
                    </div>
                  );
                })()}
                {selBuque.alerta && resp && (
                  <button
                    onClick={async () => { const r = await construirRecibo(selBuque, resp); descargar(r, selBuque.mmsi); }}
                    className="mt-2 w-full rounded border border-cyan-300/30 bg-cyan-950/30 px-2 py-1 text-[11px] font-semibold text-cyan-100 hover:bg-cyan-900/40"
                    title="Archivo JSON con la regla exacta, los números, las fuentes y un hash SHA-256 de su contenido"
                  >
                    ⤓ Descargar recibo de esta alerta
                  </button>
                )}
                <p className="mt-2 text-[10px] leading-snug text-slate-500">Nivel de atención, no acusación: ninguna regla distingue con certeza un fondeo legítimo de un arrastre de ancla.</p>
              </>
            )}
            {selCable && (
              <>
                <div className="flex items-center justify-between gap-2">
                  <h3 className="truncate text-sm font-bold text-white">{selCable.nombre}</h3>
                  <button onClick={() => setSelCable(null)} aria-label="Cerrar" className="text-slate-400 hover:text-white">✕</button>
                </div>
                <p className="mt-1 text-[11px] text-slate-400">
                  {selCable.longitud_km ? `${selCable.longitud_km.toLocaleString('es')} km · ` : ''}corredor de vigilancia de {resp ? '2 km' : '—'} a cada lado
                </p>
                <p className="mt-2 text-[10px] leading-snug text-slate-500">Vigía vigila lo que pasa <b>encima</b> del cable; no sabe si el cable funciona. Si un cable falla, aquí puedes ver qué barcos estuvieron sobre él antes.</p>
                <div className="mt-2 flex items-center gap-1.5 text-[11px]">
                  <span className="text-slate-400">Investigar últimas</span>
                  {[6, 24, 72].map((h) => (
                    <button key={h} onClick={() => investigar(selCable.slug, h)}
                      className={`rounded border px-2 py-0.5 ${invest?.slug === selCable.slug && invest.horas === h ? 'border-cyan-300 bg-cyan-900/40 text-cyan-100' : 'border-white/15 text-slate-300 hover:border-cyan-300/50'}`}>{h} h</button>
                  ))}
                </div>
                {invest && invest.slug === selCable.slug && (
                  <div className="mt-2">
                    {invest.cargando && <p className="text-[10px] text-slate-400">Buscando en el historial…</p>}
                    {invest.error && <p className="text-[10px] text-red-300">No se pudo consultar el historial.</p>}
                    {invest.datos && (
                      <>
                        <p className="text-[10px] text-slate-400">{invest.datos.total_barcos} barcos estuvieron sobre este cable en las últimas {invest.datos.horas} h{invest.datos.total_barcos > invest.datos.barcos.length ? ` (se muestran ${invest.datos.barcos.length})` : ''}. Primero los que más tiempo estuvieron casi quietos.</p>
                        <ul className="mt-1 max-h-48 overflow-y-auto">
                          {invest.datos.barcos.map((b) => (
                            <li key={b.mmsi}>
                              <button onClick={() => volar(b.ultima.lng, b.ultima.lat)} className="w-full px-1 py-1 text-left transition hover:bg-cyan-400/10">
                                <span className="block truncate text-xs text-slate-200">{b.nombre || `MMSI ${b.mmsi}`}{b.simulado && <span className="ml-1 rounded bg-fuchsia-500/25 px-1 text-[9px] font-bold text-fuchsia-200">SIM</span>}</span>
                                <span className="block text-[10px] tabular-nums text-slate-500">{b.minutos_lento} min lento · {b.minutos_dentro} min dentro · vel. mín. {b.sog_min_kn ?? 's/d'} kn · último {new Date(b.hasta).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' })}</span>
                              </button>
                            </li>
                          ))}
                        </ul>
                        <button
                          onClick={async () => { const d = invest.datos; if (d) descargarComo(await construirInforme(d), `informe-${d.cable.slug}-${d.horas}h`); }}
                          className="mt-1.5 w-full rounded border border-cyan-300/30 bg-cyan-950/30 px-2 py-1 text-[11px] font-semibold text-cyan-100 hover:bg-cyan-900/40"
                          title="Archivo JSON con la lista de barcos, la ventana de tiempo, los límites y un hash SHA-256 de su contenido"
                        >
                          ⤓ Descargar informe de esta investigación
                        </button>
                        <p className="mt-1 text-[9px] leading-snug text-slate-500">{invest.datos.aviso}</p>
                      </>
                    )}
                  </div>
                )}
              </>
            )}
          </section>
        )}

        {/* ── pie ── */}
        <div className="mt-3 flex flex-wrap items-center justify-start gap-2 text-[11px]">
          <button onClick={() => { setLeyenda((v) => !v); setMetodo(false); }} className={`${PANEL} pointer-events-auto px-3 py-1.5 font-semibold text-cyan-200/80 hover:text-white`}>
            {leyenda ? 'Ocultar leyenda' : 'Leyenda'}
          </button>
          <button onClick={() => { setMetodo((v) => !v); setLeyenda(false); }} className={`${PANEL} pointer-events-auto px-3 py-1.5 font-semibold text-cyan-200/80 hover:text-white`}>
            {metodo ? 'Ocultar método' : 'Cómo se calcula'}
          </button>
          <button onClick={() => setMedido((v) => !v)} className={`${PANEL} pointer-events-auto px-3 py-1.5 font-semibold text-cyan-200/80 hover:text-white`}>
            {medido ? 'Ocultar medidas' : 'Lo medido'}
          </button>
          <button onClick={alternarReplay} className={`${PANEL} pointer-events-auto px-3 py-1.5 font-semibold text-cyan-200/80 hover:text-white`}>
            {replayOn ? 'Cerrar replay' : 'Replay 3 h'}
          </button>
        </div>

        {replayOn && (
          <aside className={`${PANEL} pointer-events-auto absolute left-1/2 top-24 w-[min(30rem,calc(100%-2rem))] -translate-x-1/2 p-3 text-xs`} aria-label="Replay">
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-bold text-white">Replay · últimas {replay?.horas ?? 3} h</h2>
              <span className="tabular-nums text-cyan-200">{replay ? etiquetaTiempo(totalMin - trans) : '—'}</span>
            </div>
            {replayCarga && <p className="mt-2 text-slate-400">Cargando pistas…</p>}
            {replayError && <p className="mt-2 text-red-300">No se pudieron cargar las pistas.</p>}
            {replay && (
              <>
                <div className="mt-2 flex items-center gap-2">
                  <button onClick={() => { if (trans >= totalMin) setTrans(0); setPlay((v) => !v); }} aria-label={play ? 'Pausar' : 'Reproducir'}
                    className="rounded border border-cyan-300/30 bg-cyan-950/30 px-2.5 py-1 font-semibold text-cyan-100 hover:bg-cyan-900/40">{play ? '❚❚' : '▶'}</button>
                  <input type="range" min={0} max={totalMin} step={1} value={trans} aria-label="Instante del replay"
                    onChange={(e) => { setPlay(false); setTrans(Number(e.target.value)); }} className="min-w-0 flex-1 accent-cyan-400" />
                </div>
                <p className="mt-1.5 text-[10px] text-slate-400">{replay.buques.length} buques con atención{replay.buques.some((b) => b.simulado) ? ' (algunos SIMULADOS)' : ''}. Cada ~10 min hay una posición real; entre ellas se interpola en línea recta. Cada uno aparece cuando su primera posición de la ventana ya existe.</p>
              </>
            )}
          </aside>
        )}

        {medido && <Medido className={`${PANEL} pointer-events-auto absolute bottom-14 right-3 max-h-[calc(100%-11rem)] max-w-sm overflow-y-auto p-4 text-xs leading-relaxed sm:right-4`} />}

        {leyenda && (
          <aside className={`${PANEL} pointer-events-auto absolute bottom-14 left-3 max-h-[calc(100%-11rem)] max-w-xs overflow-y-auto p-4 text-xs leading-relaxed sm:left-4`} aria-label="Leyenda">
            <h2 className="font-bold text-white">Cómo leer el mapa</h2>
            <ul className="mt-2 space-y-1.5 text-slate-300">
              <li><span className="mr-2 inline-block h-0.5 w-5 align-middle" style={{ background: 'linear-gradient(90deg,#22d3ee,#a78bfa,#f472b6)' }} />Línea de color: un <b>cable submarino</b> (el color solo los distingue entre sí).</li>
              <li><span className="mr-2 inline-block h-0.5 w-5 align-middle" style={{ background: COLOR_NIVEL.ALTO }} />Cable en rojo brillante: tiene encima un barco con atención.</li>
              <li><span className="mr-2 inline-block h-2.5 w-2.5 rounded-full align-middle" style={{ background: COLOR_ESTADO.transito }} />Punto blanco: barco <b>en tránsito</b> (3 nudos o más).</li>
              <li><span className="mr-2 inline-block h-2.5 w-2.5 rounded-full align-middle" style={{ background: COLOR_ESTADO.lento }} />Ámbar: <b>lento</b> (menos de 3 nudos).</li>
              <li><span className="mr-2 inline-block h-2.5 w-2.5 rounded-full align-middle" style={{ background: COLOR_ESTADO.parado }} />Naranja: <b>parado</b> (menos de 0,5 nudos).</li>
              <li><span className="mr-2 inline-block h-2.5 w-2.5 rounded-full align-middle" style={{ background: COLOR_ESTADO.atracado }} />Gris: atracado o sin dato.</li>
              <li>Al acercarte, el punto pasa a una <b>flecha</b> que apunta hacia donde navega.</li>
              <li><span className="mr-2 inline-block h-3 w-3 rounded-full border-2 align-middle" style={{ borderColor: COLOR_NIVEL.ALTO }} /><span className="mr-2 inline-block h-3 w-3 rounded-full border-2 align-middle" style={{ borderColor: COLOR_NIVEL.MEDIO }} /><span className="mr-2 inline-block h-3 w-3 rounded-full border-2 align-middle" style={{ borderColor: COLOR_NIVEL.BAJO }} />Anillo que late: <b>nivel de atención</b> (alta, media, baja).</li>
              <li><span className="mr-2 inline-block h-2 w-2 rounded-full align-middle" style={{ background: '#a5f3fc' }} />Punto celeste pequeño: <b>punto de amarre</b>, donde el cable llega a tierra.</li>
              <li><span className="mr-2 inline-block h-3 w-5 border border-dashed align-middle" style={{ borderColor: '#38bdf8' }} />Rectángulo punteado: <b>zona escuchada</b> (azul = hay receptores; rojo = sin señal).</li>
            </ul>
            <p className="mt-2 text-[10px] text-slate-400">Pulsa un cable para <b>investigar</b> qué barcos estuvieron sobre él, o un barco para ver su prueba de deriva.</p>
          </aside>
        )}

        {metodo && resp && (
          <aside className={`${PANEL} pointer-events-auto absolute bottom-14 left-3 max-w-md p-4 text-xs leading-relaxed sm:left-4`} aria-label="Método">
            <h2 className="font-bold text-white">Cómo se calcula el nivel de atención</h2>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-slate-300">
              <li>Corredor de vigilancia: 2 km a cada lado del cable, en tramos de ~50 km.</li>
              <li>Parado: menos de {resp.meta.metodo.umbral_parado_kn} kn · Lento: menos de {resp.meta.metodo.umbral_lento_kn} kn.</li>
              <li><b style={{ color: COLOR_NIVEL.MEDIO }}>MEDIO</b>: lento o parado dentro del corredor. <b style={{ color: COLOR_NIVEL.ALTO }}>ALTO</b>: así desde hace {resp.meta.metodo.minutos_para_alto} min o más.</li>
              <li><b style={{ color: COLOR_NIVEL.BAJO }}>BAJO</b>: parado a menos de {resp.meta.metodo.radio_amarre_m / 1000} km de un punto de amarre (probablemente atracado).</li>
              <li>Un buque que declara estar amarrado no genera alerta. Ese estado lo teclea la tripulación.</li>
              <li><b>Zonas de estacionamiento habitual</b>: celdas de ~{resp.meta.metodo.habitual_celda_km} km donde, en las últimas {resp.meta.metodo.habitual_horas} h, se detuvieron al menos {resp.meta.metodo.habitual_min_buques} buques distintos. Se aprenden del propio AIS (con poco historial detectan menos). Ahí, parado o lento pasa a BAJO.</li>
              <li><b>Prueba de deriva pasiva</b>: con la pista de las últimas 3 h (≥ {resp.meta.metodo.deriva.min_muestras} posiciones y ≥ {resp.meta.metodo.deriva.min_minutos} min) se compara lo que se movió con lo que se movería sin motor: corriente + {resp.meta.metodo.deriva.viento_k * 100}% del viento, con tolerancia {resp.meta.metodo.deriva.tolerancia_base_kn} kn + {resp.meta.metodo.deriva.tolerancia_viento * 100}% del viento. «No es deriva» sube a ALTO; «sujeto al fondo» baja el nivel.</li>
            <li><b>Recorrido largo</b> (informativo): en marcha y sin salir del corredor ≥ {resp.meta.metodo.recorrido_min_km} km seguidos (con datos cada ≤ {resp.meta.metodo.recorrido_hueco_min} min). No sube el nivel; se sella para validarlo después.</li>
              <li><b>Inmóvil</b>: si en las últimas horas no salió de {resp.meta.metodo.inmovil_radio_m} m durante al menos {resp.meta.metodo.inmovil_min_h} h, el ALTO baja a MEDIO: no arrastra ni deriva. «Propulsión» se mantiene en ALTO.</li>
              <li><b>Alertas selladas</b>: cada hora se guardan las alertas ALTO/MEDIO con datos reales y un hash encadenado, para poder validarlas después sin ajustar el resultado.{' '}
              {sellos ? (sellos.total > 0
                ? <>Hay {sellos.total} sello(s); el último: <code className="text-cyan-200">{sellos.sellos[0].hash.slice(0, 12)}…</code> ({sellos.integra_en_lo_mostrado ? 'cadena íntegra' : 'CADENA ROTA'}).</>
                : 'Todavía no hay sellos.') : 'Cargando…'}</li>
            </ul>
            <p className="mt-2 text-slate-400">{resp.meta.metodo.nota}</p>
            <p className="mt-2 text-[10px] text-slate-500">Cables y puntos de amarre: TeleGeography (submarinecablemap.com); su licencia para uso comercial está pendiente de confirmar. AIS: AISstream. Mapa: Esri. {resp.meta.pruebas.atribucion}.</p>
            <p className="mt-1 text-[10px] text-slate-400">Prueba de deriva en este momento: {resp.meta.pruebas.evaluadas} buques evaluados · {resp.meta.pruebas.sin_agua} con pista pero sin dato de corriente (el modelo no llega a la costa).</p>
          </aside>
        )}
      </div>
    </div>
  );
}
