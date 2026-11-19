// Comprobación de src/lib/replay.ts sin navegador: node --experimental-strip-types tools/probar_replay.mts
import { estadoEn, etiquetaTiempo, featuresReplay } from '../src/lib/replay.ts';
const p: any = [[60, 0, 0, 0], [30, 1, 0, 0], [0, 1, 1, 0]];
const ok = (c: boolean, m: string) => { if (!c) { console.log('FALLA', m); process.exitCode = 1; } };
ok(estadoEn(p, 90) === null, 'antes de la primera muestra no hay estado');
const a = estadoEn(p, 60)!; ok(a.pos[0] === 0 && a.rastro.length === 1, 'en la primera muestra');
const b = estadoEn(p, 45)!; ok(Math.abs(b.pos[0] - 0.5) < 1e-9 && b.pos[1] === 0 && b.rastro.length === 2, 'interpola a mitad de tramo: ' + JSON.stringify(b));
const c = estadoEn(p, 15)!; ok(c.pos[0] === 1 && Math.abs(c.pos[1] - 0.5) < 1e-9 && c.rastro.length === 3, 'segundo tramo');
const d = estadoEn(p, 0)!; ok(d.pos[0] === 1 && d.pos[1] === 1, 'al final');
const e = estadoEn(p, -5)!; ok(e.pos[1] === 1, 'después de la última se queda');
ok(estadoEn([], 10) === null, 'pista vacía');
ok(etiquetaTiempo(135) === '−2 h 15 min' && etiquetaTiempo(120) === '−2 h' && etiquetaTiempo(45) === '−45 min' && etiquetaTiempo(0) === 'ahora', 'etiquetas: ' + [135,120,45,0].map(etiquetaTiempo).join('|'));
const f = featuresReplay({ hasta: '', horas: 1, nota: '', buques: [{ mmsi: '1', nombre: 'A', nivel: 'ALTO', recorrido_km: null, cable: null, simulado: false, pista: p }, { mmsi: '2', nombre: 'B', nivel: null, recorrido_km: 20, cable: null, simulado: false, pista: [[10, 5, 5, 1]] }] }, 45);
ok(f.features.length === 2 && f.features[0].properties!.tipo === 'rastro' && f.features[1].properties!.tipo === 'pos', 'solo el buque con datos a t=45 (rastro + punto): ' + f.features.length);
console.log(process.exitCode ? 'HAY FALLOS' : 'todo OK');
