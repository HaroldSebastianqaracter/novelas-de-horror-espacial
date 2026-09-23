import "./ui.css";

interface Props {
  completados: number;
  /** 0 mientras la estructura no ha fijado el total. */
  total: number;
}

export function Progreso({ completados, total }: Props) {
  const pct = total > 0 ? Math.min(100, Math.round((completados / total) * 100)) : 0;
  const descripcion =
    total > 0 ? `${completados} de ${total} capítulos cerrados` : "El total de capítulos se fija en la estructura";
  return (
    <div className="progreso">
      <div
        className="progreso__barra"
        role="progressbar"
        aria-label="Capítulos cerrados"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={completados}
        aria-valuetext={descripcion}
      >
        <span style={{ width: `${pct}%` }} />
      </div>
      <span className="progreso__texto">{total > 0 ? `${completados} / ${total} cap.` : `${completados} / ? cap.`}</span>
    </div>
  );
}
