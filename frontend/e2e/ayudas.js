const b64 = (objeto) => Buffer.from(JSON.stringify(objeto)).toString("base64url");

export function tokenFalso(email) {
  const ahora = Math.floor(Date.now() / 1000);
  return `${b64({ alg: "HS256", typ: "JWT" })}.${b64({ sub: `id-${email}`, email, aud: "authenticated", role: "authenticated", iat: ahora, exp: ahora + 3600 })}.firma`;
}

function sesionDe(email) {
  const ahora = Math.floor(Date.now() / 1000);
  return {
    access_token: tokenFalso(email),
    token_type: "bearer",
    expires_in: 3600,
    expires_at: ahora + 3600,
    refresh_token: "refresco",
    user: { id: `id-${email}`, aud: "authenticated", role: "authenticated", email, app_metadata: {}, user_metadata: {}, created_at: "2026-10-01T00:00:00Z" },
  };
}

export async function simularSupabase(page, { usuarios = { "ana@x.com": "secreto1" } } = {}) {
  await page.route("**/auth/v1/**", async (ruta) => {
    const peticion = ruta.request();
    const url = new URL(peticion.url());
    const json = (status, cuerpo) => ruta.fulfill({ status, contentType: "application/json", body: JSON.stringify(cuerpo) });
    if (url.pathname.endsWith("/token")) {
      const { email, password } = peticion.postDataJSON();
      if (usuarios[email] === password) return json(200, sesionDe(email));
      return json(400, { code: "invalid_credentials", error_code: "invalid_credentials", msg: "Invalid login credentials", message: "Invalid login credentials" });
    }
    if (url.pathname.endsWith("/signup")) {
      const { email } = peticion.postDataJSON();
      return json(200, sesionDe(email));
    }
    if (url.pathname.endsWith("/logout")) return ruta.fulfill({ status: 204 });
    return json(404, { message: "no simulado" });
  });
}

// `extra(url, peticion, json)` resuelve las rutas propias de cada prueba; si devuelve undefined, sigue el flujo común.
export async function simularApi(page, { me, turnos = [], ahora = "2026-10-07T10:00:00-03:00", registro, extra, notificaciones = [] } = {}) {
  const pedidos = [];
  await page.route("**/api/**", async (ruta) => {
    const peticion = ruta.request();
    const url = new URL(peticion.url());
    const authorization = peticion.headers()["authorization"] ?? null;
    pedidos.push({ metodo: peticion.method(), ruta: url.pathname, consulta: url.search, authorization, cuerpo: peticion.postData() });
    const json = (status, cuerpo) => ruta.fulfill({ status, contentType: "application/json", body: JSON.stringify(cuerpo) }).then(() => true);
    if (url.pathname === "/api/health") return json(200, { estado: "ok", base: "ok", ahora });
    if (!authorization?.startsWith("Bearer ")) return json(401, { codigo: "SIN_SESION", mensaje: "Falta el token de sesión." });
    if (url.pathname === "/api/me") {
      const valor = typeof me === "function" ? me(pedidos) : me;
      return valor.status ? json(valor.status, valor.cuerpo) : json(200, valor);
    }
    if (url.pathname === "/api/registro") {
      const respuesta = registro ? registro(peticion.postDataJSON()) : { status: 201, cuerpo: me };
      return json(respuesta.status, respuesta.cuerpo);
    }
    if (url.pathname === "/api/notificaciones") return json(200, typeof notificaciones === "function" ? notificaciones() : notificaciones);
    const propia = extra ? await extra(url, peticion, json) : undefined;
    if (propia) return;
    if (url.pathname === "/api/turnos") return json(200, typeof turnos === "function" ? turnos(url.searchParams) : turnos);
    return json(404, { codigo: "NO_ENCONTRADO", mensaje: "No existe." });
  });
  return pedidos;
}
