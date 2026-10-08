const GENERICO = "No se pudo completar la operación. Probá de nuevo.";

export function traducirErrorAuth(error) {
  const codigo = error?.code ?? "";
  const mensaje = error?.message ?? "";
  if (codigo === "invalid_credentials" || /invalid login credentials/i.test(mensaje)) return "Email o contraseña incorrectos.";
  if (codigo === "user_already_exists" || /already registered/i.test(mensaje)) return "Ese email ya tiene una cuenta. Ingresá con tu contraseña.";
  if (codigo === "weak_password" || /password should be/i.test(mensaje)) return "La contraseña es muy débil: usá al menos 6 caracteres.";
  if (codigo === "over_request_rate_limit" || codigo === "over_email_send_rate_limit" || error?.status === 429) {
    return "Demasiados intentos. Esperá un momento y probá de nuevo.";
  }
  if (error?.name === "AuthRetryableFetchError" || /failed to fetch|network/i.test(mensaje)) {
    return "No se pudo conectar con el servicio de ingreso. Revisá tu conexión.";
  }
  return GENERICO;
}
