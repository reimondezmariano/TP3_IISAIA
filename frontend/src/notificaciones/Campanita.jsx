import { useState } from "react";
import { fechaLocal, horaLocal } from "../lib/fechas.js";

export default function Campanita({ notificaciones }) {
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
                <p>{n.mensaje}</p>
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
