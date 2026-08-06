# Tickets TI

Sistema de tickets para departamento de TI: cualquiera crea un ticket,
el equipo de TI lo gestiona en un tablero por estado (Abierto → En
progreso → Resuelto → Cerrado), con prioridades, asignación y una
bitácora de comentarios por ticket.

Usa **SQLite** (un solo archivo `tickets.db`, sin servidor de base de
datos que instalar) — funciona igual desde el primer arranque.

## Cómo correrlo

```bash
cd backend
pip install fastapi uvicorn pydantic
uvicorn app:app --reload
```

Abre **http://localhost:8000**. Ya arranca con 5 tickets de ejemplo
para que veas el tablero funcionando.

## Qué hace cada archivo

```
backend/
  app.py         # API en FastAPI: crear/listar/actualizar tickets,
                  # comentarios y estadísticas
  db.py          # Toda la lógica de datos (SQLite, sin ORM)
  requirements.txt
  tickets.db     # se crea solo al primer arranque
frontend/
  index.html     # Tablero kanban (HTML + JS, un solo archivo, sin frameworks)
```

## Cómo se probó

`db.py` sí se corrió de extremo a extremo en este entorno (crear
ticket, cambiar estado, asignar, comentar, calcular estadísticas) —
todo funcionó. Lo único que no pude probar aquí es el servidor FastAPI
completo por falta de acceso a internet para instalar el paquete; la
sintaxis de `app.py` está verificada pero pruébalo tú al primer
arranque.

## Instalarla como ícono en el celular (PWA)

Ya está lista para "instalarse" como app, sin pasar por ninguna tienda
de apps:

- **Android (Chrome):** entra a la URL de la app → menú (⋮) →
  **"Instalar app"** o **"Añadir a pantalla de inicio"**.
- **iOS (Safari, no funciona desde Chrome en iPhone):** entra a la URL
  → botón de compartir (el cuadrito con la flecha) →
  **"Añadir a pantalla de inicio"**.

En ambos casos queda un ícono como cualquier otra app, abre sin la
barra del navegador, y usa el ícono verde/cobre que generamos.

## Hacer que funcione desde cualquier lugar (no solo tu red)

Ahora mismo la app vive en tu laptop y solo la ve gente conectada a tu
misma red (con `http://TU_IP:8000`). Para que un empleado la abra
desde su casa o con datos móviles, necesitas subirla a un servidor con
IP pública — tu laptop no sirve para esto a largo plazo (se apaga, se
mueve de red, etc).

**Opción recomendada para empezar, gratis:** [Render.com](https://render.com)
o [Railway.app](https://railway.app) — ambos aceptan proyectos de
Python/FastAPI, se conectan directo a un repositorio de GitHub, y te
dan una URL pública tipo `https://tickets-ti.onrender.com` sin
configurar servidores tú mismo.

⚠️ **Importante sobre los datos:** este proyecto usa SQLite (un
archivo). En el plan gratis de la mayoría de estos hostings, el
almacenamiento es temporal — si el servidor se reinicia (pasa
seguido en el plan gratis), **se pierden los tickets guardados**. Para
uso real sostenido, dime cuando llegues a ese punto y te ayudo a
migrar a una base de datos con almacenamiento persistente (por
ejemplo Postgres, que Render también ofrece gratis por separado).

Si quieres, en tu próximo mensaje dime si prefieres Render o Railway y
te armo la guía paso a paso para subirlo — es un proceso aparte
(crear cuenta, conectar el código, configurar variables) que vale la
pena hacer con calma.

## Qué extendería primero

1. **Login real** — hoy "solicitante" y "autor del comentario" son
   campos de texto libre; cualquiera puede escribir el nombre que
   quiera. Lo primero en cualquier despliegue real es autenticación
   (aunque sea simple, con usuarios de un archivo o Google/Microsoft
   login).
2. **Notificaciones** — avisar por correo o Slack cuando a alguien le
   asignan un ticket o cuando cambia de estado. Es lo que más se pide
   en este tipo de herramienta.
3. **Adjuntar archivos** (capturas de pantalla del error, por
   ejemplo) — muy común en soporte técnico.
4. **SLA y alertas de vencimiento** — marcar tickets urgentes que
   llevan más de X horas sin moverse de "abierto".
5. **Filtros y búsqueda** en el tablero — hoy se ve todo; con más de
   ~30 tickets activos hace falta filtrar por categoría/asignado.
