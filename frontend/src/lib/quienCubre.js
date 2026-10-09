// Quién hace la guardia (D31): si hay asignado, él es el nombre principal y el titular pasa a dato secundario.
// Sin asignado (o si el asignado es el propio titular) se muestra el titular, o "Sin titular" en BAJA.
export function quienCubre(turno) {
  const { titular, asignado } = turno;
  if (asignado && asignado.id !== titular?.id) {
    return { principal: asignado.nombre, secundario: titular ? `cubre a ${titular.nombre}` : "cubre por baja del titular" };
  }
  return { principal: titular ? titular.nombre : "Sin titular", secundario: null };
}
