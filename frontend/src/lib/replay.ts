// Replay: reproduce las últimas horas de los buques con atención. Funciones puras (se prueban sin navegador).

/** [minutos antes del final, lng, lat, sog en nudos]; de la más antigua a la más reciente. */
export type MuestraReplay = [number, number, number, number | null];

export interface BuqueReplay {
  mmsi: string; nombre: string; nivel: 'ALTO' | 'MEDIO' | 'BAJO' | null; recorrido_km: number | null;
  cable: string | null; simulado: boolean; pista: MuestraReplay[];
}
export interface ReplayResponse { hasta: string; horas: number; buques: BuqueReplay[]; nota: string }

export interface EstadoReplay { pos: [number, number]; rastro: [number, number][] }

/**
 * Dónde estaba el buque `t` minutos antes del final y el rastro que llevaba hasta ahí.
 * Entre dos muestras se interpola en línea recta; antes de su primera muestra, null (no se sabe dónde estaba);
 * después de la última, se queda en ella.
 */
export function estadoEn(pista: MuestraReplay[], t: number): EstadoReplay | null {
  if (pista.length === 0 || t > pista[0][0]) return null;
  const rastro: [number, number][] = [];
  let pos: [number, number] = [pista[0][1], pista[0][2]];
  for (let i = 0; i < pista.length; i++) {
    const [m, lng, lat] = pista[i];
    if (m >= t) { rastro.push([lng, lat]); pos = [lng, lat]; continue; }
    const [m0, lng0, lat0] = pista[i - 1];
    const f = (m0 - t) / (m0 - m);
    if (f > 0) {                       // si t coincide con una muestra, esa ya está en el rastro: no se repite
      pos = [lng0 + (lng - lng0) * f, lat0 + (lat - lat0) * f];
      rastro.push(pos);
    }
    return { pos, rastro };
  }
  return { pos, rastro };
}

/** GeoJSON con la posición (Point) y el rastro (LineString) de cada buque a `t` minutos antes del final. */
export function featuresReplay(datos: ReplayResponse, t: number): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  for (const b of datos.buques) {
    const e = estadoEn(b.pista, t);
    if (!e) continue;
    const props = { mmsi: b.mmsi, nombre: b.nombre, nivel: b.nivel ?? 'info' };
    if (e.rastro.length >= 2) features.push({ type: 'Feature', properties: { ...props, tipo: 'rastro' }, geometry: { type: 'LineString', coordinates: e.rastro } });
    features.push({ type: 'Feature', properties: { ...props, tipo: 'pos' }, geometry: { type: 'Point', coordinates: e.pos } });
  }
  return { type: 'FeatureCollection', features };
}

/** «−2 h 15 min» a partir de minutos antes del final. */
export function etiquetaTiempo(minAntes: number): string {
  const m = Math.round(minAntes);
  if (m <= 0) return 'ahora';
  const h = Math.floor(m / 60);
  return `−${h > 0 ? `${h} h ` : ''}${m % 60} min`.replace(' 0 min', '');
}
