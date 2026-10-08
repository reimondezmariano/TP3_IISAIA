import { useCallback, useState } from "react";
import { derivarEstado } from "./vacantes.js";

// Estado en memoria de las acciones simuladas; se pierde al recargar la pestaña.
export function useVacantesSimuladas({ usuario, ahora }) {
  const [overrides, setOverrides] = useState({});
  const cambiar = useCallback(
    (turnoId, parche) => setOverrides((previo) => ({ ...previo, [turnoId]: { ...previo[turnoId], ...parche } })),
    [],
  );

  return {
    estadoDe: (turno) => derivarEstado({ turno, usuario, ahora, override: overrides[turno.id] }),
    avisarAusencia: (turnoId, motivo) => cambiar(turnoId, { vacante: true, motivo }),
    retirarAviso: (turnoId) => cambiar(turnoId, { vacante: false, motivo: undefined }),
    postularme: (turnoId) => cambiar(turnoId, { postulado: true }),
    retirarPostulacion: (turnoId) => cambiar(turnoId, { postulado: false }),
  };
}
