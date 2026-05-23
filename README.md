# Sorteo App 🎰

Aplicación web de sorteos con login de Google. Crea sorteos, agrega participantes por correo electrónico y elige un ganador al azar.

## Características

- **Login con Google** (OAuth 2.0)
- **Crear sorteos** con título y descripción
- **Agregar participantes** por correo electrónico
- **Ejecutar sorteo** para elegir un ganador al azar
- **Dockerizado** para fácil despliegue

## Inicio Rápido con Docker

### 1. Clonar el repositorio

```bash
git clone https://github.com/maestroyaco/sorteo-app.git
cd sorteo-app
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Edita .env con tus credenciales de Google OAuth
```

### 3. Ejecutar con Docker Compose

```bash
docker-compose up -d
```

La app estará disponible en `http://localhost:5000`

## Configurar Google OAuth

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un proyecto nuevo (o usa uno existente)
3. Ve a **APIs & Services > Credentials**
4. Crea un **OAuth 2.0 Client ID** (tipo: Web Application)
5. Agrega como **Authorized redirect URI**: `http://localhost:5000/authorize/google`
6. Copia el **Client ID** y **Client Secret** al archivo `.env`

## Ejecución sin Docker

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edita .env con tus credenciales
python app.py
```

## Variables de Entorno

| Variable | Descripción | Requerida |
|---|---|---|
| `FLASK_SECRET_KEY` | Clave secreta para sesiones Flask | Sí |
| `GOOGLE_CLIENT_ID` | Client ID de Google OAuth | Sí (para login) |
| `GOOGLE_CLIENT_SECRET` | Client Secret de Google OAuth | Sí (para login) |
| `DATABASE_PATH` | Ruta de la base de datos SQLite | No (default: sorteo.db) |
| `OAUTHLIB_INSECURE_TRANSPORT` | Permitir HTTP (dev only) | No (default: 0) |

## Stack Tecnológico

- **Backend**: Python / Flask
- **Auth**: Google OAuth 2.0 (Authlib)
- **DB**: SQLite
- **Frontend**: Bootstrap 5 + Bootstrap Icons
- **Server**: Gunicorn
- **Container**: Docker

## Licencia

MIT
