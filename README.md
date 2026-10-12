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
- `investors/` — investor portal: models, profit-sharing logic (`services.py`), Paystack client (`paystack.py`)

## Investor portal

Investors sign in at `/investors/`. From there they can:

- deposit money through Paystack (card, M-Pesa or bank);
- see their principal (confirmed deposits) and their share of all investor
  capital;
- see profit earned, paid out and still owed, plus a growth chart.

**Share %** = an investor's confirmed deposits ÷ all investors' confirmed
deposits. Profit is **tracked and paid out**, not reinvested, so the principal
stays equal to what the investor deposited.

### Admin tasks (`/admin/`)

- **Add an investor:** create a User with an email address (Paystack needs
  one) and add them to the **Investors** group. There is no public signup.
- **Declare profit:** add a *Profit distribution* with the total profit and an
  "as of" date. On save it is split across investors according to their
  confirmed capital on that date. Allocations can't be edited afterwards.
- **Record payouts:** under *Profit allocations*, select the rows and run
  "Mark selected allocations as paid".
- **Deposits** are read-only. Their status comes only from Paystack.

### Paystack setup

1. Get your keys from Paystack Dashboard → Settings → API Keys & Webhooks. Use
   the **test** keys until everything works.
2. Set the webhook URL there to `https://<your-domain>/investors/paystack/webhook/`.
   Paystack calls it when a payment succeeds, even if the investor closes the
   browser before returning to the site.
3. Set the environment variables below.

## Deploy to Render

`render.yaml` describes the whole setup (a Blueprint): a Python web service
running gunicorn, plus a Render Postgres database. `build.sh` runs on every
deploy: it installs packages, collects static files, applies migrations and
creates the first admin account.

1. **Push this code to GitHub.** Render deploys from the branch you pick in
   step 3 (usually `main`). Every later push to that branch redeploys.
2. **Create a Render account** at https://dashboard.render.com and connect
   your GitHub account when asked.
3. **New → Blueprint**, pick this repository and branch. Render reads
   `render.yaml` and lists the `chakataqa` web service and the `chakataqa-db`
   database.
4. **Fill in the values Render asks for:**
   - `PAYSTACK_SECRET_KEY`, `PAYSTACK_PUBLIC_KEY` — start with the test keys.
   - `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`,
     `DJANGO_SUPERUSER_PASSWORD` — your admin login.

   `DJANGO_SECRET_KEY` is generated and `DATABASE_URL` is filled in from the
   database, so you don't set them.
5. **Click Apply** and watch the deploy log. It ends with
   "Superuser created successfully" and then "Your service is live".
6. **Open the site** at `https://chakataqa.onrender.com` (Render shows the
   exact URL at the top of the service page) and sign in at `/admin/`.
7. **Remove `DJANGO_SUPERUSER_PASSWORD`** from the service's *Environment*
   tab. The admin account stays; change its password later at `/admin/`.
8. **Point Paystack at the site:** in the Paystack dashboard set the webhook URL
   to `https://chakataqa.onrender.com/investors/paystack/webhook/`, then make a
   test deposit from an investor account.

**Custom domain (optional):** add it under the service's *Settings → Custom
Domains*, follow Render's DNS instructions, then add the domain to
`DJANGO_ALLOWED_HOSTS` (e.g. `chakataqa.com,www.chakataqa.com`) and update
the Paystack webhook URL.

**Free plan limits:** the web service sleeps after about 15 minutes without
visits and takes up to a minute to wake. A free Postgres database expires 30
days after creation (then 14 days' grace before deletion), so upgrade the
database to a paid plan before switching to live Paystack keys or storing
real investor data. Both run in the Frankfurt region; change `region` in
`render.yaml` before the first deploy if you want another one.

**When something breaks,** open the service's *Logs* tab. Build errors appear
there during deploy, and server errors are printed there at runtime.

## Environment variables

- `DJANGO_SECRET_KEY` — required in production
- `DJANGO_DEBUG` — set to `0` in production
- `DJANGO_ALLOWED_HOSTS` — comma-separated host names (Render's own
  `*.onrender.com` host is added automatically)
- `DATABASE_URL` — Postgres connection URL; without it the app uses `db.sqlite3`
- `PAYSTACK_SECRET_KEY` — `sk_test_...` or `sk_live_...`
- `PAYSTACK_PUBLIC_KEY` — `pk_test_...` or `pk_live_...`
- `PAYSTACK_CURRENCY` — defaults to `KES`; must be enabled on your Paystack account
- `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`,
  `DJANGO_SUPERUSER_PASSWORD` — if the password is set, `build.sh` creates
  this admin account (skipped when it already exists)

## Tests

```bash
python manage.py test
```
