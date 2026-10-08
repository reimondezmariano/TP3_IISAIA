import { useCallback } from "react";
import { ErrorApi } from "../lib/api.js";
import { postular as postularApi, retirarPostulacion } from "../lib/postulaciones.js";

// Códigos con los que el servidor dice que la postulación ya no está para retirar: el calendario se recarga igual.
const YA_NO_VIGENTE = ["POSTULACION_YA_RETIRADA", "POSTULACION_NO_ENCONTRADA"];

// `alCambiar` recarga los turnos: la postulación propia de cada turno (`miPostulacionId`) la informa el servidor.
export function usePostulaciones(api, { alCambiar = () => {} } = {}) {
  const postular = useCallback(
    async (turnoId) => {
      const postulacion = await postularApi(api, turnoId);
      await alCambiar();
      return postulacion;
    },
    [api, alCambiar],
  );

  const retirar = useCallback(
    async (postulacionId) => {
      try {
        await retirarPostulacion(api, postulacionId);
      } catch (error) {
        if (error instanceof ErrorApi && YA_NO_VIGENTE.includes(error.codigo)) await alCambiar();
        throw error;
      }
      await alCambiar();
    },
    [api, alCambiar],
  );

  return { postular, retirar };
}
