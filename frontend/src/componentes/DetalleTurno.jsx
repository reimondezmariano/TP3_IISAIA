import { useState } from "react";
import { etiquetaDia, fechaLocal, horaLocal } from "../lib/fechas.js";
import { quienCubre } from "../lib/quienCubre.js";

export default function DetalleTurno({ turno, estado, acciones, panel = null, onCerrar }) {
  const [motivo, setMotivo] = useState("");
  const [intentoSinMotivo, setIntentoSinMotivo] = useState(false);
  const [accionError, setAccionError] = useState(null);
  const [haciendo, setHaciendo] = useState(false);
  const diaSiguiente = fechaLocal(turno.fin) !== turno.fecha;
  const { principal, secundario } = quienCubre(turno);
  const puede = (accion) => estado.acciones.includes(accion);

  // Las acciones de ausencia y postulación van a la API: se espera la respuesta y se muestra su error.
  async function ejecutar(accion) {
    if (haciendo) return;
    setHaciendo(true);
    setAccionError(null);
    try {
      await accion();
    } catch (error) {
      setAccionError(error.message);
    } finally {
      setHaciendo(false);
    }
  }

  function avisar(evento) {
    evento.preventDefault();
    if (!motivo.trim()) {
      setIntentoSinMotivo(true);
      return;
    }
    setIntentoSinMotivo(false);
    ejecutar(async () => {
      await acciones.avisarAusencia(turno.id, motivo.trim());
      setMotivo("");
    });
  }
  return (
    <div className="detalle-fondo">
      <section className="detalle" role="dialog" aria-modal="true" aria-labelledby="detalle-titulo">
        <h2 id="detalle-titulo">Detalle de la guardia</h2>
        <dl>
          <dt>Día</dt>
          <dd>{etiquetaDia(turno.fecha)}</dd>
          <dt>Horario</dt>
          <dd>{horaLocal(turno.inicio)} – {horaLocal(turno.fin)}{diaSiguiente ? " (+1 día)" : ""} · {turno.duracionHoras} h</dd>
          <dt>{secundario ? "Cubre" : "Titular"}</dt>
          <dd>{secundario ? `${principal}, ${secundario}` : turno.titular ? principal : "Sin titular (baja)"}</dd>
          {estado.etiqueta && (
            <>
              <dt>Estado</dt>
              <dd><strong>{estado.etiqueta}</strong></dd>
            </>
          )}
          {turno.vacante && (
            <>
              <dt>Vacante</dt>
              <dd>Generada por {turno.vacante.generadaPor.nombre}</dd>
            </>
          )}
        </dl>
        {(puede("AVISAR_AUSENCIA") || puede("GENERAR_VACANTE")) && (
          <form onSubmit={avisar} noValidate>
            <label>
              Motivo (solo lo ven los coordinadores)
              <input value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={500} />
            </label>
            {intentoSinMotivo && !motivo.trim() && <p role="alert" className="error">Escribí el motivo de la ausencia.</p>}
            <button type="submit" disabled={haciendo}>{haciendo ? "Enviando…" : puede("GENERAR_VACANTE") ? "Generar vacante" : "Avisar ausencia"}</button>
          </form>
        )}
        {(puede("RETIRAR_AVISO") || puede("RETIRAR_VACANTE")) && (
          <button type="button" disabled={haciendo} onClick={() => ejecutar(() => acciones.retirarAviso(turno.vacante.id))}>
            {puede("RETIRAR_VACANTE") ? "Retirar vacante" : "Retirar aviso"}
          </button>
        )}
        {puede("POSTULARME") && <button type="button" disabled={haciendo} onClick={() => ejecutar(() => acciones.postularme(turno.id))}>Postularme</button>}
        {puede("RETIRAR_POSTULACION") && <button type="button" disabled={haciendo} onClick={() => ejecutar(() => acciones.retirarPostulacion(turno.miPostulacionId))}>Retirar postulación</button>}
        {panel}
        {accionError && <p role="alert" className="error">{accionError}</p>}
        <button type="button" className="secundario" onClick={onCerrar}>Cerrar</button>
      </section>
    </div>
  );
}
