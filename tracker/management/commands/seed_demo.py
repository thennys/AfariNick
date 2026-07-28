"""
A deterministic demo-data seeder.

I rewrote this to be fully deterministic (no random values) for three reasons:
its plot codes are stable, so the sample import CSV always matches; every plot gets
real coordinates in the Volta Region cocoa belt, so the Leaflet map always shows a
clean spread of markers; and re-running it always produces the exact same demo
state. It is destructive on purpose — it clears prior rows first so the demo starts
from a known baseline.
"""
import datetime

from django.core.management.base import BaseCommand

from tracker.models import Farmer, HarvestRecord, Plot


class Command(BaseCommand):
    help = "Seed the database with deterministic demo farmers, plots (with map coordinates) and harvests."

    # I fix four farmers in real Volta Region cocoa towns.
    FARMERS = [
        # (name, phone, community)
        ("Kwaku Mensah", "+233201234567", "Kpando"),
        ("Ama Owusu", "+233209876543", "Hohoe"),
        ("Yaw Darko", "+233244001122", "Jasikan"),
        ("Efua Sarpong", "+233265778899", "Kadjebi"),
    ]

    # I fix seven plots, each with a real latitude/longitude near its farmer's town
    # so every one of them appears on the map. The last two numbers are the starting
    # harvest weight and the monthly increment I use to build a realistic rising
    # trend (which also makes the next-harvest prediction meaningful).
    PLOTS = [
        # (plot_code, farmer_index, size_ha, variety, latitude, longitude, base_kg, step_kg)
        ("VR-KP-011", 0, 2.5, "CRIG Hybrid", 6.99890, 0.29540, 90, 12),
        ("VR-KP-012", 0, 3.1, "Amazon",      7.01250, 0.31100, 110, 9),
        ("VR-HO-021", 1, 1.8, "CRIG Hybrid", 7.15170, 0.47350, 80, 15),
        ("VR-HO-022", 1, 4.0, None,          7.16020, 0.48800, 130, 8),
        ("VR-JA-031", 2, 2.2, "Amelonado",   7.40480, 0.46670, 100, 11),
        ("VR-KA-041", 3, 3.4, "CRIG Hybrid", 7.53330, 0.45000, 95, 14),
        ("VR-KA-042", 3, 2.0, "Amazon",      7.54800, 0.46200, 120, 7),
    ]

    # I cycle grades deterministically across each plot's five harvests.
    GRADES = ["A", "B", "A", "C", "B"]

    def handle(self, *args, **options):
        # I wipe existing data first so the demo state is deterministic.
        HarvestRecord.objects.all().delete()
        Plot.objects.all().delete()
        Farmer.objects.all().delete()

        farmers = []
        for i, (name, phone, town) in enumerate(self.FARMERS):
            farmers.append(
                Farmer.objects.create(
                    name=name,
                    phone_number=phone,
                    community=town,
                    date_registered=datetime.date(2025, 11, 1) + datetime.timedelta(days=i * 3),
                )
            )

        harvest_count = 0
        for code, farmer_idx, size, variety, lat, lng, base, step in self.PLOTS:
            plot = Plot.objects.create(
                farmer=farmers[farmer_idx],
                plot_code=code,
                size_hectares=size,
                cocoa_variety=variety,
                latitude=lat,
                longitude=lng,
                date_registered=datetime.date(2025, 12, 1),
            )
            # I build five monthly harvests (Jan–May 2026) with a steady upward trend
            # plus a small deterministic wiggle so the data looks natural, not linear.
            for month in range(1, 6):
                wiggle = 3 if month % 2 else -2
                weight = base + step * (month - 1) + wiggle
                HarvestRecord.objects.create(
                    plot=plot,
                    harvest_date=datetime.date(2026, month, 15),
                    weight_kg=weight,
                    quality_grade=self.GRADES[month - 1],
                )
                harvest_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Farmer.objects.count()} farmers, {Plot.objects.count()} plots "
            f"(all with map coordinates), {harvest_count} harvest records."
        ))
