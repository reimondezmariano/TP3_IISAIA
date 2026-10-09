// Semáforo de cada guardia (D08): se calcula con lo que trae GET /api/turnos, no se guarda.
// Un turno marcado sin cobertura (D19) tiene su propio color. BAJA (D24) va después: un horario sin titular es rojo aunque además tenga una vacante,
// salvo que haya postulantes (D34): entonces es ámbar y conserva la etiqueta BAJA.
export const ESTADOS = [
  { clase: "cubierta", nombre: "Cubierta" },
  { clase: "vacante", nombre: "Vacante abierta" },
  { clase: "urgente", nombre: "Vacante urgente" },
  { clase: "baja", nombre: "BAJA (sin titular)" },
  { clase: "baja-postulantes", nombre: "BAJA con postulantes" },
  { clase: "sin-cobertura", nombre: "Sin cobertura" },
];

export function semaforo(turno) {
  if (turno.sinCobertura) return { clase: "sin-cobertura", etiqueta: "Sin cobertura" };
  if (turno.titular === null && cantidadPostulantes(turno) > 0) return { clase: "baja-postulantes", etiqueta: "BAJA" };
  if (turno.titular === null) return { clase: "baja", etiqueta: "BAJA" };
  if (turno.vacante?.urgente) return { clase: "urgente", etiqueta: "Vacante urgente" };
  if (turno.vacante) return { clase: "vacante", etiqueta: "Vacante" };
  return { clase: "cubierta", etiqueta: null };
}

export function cantidadPostulantes(turno) {
  return turno.cantidadPostulantes ?? 0;
}

export function textoPostulantes(turno) {
  const n = cantidadPostulantes(turno);
  if (n === 0) return null;
  return `${n} ${n === 1 ? "postulante" : "postulantes"}`;
}
