import { useCallback, useEffect, useRef, useState } from "react";
import { ErrorApi } from "../lib/api.js";
import { rangoSemana } from "../lib/fechas.js";

const CUENTA_CAMBIADA = ["CUENTA_PENDIENTE", "CUENTA_DADA_DE_BAJA"];

export const INTERVALO_MS = 15_000; // el calendario se actualiza solo, igual que las notificaciones (D05)

// Pide los turnos de una semana (lunes a domingo) o, con `hasta`, del rango que empieza en `lunes` (la grilla del mes).
export function useTurnosSemana(api, lunes, { alCuentaCambiada, intervaloMs = INTERVALO_MS, hasta = null }) {
  const rango = hasta ? { desde: lunes, hasta } : rangoSemana(lunes);
  const [resultado, setResultado] = useState({ estado: "cargando", turnos: [], error: null });
  const [intento, setIntento] = useState(0);
  const silencioso = useRef(false); // refrescar: vuelve a pedir sin ocultar la semana que ya se ve

  useEffect(() => {
    let vigente = true; // si cambia la semana o se desmonta, la respuesta se descarta
    if (!silencioso.current) setResultado((previo) => ({ ...previo, estado: "cargando", error: null }));
    silencioso.current = false;
    api
      .get("/api/turnos", rango)
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
  }, [api, lunes, hasta, intento]);

  // Refresco periódico: un fallo conserva lo que se ve y reintenta en el próximo ciclo (salvo que la cuenta haya cambiado).
  useEffect(() => {
    let vigente = true;
    const reloj = setInterval(() => {
      api
        .get("/api/turnos", rango)
        .then((turnos) => vigente && setResultado({ estado: "ok", turnos, error: null }))
        .catch((error) => {
          if (vigente && error instanceof ErrorApi && CUENTA_CAMBIADA.includes(error.codigo)) alCuentaCambiada();
        });
    }, intervaloMs);
    return () => {
      vigente = false;
      clearInterval(reloj);
    };
    // alCuentaCambiada no debe reiniciar el reloj.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, lunes, hasta, intervaloMs]);

  const reintentar = useCallback(() => setIntento((n) => n + 1), []);
  const refrescar = useCallback(() => {
    silencioso.current = true;
    setIntento((n) => n + 1);
  }, []);
  return { ...resultado, reintentar, refrescar };
}
