'use client';

import dynamic from 'next/dynamic';

// El globo usa WebGL y `window`: sólo se carga en el navegador.
const Guardian = dynamic(() => import('@/components/globe/Guardian'), {
  ssr: false,
  loading: () => <div className="fixed inset-0 bg-[#020611]" aria-busy="true" />,
});

export default function RootPage() {
  return <Guardian />;
}
