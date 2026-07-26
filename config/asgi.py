"""ASGI entrypoint. Included for completeness; the app runs fine under WSGI too."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()
