# Vigía — web

Pantalla pública de Vigía (Next.js 14 + React 18 + MapLibre). Todo el producto, el nombre, cómo arrancarlo y la API están en el [README de la raíz](../README.md).

```bash
npm install
NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1 npm run dev -- -p 3001
npx tsc --noEmit && npx next lint && npx next build
node --experimental-strip-types tools/probar_replay.mts
```
El nombre del producto se cambia en `src/lib/marca.ts`.
