# Cómo publicar Guardia Viva (Render + Supabase)

Guía para quien nunca usó Render. Los nombres de los menús de los paneles pueden cambiar un poco con el tiempo: si algo no aparece donde dice, buscá una opción con el mismo nombre en la misma sección.

**Regla de oro:** nunca pegues claves, contraseñas ni el código de coordinación en el chat, en un mensaje ni en un archivo del repositorio. Se cargan solo en los paneles y en tu archivo `backend/.env` (que git ignora).

## 1. Qué es cada pieza

- **Supabase** guarda los datos (turnos, médicos, vacantes) y las cuentas de usuario (email y contraseña). Ya está creado.
- **Render** es la computadora en internet donde corre la app. Va a mostrar la pantalla y, por debajo, atender los pedidos de la pantalla (`/api`). Todo en un solo servicio.
- **GitHub** conecta las dos puntas: cada vez que se une un cambio a la rama `main`, Render vuelve a publicar la app solo.

## 2. Supabase: configuración que se hace una sola vez

En el panel del proyecto, en supabase.com:

1. **Authentication**, **Sign In / Providers**, **Email**: apagá **Confirm email** y apretá **Save changes**. Es para que al crear una cuenta no haga falta confirmarla por mail (D06). No toques lo demás.
2. **Project Settings**, **API**: copiá y guardá en un lugar privado la **Project URL** y la clave **anon public** (la pública, no la `service_role`).
3. **Project Settings**, **Database**: copiá la cadena de conexión **Session pooler** (empieza con `postgresql://`; tiene una contraseña adentro, tratala como secreta).
4. Más adelante (paso 6): **Authentication**, **URL Configuration**: poner la dirección que te dé Render en **Site URL**.

## 3. Supabase: aplicar las migraciones (desde tu computadora, una sola vez y al final)

Esto cambia la base real. **No lo hagas hasta que estén mergeados la etapa 3 de F3 y todo lo demás que cambie las tablas**, para migrar todo junto. Las migraciones se aplican desde tu computadora porque el plan gratis de Render no tiene un paso previo al despliegue.

1. Abrí `backend/.env` y poné la cadena del Session pooler en `DATABASE_URL`. **Anotá cuál era el valor anterior** (la base local) para poder volver.
2. Desde la carpeta `backend`, mirá a qué base apunta y en qué versión está. Tiene que decir tu proyecto de Supabase y no `localhost`:

   ```bash
   .venv/Scripts/python -c "from app.config import get_settings; print(get_settings().database_url.split('@')[-1])"
   .venv/Scripts/alembic current
   ```

   La versión actual tiene que ser `0001`. Si dice otra cosa o la base no es la que esperás, **pará acá** y avisá.
3. Aplicá las migraciones pendientes:

   ```bash
   .venv/Scripts/alembic upgrade head
   .venv/Scripts/alembic current
   ```

   Tiene que terminar en la última versión pendiente (hoy `0004`).
4. Volvé `DATABASE_URL` al valor anterior (la base local) si vas a seguir trabajando en tu computadora.

### Datos de ejemplo (opcional)

El script de datos de ejemplo **borra todo lo que haya** y carga médicos, horarios y un coordinador de prueba. Con `DATABASE_URL` apuntando a Supabase:

```bash
.venv/Scripts/python -m scripts.seed --confirmar
```

Usalo solo antes de la demo o para reiniciarla. No lo corras si ya hay cuentas o datos reales que quieras conservar.

## 4. Render: crear el servicio (una sola vez)

1. Entrá a render.com con tu cuenta de GitHub y dale permiso **solo a este repositorio**.
2. **New**, **Blueprint**, elegí el repositorio y la rama `main`. Render lee el archivo `render.yaml` y propone el servicio `guardia-viva` en el plan **Free**.
3. Render te va a pedir los valores de las variables que no están en el archivo. Cargalas a mano:

   | Variable | De dónde sale |
   |---|---|
   | `DATABASE_URL` | Cadena del **Session pooler** de Supabase (paso 2.3) |
   | `SUPABASE_URL` | **Project URL** (paso 2.2) |
   | `SUPABASE_JWT_SECRET` | Dejala vacía, salvo que el proyecto de Supabase todavía firme con secreto JWT (**Project Settings**, **API**, **JWT Settings**) |
   | `CODIGO_COORDINACION` | El código del servicio que usa el equipo (D30). Pedíselo al equipo, no lo pegues en ningún chat |
   | `VITE_SUPABASE_URL` | La misma **Project URL** |
   | `VITE_SUPABASE_ANON_KEY` | La clave **anon public** (paso 2.2) |

   `APP_TIMEZONE` y `MODO_DEMO` ya vienen puestas.
4. Apretá **Apply** (o **Deploy**). La primera publicación tarda varios minutos: Render compila la pantalla y arma el servicio.
5. Cuando diga **Live**, abrí la dirección que te da Render (algo como `https://guardia-viva-xxxx.onrender.com`). Tiene que cargar la pantalla de acceso.

## 5. Después de publicar

1. Copiá esa dirección en Supabase, **Authentication**, **URL Configuration**, **Site URL**, y guardá.
2. Probá desde el celular: crear una cuenta, entrar y ver el calendario.
3. **Antes de presentar:** el plan gratis duerme el servicio después de unos 15 minutos sin uso, y el primer pedido tarda hasta un minuto en despertarlo. Abrí la app unos minutos antes de empezar. Los límites exactos se ven en el panel de Render.
4. **Reiniciar la demo:** el comando de datos de ejemplo de la sección 3, con `DATABASE_URL` apuntando a Supabase.
5. **Cuando termine la presentación:** en Render, **Environment**, poné `MODO_DEMO` en `false`.

## 6. Si algo falla

- **La pantalla queda en blanco o dice "Falta configurar VITE_SUPABASE_URL…":** falta cargar `VITE_SUPABASE_URL` o `VITE_SUPABASE_ANON_KEY`. Esas dos se incrustan al compilar, así que después de cargarlas hay que volver a publicar (**Manual Deploy**, **Deploy latest commit**). Si las cargaste y sigue igual, puede que Render no las pase a la compilación: avisá, hay una alternativa.
- **"Falta configurar SUPABASE_URL" o error 503 al entrar:** falta `SUPABASE_URL` en el servicio.
- **El servicio dice "Failed" o no pasa a Live:** abrí **Logs** en Render. Si dice que no se puede conectar a la base, revisá `DATABASE_URL` (que sea la del Session pooler y esté completa).
- **Volver a la versión anterior:** en Render, **Events** o **Deploys**, elegí un despliegue anterior y **Rollback**.

## 7. Qué NO hacer

- Pegar claves, la cadena de la base o el código de coordinación en el chat, en un issue, en un PR o en un archivo del repositorio.
- Apuntar las pruebas (`TEST_DATABASE_URL`) a Supabase: las pruebas borran y recrean la base. Solo corren contra el Postgres local.
- Correr el seed o las migraciones sin haber mirado antes a qué base apunta `DATABASE_URL`.
- Aplicar migraciones de a una, a medida que se mergean los PR: se aplican todas juntas, una sola vez, al final.
