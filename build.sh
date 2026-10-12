#!/usr/bin/env bash
# Render runs this on every deploy (see render.yaml).
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Create the first admin from DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD.
# Later deploys skip it because the user already exists.
if [[ -n "$DJANGO_SUPERUSER_PASSWORD" ]]; then
  python manage.py createsuperuser --no-input || echo "Superuser not created (it may already exist)."
fi
