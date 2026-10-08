import { fechaLocal, horaLocal } from "../lib/fechas.js";

export default function TarjetaTurno({ turno, usuario, estado, onAbrir }) {
  const sinTitular = turno.titular === null;
  const mia = !sinTitular && turno.titular.id === usuario.id;
  const diaSiguiente = fechaLocal(turno.fin) !== turno.fecha;
  const horario = `${horaLocal(turno.inicio)} – ${horaLocal(turno.fin)}${diaSiguiente ? " (+1 día)" : ""}`;
  const clases = ["turno", mia && "mio", sinTitular && "baja", estado?.tipo === "VACANTE" && "vacante"].filter(Boolean).join(" ");
  const etiqueta = estado?.etiqueta && estado.etiqueta !== "BAJA" ? estado.etiqueta : null;

  return (
    <button type="button" className={clases} data-testid="turno" data-turno-id={turno.id} onClick={() => onAbrir(turno)}>
      <span className="turno-horario">{horario}</span>
      <span className="turno-duracion">{turno.duracionHoras} h</span>
      <span className="turno-titular">{sinTitular ? "Sin titular" : turno.titular.nombre}</span>
      <span className="insignias">
        {mia && <span className="insignia mia">Mi guardia</span>}
        {sinTitular && <span className="insignia baja">BAJA</span>}
        {etiqueta && <span className={`insignia ${estado.urgente ? "urgente" : "vacante"}`}>{etiqueta}</span>}
      </span>
    </button>
  );
}
