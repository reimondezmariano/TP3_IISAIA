import { useState } from "react";
import { etiquetaDia, fechaLocal, horaLocal } from "../lib/fechas.js";

export default function DetalleTurno({ turno, estado, acciones, onCerrar }) {
  const [motivo, setMotivo] = useState("");
  const [intentoSinMotivo, setIntentoSinMotivo] = useState(false);
  const diaSiguiente = fechaLocal(turno.fin) !== turno.fecha;
  const puede = (accion) => estado.acciones.includes(accion);

  function avisar(evento) {
    evento.preventDefault();
    if (!motivo.trim()) {
      setIntentoSinMotivo(true);
      return;
    }
    acciones.avisarAusencia(turno.id, motivo.trim());
    setMotivo("");
    setIntentoSinMotivo(false);
  }

  return (
    <div className="detalle-fondo">
      <section className="detalle" role="dialog" aria-modal="true" aria-labelledby="detalle-titulo">
        <h2 id="detalle-titulo">Detalle de la guardia</h2>
        <p data-testid="rotulo-simulado" className="aviso">
          Simulado: todavía no hay vacantes ni postulaciones en el servidor; lo que hagas acá solo vive en esta pestaña.
        </p>
        <dl>
          <dt>Día</dt>
          <dd>{etiquetaDia(turno.fecha)}</dd>
          <dt>Horario</dt>
          <dd>{horaLocal(turno.inicio)} – {horaLocal(turno.fin)}{diaSiguiente ? " (+1 día)" : ""} · {turno.duracionHoras} h</dd>
          <dt>Titular</dt>
          <dd>{turno.titular ? turno.titular.nombre : "Sin titular (baja)"}</dd>
          {estado.etiqueta && (
            <>
              <dt>Estado</dt>
              <dd><strong>{estado.etiqueta}</strong></dd>
            </>
          )}
        </dl>
        {estado.postulantes.length > 0 && (
          <>
            <h3>Postulantes</h3>
            <ul>{estado.postulantes.map((p) => <li key={p.id}>{p.nombre}</li>)}</ul>
          </>
        )}
        {puede("AVISAR_AUSENCIA") && (
          <form onSubmit={avisar} noValidate>
            <label>
              Motivo (solo lo ven los coordinadores)
              <input value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={500} />
            </label>
            {intentoSinMotivo && !motivo.trim() && <p role="alert" className="error">Escribí el motivo de la ausencia.</p>}
            <button type="submit">Avisar ausencia</button>
          </form>
        )}
        {puede("RETIRAR_AVISO") && <button type="button" onClick={() => acciones.retirarAviso(turno.id)}>Retirar aviso</button>}
        {puede("POSTULARME") && <button type="button" onClick={() => acciones.postularme(turno.id)}>Postularme</button>}
        {puede("RETIRAR_POSTULACION") && <button type="button" onClick={() => acciones.retirarPostulacion(turno.id)}>Retirar postulación</button>}
        <button type="button" className="secundario" onClick={onCerrar}>Cerrar</button>
      </section>
    </div>
  );
}
