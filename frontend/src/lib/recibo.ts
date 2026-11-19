// «Recibo» de una alerta: un archivo JSON con la regla exacta, los números y las fuentes que la produjeron, más un
// hash SHA-256 de su contenido. El hash prueba que el archivo no se alteró después de generarse; NO prueba que los
// datos de origen (AIS, modelo de corrientes) sean correctos. Se construye en el navegador con lo que ya mostró la
// pantalla: no envía nada a ningún servidor.
import { MARCA } from './marca';
import type { BuqueProps, BuquesResponse, HistorialCable } from './cables';

/** JSON con las claves ordenadas, para que el mismo contenido dé siempre el mismo hash. */
export function canonico(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(canonico).join(',')}]`;
  if (v && typeof v === 'object') {
    const o = v as Record<string, unknown>;
    return `{${Object.keys(o).sort().map((k) => `${JSON.stringify(k)}:${canonico(o[k])}`).join(',')}}`;
  }
  return JSON.stringify(v);
}

export async function sha256(texto: string): Promise<string> {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(texto));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function reglaExacta(b: BuqueProps, m: BuquesResponse['meta']['metodo']): string {
  const partes = [
    `Nivel ${b.alerta ?? 'sin alerta'}: buque ${b.estado} (parado < ${m.umbral_parado_kn} kn, lento < ${m.umbral_lento_kn} kn) a ${b.dist_m ?? '?'} m del cable ${b.cable_nombre ?? '?'} (corredor de 2 km).`,
    `ALTO si lleva así ≥ ${m.minutos_para_alto} min (lleva ${b.minutos ?? 0}); BAJO si está a menos de ${m.radio_amarre_m / 1000} km de un punto de amarre o en una zona de estacionamiento habitual (${b.habitual ? 'sí' : 'no'}). Inmóvil: ${b.inmovil_h ?? 0} h sin salir de ${m.inmovil_radio_m} m (si ≥ ${m.inmovil_min_h} h, el ALTO baja a MEDIO).`,
  ];
  if (b.prueba) {
    const d = m.deriva;
    partes.push(
      `Prueba de deriva pasiva: observado = ajuste por mínimos cuadrados de ${b.prueba.muestras} posiciones en ${b.prueba.minutos} min (mínimo ${d.min_muestras} y ${d.min_minutos} min); `
      + `esperado = corriente + ${d.viento_k * 100} % del viento; tolerancia = ${d.tolerancia_base_kn} kn + ${d.tolerancia_viento * 100} % del viento `
      + `(+ margen si la corriente es la del agua cercana); quieto si < ${d.quieto_kn} kn. Diferencia ${b.prueba.residuo_kn} kn frente a tolerancia ${b.prueba.tol_kn} kn → ${b.prueba.veredicto}.`,
    );
  }
  return partes.join(' ');
}

export interface Recibo {
  contenido: Record<string, unknown>;
  sha256: string;
}

export async function construirRecibo(b: BuqueProps & { lng: number; lat: number }, resp: BuquesResponse): Promise<Recibo> {
  const contenido = {
    formato: MARCA.formatoRecibo,
    banner: b.simulado ? 'SIMULADO' : 'REAL (AIS terrestre de AISstream; corrientes y viento de modelo)',
    generado_por_la_pantalla_a_las: new Date().toISOString(),
    datos_de_la_pantalla_generados_a_las: resp.meta.generado,
    buque: { mmsi: b.mmsi, nombre: b.nombre, lat: b.lat, lng: b.lng, sog_kn: b.sog, cog_grados: b.cog, nav_declarado: b.nav, ultima_posicion: b.ts },
    cable: { nombre: b.cable_nombre ?? null, distancia_m: b.dist_m ?? null },
    nivel: b.alerta ?? null,
    minutos_en_estado: b.minutos ?? null,
    zona_habitual: b.habitual ?? false,
    horas_inmovil: b.inmovil_h ?? 0,
    prueba_de_deriva: b.prueba ?? null,
    regla_exacta: reglaExacta(b, resp.meta.metodo),
    parametros: resp.meta.metodo,
    fuentes: [
      'Cables y puntos de amarre: TeleGeography (licencia comercial sin confirmar)',
      'AIS: AISstream (estaciones terrestres; cobertura parcial)',
      resp.meta.pruebas.atribucion,
    ],
    limites: [
      'Es un nivel de atención, no una acusación: ninguna regla distingue con certeza un fondeo legítimo de un arrastre de ancla.',
      'Las corrientes y el viento son de un modelo (~8 km); cerca de la costa pueden faltar o ser aproximadas.',
      'Los umbrales son heurísticas sin validar con incidentes reales.',
      'El hash demuestra que este archivo no cambió desde que se generó; no demuestra que los datos de origen sean correctos.',
    ],
  };
  return { contenido, sha256: await sha256(canonico(contenido)) };
}

/** Descarga el recibo como archivo `recibo-<mmsi>-<hash corto>.json` con { contenido, sha256 }. */
export function descargar(r: Recibo, mmsi: string): void {
  const blob = new Blob([JSON.stringify(r, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `recibo-${mmsi}-${r.sha256.slice(0, 8)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

/** Informe de una investigación (qué barcos estuvieron sobre un cable): mismo formato que el recibo, con hash de su contenido. */
export async function construirInforme(h: HistorialCable): Promise<Recibo> {
  const contenido = {
    formato: 'informe-vigia/1',
    generado_por_la_pantalla_a_las: new Date().toISOString(),
    cable: h.cable,
    ventana: { horas: h.horas, desde: h.desde, hasta: h.hasta },
    total_barcos: h.total_barcos,
    barcos_incluidos: h.barcos.length,
    barcos: h.barcos,
    fuentes: ['AIS: AISstream (estaciones terrestres; cobertura parcial)', 'Cables: TeleGeography'],
    limites: [
      h.aviso,
      'Es una lista de presencia, no de culpa: estar sobre un cable no prueba que se dañara.',
      'El hash demuestra que este archivo no cambió desde que se generó; no demuestra que los datos de origen sean correctos.',
    ],
  };
  return { contenido, sha256: await sha256(canonico(contenido)) };
}

/** Descarga un recibo o informe como `<nombre>-<hash corto>.json`. */
export function descargarComo(r: Recibo, nombre: string): void {
  const blob = new Blob([JSON.stringify(r, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${nombre}-${r.sha256.slice(0, 8)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}
