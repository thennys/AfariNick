# Afarinick — Farm Plot & Harvest Tracker

A small internal tool for Afarinick's Volta Region cocoa operations: register
contracted **farmers** and their **plots**, log **harvest records** from the field,
and read back performance summaries. Built for the Software Engineer take-home
assignment.

Backend is **Django** with plain **function-based views** and a hand-written JSON
API (no Django REST Framework, no Django Forms, no class-based views — matching the
conventions in the brief). The frontend is **raw HTML + jQuery/AJAX**. All three
bonus features are included, plus an interactive **Swagger UI**.

---

## Contents

- [Tech stack & key decisions](#tech-stack--key-decisions)
- [Quick start](#quick-start)
- [Testing the API with Swagger UI](#testing-the-api-with-swagger-ui)
- [API reference](#api-reference)
- [Data model](#data-model)
- [Bonus features](#bonus-features)
- [Running the tests](#running-the-tests)
- [Management commands](#management-commands)
- [Deployment & CI](#deployment--ci)
- [Assumptions I made](#assumptions-i-made)
- [What I'd do differently with more time](#what-id-do-differently-with-more-time)

---

## Tech stack & key decisions

| Area | Choice | Why I chose it |
|------|--------|----------------|
| Framework | Django 5 | Matches the brief and the team's stack. |
| Views | **Function-based only** | The brief states the team uses function-based views throughout, so there is not a single class-based view in this project. |
| Forms | **Hand-written HTML + AJAX** | The brief asks not to use the Django Forms framework; I gather and validate input myself. |
| API style | Plain Django `JsonResponse` | Keeps things dependency-light and faithful to "we use function-based views." I did **not** add DRF. |
| Database | **SQLite by default**, PostgreSQL via env var | See the note below. |
| API docs | Hand-written OpenAPI 3 + Swagger UI (CDN) | Interactive docs without pulling in DRF/spectacular. |
| GIS | Plain `latitude`/`longitude` fields + Leaflet | Runs anywhere with no GDAL/PostGIS system dependencies. |

### Database choice — please read

The brief says PostgreSQL is the target but SQLite is fine if Postgres setup is a
blocker, as long as I say which I used and why.

**I default to SQLite** so this project runs cleanly on a fresh machine with zero
database setup — which is exactly what the "migrations run cleanly from scratch" and
"setup steps that work on a clean environment" checks call for. The code is fully
Postgres-ready: set `POSTGRES_DB` (and friends) in the environment, uncomment
`psycopg2-binary` in `requirements.txt`, and the same code switches to PostgreSQL
with no other changes (see `config/settings.py`). Nothing in the models or queries
is SQLite-specific.

---

## Quick start

Requires **Python 3.10+**.

```bash
# 1. From the project root, create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create the database schema (runs cleanly from scratch)
python manage.py migrate

# 4. (Optional but recommended) load realistic demo data so the UI isn't empty
python manage.py seed_demo

# 5. Run the server
python manage.py runserver
```

Then open:

- **Dashboard** → http://127.0.0.1:8000/
- **API docs (Swagger UI)** → http://127.0.0.1:8000/api/docs/
- **Django admin** → http://127.0.0.1:8000/admin/ (run `python manage.py createsuperuser` first if you want to log in)

---

## Testing the API with Swagger UI

I wired up a live, interactive Swagger console so you can exercise every endpoint
from the browser without curl or Postman.

1. Start the server (`python manage.py runserver`).
2. Go to **http://127.0.0.1:8000/api/docs/**.
3. You'll see the endpoints grouped by tag: **Farmers**, **Plots**, **Harvests**,
   **System**.
4. Click any endpoint to expand it, then click **Try it out**.
5. For write endpoints, an editable JSON body appears pre-filled with a realistic
   example. Adjust the values and click **Execute**.
6. Swagger shows you the exact `curl` command it sent, the response code, and the
   JSON response body.

**A good 60-second walkthrough:**

1. `POST /api/farmers/` → create a farmer. Note the `id` in the response.
2. `POST /api/plots/` → create a plot; set `farmer_id` to that id, and give it a
   `plot_code`, `size_hectares`, and optionally `latitude`/`longitude`.
3. `POST /api/harvests/` → log a harvest against that plot's id. Try a **negative
   `weight_kg`** to see the validation reject it with a clear message.
4. `GET /api/plots/{plot_id}/summary/` → see total weight, record count, and average.
5. `GET /api/plots/{plot_id}/predict/` → see the next-harvest projection (log a few
   harvests first so the trend has data).

> Note on CSRF: the JSON API endpoints are intentionally CSRF-exempt so the Swagger
> "Try it out" console and the jQuery frontend can call them directly. In
> production I'd protect these with token or session authentication plus CSRF; I
> kept it simple here because this is an internal tool and the brief isn't a
> security exercise.

The raw OpenAPI schema is available at **`/api/schema/`** if you'd rather import it
into Postman or Insomnia.

---

## API reference

All endpoints are JSON. Base path: `/api`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/overview/` | Dashboard counts (farmers, plots, records, total kg) |
| GET / POST | `/api/farmers/` | List all farmers / register a farmer |
| GET / PUT / DELETE | `/api/farmers/<id>/` | Retrieve / update / delete a farmer |
| GET / POST | `/api/plots/` | List all plots (with farmer name) / register a plot |
| GET / PUT / DELETE | `/api/plots/<id>/` | Retrieve / update / delete a plot |
| **GET** | **`/api/plots/<plot_id>/summary/`** | **Required endpoint:** total weight, count, average |
| GET | `/api/plots/<plot_id>/predict/` | Next-harvest estimate (AI/ML bonus) |
| GET / POST | `/api/harvests/` | List harvests (`?plot_id=` filter) / log a harvest |
| GET / DELETE | `/api/harvests/<id>/` | Retrieve / delete a harvest record |
| POST | `/api/harvests/import/` | Bulk import from CSV/Excel (data import bonus) |

Validation errors come back as `{"errors": {"field": "message"}}` with HTTP 400.

---

## Data model

```
Farmer (top-level)
  ├─ name, phone_number, community, date_registered
  └─ has many Plots
        Plot
          ├─ plot_code (unique), size_hectares, cocoa_variety (optional),
          │  date_registered, latitude/longitude (optional)
          └─ has many HarvestRecords
                HarvestRecord
                  └─ harvest_date, weight_kg (> 0), quality_grade (A/B/C)
```

Integrity is enforced at three layers so bad data is hard to create: model field
validators, a database **CHECK constraint** that weight must be positive, and
explicit checks in the views at the API boundary.

---

## Bonus features

I completed **all three** optional bonuses.

- **GIS** — `Plot` carries optional `latitude`/`longitude`, and the dashboard renders
  every located plot as a marker on a **Leaflet** map centred on the Volta Region.
  I chose lat/lng floats over a PostGIS `PointField` deliberately: it delivers the
  map feature the brief asks for while keeping the project runnable on SQLite with
  no GDAL/PostGIS system libraries to install.
- **Data import** — `POST /api/harvests/import/` accepts a **CSV or Excel** file
  (columns: plot code, date, weight, grade), read with **pandas** (+ openpyxl for
  Excel). It validates every row independently, bulk-creates the valid ones, and
  returns a row-numbered report of which rows failed and why. A ready-made
  `sample_harvests.csv` (with some deliberately bad rows) is included so you can see
  the failure reporting immediately — upload it from the **Import Harvests** tab.
- **AI/ML** — `GET /api/plots/<plot_id>/predict/` returns a simple next-harvest
  weight estimate. With 2+ records I fit a least-squares **linear trend** over the
  chronological history and project the next point (clamped at zero); with one
  record I carry it forward; with none I say so. I kept it transparent and returned
  the method + sample size rather than reaching for a trained model, which the brief
  explicitly said wasn't expected.

---

## Running the tests

```bash
python manage.py test
```

I focused the tests where a bug would hurt most: the required summary endpoint's
maths, the "no negative weights" rule, and the prediction bonus.

---

## Management commands

I included two custom commands:

- `python manage.py seed_demo` — loads realistic demo farmers, plots and harvests
  (Volta Region coordinates) so the dashboard and map aren't empty on first run.
- `python manage.py harvest_report [--min-weight 200]` — prints a per-plot harvest
  summary (total, average, record count) to the console, sorted by total. Handy for
  a quick check over SSH or a scheduled job.

---

## Deployment & CI

- **Continuous integration:** `.github/workflows/ci.yml` runs on every push and pull
  request — it installs dependencies, applies migrations, and runs the test suite,
  so a broken migration or failing test is caught before merge.
- **Hosting:** the project is ready to deploy to **Render** (recommended, via the
  committed `render.yaml` + `build.sh`) or **Vercel** (via `vercel.json` +
  `api/index.py`), backed by a **Neon** serverless PostgreSQL database. Static files
  are served by WhiteNoise, and the database is chosen from `DATABASE_URL`, so no
  code changes are needed to switch from local SQLite to Neon.
- Full step-by-step instructions — including Neon setup and an optional **Vercel
  Blob** section for persistent file storage — are in
  **[DEPLOYMENT.md](DEPLOYMENT.md)**.

---

## Assumptions I made

- **`plot_code` is unique** across the whole system. The import bonus matches
  harvest rows to plots by code, so it has to be unambiguous.
- **Quality grade is a fixed set** (A/B/C). I normalise inputs like `"Grade A"` →
  `"A"` on the way in.
- **Deleting a farmer cascades** to their plots and harvests (and deleting a plot
  cascades to its harvests). A plot or harvest has no meaning without its parent, so
  I chose `CASCADE` and report the number of cascaded rows in the delete response.
- **Coordinates are optional but paired** — if you supply one of latitude/longitude
  you must supply both, so a map marker is never half-defined.
- **Dates** are accepted as `YYYY-MM-DD` (plus a few common variants on import).

---

## What I'd do differently with more time

- **Authentication & permissions** — add login and role-based access (field officer
  vs. manager) and re-enable CSRF on the API behind token/session auth.
- **Pagination & filtering** — the list endpoints return everything today; at
  plantation scale I'd paginate and add query filters (by farmer, community, date
  range).
- **Richer prediction** — factor in seasonality and plot size, and expose a
  confidence range rather than a single number.
- **PostGIS upgrade path** — if the GIS work grows (plot boundaries, spatial
  queries), migrate the lat/lng fields to a GeoDjango `PointField` on PostGIS.
- **More test coverage** — CRUD edge cases and the CSV importer's row-level report,
  plus a small frontend smoke test.
- **Harvest edit endpoint** — I included create/read/delete for harvests and full
  CRUD for farmers and plots; with more time I'd round out harvest update too.
