"""
Root URL configuration.

I keep the project-level urls thin: the admin plus everything from the tracker
app. All the real routing lives in tracker/urls.py so the app stays portable.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("tracker.urls")),
]
