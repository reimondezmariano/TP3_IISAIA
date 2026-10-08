import { useCallback, useEffect, useState } from "react";
import { ErrorApi } from "../lib/api.js";
import { rangoSemana } from "../lib/fechas.js";

const CUENTA_CAMBIADA = ["CUENTA_PENDIENTE", "CUENTA_DADA_DE_BAJA"];

export function useTurnosSemana(api, lunes, { alCuentaCambiada }) {
  const [resultado, setResultado] = useState({ estado: "cargando", turnos: [], error: null });
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    let vigente = true; // si cambia la semana o se desmonta, la respuesta se descarta
    setResultado((previo) => ({ ...previo, estado: "cargando", error: null }));
    api
      .get("/api/turnos", rangoSemana(lunes))
      .then((turnos) => vigente && setResultado({ estado: "ok", turnos, error: null }))
      .catch((error) => {
        if (!vigente) return;
        if (error instanceof ErrorApi && CUENTA_CAMBIADA.includes(error.codigo)) alCuentaCambiada();
        setResultado({ estado: "error", turnos: [], error });
      });
    return () => {
      vigente = false;
    };
    // alCuentaCambiada no debe re-disparar el pedido.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, lunes, intento]);

  const reintentar = useCallback(() => setIntento((n) => n + 1), []);
  return { ...resultado, reintentar };
}
