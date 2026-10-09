import { fechaLocal, horaLocal } from "../lib/fechas.js";
import { quienCubre } from "../lib/quienCubre.js";
import { semaforo, textoPostulantes } from "../lib/semaforo.js";

export default function TarjetaTurno({ turno, usuario, onAbrir }) {
  const sinTitular = turno.titular === null;
  const mia = !sinTitular && turno.titular.id === usuario.id;
  const diaSiguiente = fechaLocal(turno.fin) !== turno.fecha;
  const horario = `${horaLocal(turno.inicio)} – ${horaLocal(turno.fin)}${diaSiguiente ? " (+1 día)" : ""}`;
  const { clase, etiqueta } = semaforo(turno);
  const postulantes = textoPostulantes(turno);
  const { principal, secundario } = quienCubre(turno);

  return (
    <button type="button" className={`turno ${clase}`} data-testid="turno" data-turno-id={turno.id} data-semaforo={clase} onClick={() => onAbrir(turno)}>
      <span className="turno-horario">{horario}</span>
      <span className="turno-duracion">{turno.duracionHoras} h</span>
      <span className="turno-titular">{principal}</span>
      {secundario && <span className="turno-secundario">{secundario}</span>}
      <span className="insignias">
        {mia && <span className="insignia mia">Mi guardia</span>}
        {postulantes && <span className="insignia postulantes">{postulantes}</span>}
        {etiqueta && <span className={`insignia ${clase}`}>{etiqueta}</span>}
      </span>
    </button>
  );
}
