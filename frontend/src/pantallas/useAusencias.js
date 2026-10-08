import { useCallback } from "react";
import { ErrorApi } from "../lib/api.js";
import { generarLote, generarVacante, retirarVacante } from "../lib/vacantes.js";

// Códigos con los que el servidor dice que la vacante ya no está para retirar: el calendario se recarga igual.
const YA_NO_ABIERTA = ["VACANTE_NO_ABIERTA", "VACANTE_NO_ENCONTRADA"];

// `alCambiar` recarga los turnos: la vacante abierta de cada turno la informa el servidor.
export function useAusencias(api, usuario, { alCambiar = () => {} } = {}) {
  const avisar = useCallback(
    async (turnoId, motivo) => {
      const vacante = await generarVacante(api, turnoId, motivo);
      await alCambiar();
      return vacante;
    },
    [api, alCambiar],
  );

  const retirar = useCallback(
    async (vacanteId) => {
      try {
        await retirarVacante(api, vacanteId);
      } catch (error) {
        if (error instanceof ErrorApi && YA_NO_ABIERTA.includes(error.codigo)) await alCambiar();
        throw error;
      }
      await alCambiar();
    },
    [api, alCambiar],
  );

  // Un coordinador usa el lote (todo o nada). El servidor no le permite el lote a un médico: una por una,
  // y se informa qué fechas quedaron y cuáles no.
  const avisarVarios = useCallback(
    async (turnoIds, motivo) => {
      if (usuario.rol === "COORDINADOR") {
        const { vacantes } = await generarLote(api, turnoIds, motivo);
        await alCambiar();
        return { ok: vacantes.map((v) => v.turnoId), fallaron: [] };
      }
      const ok = [];
      const fallaron = [];
      for (const turnoId of turnoIds) {
        try {
          await generarVacante(api, turnoId, motivo);
          ok.push(turnoId);
        } catch (error) {
          if (!(error instanceof ErrorApi)) throw error;
          fallaron.push({ turnoId, mensaje: error.message });
        }
      }
      if (ok.length > 0) await alCambiar();
      return { ok, fallaron };
    },
    [api, alCambiar, usuario.rol],
  );

  return { avisar, retirar, avisarVarios };
}
