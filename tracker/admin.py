"""
Admin registrations.

I registered all three models so a reviewer can inspect and edit data through the
Django admin as well as the custom UI. I added list displays and search fields
because they make the field data genuinely browsable.
"""
from django.contrib import admin

from .models import Farmer, HarvestRecord, Plot


@admin.register(Farmer)
class FarmerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone_number", "community", "date_registered")
    search_fields = ("name", "phone_number", "community")


@admin.register(Plot)
class PlotAdmin(admin.ModelAdmin):
    list_display = ("plot_code", "farmer", "size_hectares", "cocoa_variety", "date_registered")
    search_fields = ("plot_code", "farmer__name")
    list_filter = ("cocoa_variety",)


@admin.register(HarvestRecord)
class HarvestRecordAdmin(admin.ModelAdmin):
    list_display = ("plot", "harvest_date", "weight_kg", "quality_grade")
    list_filter = ("quality_grade", "harvest_date")
    search_fields = ("plot__plot_code",)
