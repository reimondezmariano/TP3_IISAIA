import { useCallback, useEffect, useState } from "react";

// Usuarios y horarios del servicio (D26) más las acciones de coordinación. Cada acción devuelve la
// respuesta del servidor (con los turnos afectados) y recarga las listas.
export function useStaff(api) {
  const [datos, setDatos] = useState({ estado: "cargando", usuarios: [], horarios: [], error: null });

  const cargar = useCallback(async () => {
    try {
      const [usuarios, horarios] = await Promise.all([api.get("/api/usuarios"), api.get("/api/horarios")]);
      setDatos({ estado: "ok", usuarios, horarios, error: null });
    } catch (error) {
      setDatos((previo) => ({ ...previo, estado: "error", error }));
    }
  }, [api]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const y = useCallback(
    async (pedido) => {
      const respuesta = await pedido();
      await cargar();
      return respuesta;
    },
    [cargar],
  );

  return {
    ...datos,
    recargar: cargar,
    activar: (id) => y(() => api.patch(`/api/usuarios/${id}`, { estado: "ACTIVO" })),
    cambiarRol: (id, rol) => y(() => api.patch(`/api/usuarios/${id}`, { rol })),
    darDeBaja: (id, fechaBaja) => y(() => api.post(`/api/usuarios/${id}/baja`, { fechaBaja })),
    crearHorario: (cuerpo) => y(() => api.post("/api/horarios", cuerpo)),
    nuevaVersion: (horarioId, cuerpo) => y(() => api.post(`/api/horarios/${horarioId}/versiones`, cuerpo)),
  };
}
