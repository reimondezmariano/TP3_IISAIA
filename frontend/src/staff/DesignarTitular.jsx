import { useState } from "react";
import { useEnvio } from "../pantallas/useEnvio.js";

// Nuevo titular para un horario marcado BAJA (D24): abre una versión con el médico elegido.
export default function DesignarTitular({ medicos, desdePorDefecto, onDesignar }) {
  const [medicoId, setMedicoId] = useState("");
  const [desde, setDesde] = useState(desdePorDefecto);
  const { enviando, error, enviar } = useEnvio(async () => {
    if (!medicoId) throw new Error("Elegí el nuevo titular.");
    if (!desde) throw new Error("Elegí desde qué fecha.");
    await onDesignar({ desde, medicoId: Number(medicoId) });
  });
  return (
    <form onSubmit={enviar} noValidate>
      <label>
        Nuevo titular
        <select value={medicoId} onChange={(e) => setMedicoId(e.target.value)}>
          <option value="">Elegí un médico</option>
          {medicos.map((m) => (
            <option key={m.id} value={m.id}>{m.nombre}</option>
          ))}
        </select>
      </label>
      <label>
        Desde
        <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
      </label>
      {error && <p role="alert" className="error">{error}</p>}
      <button type="submit" disabled={enviando}>{enviando ? "Guardando…" : "Designar titular"}</button>
    </form>
  );
}
