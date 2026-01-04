# Sugar App

A full‑stack web application with a **FastAPI** backend, **PostgreSQL** database, and **React (Vite)** frontend.

---

## Tech Stack

### Backend
- Python 3.11
- FastAPI
- Uvicorn
- SQLAlchemy
- Alembic (migrations)
- PostgreSQL
- JWT authentication (PyJWT)

### Frontend
- React
- Vite
- TypeScript

### Infrastructure
- Docker & Docker Compose (backend + database)
- Local Node.js for frontend

---

## Project Structure

```
sugar-app/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── seed.py
│   │   └── ...
│   ├── alembic/
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
└── README.md
```

---

## Prerequisites

Make sure you have the following installed:

- Docker
- Docker Compose
- Node.js (18+ recommended)
- npm

---

## Running the App (Recommended Setup)

This setup runs **PostgreSQL + Backend in Docker** and **Frontend locally**.

### 1. Start Backend & Database

From the project root:

```bash
docker compose up -d --build
```

Verify containers are running:

```bash
docker compose ps
```

---

### 2. Run Database Migrations

```bash
docker compose exec backend alembic upgrade head
```

---

### 3. Seed the Database (Admin User)

```bash
docker compose exec backend python -m app.seed
```

Default credentials:

- **Username:** `admin`
- **Password:** `admin123`

---

### 4. Start the Frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

---

### 5. Access the App

- Frontend: http://localhost:5173
- Backend API Docs: http://localhost:8000/docs

---

## Environment Configuration

### Frontend

`frontend/.env`

```env
VITE_API_URL=http://localhost:8000
```

### Backend

Configured via Docker Compose (PostgreSQL connection is internal to Docker).

---

## Resetting the Database

### Option A: Full Reset (Recommended)
Deletes **all data and schema** by removing the Docker volume.

```bash
docker compose down -v
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed
```

---

### Option B: Reset Data Only (Keep Volume)
Drops and recreates the public schema.

```bash
docker compose exec db psql -U app -d finance -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed
```

---

## Common Issues

### Missing Python Dependency (e.g. jwt)
If you see:

```
ModuleNotFoundError: No module named 'jwt'
```

Temporary fix:

```bash
docker compose exec backend pip install PyJWT
```

Permanent fix: add `PyJWT` to `backend/pyproject.toml` and rebuild.

---

### Frontend Login Fails

- Ensure backend is running: http://localhost:8000/docs
- Ensure frontend `.env` points to the correct API URL
- Ensure CORS allows `http://localhost:5173`

---

### Service Not Running Error

If you see:

```
service "backend" is not running
```

Make sure containers are started first:

```bash
docker compose up -d
```

---

## Development Notes

- Backend auto‑reloads inside Docker on file changes
- Frontend auto‑reloads via Vite
- All backend commands (`alembic`, `seed`, etc.) must be run from inside the backend container

---

## License

MIT

