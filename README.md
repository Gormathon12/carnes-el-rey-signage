# 🥩 Carnes el Rey — Digital Signage

Sistema de cartelería digital para hasta **10 pantallas** (Android TV u otras).
Un panel de administración permite armar playlists de imágenes y videos por
pantalla, y cada TV reproduce su playlist en loop infinito, refrescándose sola
cuando hay cambios.

- **Backend:** FastAPI + SQLite
- **Frontend:** HTML/JS puro (sin frameworks)
- **Almacenamiento de media:** Cloudinary
- **Hosting:** Railway

---

## 📁 Estructura

```
digital-signage/
├── backend/
│   ├── main.py            # arranque, crea tablas y las 10 pantallas, sirve el frontend
│   ├── models.py          # modelos Screen y MediaItem
│   ├── database.py        # conexión SQLite
│   ├── routes/
│   │   ├── auth.py        # login + JWT
│   │   ├── media.py       # integración con Cloudinary
│   │   └── playlists.py   # endpoints de playlists e items
│   └── requirements.txt
├── frontend/
│   ├── admin/index.html   # panel de administración
│   ├── tv/index.html      # vista de TV (?screen=1 .. ?screen=10)
│   └── assets/
├── railway.toml
├── Procfile
├── requirements.txt       # raíz (apunta a backend/requirements.txt)
└── .env.example
```

---

## 1) Crear cuenta en Cloudinary y obtener credenciales

1. Entrá a **https://cloudinary.com/users/register_free** y creá una cuenta gratuita.
2. Confirmá tu email e ingresá al **Dashboard** (https://cloudinary.com/console).
3. En la parte superior vas a ver tus credenciales (**Product Environment Credentials**):
   - **Cloud Name**
   - **API Key**
   - **API Secret** (click en el ojito 👁 para verlo)
4. Copiá esos tres valores; los vas a poner en las variables de entorno.

> El plan gratuito alcanza de sobra para una carnicería (25 GB de almacenamiento
> y 25 GB de ancho de banda mensual). Las carpetas se crean solas:
> `digital-signage/screen-1` … `digital-signage/screen-10`.

---

## 2) Variables de entorno

Copiá `.env.example` a `.env` y completá los valores:

```bash
cp .env.example .env
```

```ini
CLOUDINARY_CLOUD_NAME=tu_cloud_name
CLOUDINARY_API_KEY=tu_api_key
CLOUDINARY_API_SECRET=tu_api_secret
ADMIN_USER=admin
ADMIN_PASSWORD=carneselrey123
SECRET_KEY=pega_aqui_un_valor_aleatorio_largo
```

Para generar un `SECRET_KEY` seguro:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> ⚠️ Cambiá `ADMIN_PASSWORD` por una contraseña propia antes de poner esto en
> producción.

---

## 3) Correr en local (opcional, para probar)

```bash
cd digital-signage
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate

pip install -r requirements.txt
cd backend
uvicorn main:app --reload
```

- Panel admin: **http://localhost:8000/admin**
- Pantalla TV 1: **http://localhost:8000/tv?screen=1**
- Documentación de la API: **http://localhost:8000/docs**

---

## 4) Deploy GRATIS en Render + Neon (recomendado)

Opción 100% gratuita y sin que se borren las playlists. Usa tres servicios free:
**Render** (corre la app), **Neon** (base de datos PostgreSQL) y **Cloudinary**
(la media, ya configurada en el paso 1).

### 4.1 Base de datos gratis en Neon
1. Entrá a **https://neon.tech** → **Sign up** (gratis, con GitHub).
2. Creá un proyecto (cualquier nombre, ej. `carnes-el-rey`).
3. En el dashboard, copiá la **Connection string** (botón "Connect"). Se ve así:
   `postgresql://usuario:password@ep-xxxx.neon.tech/neondb?sslmode=require`
4. Guardala; la vas a pegar en Render como `DATABASE_URL`.

### 4.2 App gratis en Render
1. Entrá a **https://render.com** → **Sign up** con GitHub.
2. **New + → Blueprint** → conectá el repo `carnes-el-rey-signage`.
   Render detecta `render.yaml` y crea el servicio solo.
   (Alternativa: **New + → Web Service**, runtime Python, start command
   `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`.)
3. En **Environment**, cargá las variables:
   ```
   CLOUDINARY_CLOUD_NAME = (paso 1)
   CLOUDINARY_API_KEY    = (paso 1)
   CLOUDINARY_API_SECRET = (paso 1)
   DATABASE_URL          = (la connection string de Neon, paso 4.1)
   ADMIN_USER            = admin
   ADMIN_PASSWORD        = (tu contraseña)
   ```
   (`SECRET_KEY` se genera solo gracias al blueprint.)
4. **Create** y esperá el build. Te queda una URL tipo
   `https://carnes-el-rey-signage.onrender.com`.

> ⚠️ En el plan free de Render la app se "duerme" tras ~15 min sin tráfico y
> tarda ~1 minuto en despertar. Con las TVs prendidas (consultan cada 30 s) se
> mantiene despierta. Gracias a Neon, **las playlists no se pierden** aunque se
> duerma o se vuelva a desplegar.

---

## 4-bis) Deploy en Railway (alternativa)

1. Subí este proyecto a un repo de **GitHub** (o usá `railway init` con el CLI).
2. Entrá a **https://railway.app**, creá una cuenta y hacé **New Project →
   Deploy from GitHub repo**, eligiendo este repositorio.
3. Railway detecta Python automáticamente (por `requirements.txt`) y usa el
   `startCommand` de `railway.toml`.
4. En **Variables**, cargá las mismas variables del `.env`:
   `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`,
   `ADMIN_USER`, `ADMIN_PASSWORD`, `SECRET_KEY`.
   (No hace falta `PORT`: Railway lo inyecta solo.)
5. En **Settings → Networking → Generate Domain** para obtener una URL pública,
   por ejemplo `https://carnes-el-rey.up.railway.app`.

### Persistir la base de datos (recomendado)

SQLite se guarda en el disco del contenedor, que en Railway es **efímero** (se
borra en cada redeploy). Para conservar los nombres de pantallas y las playlists:

1. En el servicio, **Settings → Volumes → New Volume**, montalo en `/data`.
2. Agregá la variable `DATABASE_URL=sqlite:////data/signage.db`.

(Los archivos de media siempre están a salvo: viven en Cloudinary, no en SQLite.)

---

## 5) Acceder al panel admin

- Abrí `https://TU-DOMINIO/admin`
- Ingresá con el **usuario** y **contraseña** que pusiste en las variables
  (`ADMIN_USER` / `ADMIN_PASSWORD`).

Desde el panel podés:

- Ver las 10 pantallas como tarjetas (tocá una para entrar).
- Renombrar cada pantalla (ej: "Vidrieras", "Caja", "Promociones").
- Subir imágenes (JPG/PNG) y videos (MP4) — se suben a Cloudinary.
- Reordenar con las flechas ▲▼, activar/desactivar y borrar elementos.
- Cambiar la duración de cada imagen (en segundos; por defecto 10 s).
  Los videos duran lo que dura el archivo.

El panel está optimizado para usarse desde el **celular**.

---

## 6) Abrir las pantallas en Android TV

Cada TV muestra una pantalla distinta vía URL:

| Pantalla | URL |
|----------|-----|
| TV 1 | `https://TU-DOMINIO/tv?screen=1` |
| TV 2 | `https://TU-DOMINIO/tv?screen=2` |
| … | … |
| TV 10 | `https://TU-DOMINIO/tv?screen=10` |

### Pasos en el Android TV

1. En la Play Store del TV, instalá un navegador kiosco. Recomendado:
   **"Fully Kiosk Browser"** o **"Kiosk Browser Lockdown"**.
2. Configurá como **Start URL** la dirección de esa pantalla, por ejemplo
   `https://TU-DOMINIO/tv?screen=3`.
3. Activá:
   - **Pantalla completa / Fullscreen**
   - **Mantener pantalla encendida / Keep screen on**
   - **Autostart al encender** (para que arranque solo).
4. (Opcional) Deshabilitá la barra de navegación y el gesto de salida para que
   quede como cartel fijo.

La vista de TV ya viene pensada para esto: fondo negro, sin cursor, sin scroll,
sin interfaz, transición *fade* entre imágenes y autoplay silenciado en videos.

> La pantalla consulta al servidor cada **30 segundos** si la playlist cambió.
> Cuando hay cambios, los aplica al terminar el elemento que esté mostrando (sin
> cortes bruscos).

---

## 🔌 Referencia de la API

| Método | Endpoint | Auth | Descripción |
|--------|----------|------|-------------|
| POST | `/auth/login` | — | Devuelve un token JWT |
| GET  | `/playlists` | — | Lista las 10 pantallas |
| GET  | `/playlists/{id}/items` | — | Items activos y ordenados (`?all=true` incluye inactivos) |
| GET  | `/playlists/{id}/version` | — | Timestamp para detectar cambios |
| POST | `/playlists/{id}/items` | ✅ | Sube archivo a Cloudinary y lo agrega |
| PUT  | `/playlists/{id}/items/{item}` | ✅ | Edita duración / activo |
| DELETE | `/playlists/{id}/items/{item}` | ✅ | Borra de Cloudinary y BD |
| PUT  | `/playlists/{id}/reorder` | ✅ | Reordena por lista de IDs |
| PUT  | `/playlists/{id}/name` | ✅ | Renombra la pantalla |

Los endpoints con ✅ requieren el header `Authorization: Bearer <token>`.
Los endpoints de lectura son públicos para que las TV consulten sin login.

---

## 🛠️ Notas técnicas

- Las 10 pantallas se crean automáticamente al iniciar la app.
- CORS está habilitado para todos los orígenes (las TV pueden acceder por IP local).
- Formatos soportados: **JPG, PNG** (imagen) y **MP4** (video). Máx. 100 MB por archivo.
- La vista de TV está pensada para **1080p** en Android TV.
