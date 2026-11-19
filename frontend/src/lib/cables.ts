// Cliente de la API pública del Vigía. No usa la sesión: todo es de solo lectura.
import axios from 'axios';
import type { ReplayResponse } from './replay';

export const CABLES_API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

export type Nivel = 'ALTO' | 'MEDIO' | 'BAJO';
export type EstadoBuque = 'transito' | 'lento' | 'parado' | 'atracado' | 'sin_dato';

export type Veredicto = 'deriva' | 'fijo' | 'propulsion' | 'indeterminado';

/** Resultado de la prueba de deriva pasiva (ver backend cables/deriva.py). Velocidades en nudos; rumbos en grados. */
export interface PruebaDeriva {
  veredicto: Veredicto;
  obs_kn: number; obs_rumbo: number; obs_ve: number; obs_vn: number;
  esp_kn: number; esp_rumbo: number; esp_ve: number; esp_vn: number;
  residuo_kn: number; tol_kn: number;
  /** Tolerancia base de la región (0,4 kn por defecto; 0,7 en el Mar del Norte, medida contra boyas reales). */
  tol_base_kn?: number;
  corriente_kn: number; corriente_hacia: number;
  /** 0 = corriente de la propia celda; > 0 = se tomó la del agua más cercana, a tantos km (aproximación). */
  aprox_km?: number;
  viento_kn: number; viento_desde: number;
  muestras: number; minutos: number;
  /** Posiciones reales [lng, lat], de la más vieja a la más reciente. */
  pista: [number, number][];
}

export interface BuqueProps {
  mmsi: string;
  nombre: string;
  sog: number | null;
  cog: number | null;
  nav: number | null;
  estado: EstadoBuque;
  ts: string | null;
  simulado: boolean;
  cable?: string;
  cable_nombre?: string;
  dist_m?: number;
  minutos?: number;
  alerta?: Nivel | null;
  habitual?: boolean;
  /** Horas sin salir de ~250 m (0 si se mueve o no hay pista suficiente). */
  inmovil_h?: number;
  /** Km seguidos en marcha dentro del corredor (≥ 15): señal INFORMATIVA, no sube el nivel. */
  recorrido_km?: number;
  prueba?: PruebaDeriva;
}

export type BuqueFeature = GeoJSON.Feature<GeoJSON.Point, BuqueProps>;

export interface Silencio {
  mmsi: string;
  nombre: string;
  lat: number;
  lng: number;
  ultima: string;
  minutos_sin_senal: number;
  cable: string;
  cable_nombre: string;
  distancia_m: number;
}

export interface Zona {
  nombre: string;
  /** Esquinas opuestas [[lat1, lon1], [lat2, lon2]]. */
  caja: [[number, number], [number, number]];
}

export interface BuquesResponse {
  type: 'FeatureCollection';
  features: BuqueFeature[];
  meta: {
    generado: string;
    total: number;
    en_corredor: number;
    alertas: Record<Nivel, number>;
    recorridos: number;
    simulados: number;
    zonas: Zona[];
    metodo: {
      umbral_parado_kn: number;
      umbral_lento_kn: number;
      minutos_para_alto: number;
      radio_amarre_m: number;
      nota: string;
      habitual_min_buques: number; habitual_celda_km: number; habitual_horas: number;
      inmovil_radio_m: number; inmovil_min_h: number; recorrido_min_km: number; recorrido_hueco_min: number;
      deriva: { viento_k: number; tolerancia_base_kn: number; tolerancia_viento: number; min_muestras: number; min_minutos: number; quieto_kn: number };
    };
    pruebas: { evaluadas: number; con_pista: number; sin_agua: number; atribucion: string };
  };
  silencios: Silencio[];
}

export interface CableProps {
  slug: string;
  nombre: string;
  color: string;
  longitud_km: number | null;
  /** Índice de color (0–5), asignado en el cliente para variar el aspecto. */
  tono?: number;
}
export type CablesGeoJSON = GeoJSON.FeatureCollection<GeoJSON.MultiLineString | GeoJSON.LineString, CableProps> & { atribucion?: string };

// Instancia aparte de la del resto de la app: es pública, sin cookies ni lógica de refresco de sesión.
const publico = axios.create({ baseURL: CABLES_API, timeout: 30_000, withCredentials: false });

function tono(slug: string): number {
  let h = 0;
  for (let i = 0; i < slug.length; i++) h = (h * 31 + slug.charCodeAt(i)) >>> 0;
  return h % 6;
}

export async function fetchCables(): Promise<CablesGeoJSON> {
  const { data: d } = await publico.get<CablesGeoJSON>('/cables/');
  for (const f of d.features) f.properties.tono = tono(f.properties.slug);
  return d;
}

export const fetchAmarres = async () =>
  (await publico.get<GeoJSON.FeatureCollection<GeoJSON.Point, { nombre: string; pais: string }>>('/cables/amarres/')).data;
export interface SellosResponse {
  total: number;
  integra_en_lo_mostrado: boolean;
  sellos: { ts: string; hash: string; hash_anterior: string; contenido: { alertas: unknown[] } }[];
}
export const fetchSellos = async () => (await publico.get<SellosResponse>('/cables/sellos/')).data;
export interface ResumenBoyas {
  n_puntos: number; n_boyas: number; error_mediano_kn: number; error_p90_kn: number; rmse_kn: number;
  dentro_de_tolerancia_pct: number; error_si_modelo_fuera_cero_kn: number;
}
export interface ValidacionResponse {
  deriva_pasiva: {
    generado: string; ventana_h: number; evaluados: number; sin_fuerzas: number; buques_con_pista: number;
    tabla: Record<string, Partial<Record<Veredicto, number>>>; limites: string[];
  } | null;
  corrientes_vs_boyas: {
    generado: string; tolerancia_asumida_kn: number; resultados: Record<string, ResumenBoyas>;
    boyas_sin_modelo: Record<string, number>; limites: string[];
  } | null;
}
export const fetchValidacion = async () => (await publico.get<ValidacionResponse>('/cables/validacion/')).data;
export const fetchBuques = async () => (await publico.get<BuquesResponse>('/cables/buques/')).data;

// ─── presentación compartida ─────────────────────────────────────────────────

export const COLOR_NIVEL: Record<Nivel, string> = { ALTO: '#ff3b5c', MEDIO: '#ffb020', BAJO: '#7dd3fc' };
export const COLOR_ESTADO: Record<EstadoBuque, string> = {
  transito: '#e6f0ff', lento: '#ffb020', parado: '#ff7a1a', atracado: '#5b6b82', sin_dato: '#5b6b82',
};
export const TONOS_CABLE = ['#22d3ee', '#a78bfa', '#f472b6', '#34d399', '#60a5fa', '#fbbf24'];
export const ETIQUETA_ESTADO: Record<EstadoBuque, string> = {
  transito: 'En tránsito', lento: 'Lento', parado: 'Parado', atracado: 'Amarrado', sin_dato: 'Sin dato',
};

/** ¿Está el punto dentro de la caja de la zona? (cajas de AISstream: esquinas opuestas lat/lon) */
export function enZona(lat: number, lng: number, z: Zona): boolean {
  const [[a, b], [c, d]] = z.caja;
  return lat >= Math.min(a, c) && lat <= Math.max(a, c) && lng >= Math.min(b, d) && lng <= Math.max(b, d);
}

export const TEXTO_VEREDICTO: Record<Veredicto, { titulo: string; detalle: string; color: string }> = {
  deriva: { titulo: 'A la deriva', detalle: 'Se mueve como el agua y el viento lo moverían: sin propulsión.', color: '#fbbf24' },
  fijo: { titulo: 'Sujeto al fondo', detalle: 'El agua lo arrastraría y no se mueve: fondeado o amarrado.', color: '#7dd3fc' },
  propulsion: { titulo: 'No es deriva', detalle: 'Se mueve distinto de lo que haría el agua: propulsión, o algo lo arrastra o lo retiene.', color: '#ff3b5c' },
  indeterminado: { titulo: 'Sin fuerzas para decidir', detalle: 'Está quieto y el agua casi no lo movería: no se puede distinguir.', color: '#94a3b8' },
};

/** Punto a donde llegaría tras `horas` con velocidad (este, norte) en nudos desde (lng, lat). */
export function proyectar(lng: number, lat: number, ve: number, vn: number, horas: number): [number, number] {
  const km = 1.852 * horas;
  return [lng + (ve * km) / (111.195 * Math.max(0.2, Math.cos((lat * Math.PI) / 180))), lat + (vn * km) / 111.195];
}

export const fetchReplay = async (horas = 3) => (await publico.get<ReplayResponse>('/cables/replay/', { params: { horas } })).data;

export interface BarcoSobreCable {
  mmsi: string; nombre: string; simulado: boolean;
  desde: string; hasta: string; posiciones: number;
  minutos_dentro: number; minutos_lento: number;
  sog_min_kn: number | null; sog_medio_kn: number | null; nav_declarado: number | null;
  ultima: { lat: number; lng: number };
}
export interface HistorialCable {
  cable: { slug: string; nombre: string }; horas: number; desde: string; hasta: string;
  total_barcos: number; barcos: BarcoSobreCable[]; aviso: string;
}
export const fetchHistorialCable = async (slug: string, horas: number) =>
  (await publico.get<HistorialCable>(`/cables/${slug}/historial/`, { params: { horas } })).data;
