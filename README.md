# 🔮 Bot de Telegram — Profeta de Reactivos

Capa conversacional sobre el backend FastAPI existente. Un operario de planta
elige las condiciones del proceso con **botones** (no sliders) desde su celular y
recibe la dosis de colector recomendada, el ahorro estimado y la justificación.

El bot **no tiene backend propio**: es otro cliente del mismo FastAPI que consume
el frontend web (`POST /api/optimizar`, `GET /api/modelos/status`).

```
Operario (Telegram) → Bot (polling) → Backend FastAPI (:8000)
```

## Estructura

| Archivo | Rol |
|---|---|
| `bot.py` | Lógica del bot: comandos, botones inline, flujo conversacional |
| `api_client.py` | Cliente httpx async al backend (optimizar + estado) |
| `variables.py` | Las 6 variables con rangos discretos + perfiles rápidos |
| `config.py` | Variables de entorno (token, API_URL, whitelist) |
| `requirements.txt` | Dependencias |
| `Dockerfile` | Imagen para deploy |

## Funcionalidades

- `/start` → menú con **🧪 Nueva recomendación** y **📡 Estado del sistema**.
- **Perfil rápido** (MVP): 4 perfiles predefinidos (típica, alta turbidez, mineral pobre/rico).
- **Variable por variable** (V2): 6 preguntas con botones de rango. Cada botón envía
  el **punto medio** del rango → siempre dentro de rango operativo (evita el 422).
- Resultado: dosis recomendada, Δ vs. actual, recuperación, ahorro diario/anual, agua.
  - **❓ ¿Por qué esta dosis?** → texto `recomendacion`.
  - **📊 Ver los 9 escenarios** → tabla monoespaciada.
- `/estado` → estado de los 3 modelos IA (o respaldo analítico).
- `/myid` → devuelve tu `chat_id` (para configurar la whitelist).
- **Control de acceso** por whitelist de `chat_id`.
- **Anti-spam**: intervalo mínimo entre consultas por usuario.

## Correr localmente

1. Crea el bot con [@BotFather](https://t.me/BotFather) → copia el token.
2. Configura el entorno:

```bash
cd bot-telegram
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/Mac:
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # (cp .env.example .env en Linux/Mac)
```

3. Edita `.env` con tu `TELEGRAM_BOT_TOKEN` y `API_URL` (por defecto `http://localhost:8000`).
4. Asegúrate de que el backend esté corriendo (`uvicorn main:app --port 8000` en `../backend`).
5. Arranca el bot:

```bash
python bot.py
```

6. En Telegram, abre tu bot y envía `/start`. Usa `/myid` para obtener tu `chat_id`
   y ponlo en `ALLOWED_CHAT_IDS` del `.env` cuando quieras restringir el acceso.

---

## 🚀 Deploy en Render

El bot usa **polling**, por lo que en Render es un **Background Worker** (no expone
puertos ni necesita URL pública). El backend es un **Web Service**.

> Requisito previo: tu código debe estar en un repo de GitHub/GitLab. Si aún no lo está:
>
> ```bash
> cd ..            # carpeta "app" (contiene backend/, frontend/, bot-telegram/)
> git init
> git add .
> git commit -m "Profeta de Reactivos: backend + frontend + bot Telegram"
> git branch -M main
> git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
> git push -u origin main
> ```

### Opción A — Blueprint (automático, recomendado)

Ya existe `app/render.yaml` que declara **backend (web)** + **bot (worker)**.

1. En Render: **New → Blueprint**.
2. Conecta el repo y selecciona la rama `main`. Render detecta `render.yaml`.
3. Render te pedirá las variables marcadas `sync: false`:
   - `TELEGRAM_BOT_TOKEN` → el token de BotFather.
   - `API_URL` → déjalo por ahora; lo llenarás con la URL del backend en el paso 5.
   - `ALLOWED_CHAT_IDS` → tus `chat_id` separados por coma (o vacío al inicio).
4. **Apply** → Render crea `profeta-backend` y `profeta-bot-telegram`.
5. Cuando `profeta-backend` termine de desplegarse, copia su URL pública
   (ej. `https://profeta-backend.onrender.com`), ve al worker
   `profeta-bot-telegram` → **Environment** → pon `API_URL` con esa URL → **Save**
   (el worker reinicia solo).

> Nota: si tu repo empieza en una carpeta distinta a `app/`, mueve `render.yaml`
> a la raíz del repo y ajusta los `rootDir` (`backend`, `bot-telegram`).

### Opción B — Manual desde el dashboard

**1) Backend (Web Service):**
- **New → Web Service** → conecta el repo.
- **Root Directory**: `backend`
- **Runtime**: Python 3
- **Build Command**:
  ```
  pip install -r requirements.txt && python train_models.py || true
  ```
- **Start Command**:
  ```
  uvicorn main:app --host 0.0.0.0 --port $PORT
  ```
- **Environment**: `CORS_ORIGINS = *`
- Deploy y copia la URL pública resultante.

**2) Bot (Background Worker):**
- **New → Background Worker** → mismo repo.
- **Root Directory**: `bot-telegram`
- **Runtime**: Python 3
- **Build Command**:
  ```
  pip install -r requirements.txt
  ```
- **Start Command**:
  ```
  python bot.py
  ```
- **Environment Variables**:
  | Key | Value |
  |---|---|
  | `TELEGRAM_BOT_TOKEN` | (token de BotFather) |
  | `API_URL` | `https://profeta-backend.onrender.com` |
  | `ALLOWED_CHAT_IDS` | tus chat_id (opcional) |
  | `API_TIMEOUT` | `15` |
  | `MIN_SECONDS_BETWEEN_QUERIES` | `2` |
- Deploy.

### Opción C — Docker en Render
Render también puede construir el `Dockerfile` de esta carpeta. Elige **Runtime: Docker**
y **Root Directory: `bot-telegram`**; no necesitas Build/Start command.

---

### Resumen de comandos de deploy

```bash
# 1. Subir el repo (desde la carpeta "app")
git init
git add .
git commit -m "Profeta de Reactivos + bot Telegram"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main

# 2. En Render (dashboard, no CLI):
#    - Backend  → New > Web Service      (Root: backend,     Start: uvicorn main:app --host 0.0.0.0 --port $PORT)
#    - Bot      → New > Background Worker (Root: bot-telegram, Start: python bot.py)
#    o simplemente: New > Blueprint  (usa app/render.yaml)
```

> El plan **free** de Render duerme los Web Services inactivos; la primera consulta
> tras la inactividad puede tardar ~30 s en despertar el backend. El worker del bot
> se mantiene vivo mientras el plan lo permita.
