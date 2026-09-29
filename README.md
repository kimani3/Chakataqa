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

## Environment variables

- `DJANGO_SECRET_KEY` — required in production
- `DJANGO_DEBUG` — set to `0` in production
- `DJANGO_ALLOWED_HOSTS` — comma-separated host names
- `PAYSTACK_SECRET_KEY` — `sk_test_...` or `sk_live_...`
- `PAYSTACK_PUBLIC_KEY` — `pk_test_...` or `pk_live_...`
- `PAYSTACK_CURRENCY` — defaults to `KES`; must be enabled on your Paystack account

## Tests

```bash
python manage.py test
```
