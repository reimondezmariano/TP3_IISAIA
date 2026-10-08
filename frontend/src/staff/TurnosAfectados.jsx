import { describirTurno } from "./formato.js";

const nombre = (p) => (p ? p.nombre : "sin titular");

function Lista({ titulo, turnos }) {
  if (!turnos || turnos.length === 0) return null;
  return (
    <>
      <h4>{titulo} ({turnos.length})</h4>
      <ul>
        {turnos.map((t) => (
          <li key={t.id}>
            {describirTurno(t)} · titular: {nombre(t.titular)}{t.asignado ? ` · asignado: ${t.asignado.nombre}` : ""}
          </li>
        ))}
      </ul>
    </>
  );
}

// Resultado de un cambio de staff o de plantilla: lo que hizo y los turnos ya guardados que toca (D12, D24).
export default function TurnosAfectados({ resultado, onCerrar }) {
  const { titulo, turnosAfectados = [], coberturasReabiertas = [], horariosSinTitular = [] } = resultado;
  const sinNovedades = turnosAfectados.length === 0 && coberturasReabiertas.length === 0;
  return (
    <section className="resultado" role="status" aria-label="Resultado del cambio">
      <h3>{titulo}</h3>
      {horariosSinTitular.length > 0 && (
        <p>{horariosSinTitular.length === 1 ? "1 horario quedó sin titular (BAJA)." : `${horariosSinTitular.length} horarios quedaron sin titular (BAJA).`}</p>
      )}
      <Lista titulo="Turnos ya guardados que cambian" turnos={turnosAfectados} />
      <Lista titulo="Coberturas que se reabren como vacantes" turnos={coberturasReabiertas} />
      {sinNovedades && <p>No hay turnos ya guardados afectados.</p>}
      <button type="button" className="secundario" onClick={onCerrar}>Entendido</button>
    </section>
  );
}
