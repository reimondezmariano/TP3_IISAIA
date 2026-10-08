import { createClient } from "@supabase/supabase-js";

// Supabase se usa solo para el login (D06, D07): los datos van por /api con el token de la sesión.
export function crearAuthSupabase() {
  const url = import.meta.env.VITE_SUPABASE_URL;
  const clave = import.meta.env.VITE_SUPABASE_ANON_KEY;
  if (!url || !clave) {
    throw new Error("Falta configurar VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY en frontend/.env.");
  }
  return createClient(url, clave).auth;
}
