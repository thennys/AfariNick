"""
App URL routing.

I grouped the routes by resource and kept the required endpoint,
GET /api/plots/<plot_id>/summary/, exactly as the brief specifies. Every path maps
to a function-based view.
"""
from django.urls import path

from . import views

urlpatterns = [
    # Pages
    path("", views.dashboard, name="dashboard"),
    path("api/docs/", views.swagger_ui, name="swagger-ui"),
    path("api/schema/", views.openapi_schema, name="openapi-schema"),

    # System
    path("api/overview/", views.overview, name="overview"),

    # Farmers (full CRUD)
    path("api/farmers/", views.farmers_collection, name="farmers-collection"),
    path("api/farmers/<int:farmer_id>/", views.farmer_detail, name="farmer-detail"),

    # Plots (full CRUD + summary + prediction)
    path("api/plots/", views.plots_collection, name="plots-collection"),
    path("api/plots/<int:plot_id>/", views.plot_detail, name="plot-detail"),
    path("api/plots/<int:plot_id>/summary/", views.plot_summary, name="plot-summary"),
    path("api/plots/<int:plot_id>/predict/", views.plot_predict, name="plot-predict"),

    # Harvests (list, log, read, delete + CSV/Excel import)
    path("api/harvests/", views.harvests_collection, name="harvests-collection"),
    path("api/harvests/import/", views.harvest_import, name="harvest-import"),
    path("api/harvests/<int:harvest_id>/", views.harvest_detail, name="harvest-detail"),
]
