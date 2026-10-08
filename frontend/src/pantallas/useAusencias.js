import { useCallback, useState } from "react";
import { ErrorApi } from "../lib/api.js";
import { generarLote, generarVacante, leerRecordadas, olvidar, recordar, retirarVacante } from "../lib/vacantes.js";

// Códigos con los que el servidor dice que la vacante ya no está para retirar.
const YA_NO_ABIERTA = ["VACANTE_NO_ABIERTA", "VACANTE_NO_ENCONTRADA"];

export function useAusencias(api, usuario) {
  const [abiertas, setAbiertas] = useState(() => leerRecordadas(usuario.id));

  const avisar = useCallback(
    async (turnoId, motivo) => {
      const vacante = await generarVacante(api, turnoId, motivo);
      recordar(usuario.id, turnoId, vacante.id);
      setAbiertas((previas) => ({ ...previas, [turnoId]: vacante.id }));
      return vacante;
    },
    [api, usuario.id],
  );

  const retirar = useCallback(
    async (turnoId) => {
      const vacanteId = abiertas[turnoId];
      if (vacanteId === undefined) return;
      const olvidarLocal = () => {
        olvidar(usuario.id, turnoId);
        setAbiertas(({ [turnoId]: _quitada, ...resto }) => resto);
      };
      try {
        await retirarVacante(api, vacanteId);
      } catch (error) {
        if (error instanceof ErrorApi && YA_NO_ABIERTA.includes(error.codigo)) olvidarLocal();
        throw error;
      }
      olvidarLocal();
    },
    [api, abiertas, usuario.id],
  );

  // Un coordinador usa el lote (todo o nada). El servidor no le permite el lote a un médico: una por una,
  // y se informa qué fechas quedaron y cuáles no.
  const avisarVarios = useCallback(
    async (turnoIds, motivo) => {
      if (usuario.rol === "COORDINADOR") {
        const { vacantes } = await generarLote(api, turnoIds, motivo);
        return { ok: vacantes.map((v) => v.turnoId), fallaron: [] };
      }
      const ok = [];
      const fallaron = [];
      for (const turnoId of turnoIds) {
        try {
          await avisar(turnoId, motivo);
          ok.push(turnoId);
        } catch (error) {
          if (!(error instanceof ErrorApi)) throw error;
          fallaron.push({ turnoId, mensaje: error.message });
        }
      }
      return { ok, fallaron };
    },
    [api, avisar, usuario.rol],
  );

  return { abiertas, avisar, retirar, avisarVarios };
}
