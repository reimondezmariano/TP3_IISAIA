# TP Final — Sistema de gestión de guardias médicas

**Grupo 7** — Ana María Florencia Lucca, Carlos Alejandro Lugones, Mariano Ezequiel Reimondez

Reemplazo del grupo de WhatsApp + planilla de Excel que hoy usa el servicio hospitalario
para gestionar guardias, por una aplicación (móvil + web) con calendario en tiempo real,
plantilla base de guardia, semáforo de vacantes (rojo/amarillo/verde) y notificaciones
push propias. Ver la especificación completa en
[`prompt_tp_final_v02.md`](prompt_tp_final_v02.md).

## Estado actual

**Etapa en curso: diseño de frontend.** Todavía no hay backend ni persistencia real —
el prototipo corre con datos de ejemplo en memoria, pensado para validar los flujos e
interacciones antes de definir el modelo de datos y la API.

Prototipo interactivo: **[Guardia Viva](https://claude.ai/artifact/3T56cETi81zUAJxqujU7hv)**

## Historial de versiones

### v1 — Especificación funcional
Documento de partida (`prompt_tp_final_v02.md`) con el diseño completo del sistema:
- Dominio: equipo de 10-12 médicos, turnos de duración variable (6/7/8/12/24 h) que
  pueden cruzar la medianoche, superposición de turnos.
- Plantilla base de guardia (titular fijo por día/horario, con soporte para rotación
  entre dos o más titulares) como dato de fondo, distinto de la gestión de vacantes.
- Semáforo de tres estados (rojo/amarillo/verde) y regla de priorización de candidatos
  por horas de descanso desde la última guardia efectivamente realizada.
- Roles médico/coordinador con control de permisos doble (visual + servidor).
- Alta, baja e inactivación de médicos sin borrar historial.
- Notificaciones push propias de la app (se descartó WhatsApp Business API).
- Requisito de persistencia sobre un recurso de Google Drive (mecanismo concreto
  todavía abierto).
- Pendientes explícitos: diseño visual definitivo, modelo de datos completo, mecanismo
  técnico de push, y si hace falta un Data Warehouse.

### v2 — Primer prototipo de frontend interactivo ("Guardia Viva")
A partir de la v1, se construyó un prototipo funcional de la interfaz, con foco en
validar la experiencia antes de tocar backend:

- **Vista mensual** tipo Google Calendar/Apple Calendar, con indicador visual (punto
  rojo/amarillo) en los días con novedades, sin listar los turnos completos en el
  casillero del día.
- **Vista diaria** como línea de tiempo horizontal de 24 h, con una fila por turno,
  barras superpuestas coloreadas por estado, línea de "ahora", y control de **zoom**
  (+/−) para ajustar la densidad horaria — al estilo Google Calendar.
- **Transición mes → día**: tocar un día en la vista mensual "hace zoom" a su detalle,
  con botón para volver.
- **Simulador de tres roles en una sola pantalla**: paneles de Médico 1 (Valentina
  Ríos), Médico 2 (Martín Aguirre) y Coordinadora (Renata Ibarra), cada uno navegando
  su propio calendario de forma independiente pero compartiendo el mismo estado — una
  acción en un panel (generar vacante, postularse, confirmar) se refleja al instante
  en los otros dos, con un toast de aviso por panel y un feed de "Actividad en vivo"
  compartido arriba de todo. Simula el efecto de las notificaciones push en tiempo real
  sin necesidad de backend.
- **Flujos completos implementados**: generar vacante → postularse → confirmar
  candidato por el coordinador (con lista de candidatos ordenada por horas de descanso
  desde la última guardia, incluyendo el caso de médico sin guardias previas) → retirar
  postulación.
- **Datos de ejemplo**: 11 médicos, plantilla semanal con las 5 duraciones de turno de
  la consigna (6, 7, 8, 12, 24 h), turnos que cruzan la medianoche, y un caso de
  titular en rotación (jueves 08–16, alternando semana por medio) para probar ese
  mecanismo.
- **Fuera de alcance de esta versión** (a propósito, para no desviar el foco de
  frontend): alta/baja/inactivación de médicos, edición de la plantilla base desde la
  UI, y toda la persistencia — hoy es sólo estado en memoria del navegador.

## Próximos pasos

- Pulir diseño visual definitivo (colores, tipografía, disposición) sobre esta base.
- Definir el modelo de datos completo (entidades, atributos, relaciones), incluyendo
  cómo modelar la plantilla base y su relación con los turnos generados por excepción.
- Diseñar el contrato de API (siguiendo la misma lógica que el TP2 con OpenAPI).
- Definir el mecanismo técnico de notificaciones push (proveedor, payload, tokens).
- Resolver la implementación de persistencia sobre Google Drive y justificarla.
- Evaluar si el TP final requiere vincularse a un Data Warehouse.
