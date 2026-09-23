import { useEffect, useState } from "react";
import { instanteDeApi } from "../api/reglas";

export function haceTanto(iso: string, ahora = Date.now()): string {
  const s = Math.max(0, Math.round((ahora - instanteDeApi(iso).getTime()) / 1000));
  if (s < 5) return "ahora";
  if (s < 60) return `hace ${s} s`;
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  if (s < 86400) return `hace ${Math.floor(s / 3600)} h`;
  return `hace ${Math.floor(s / 86400)} d`;
}

/** La hora actual, refrescada cada `intervalo` ms; con `null`, no se refresca. */
export function useAhora(intervalo: number | null): number {
  const [ahora, setAhora] = useState(() => Date.now());
  useEffect(() => {
    if (intervalo === null) return;
    const id = setInterval(() => setAhora(Date.now()), intervalo);
    return () => clearInterval(id);
  }, [intervalo]);
  return ahora;
}

/** «hace 3 min», que se refresca solo cada 30 s. */
export function Hace({ iso, className }: { iso: string; className?: string }) {
  const ahora = useAhora(30_000);
  const instante = instanteDeApi(iso);
  if (Number.isNaN(instante.getTime())) return <span className={className}>{iso}</span>;
  return (
    <time className={className} dateTime={instante.toISOString()} title={instante.toLocaleString("es-ES")}>
      {haceTanto(iso, ahora)}
    </time>
  );
}
