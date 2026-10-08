import { useState } from "react";

// Aviso emergente de una vacante urgente (D05, D15). "Entendido" la marca como leída.
export default function AvisoUrgente({ notificaciones }) {
  const { urgentes, marcarLeida, descartarUrgente } = notificaciones;
  const [error, setError] = useState(null);
  const actual = urgentes[0];
  if (!actual) return null;

  async function entendido() {
    setError(null);
    try {
      await marcarLeida(actual.id);
    } catch (e) {
      setError(e.message);
      descartarUrgente(actual.id); // sigue sin leer en la campanita; no se vuelve a mostrar como emergente
    }
  }

  return (
    <div className="aviso-urgente" role="alert">
      <strong>Vacante urgente</strong>
      <p>{actual.mensaje}</p>
      {urgentes.length > 1 && <p className="chico">Y {urgentes.length - 1} más.</p>}
      {error && <p className="chico">{error}</p>}
      <button type="button" onClick={entendido}>Entendido</button>
    </div>
  );
}
