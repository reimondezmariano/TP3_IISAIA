# Prompt — TP Final: Sistema de gestión de guardias médicas

## Contexto y problema a resolver

Diseñar y especificar una aplicación (móvil + web) para reemplazar el sistema actual de gestión de guardias médicas de un servicio hospitalario, que hoy se maneja con:
- Un grupo de WhatsApp donde se avisan ausencias y se ofrecen guardias.
- Una planilla de Excel que un coordinador actualiza a mano cada vez que algo cambia, cada pocos minutos.

El objetivo es digitalizar y automatizar ese flujo, centralizando tanto la gestión como las notificaciones dentro de la propia aplicación (ver sección de notificaciones más abajo), y reemplazando el Excel por un calendario en tiempo real dentro de la propia aplicación.

## Datos del dominio

- El equipo de guardia está compuesto por **entre 10 y 12 médicos**.
- Las guardias tienen **duración variable**: 6, 7, 8, 12 o 24 horas. No hay una duración fija, por lo que cada turno se define con **fecha/hora de inicio** y **fecha/hora de fin** (dos campos separados, no solo una franja horaria dentro de un mismo día).
- Un turno puede **cruzar la medianoche** (ej: sábado 18:00 a domingo 06:00). Es una única entidad con un único estado; visualmente se representa en ambos días que ocupa, pero en los datos es un solo registro.
- A una hora determinada del día puede haber **más de 10 médicos trabajando en simultáneo**, porque los turnos del servicio se superponen entre sí (no hay un único médico de guardia por franja horaria).
- Cada médico se identifica solo con **nombre y apellido** (no hace falta teléfono ni otros datos: el contacto ya lo resuelve la propia aplicación, ver notificaciones).

## Plantilla base de guardia (dato estructural, no gestionado turno por turno)

Este es un concepto central del diseño, distinto de la lógica de vacantes: la guardia **ya está organizada de fondo, todo el año**, con cada médico teniendo asignado su día de la semana y horario fijo (por ejemplo, "todos los jueves de 9 a 16 horas"). Esta plantilla es un dato de base, cargado una vez por el coordinador al ingresar a cada médico, y no algo que se re-cargue turno por turno ni día por día.

- **Cada casillero de la plantilla (día de la semana + horario) tiene uno o más titulares posibles**, con una regla de asignación:
  - En el caso general (la gran mayoría de los casilleros), hay **un único titular fijo**.
  - Como excepción, que puede darse en **cualquier casillero sin poder anticiparse de antemano cuáles**, puede haber **más de un titular en rotación** (por ejemplo, dos médicos alternando semana por medio en el mismo día y horario). Por eso el mecanismo de la plantilla soporta, en todos los casos por diseño, una lista de uno o más titulares con su regla de alternancia, aunque en la enorme mayoría de los casilleros esa lista tenga un solo nombre.
- **El estado por defecto de todo turno de la plantilla es verde**: al ya tener un titular fijo (o el titular que corresponde según la rotación de esa semana), no requiere ninguna confirmación activa de nadie. El verde, en este caso, no significa "alguien confirmó hoy algo", sino simplemente "este lugar está ocupado".
- El semáforo (rojo / amarillo / verde) descrito más abajo actúa **por excepción, sobre esta base**: solo entra en juego cuando el titular correspondiente de un turno puntual avisa que no puede cubrirlo. Ahí, y solo ahí, ese casillero puntual pasa a rojo y arranca el flujo de vacante, cola de candidatos y confirmación. El resto de la plantilla sigue funcionando en verde sin intervención.
- Cuando la vacante puntual se cubre y se confirma, el turno vuelve a verde, pero con otro nombre asignado ese día específico; la plantilla base (quién es el titular "de fondo" ese día de la semana) no cambia por una vacante puntual cubierta.

## Roles de usuario

- **Médico**: puede generar una vacante (avisar que va a faltar a un turno propio) y tomar una vacante disponible (ofrecerse para cubrir un turno de otro).
- **Coordinador**: tiene todos los permisos de un médico, más la capacidad exclusiva de **confirmar o rechazar** a quien tomó una vacante, y la capacidad de **gestionar el estado de los médicos** (alta, baja/inactivación, reactivación, y edición de la plantilla base). Puede haber **más de un coordinador habilitado** (ej: para cubrir ausencias del coordinador titular, como vacaciones).
- El control de permisos debe ser doble: visual (el botón de confirmar/rechazar, o las opciones de gestión de médicos, no se muestran a médicos comunes) **y** del lado del servidor (el backend valida el rol antes de ejecutar la acción, sin confiar solo en la interfaz).

## Alta, baja e inactivación de médicos

- Un médico que deja la institución (renuncia, despido, fin de contrato) **no se borra** de la base de datos: se marca como **inactivo**. Borrarlo directamente rompería la trazabilidad de los turnos y vacantes históricos que ya tienen su nombre asociado.
- Efectos de pasar a un médico a estado inactivo:
  - **Pierde el acceso a la aplicación de inmediato**: aunque conserve credenciales válidas, el sistema le rechaza el login mientras esté inactivo. No existe ningún mecanismo de autogestión (como recuperación de contraseña) para revertir esto: la única forma de volver a entrar es que **un coordinador lo reactive manualmente**, pasándolo de nuevo a estado activo. Esto es intencional: alguien que ya no forma parte del equipo no debe seguir enterándose de la operación interna de las guardias (quién falta, quién cubre, etc.), por una cuestión de privacidad y seguridad, no solo organizativa.
  - Deja de estar disponible como candidato para tomar vacantes nuevas y no debería poder generar vacantes nuevas.
  - Sigue apareciendo, tal cual estaba, en el historial y en el calendario de meses pasados: la trazabilidad de quién trabajó cuándo no se altera retroactivamente.
  - El coordinador debe poder ver qué **turnos futuros de la plantilla base** tenían a ese médico como titular, para resolverlos: reasignar directamente esos casilleros a otro médico (por ejemplo, el que lo reemplaza en el puesto) o dejarlos temporalmente sin titular hasta asignar reemplazo.
- **Alta de un médico nuevo que reemplaza a uno que se fue**: como la guardia se gestiona sobre la plantilla base (no turno por turno), incorporar a alguien en el mismo día y horario que tenía el médico anterior es tan simple como que el coordinador actualice ese casillero de la plantilla con el nuevo nombre como titular. De ahí en adelante, todos los turnos futuros de ese casillero pasan a mostrar al médico nuevo en verde por defecto, sin necesidad de cargar nada turno por turno; los turnos ya pasados conservan el nombre del médico anterior.

## Estados de un turno (semáforo de tres colores)

Este semáforo aplica a la gestión de excepciones sobre la plantilla base (ver sección anterior), no a la operación normal de un turno ya cubierto por su titular.

1. **Rojo — Vacante libre**: el turno fue liberado por su médico titular y todavía nadie lo tomó, o quedó liberado tras agotarse la cola de candidatos.
2. **Amarillo — Pendiente de confirmación**: un médico tomó la vacante, pero el coordinador todavía no la confirmó ni la rechazó. Mientras está en amarillo, nadie más puede tomarla directamente (ver cola de candidatos, más abajo).
3. **Verde — Confirmado**: el turno está cubierto y cerrado, ya sea porque lo cubre su titular de plantilla sin ninguna novedad, o porque una vacante puntual fue tomada y confirmada por el coordinador.

### Regla de la cola de candidatos

- Si, mientras un turno está en rojo, más de un médico intenta tomarlo, **solo el primero en llegar al servidor** pasa a ocupar el turno (estado amarillo); los siguientes quedan anotados en una **cola en orden de llegada**, sin perder su interés.
- Si el coordinador **rechaza** al médico en amarillo, el turno **no vuelve directamente a rojo**: pasa automáticamente al **siguiente de la cola**, que queda en amarillo pendiente de confirmación.
- Este proceso se repite mientras haya candidatos en la cola.
- Si el coordinador rechaza al último candidato de la cola (no queda nadie más esperando), recién ahí el turno vuelve a **rojo**, libre para que cualquiera lo tome de nuevo desde cero.
- La concurrencia (dos médicos apretando el botón casi al mismo tiempo) se resuelve en el servidor con un mecanismo que procesa los pedidos de a uno por turno (bloqueo a nivel de base de datos), garantizando que nunca dos personas queden asignadas al mismo turno.

## Flujos principales

### 1. Generar vacante (médico titular avisa que falta)
1. El médico abre la app y toca **"Generar vacante"**.
2. Se abre un calendario donde elige el día (o rango de días si cruza medianoche) y la hora de inicio y fin del turno que no puede cubrir.
3. Al confirmar, ese turno pasa a **rojo** en el calendario, visible para todos.
4. Se dispara automáticamente una notificación dentro de la app avisando la vacante (día y horario), ver sección de notificaciones.

### 2. Tomar vacante (otro médico se ofrece a cubrirla)
1. El médico entra a la app, ve el calendario o la lista de vacantes en rojo, y toca **"Tomar vacante"** sobre la que le interesa.
2. Si nadie más la tomó antes, el turno pasa a **amarillo**, asignado provisoriamente a ese médico.
3. Se dispara una notificación automática dentro de la app: *"Vacante tomada por [nombre], pendiente de confirmación por coordinación."*
4. Si otro médico intenta tomarla mientras está en amarillo, queda anotado en la cola de candidatos (no ve un error confuso, sino que su pedido queda en espera).

### 3. Confirmar o rechazar (exclusivo del coordinador)
1. El coordinador ve, en su sección propia de la app, los turnos en amarillo pendientes de resolución.
2. Si aprieta **"Confirmar"**, el turno pasa a **verde**, cerrado con ese médico.
3. Si aprieta **"Rechazar"**:
   - Si hay alguien más en la cola de candidatos para ese turno, pasa automáticamente al siguiente, que queda en amarillo con su propia notificación.
   - Si no hay nadie más en la cola, el turno vuelve a **rojo**, libre de nuevo.

### 4. Liberar una vacante ya tomada
- Si un médico que tomó una vacante se arrepiente (mientras está en amarillo, antes de la confirmación), puede liberarla: el turno vuelve a quedar disponible para el siguiente candidato en cola, o a rojo si no hay cola.
- Se notifica dentro de la app que la vacante quedó liberada nuevamente.

### 5. Gestión de médicos (exclusivo del coordinador)
1. Alta de un médico nuevo: nombre y apellido, y asignación de su casillero (o casilleros) en la plantilla base.
2. Baja/inactivación: marca al médico como inactivo, bloqueando su acceso de inmediato, y muestra al coordinador los turnos futuros de plantilla donde ese médico era titular, para reasignarlos.
3. Reactivación: exclusiva del coordinador, vuelve a habilitar el acceso de un médico marcado como inactivo.
4. Edición de la plantilla base: cambiar el o los titulares de un casillero (día de la semana + horario), incluyendo la posibilidad de definir una rotación entre dos o más titulares con una regla de alternancia simple (por ejemplo, semana por medio).

## Vistas de la aplicación

### Vista mensual (resumen)
- Calendario tipo Google Calendar / Apple Calendar, navegable hacia meses futuros (incluye guardias planificadas con semanas o meses de anticipación, no solo el día a día inmediato).
- Cada casillero de día muestra **solo el número del día**, sin listar los turnos completos (sería ilegible con 10-12 médicos por día).
- Si ese día tiene algo que requiere atención (una vacante en rojo o un pendiente en amarillo), se muestra un **indicador visual pequeño** (punto o badge de color) en el casillero. Los días sin novedades (todo confirmado en verde, incluido el verde de plantilla base) no muestran alertas.

### Vista diaria (línea de tiempo / timeline)
- Al tocar un día desde la vista mensual, se abre el detalle de ese día como una **línea de tiempo horizontal de 24 horas**.
- Cada médico activo ese día tiene su propia fila/carril, con una barra que va desde su hora de entrada hasta su hora de salida.
- Las barras se pintan del color de estado correspondiente (verde confirmado o de plantilla base, amarillo pendiente, rojo vacante).
- Como puede haber más de 10 médicos simultáneos, esta vista debe soportar múltiples barras superpuestas en la misma franja horaria, cada una en su propia fila, para que se entienda de un vistazo quién está trabajando a una hora determinada.
- Formato preferentemente **apaisado/horizontal** (tanto en el celular rotado como naturalmente en la vista web), porque deja más espacio para desplegar las 24 horas sin amontonar la información.
- Se incluye una línea vertical indicando la hora actual ("ahora"), para ubicarse rápido en el día.

### Vista web (para computadora)
- No es una aplicación aparte ni de escritorio instalable: es una **página web** que consume el mismo backend y muestra la misma información en tiempo real que la app móvil.
- Pensada para pantallas grandes, aprovecha mejor la vista de línea de tiempo horizontal.
- Incluye función de **impresión** (usando la función nativa de impresión del navegador), para reemplazar el uso actual del Excel impreso o compartido.
- No requiere ningún paso de "exportar" a un archivo aparte: el calendario vive siempre actualizado en la web, no hay generación manual de documentos.

## Notificaciones (dentro de la propia aplicación)

Se descartó integrar con la API de WhatsApp Business como mecanismo de aviso automático: esa API está pensada para conversaciones uno a uno entre empresa y cliente, no soporta bien el envío a grupos sin costos y trámites de aprobación por mensaje, y hubiera significado depender de un servicio de terceros para algo central del sistema. En su lugar, la aplicación implementa su **propio sistema de notificaciones push** (por ejemplo, vía Firebase Cloud Messaging o Apple Push Notification), que le llegan a todos los médicos activos registrados, replicando el efecto de "aviso al grupo" pero de forma nativa, gratuita para este volumen de uso, y sin depender de infraestructura externa. Además, al ser parte de la propia app, la notificación puede llevar directo a la pantalla del turno correspondiente con las acciones ya disponibles (tomar, confirmar), algo que un simple mensaje de texto no permite.

| Evento | Notificación disparada |
|---|---|
| Se genera una vacante | Aviso de nueva vacante: día y horario |
| Un médico toma la vacante | "Vacante tomada por [nombre], pendiente de confirmación por coordinación" |
| El coordinador confirma | Aviso de vacante confirmada con el nombre del médico |
| El coordinador rechaza y pasa al siguiente de la cola | Mismo formato que "tomada", con el nuevo nombre |
| El coordinador rechaza y no hay más cola / se libera una vacante ya tomada | Aviso de vacante liberada nuevamente |

Los médicos inactivos no reciben ninguna notificación ni tienen acceso a la app (ver sección de alta, baja e inactivación).

## Decisiones de diseño ya tomadas (y su justificación)

- **Plantilla base de guardia como dato estructural de fondo**, distinta de la gestión de vacantes: evita que el coordinador tenga que recargar turno por turno, día por día, a los médicos que ya tienen un día y horario fijo asignado. El semáforo actúa solo por excepción sobre esa base.
- **Todo casillero de la plantilla soporta, por diseño, uno o más titulares con regla de alternancia**, aunque en la inmensa mayoría de los casos tenga uno solo: no se puede anticipar de antemano en qué casillero puntual va a aparecer un caso de rotación (por ejemplo, dos médicos alternando un sábado por medio), así que en vez de tratarlo como una excepción estructural aparte, se usa el mismo mecanismo en todos lados.
- **El verde es el estado por defecto de la plantilla, no algo que haya que confirmar activamente**: refleja que ese lugar está ocupado, sea por el titular fijo de siempre o por un reemplazo puntual ya cerrado.
- **Los médicos no se borran, se inactivan**: preserva la trazabilidad histórica de turnos y vacantes ya cerrados.
- **La inactivación bloquea el acceso a la aplicación de inmediato y sin autogestión posible**: un médico que dejó la institución no debe poder seguir viendo la operación interna del equipo; solo un coordinador puede reactivarlo.
- **Notificaciones push nativas de la aplicación en vez de integración con WhatsApp Business API**: evita costos por mensaje, trámites de aprobación ante Meta, y la limitación de que esa API no está pensada para mensajería grupal; además permite notificaciones más ricas (acceso directo a la pantalla de acción).
- **Login con roles (médico / coordinador)** en vez de esquemas más complejos (multi-factor, tokens con expiración, permisos granulares): el equipo es chico (10-12 personas conocidas) y dos roles alcanzan; no vale la pena sobre-diseñar la seguridad para este caso.
- **Turno con inicio y fin como dos campos de fecha/hora independientes**, no como "un día + un horario", para poder representar turnos que cruzan la medianoche sin partirlos en dos entidades.
- **Separación resumen mensual / detalle diario**, en vez de mostrar todo en la grilla del mes, porque con 10+ médicos por día la vista mensual se volvería ilegible.
- **Cola de candidatos en vez de volver a rojo ante cada rechazo**: evita perder tiempo y ofrece automáticamente el turno al siguiente interesado sin intervención manual del coordinador para "re-publicarlo".
- **Concurrencia resuelta en el servidor** (no confiar en que el cliente evite duplicados): el primer pedido que llega gana, los demás se encolan o reciben rechazo según corresponda.

## Pendiente de definir (para una próxima sesión)

- Terminar de pulir el diseño visual de las vistas (colores definitivos, tipografía, disposición exacta de botones).
- Definir el modelo de datos completo (entidades, atributos, relaciones) como paso previo a construir el contrato de API, incluyendo cómo modelar la plantilla base (casillero con uno o más titulares y regla de alternancia) y su relación con los turnos puntuales generados por excepción (siguiendo la misma lógica que se trabajó en el TP2 con OpenAPI: separar bien qué es lo que se pide y qué se genera del lado del servidor, elegir bien qué se anida y qué no, y qué códigos de estado corresponden a cada caso).
- Evaluar si hace falta persistir historial (quién tomó y liberó qué, para trazabilidad), o si alcanza con el estado actual de cada turno.
- Definir el mecanismo técnico concreto de las notificaciones push (proveedor, formato de payload, manejo de tokens de dispositivo).
- Analizar si el TP final requiere que esto esté vinculado a un Data Warehouse (idea mencionada al principio, todavía sin desarrollar).
