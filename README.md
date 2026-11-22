# Somaliland GeoData Portal

A national portal where **government GIS specialists upload geospatial data**, **reviewers approve it**, and **everyone else can browse, view on a map and download it**.

Built with Django 5. It runs on SQLite for development and PostgreSQL in production. GDAL is not required.

---

## Roles

| Role | Who | Can do |
|---|---|---|
| Visitor | Anyone | Browse catalog & map, download *open* datasets |
| Public user | Anyone who registers | + download *registered-only* datasets |
| Team uploader | Staff of the organization that runs the portal | + upload datasets (their own, or data sent in by other institutions) |
| Team reviewer | Senior staff of the same organization | + approve or return uploads (never their own) |
| Administrator | Django superuser | Everything, incl. users, institutions, categories |

**Only your team uploads.** Sign-up always creates a public account, and there is no way to request upload rights from the website.
To add a team member: **Admin → Users** → select the user → action **"Set role: Team uploader"** (or *Team reviewer*).

**Outside institutions send data to the team** using the contacts on the **Share your data** page (`/share-data/`): Telegram, email and phone, set in `.env`:

```
PORTAL_ORGANIZATION=Your organization name
CONTRIBUTE_TELEGRAM_URL=https://t.me/yourusername
CONTRIBUTE_TELEGRAM_HANDLE=@yourusername
CONTRIBUTE_EMAIL=data@yourdomain.so
CONTRIBUTE_PHONE=+252 ...
```

When a team member uploads data received from an institution, they choose it as the **Source institution**, so the dataset is credited to that institution.

## Publishing workflow

```
Institution sends data (Telegram/email) ──► Team uploads ──► PENDING ──► Reviewer approves ──► PUBLISHED (visible to all)
                          │
                          └──► Reviewer requests changes ──► RETURNED ──► uploader edits ──► PENDING
```

Dataset files are stored in `private_media/`, **outside** the public media folder. Downloads always go through the portal. It checks status and access level, and counts every download (see `DownloadLog` in the admin).

## Run it in your browser (no installation)

1. On the GitHub page, click **Code → Codespaces → Create codespace on main**.
2. Wait 2–3 minutes while it installs and sets up the demo data.
3. The portal opens in a new tab. If it doesn't, open the **Ports** tab and click the globe icon next to port 8000.

Logins (password `ChangeMe-2026!`): `admin` (administrator, use `/admin/`), `specialist`, `reviewer`, `citizen`.

## Quick start (development)

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # then edit values

python manage.py makemigrations organizations accounts datasets
python manage.py migrate
python manage.py seed_portal --demo  # categories, institutions, demo users + sample dataset
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000. Demo logins (password `ChangeMe-2026!`): `specialist` (team uploader), `reviewer` (team reviewer), `citizen` (public user).
**Delete the demo users before going live.**

## Supported upload formats

| Format | Checks done on upload |
|---|---|
| Shapefile (.zip) | must contain .shp/.shx/.dbf; CRS read from .prj; zip paths checked for safety |
| GeoJSON | valid JSON, lon/lat range, feature count, bounding box (files ≤ 15 MB are drawn in the Map Viewer) |
| GeoPackage, GeoTIFF | file signature checked |
| KML/KMZ, CSV | accepted as-is |

Maximum size: `MAX_UPLOAD_MB` (default 500). Your web server must allow the same size (Nginx `client_max_body_size 500M;`).

## Project layout

```
config/          settings, urls, wsgi
accounts/        User (with role), login/register/profile
organizations/   Government institutions
datasets/        Dataset, Category, DownloadLog, upload/review/catalog/map views, file checks
  management/commands/seed_portal.py
templates/       HTML pages
static/          css/portal.css, js/map.js, images/
private_media/   uploaded dataset files (created automatically; never served directly)
media/           thumbnails and logos (public)
```

## Before going live: checklist

- [ ] `DJANGO_DEBUG=False`, a long random `DJANGO_SECRET_KEY`, real `DJANGO_ALLOWED_HOSTS`
- [ ] PostgreSQL (`DATABASE_ENGINE=postgresql`) with daily backups of the database **and** `private_media/`
- [ ] HTTPS (e.g. Let's Encrypt) in front of Gunicorn behind Nginx
- [ ] `python manage.py collectstatic`; Nginx serves `/static/` and `/media/` only, **never** `private_media/`
- [ ] Replace `static/images/emblem.svg` with the official emblem, and add `static/images/hero.jpg` (compressed, under 250 KB)
- [ ] Replace the institution list in `seed_portal.py` and the placeholder text on the About page (terms, privacy, contact)
- [ ] Remove demo users and the sample dataset
- [ ] Email settings, so password resets and request notifications can be sent

## Suggested next steps

1. **Background processing (Celery + Redis):** reproject to EPSG:4326, convert rasters to Cloud-Optimized GeoTIFF, generate thumbnails automatically (needs GDAL).
2. **OGC services:** publish approved layers to GeoServer (WMS/WFS) so QGIS/ArcGIS users can connect directly.
3. **Somali translation:** wrap template strings in `{% translate %}` and run `makemessages -l so`. Language support is already enabled in settings.
4. **Email notifications:** tell the uploader when their dataset is approved or returned, and tell reviewers about new submissions.
5. **Versioning:** let specialists upload a new version of a published dataset without losing the old one.
6. **API:** a read-only JSON/DCAT catalog endpoint for other government systems.
