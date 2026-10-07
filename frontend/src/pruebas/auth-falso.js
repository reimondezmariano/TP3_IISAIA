import { vi } from "vitest";

export function sesionFalsa(email = "ana@x.com") {
  return { access_token: `tok-${email}`, user: { email } };
}

export function crearAuthFalso({ sesion = null } = {}) {
  let actual = sesion;
  const oyentes = new Set();
  const emitir = (evento, nueva) => {
    actual = nueva;
    oyentes.forEach((cb) => cb(evento, nueva));
  };
  return {
    emitir,
    getSession: vi.fn(async () => ({ data: { session: actual } })),
    onAuthStateChange: vi.fn((cb) => {
      oyentes.add(cb);
      return { data: { subscription: { unsubscribe: () => oyentes.delete(cb) } } };
    }),
    signInWithPassword: vi.fn(async ({ email }) => {
      const nueva = sesionFalsa(email);
      emitir("SIGNED_IN", nueva);
      return { data: { session: nueva }, error: null };
    }),
    signUp: vi.fn(async ({ email }) => {
      const nueva = sesionFalsa(email);
      emitir("SIGNED_IN", nueva);
      return { data: { session: nueva }, error: null };
    }),
    signOut: vi.fn(async () => {
      emitir("SIGNED_OUT", null);
      return { error: null };
    }),
  };
}
