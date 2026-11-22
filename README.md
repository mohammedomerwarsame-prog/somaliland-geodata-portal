# Somaliland GeoData Portal

A national portal where **government GIS specialists upload geospatial data**, **reviewers approve it**, and **everyone else can browse, view on a map and download it**.

Built with Django 5. It runs on SQLite for development and PostgreSQL in production. GDAL is not required.

---

## Roles

| Role | Who | Can do |
|---|---|---|
| Visitor | Anyone | Browse catalog & map, download *open* datasets |
| Public user | Anyone who registers | + download *registered-only* datasets |
| GIS specialist | Approved staff of an institution | + upload datasets for their institution, edit them while pending/returned |
| Data reviewer | Senior staff / data office | + approve or return uploads (never their own) |
| Administrator | Django superuser | Everything, incl. institutions, users, categories |

**Nobody can make themselves a specialist.** Sign-up always creates a public account. To get upload rights:
1. The person registers, then goes to **Profile → Request specialist access** and picks their institution.
2. An administrator opens **Admin → Specialist requests**, checks the request (for example by calling the institution) and runs the **"Approve"** action.

Admins can also set roles directly in **Admin → Users** (actions: *Set role: GIS specialist / reviewer / public*).

## Publishing workflow

```
Specialist uploads ──► PENDING ──► Reviewer approves ──► PUBLISHED (visible to all)
                          │
                          └──► Reviewer requests changes ──► RETURNED ──► specialist edits ──► PENDING
```

Dataset files are stored in `private_media/`, **outside** the public media folder. Downloads always go through the portal. It checks status and access level, and counts every download (see `DownloadLog` in the admin).

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

Open http://127.0.0.1:8000. Demo logins (password `ChangeMe-2026!`): `specialist`, `reviewer`, `citizen`.
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
accounts/        User (with role + institution), SpecialistRequest, login/register/profile
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
