"""WSGI entrypoint. I kept the Django default here since deployment isn't part of the brief."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
