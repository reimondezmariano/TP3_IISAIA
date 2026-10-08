// Semáforo de cada guardia (D08): se calcula con lo que trae GET /api/turnos, no se guarda.
// BAJA (D24) va primero: un horario sin titular es rojo aunque además tenga una vacante.
export const ESTADOS = [
  { clase: "cubierta", nombre: "Cubierta" },
  { clase: "vacante", nombre: "Vacante abierta" },
  { clase: "urgente", nombre: "Vacante urgente" },
  { clase: "baja", nombre: "BAJA (sin titular)" },
];

export function semaforo(turno) {
  if (turno.titular === null) return { clase: "baja", etiqueta: "BAJA" };
  if (turno.vacante?.urgente) return { clase: "urgente", etiqueta: "Vacante urgente" };
  if (turno.vacante) return { clase: "vacante", etiqueta: "Vacante" };
  return { clase: "cubierta", etiqueta: null };
}
