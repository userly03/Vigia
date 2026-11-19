// Service worker retirado. Versiones anteriores de la web registraron uno que guardaba páginas y respuestas de la API en caché.
// Este archivo existe SOLO para que los navegadores que aún lo tienen registrado lo reemplacen, borren esas cachés y se desregistren.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const claves = await caches.keys();
      await Promise.all(claves.map((k) => caches.delete(k)));
      await self.registration.unregister();
      const clientes = await self.clients.matchAll({ type: 'window' });
      clientes.forEach((c) => c.navigate(c.url));
    })(),
  );
});
