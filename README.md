# Chakataqa

Landing page for Chakataqa, a plastic recycling startup, built with Django.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/. Contact form submissions appear in the admin at
`/admin/` (create a user with `python manage.py createsuperuser`).

## Where things live

- `core/content.py` — page copy (stats, steps, services, testimonials)
- `templates/base.html`, `templates/core/index.html` — page markup
- `static/css/styles.css` — styles; colors and fonts are CSS variables at the top
- `core/models.py` — `ContactMessage` saved by the contact form

## Environment variables (production)

- `DJANGO_SECRET_KEY` — required in production
- `DJANGO_DEBUG` — set to `0` in production
- `DJANGO_ALLOWED_HOSTS` — comma-separated host names

## Tests

```bash
python manage.py test
```
