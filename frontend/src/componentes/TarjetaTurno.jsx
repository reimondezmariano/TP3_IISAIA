import { fechaLocal, horaLocal } from "../lib/fechas.js";
import { semaforo } from "../lib/semaforo.js";

export default function TarjetaTurno({ turno, usuario, onAbrir }) {
  const sinTitular = turno.titular === null;
  const mia = !sinTitular && turno.titular.id === usuario.id;
  const diaSiguiente = fechaLocal(turno.fin) !== turno.fecha;
  const horario = `${horaLocal(turno.inicio)} – ${horaLocal(turno.fin)}${diaSiguiente ? " (+1 día)" : ""}`;
  const { clase, etiqueta } = semaforo(turno);

  return (
    <button type="button" className={`turno ${clase}`} data-testid="turno" data-turno-id={turno.id} data-semaforo={clase} onClick={() => onAbrir(turno)}>
      <span className="turno-horario">{horario}</span>
      <span className="turno-duracion">{turno.duracionHoras} h</span>
      <span className="turno-titular">{sinTitular ? "Sin titular" : turno.titular.nombre}</span>
      <span className="insignias">
        {mia && <span className="insignia mia">Mi guardia</span>}
        {etiqueta && <span className={`insignia ${clase}`}>{etiqueta}</span>}
      </span>
    </button>
  );
}
