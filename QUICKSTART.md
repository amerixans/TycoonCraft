# TycoonCraft – Quick Start

Bring up the full stack locally with a few commands. This guide mirrors the actual project layout and tooling in this repository.

## Prerequisites

- Python 3.8 or newer
- Node.js 16 or newer (includes `npm`)
- PostgreSQL (running locally with a role that can create databases)
- OpenAI API key with access to `gpt-5-mini` and `gpt-image-1-mini`

> Tip: If PostgreSQL is using a password, make sure the credentials in your `.env` file match your local setup.

## 1. Database

Create a database for TycoonCraft. The backend defaults to `tycooncraft` with user `postgres` and password `postgres`; adjust to your environment if different.

```bash
createdb tycooncraft
```

## 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env` (or edit if it already exists):

```
DJANGO_SECRET_KEY=replace-me
DEBUG=True
OPENAI_API_KEY=sk-...
DB_NAME=tycooncraft
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
# Optional in production:
# CORS_ALLOWED_ORIGINS=https://app.tycooncraft.com,https://admin.tycooncraft.com
```

Run migrations and seed initial content:

```bash
python manage.py migrate
python manage.py initialize_starter_objects
python manage.py generate_upgrade_keys    # optional: seeds 1000 upgrade keys into backend/upgrade_keys.txt
DJANGO_SUPERUSER_PASSWORD=your-strong-password python manage.py create_admin_account     # optional: creates admin superuser
```

Finally, start the Django API:

```bash
python manage.py runserver
```

## 3. Frontend Setup

```bash
cd frontend
npm install
npm start
```

The React dev server proxies API calls to `http://localhost:8000` (configured in `package.json`). If your backend lives elsewhere, create `frontend/.env.local` with:

```
REACT_APP_API_URL=http://your-backend-host/api
```

## 4. Use the App

- Frontend: http://localhost:3000
- Backend API root: http://localhost:8000/api/
- Django admin (if created): http://localhost:8000/admin/
  - Credentials come from `DJANGO_SUPERUSER_USERNAME`/`DJANGO_SUPERUSER_PASSWORD` (defaults to `admin` / value you export)

Log in or register from the landing screen, craft your starter objects (Rock, Stick, Water, Dry Grass), and begin combining discoveries. Keystone placements will unlock new eras automatically; you can also unlock eras via the sidebar using time crystals.

## Troubleshooting

- **`OPENAI_API_KEY is not configured`** – Ensure `backend/.env` contains your key and restart the server.
- **`OperationalError: database ... does not exist`** – Rerun `createdb tycooncraft` (or update the DB settings in `.env`).
- **`Insufficient coins` during crafting** – Earn more by placing income-generating objects; admin accounts may go negative.
- **Frontend fails to start** – Remove `node_modules` and the lockfile, then reinstall:
  ```bash
  cd frontend
  rm -rf node_modules package-lock.json
  npm install
  ```
- **Port already in use** – Free up the port:
  ```bash
  lsof -ti:8000 | xargs kill -9    # backend
  lsof -ti:3000 | xargs kill -9    # frontend
  ```

## Next Steps

- Review the full [README.md](README.md) for deep dives into systems, API endpoints, and architecture.
- Check [deployment.md](deployment.md) and `deploy.sh`/`update.sh` for production workflows.
- Explore the seeded upgrade keys in `backend/upgrade_keys.txt` to test Pro-tier accounts.
