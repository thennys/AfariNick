#!/usr/bin/env bash
# Render runs this during every deploy. I keep it to the three steps a Django app
# needs on a fresh build: install dependencies, gather static files for WhiteNoise,
# and apply any new migrations to the (Neon) database.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
