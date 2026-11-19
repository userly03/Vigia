'use client';

// Marcador público: lo que se ha MEDIDO (no lo que se promete), con su fecha y sus límites.
import { useEffect, useState } from 'react';
import { fetchValidacion, type ValidacionResponse } from '@/lib/cables';

const MODO: Record<string, string> = { dia: 'medias diarias', hora: 'horario', actual: '3 h vs 1 instante (hoy)', ventana: '3 h vs 3 h (propuesta)' };

/** «Baltico · dia · modelo a 15 m · boya con ancla (~15 m)» → «Báltico · medias diarias · modelo 15 m · con ancla». */
function etiqueta(k: string): string {
  const [reg, modo, modelo, boya] = k.split(' · ');
  const NOMBRE: Record<string, string> = { Baltico: 'Báltico', MarNorte: 'Mar del Norte', Mediterraneo: 'Mediterráneo', Mediterraneo_regional: 'Mediterráneo (modelo regional 4 km)', MarRojo_Golfo: 'Mar Rojo y Golfo', Peru: 'Perú', Taiwan: 'Taiwán' };
  return [NOMBRE[reg] ?? reg, MODO[modo] ?? modo,
    modelo?.includes('15') ? 'modelo 15 m' : 'modelo sup.', boya?.includes('sin') ? 'boya sin ancla' : 'boya con ancla'].join(' · ');
}

const FILAS_DERIVA = ['amarrado', 'con motor', 'con motor · pero sin moverse (SOG < 0,5 kn)'];

function pct(n: number | undefined, total: number): string {
  return total ? `${Math.round(((n ?? 0) / total) * 100)} %` : '—';
}

export default function Medido({ className }: { className?: string }) {
  const [v, setV] = useState<ValidacionResponse | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => { fetchValidacion().then(setV).catch(() => setError(true)); }, []);

  return (
    <aside className={className} aria-label="Lo que se ha medido">
      <h2 className="font-bold text-white">Lo que se ha medido</h2>
      {error && <p className="mt-2 text-slate-400">No se pudo cargar.</p>}
      {!v && !error && <p className="mt-2 text-slate-400">Cargando…</p>}
      {v && (
        <div className="mt-2 space-y-3 text-slate-300">
          <section>
            <h3 className="font-semibold text-cyan-200/80">Prueba de deriva pasiva (AIS real)</h3>
            {v.deriva_pasiva ? (
              <>
                <p className="text-[10px] text-slate-500">{new Date(v.deriva_pasiva.generado).toLocaleString('es')} · {v.deriva_pasiva.ventana_h} h de AIS · {v.deriva_pasiva.evaluados} buques evaluados, {v.deriva_pasiva.sin_fuerzas} sin dato de corriente</p>
                <table className="mt-1 w-full text-[10px] tabular-nums">
                  <thead><tr className="text-slate-500"><th className="text-left font-normal">Declarado</th><th>n</th><th>deriva</th><th>fijo</th><th>propuls.</th><th>indet.</th></tr></thead>
                  <tbody>
                    {FILAS_DERIVA.filter((k) => v.deriva_pasiva!.tabla[k]).map((k) => {
                      const t = v.deriva_pasiva!.tabla[k]; const n = Object.values(t).reduce((a, b) => a + (b ?? 0), 0);
                      return (<tr key={k}><td className="max-w-[9rem] truncate" title={k}>{k}</td><td className="text-center">{n}</td>
                        <td className="text-center">{pct(t.deriva, n)}</td><td className="text-center">{pct(t.fijo, n)}</td><td className="text-center">{pct(t.propulsion, n)}</td><td className="text-center">{pct(t.indeterminado, n)}</td></tr>);
                    })}
                  </tbody>
                </table>
                <p className="mt-1 text-[10px] text-slate-500">Mide consistencia con lo que declaran los buques, no acierto: ese estado lo teclea la tripulación.</p>
              </>
            ) : <p className="text-[10px] text-slate-500">Aún sin medir.</p>}
          </section>
          <section>
            <h3 className="font-semibold text-cyan-200/80">Corrientes del modelo frente a boyas reales</h3>
            {v.corrientes_vs_boyas ? (
              <>
                <p className="text-[10px] text-slate-500">{new Date(v.corrientes_vs_boyas.generado).toLocaleString('es')} · tolerancia que asumimos: {v.corrientes_vs_boyas.tolerancia_asumida_kn} kn</p>
                <table className="mt-1 w-full text-[10px] tabular-nums">
                  <thead><tr className="text-slate-500"><th className="text-left font-normal">Caso</th><th>boyas</th><th>error med.</th><th>≤ tol.</th></tr></thead>
                  <tbody>
                    {Object.entries(v.corrientes_vs_boyas.resultados).filter(([k]) => !k.includes('modelo a 15 m') && !k.includes(' hora ') && !k.includes(' ventana ')).map(([k, r]) => (
                      <tr key={k}><td className="max-w-[14rem]" title={k}>{etiqueta(k)}</td><td className="text-center">{r.n_boyas}</td><td className="whitespace-nowrap text-center">{r.error_mediano_kn} kn</td><td className="whitespace-nowrap text-center">{r.dentro_de_tolerancia_pct} %</td></tr>
                    ))}
                  </tbody>
                </table>
                <ul className="mt-1 list-disc pl-4 text-[10px] text-slate-500">{v.corrientes_vs_boyas.limites.map((l) => <li key={l}>{l}</li>)}</ul>
              </>
            ) : <p className="text-[10px] text-slate-500">Aún sin medir.</p>}
          </section>
        </div>
      )}
    </aside>
  );
}
