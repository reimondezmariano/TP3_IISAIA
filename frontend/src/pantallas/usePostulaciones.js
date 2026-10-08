import { useCallback, useState } from "react";
import { ErrorApi } from "../lib/api.js";
import { leerRecordadas, olvidar, postular as postularApi, recordar, retirarPostulacion } from "../lib/postulaciones.js";

// Códigos con los que el servidor dice que la postulación ya no está para retirar.
const YA_NO_VIGENTE = ["POSTULACION_YA_RETIRADA", "POSTULACION_NO_ENCONTRADA"];

export function usePostulaciones(api, usuario) {
  const [postuladas, setPostuladas] = useState(() => leerRecordadas(usuario.id));

  const postular = useCallback(
    async (turnoId) => {
      const postulacion = await postularApi(api, turnoId);
      recordar(usuario.id, turnoId, postulacion.id);
      setPostuladas((previas) => ({ ...previas, [turnoId]: postulacion.id }));
      return postulacion;
    },
    [api, usuario.id],
  );

  const retirar = useCallback(
    async (turnoId) => {
      const postulacionId = postuladas[turnoId];
      if (postulacionId === undefined) return;
      const olvidarLocal = () => {
        olvidar(usuario.id, turnoId);
        setPostuladas(({ [turnoId]: _quitada, ...resto }) => resto);
      };
      try {
        await retirarPostulacion(api, postulacionId);
      } catch (error) {
        if (error instanceof ErrorApi && YA_NO_VIGENTE.includes(error.codigo)) olvidarLocal();
        throw error;
      }
      olvidarLocal();
    },
    [api, postuladas, usuario.id],
  );

  return { postuladas, postular, retirar };
}
