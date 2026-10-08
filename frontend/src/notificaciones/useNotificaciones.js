import { useCallback, useEffect, useRef, useState } from "react";

export const INTERVALO_MS = 12_000; // D05: la interfaz consulta cada 10 a 15 segundos

// Consulta GET /api/notificaciones cada INTERVALO_MS. Un fallo de red conserva lo último que se vio y
// reintenta en el próximo ciclo. Las vacantes urgentes sin leer se ofrecen una sola vez como aviso emergente.
export function useNotificaciones(api, { intervaloMs = INTERVALO_MS } = {}) {
  const [lista, setLista] = useState([]);
  const [urgentes, setUrgentes] = useState([]);
  const mostradas = useRef(new Set());

  const refrescar = useCallback(async () => {
    try {
      const nuevas = await api.get("/api/notificaciones");
      setLista(nuevas);
      const sinMostrar = nuevas.filter((n) => n.tipo === "VACANTE_URGENTE" && !n.leidaEn && !mostradas.current.has(n.id));
      if (sinMostrar.length > 0) {
        sinMostrar.forEach((n) => mostradas.current.add(n.id));
        setUrgentes((previas) => [...previas, ...sinMostrar]);
      }
    } catch {
      // se reintenta en el próximo ciclo
    }
  }, [api]);

  useEffect(() => {
    let activo = true;
    const ciclo = () => activo && refrescar();
    ciclo();
    const reloj = setInterval(ciclo, intervaloMs);
    return () => {
      activo = false;
      clearInterval(reloj);
    };
  }, [refrescar, intervaloMs]);

  const marcarLeida = useCallback(
    async (id) => {
      const leida = await api.post(`/api/notificaciones/${id}/leida`);
      setLista((previa) => previa.map((n) => (n.id === id ? { ...n, leidaEn: leida?.leidaEn ?? new Date().toISOString() } : n)));
      setUrgentes((previas) => previas.filter((n) => n.id !== id));
    },
    [api],
  );

  const marcarTodas = useCallback(async () => {
    const pendientes = lista.filter((n) => !n.leidaEn);
    const resultados = await Promise.allSettled(pendientes.map((n) => marcarLeida(n.id)));
    const fallo = resultados.find((r) => r.status === "rejected");
    if (fallo) throw fallo.reason;
  }, [lista, marcarLeida]);

  const descartarUrgente = useCallback((id) => setUrgentes((previas) => previas.filter((n) => n.id !== id)), []);

  return { lista, noLeidas: lista.filter((n) => !n.leidaEn).length, urgentes, marcarLeida, marcarTodas, descartarUrgente };
}
