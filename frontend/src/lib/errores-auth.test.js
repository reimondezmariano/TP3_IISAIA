import { expect, test } from "vitest";
import { traducirErrorAuth } from "./errores-auth.js";

test.each([
  [{ code: "invalid_credentials", message: "Invalid login credentials" }, "Email o contraseña incorrectos."],
  [{ message: "Invalid login credentials" }, "Email o contraseña incorrectos."],
  [{ code: "user_already_exists", message: "User already registered" }, "Ese email ya tiene una cuenta. Ingresá con tu contraseña."],
  [{ message: "User already registered" }, "Ese email ya tiene una cuenta. Ingresá con tu contraseña."],
  [{ code: "weak_password", message: "Password should be at least 6 characters" }, "La contraseña es muy débil: usá al menos 6 caracteres."],
  [{ code: "over_request_rate_limit", message: "x" }, "Demasiados intentos. Esperá un momento y probá de nuevo."],
  [{ name: "AuthRetryableFetchError", message: "Failed to fetch" }, "No se pudo conectar con el servicio de ingreso. Revisá tu conexión."],
  [{ message: "algo raro" }, "No se pudo completar la operación. Probá de nuevo."],
])("traduce %j", (error, esperado) => {
  expect(traducirErrorAuth(error)).toBe(esperado);
});
