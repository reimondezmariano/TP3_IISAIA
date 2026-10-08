import { useCallback, useState } from "react";
import { derivarEstado } from "./vacantes.js";

// Estado en memoria de las postulaciones simuladas; se pierde al recargar la pestaña. Las vacantes propias
// son reales: llegan en `reales` (turnoId -> id de vacante) desde useAusencias.
export function useVacantesSimuladas({ usuario, ahora, reales = {} }) {
  const [overrides, setOverrides] = useState({});
  const cambiar = useCallback(
    (turnoId, parche) => setOverrides((previo) => ({ ...previo, [turnoId]: { ...previo[turnoId], ...parche } })),
    [],
  );

  return {
    estadoDe: (turno) => {
      const override = reales[turno.id] === undefined ? overrides[turno.id] : { ...overrides[turno.id], vacante: true };
      return derivarEstado({ turno, usuario, ahora, override });
    },
    postularme: (turnoId) => cambiar(turnoId, { postulado: true }),
    retirarPostulacion: (turnoId) => cambiar(turnoId, { postulado: false }),
  };
}
