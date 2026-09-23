import { useEffect, useState } from "react";

export function haceTanto(iso: string, ahora = Date.now()): string {
  const s = Math.max(0, Math.round((ahora - new Date(iso).getTime()) / 1000));
  if (s < 5) return "ahora";
  if (s < 60) return `hace ${s} s`;
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  if (s < 86400) return `hace ${Math.floor(s / 3600)} h`;
  return `hace ${Math.floor(s / 86400)} d`;
}

/** «hace 3 min», que se refresca solo cada 30 s. */
export function Hace({ iso, className }: { iso: string; className?: string }) {
  const [ahora, setAhora] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setAhora(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);
  return (
    <time className={className} dateTime={iso} title={new Date(iso).toLocaleString("es-ES")}>
      {haceTanto(iso, ahora)}
    </time>
  );
}
