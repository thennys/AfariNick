"""
Data models for the Farm Plot & Harvest Tracker.

I modelled the three entities exactly as the brief describes them, with a clear
ownership chain: a Farmer owns many Plots, and a Plot owns many HarvestRecords.
I pushed as much integrity as possible down to the database layer (constraints,
validators, sensible field types) so bad data is hard to create in the first place.
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Farmer(models.Model):
    """
    Top-level entity. I gave it no foreign keys, matching the brief's note that a
    Farmer 'belongs to no one'. Everything else in the system ultimately hangs off
    a farmer.
    """
    name = models.CharField(max_length=150)
    # I store phone as a CharField, not an integer, because phone numbers can carry
    # leading zeros and '+233' prefixes that an integer would silently destroy.
    phone_number = models.CharField(max_length=20)
    community = models.CharField(max_length=120, help_text="Community or town the farmer operates in")
    # I use localdate (not timezone.now) so the default is a clean date in Afarinick's
    # timezone, and the API returns 'YYYY-MM-DD' rather than a full timestamp.
    date_registered = models.DateField(default=timezone.localdate)

    # I keep created/updated timestamps on every model. They cost nothing and make
    # auditing and debugging field-collected data far easier down the line.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.community})"

    def as_dict(self):
        # I centralise JSON serialisation on the model so every view returns a
        # farmer in exactly the same shape. I add plot_count because the frontend
        # likes to show it without a second request.
        return {
            "id": self.id,
            "name": self.name,
            "phone_number": self.phone_number,
            "community": self.community,
            "date_registered": self.date_registered.isoformat(),
            "plot_count": self.plots.count(),
        }


class Plot(models.Model):
    """
    A registered cocoa farm plot. I tied it to a Farmer with CASCADE delete because
    a plot has no meaning without the farmer who owns it.
    """
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="plots")
    # I chose plot_code as the human-facing identifier and made it unique, because
    # the CSV import bonus matches harvest rows to plots by code, so it must be
    # unambiguous.
    plot_code = models.CharField(max_length=50, unique=True)
    size_hectares = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Plot size in hectares (must be positive)",
    )
    # I made cocoa_variety optional exactly as specified. blank=True for forms,
    # null=True so the database can genuinely hold 'unknown'.
    cocoa_variety = models.CharField(max_length=100, blank=True, null=True)
    date_registered = models.DateField(default=timezone.localdate)

    # GIS bonus: I chose plain latitude/longitude float fields rather than a
    # GeoDjango PointField. I explain the trade-off fully in the README, but in
    # short: lat/lng keeps the project runnable on SQLite with no GDAL/PostGIS
    # system dependencies, while still giving me everything I need to drop markers
    # on a Leaflet map.
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plot_code"]

    def __str__(self):
        return f"{self.plot_code} — {self.farmer.name}"

    def as_dict(self):
        return {
            "id": self.id,
            "plot_code": self.plot_code,
            "farmer_id": self.farmer_id,
            "farmer_name": self.farmer.name,
            "size_hectares": float(self.size_hectares),
            "cocoa_variety": self.cocoa_variety,
            "date_registered": self.date_registered.isoformat(),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "harvest_count": self.harvests.count(),
        }


class HarvestRecord(models.Model):
    """A single harvest logged against a plot."""

    # I model quality grade as a fixed choice set. The brief gives Grade A/B/C, and
    # constraining it here stops typos like 'a ' or 'Grade AA' from ever landing in
    # the data, which matters when the import bonus is bulk-loading rows.
    class Grade(models.TextChoices):
        A = "A", "Grade A"
        B = "B", "Grade B"
        C = "C", "Grade C"

    plot = models.ForeignKey(Plot, on_delete=models.CASCADE, related_name="harvests")
    harvest_date = models.DateField()
    # I used a DecimalField with a MinValue validator for weight. Decimal avoids the
    # floating-point drift you get summing many float kilos, and the validator is my
    # first line of defence against the 'no negative weights' requirement.
    weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    quality_grade = models.CharField(max_length=1, choices=Grade.choices)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-harvest_date"]
        constraints = [
            # I added a DB-level CHECK constraint as a belt-and-braces backup to the
            # validator: even a raw SQL insert cannot store a non-positive weight.
            models.CheckConstraint(
                check=models.Q(weight_kg__gt=0),
                name="harvest_weight_positive",
            ),
        ]

    def __str__(self):
        return f"{self.plot.plot_code} · {self.harvest_date} · {self.weight_kg}kg ({self.quality_grade})"

    def as_dict(self):
        return {
            "id": self.id,
            "plot_id": self.plot_id,
            "plot_code": self.plot.plot_code,
            "harvest_date": self.harvest_date.isoformat(),
            "weight_kg": float(self.weight_kg),
            "quality_grade": self.quality_grade,
        }
