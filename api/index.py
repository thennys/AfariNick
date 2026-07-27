"""
Vercel serverless entrypoint.

Vercel's Python runtime looks for a WSGI/ASGI callable named ``app`` in the file it
builds. I point that at Django's WSGI application, so the whole site runs as a single
serverless function. Static files are handled by WhiteNoise inside the app, so no
separate static routing is required.
"""
from config.wsgi import application

app = application
