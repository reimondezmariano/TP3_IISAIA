import { useEffect, useState } from "react";
import { fechaLocal } from "../lib/fechas.js";

const nombreDelMes = (mes) =>
  new Date(`${mes}-01T12:00:00Z`).toLocaleDateString("es-AR", { month: "long", year: "numeric", timeZone: "UTC" });

// Horas sin cobertura del mes corriente (D19), solo para coordinadores. El mes sale del reloj del servidor.
export default function IndicadorSinCobertura({ api, ahora }) {
  const mes = fechaLocal(ahora).slice(0, 7);
  const [estado, setEstado] = useState({ cargando: true, datos: null });

  useEffect(() => {
    let vigente = true;
    api
      .get("/api/indicadores/sin-cobertura", { desde: mes, hasta: mes })
      .then((filas) => vigente && setEstado({ cargando: false, datos: filas.find((f) => f.mes === mes) ?? { mes, horas: 0, turnos: 0 } }))
      .catch(() => vigente && setEstado({ cargando: false, datos: null }));
    return () => {
      vigente = false;
    };
  }, [api, mes]);

  if (estado.cargando) return null;
  if (!estado.datos) return <p className="chico">No se pudo cargar el indicador de horas sin cobertura.</p>;
  const { horas, turnos } = estado.datos;
  return (
    <p className="chico" data-testid="indicador-sin-cobertura">
      {horas} h sin cobertura en {nombreDelMes(mes)} ({turnos} {turnos === 1 ? "turno" : "turnos"})
    </p>
  );
}
