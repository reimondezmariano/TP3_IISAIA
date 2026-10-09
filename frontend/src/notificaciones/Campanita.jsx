import { useState } from "react";
import { fechaLocal, horaLocal } from "../lib/fechas.js";

// Destino al tocar cada tipo de notificación; `onIr(destino)` lo resuelve la pantalla que la usa.
const DESTINOS = { NUEVO_REGISTRO: "staff" };

export default function Campanita({ notificaciones, onIr }) {
  const { lista, noLeidas, marcarLeida, marcarTodas } = notificaciones;
  const [abierta, setAbierta] = useState(false);
  const [error, setError] = useState(null);

  async function intentar(accion) {
    setError(null);
    try {
      await accion();
    } catch (e) {
      setError(e.message);
    }
  }

  async function abrir(n) {
    setAbierta(false);
    onIr(DESTINOS[n.tipo]);
    if (!n.leidaEn) await intentar(() => marcarLeida(n.id)); // el error no impide haber llegado a la pantalla
  }

  return (
    <div className="campanita">
      <button
        type="button"
        className="secundario"
        aria-expanded={abierta}
        aria-label={noLeidas > 0 ? `Notificaciones, ${noLeidas} sin leer` : "Notificaciones"}
        onClick={() => setAbierta((v) => !v)}
      >
        <span aria-hidden="true">🔔</span>
        {noLeidas > 0 && <span className="contador" data-testid="contador-notificaciones">{noLeidas}</span>}
      </button>
      {abierta && (
        <section className="panel-notificaciones" aria-label="Lista de notificaciones">
          {lista.length === 0 && <p className="vacio">No tenés notificaciones.</p>}
          {noLeidas > 0 && (
            <button type="button" className="secundario" onClick={() => intentar(marcarTodas)}>Marcar todas como leídas</button>
          )}
          {error && <p role="alert" className="error">{error}</p>}
          <ul>
            {lista.map((n) => (
              <li key={n.id} className={n.leidaEn ? "leida" : "no-leida"}>
                {onIr && DESTINOS[n.tipo] ? (
                  <button type="button" className="enlace-notificacion" onClick={() => abrir(n)}>{n.mensaje}</button>
                ) : (
                  <p>{n.mensaje}</p>
                )}
                <p className="chico">{fechaLocal(n.creadaEn)} {horaLocal(n.creadaEn)}</p>
                {!n.leidaEn && (
                  <button type="button" className="secundario" onClick={() => intentar(() => marcarLeida(n.id))}>Marcar leída</button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
