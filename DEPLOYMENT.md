# Deployment guide

This app ships with config for two hosts and a serverless Postgres database:

- **Neon** — serverless PostgreSQL (the database for both options below).
- **Render** — recommended primary host for the Django backend (long-running).
- **Vercel** — alternative serverless host (config included as requested).

The code reads its database from `DATABASE_URL`, so the same build runs on either
host once that variable points at Neon.

---

## 1. Create the Neon database

1. Sign in at <https://neon.tech> and create a project (pick a region close to your
   users).
2. Open **Dashboard → Connection Details** and copy the **connection string**. It
   looks like:
   ```
   postgresql://USER:PASSWORD@ep-xxxx-pooler.REGION.aws.neon.tech/DBNAME?sslmode=require
   ```
3. Prefer the **pooled** connection string (the host contains `-pooler`). Pooling
   suits both Render and serverless Vercel well.

That string is the value you'll set as `DATABASE_URL` below. `config/settings.py`
already enforces TLS for Neon.

---

## 2. Deploy to Render (recommended)

Render is the better fit for a Django app: it's a persistent web service, so
migrations and `collectstatic` run once per deploy in the build step.

**Option A — Blueprint (uses the committed `render.yaml`):**

1. Push this repo to GitHub.
2. In Render, choose **New → Blueprint** and select the repo. Render reads
   `render.yaml` and creates the web service.
3. When prompted, set **`DATABASE_URL`** to your Neon connection string.
4. Deploy. `build.sh` installs deps, runs `collectstatic`, and applies migrations.

**Option B — manual web service:**

- **Build command:** `./build.sh`
- **Start command:** `gunicorn config.wsgi:application`
- **Environment variables:**
  | Key | Value |
  |-----|-------|
  | `DATABASE_URL` | your Neon connection string |
  | `DJANGO_SECRET_KEY` | a long random string |
  | `DJANGO_DEBUG` | `0` |
  | `PYTHON_VERSION` | `3.12.3` |

After the first deploy, create an admin user from the Render **Shell** tab:
```bash
python manage.py createsuperuser
```
Optionally load demo data: `python manage.py seed_demo`.

---

## 3. Deploy to Vercel (alternative)

The repo includes `vercel.json` and `api/index.py`, which run Django as a single
serverless function. WhiteNoise serves the static files from inside the app.

1. Push the repo to GitHub and import it at <https://vercel.com/new>.
2. Under **Settings → Environment Variables**, add:
   | Key | Value |
   |-----|-------|
   | `DATABASE_URL` | your Neon connection string |
   | `DJANGO_SECRET_KEY` | a long random string |
   | `DJANGO_DEBUG` | `0` |
3. Deploy.

**Important — migrations on Vercel.** Vercel's filesystem is read-only at runtime,
so it does **not** run migrations for you. Run them once from your machine, pointed
at Neon, before or just after deploying:
```bash
export DATABASE_URL="postgresql://...neon.tech/...?sslmode=require"
python manage.py migrate
python manage.py createsuperuser   # optional
python manage.py seed_demo         # optional demo data
```

> Note: this project depends on **pandas** (for the CSV/Excel import bonus), which
> makes the Vercel serverless bundle fairly large and cold starts slower. That's the
> main reason I'd pick Render for a Django app of this shape; Vercel is included
> because it was requested and works fine for demoing.

---

## 4. Vercel Blob — only if you need to persist uploaded files

You **don't need this** for the current app: the CSV/Excel importer reads the upload
in memory and never writes it to disk, so nothing persistent is required.

Reach for Blob if you later add a feature that must **store** files (e.g. keeping the
original import files, or letting users attach photos to a plot). On serverless
Vercel the local filesystem is ephemeral, so files must go to object storage like
Vercel Blob.

**Set it up:**

1. In the Vercel dashboard: **Storage → Create → Blob**, and connect it to the
   project. Vercel adds a `BLOB_READ_WRITE_TOKEN` environment variable automatically.
2. For local testing, copy that token into your environment:
   ```bash
   export BLOB_READ_WRITE_TOKEN="vercel_blob_rw_xxx"
   ```

**Use it from Django.** Vercel Blob exposes an HTTP API, so no extra package is
needed — a small helper is enough. Add something like this (for example in a new
`tracker/storage.py`) and call it from a view when you need to persist a file:

```python
import os
import requests  # add `requests` to requirements.txt if you use this

def upload_to_blob(filename, content_bytes, content_type="application/octet-stream"):
    """Upload bytes to Vercel Blob and return the public URL."""
    token = os.environ["BLOB_READ_WRITE_TOKEN"]
    resp = requests.put(
        f"https://blob.vercel-storage.com/{filename}",
        headers={
            "authorization": f"Bearer {token}",
            "x-content-type": content_type,
            "x-add-random-suffix": "1",
        },
        data=content_bytes,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["url"]
```

Then, for instance, inside the import view you could keep a copy of the uploaded
file:
```python
url = upload_to_blob(upload.name, upload.read(), upload.content_type)
```

For heavier file needs you could instead wire an S3-compatible backend via
`django-storages`, but the lightweight helper above is enough for occasional uploads.

---

## Environment variables at a glance

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | for Postgres/Neon | Full Neon connection string. If unset, the app uses SQLite. |
| `DJANGO_SECRET_KEY` | in production | Django cryptographic key. |
| `DJANGO_DEBUG` | recommended | `0` in production, `1` locally (default). |
| `DJANGO_ALLOWED_HOSTS` | optional | Override allowed hosts (defaults include `.onrender.com`, `.vercel.app`). |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | optional | Override trusted HTTPS origins. |
| `BLOB_READ_WRITE_TOKEN` | only for Blob | Vercel Blob access token (see section 4). |
