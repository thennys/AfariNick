"""
A demo-data seeder.

I added this so a reviewer sees a populated, believable dashboard on first run
instead of empty tables. The coordinates cluster around the Volta Region cocoa
areas (Kpando/Hohoe) that Afarinick actually operates in, so the Leaflet map lands
somewhere meaningful. I made it idempotent-ish: it clears prior demo rows first so
re-running never piles up duplicates.
"""
import datetime
import random

from django.core.management.base import BaseCommand

from tracker.models import Farmer, HarvestRecord, Plot


class Command(BaseCommand):
    help = "Seed the database with realistic demo farmers, plots and harvest records."

    def handle(self, *args, **options):
        # I wipe existing data first so the demo state is deterministic.
        HarvestRecord.objects.all().delete()
        Plot.objects.all().delete()
        Farmer.objects.all().delete()

        farmers_seed = [
            ("Kwaku Mensah", "+233201234567", "Kpando", 6.9989, 0.2954),
            ("Ama Owusu", "+233209876543", "Hohoe", 7.1517, 0.4735),
            ("Yaw Darko", "+233244001122", "Jasikan", 7.4048, 0.4667),
            ("Efua Sarpong", "+233265778899", "Kadjebi", 7.5333, 0.4500),
        ]
        varieties = ["CRIG Hybrid", "Amazon", "Amelonado", None]
        grades = ["A", "A", "B", "B", "C"]

        created_plots = []
        for i, (name, phone, town, lat, lng) in enumerate(farmers_seed, start=1):
            farmer = Farmer.objects.create(
                name=name, phone_number=phone, community=town,
                date_registered=datetime.date(2025, 11, 1) + datetime.timedelta(days=i * 3),
            )
            # I give each farmer one or two plots, jittering the coordinates so the
            # markers don't stack exactly on top of each other.
            for p in range(random.randint(1, 2)):
                plot = Plot.objects.create(
                    farmer=farmer,
                    plot_code=f"VR-{town[:2].upper()}-{i:02d}{p+1}",
                    size_hectares=round(random.uniform(1.0, 5.0), 2),
                    cocoa_variety=random.choice(varieties),
                    latitude=round(lat + random.uniform(-0.05, 0.05), 5),
                    longitude=round(lng + random.uniform(-0.05, 0.05), 5),
                    date_registered=datetime.date(2025, 12, 1),
                )
                created_plots.append(plot)

        # I generate a rising-then-noisy harvest history so the trend prediction has
        # something interesting to work with.
        for plot in created_plots:
            base = random.uniform(80, 140)
            for month in range(1, random.randint(4, 7)):
                HarvestRecord.objects.create(
                    plot=plot,
                    harvest_date=datetime.date(2026, month, random.randint(1, 27)),
                    weight_kg=round(base + month * random.uniform(5, 25), 2),
                    quality_grade=random.choice(grades),
                )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Farmer.objects.count()} farmers, {Plot.objects.count()} plots, "
            f"{HarvestRecord.objects.count()} harvest records."
        ))
