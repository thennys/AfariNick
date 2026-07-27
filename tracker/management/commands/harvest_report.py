"""
A simple reporting command.

I added this so the operations team can pull a quick per-plot harvest summary
straight from the command line, without opening the dashboard — handy for cron jobs
or a quick check over SSH. It reuses the same aggregate logic as the summary API.
"""
from django.core.management.base import BaseCommand
from django.db.models import Avg, Sum

from tracker.models import Plot


class Command(BaseCommand):
    help = "Print a per-plot harvest summary (total, average, record count) to the console."

    def add_arguments(self, parser):
        # I expose one small filter so a user can focus on the productive plots.
        parser.add_argument(
            "--min-weight",
            type=float,
            default=0.0,
            help="Only show plots whose total harvested weight is at least this many kg.",
        )

    def handle(self, *args, **options):
        threshold = options["min_weight"]

        rows = []
        for plot in Plot.objects.select_related("farmer"):
            agg = plot.harvests.aggregate(total=Sum("weight_kg"), average=Avg("weight_kg"))
            total = float(agg["total"] or 0)
            if total < threshold:
                continue
            rows.append((plot, total, float(agg["average"] or 0), plot.harvests.count()))

        # I sort by total harvest descending so the strongest plots surface first.
        rows.sort(key=lambda r: r[1], reverse=True)

        if not rows:
            self.stdout.write("No plots matched the given filter.")
            return

        self.stdout.write(self.style.MIGRATE_HEADING("Harvest report — highest total first"))
        self.stdout.write(f"{'PLOT':<12}{'FARMER':<22}{'TOTAL (kg)':>12}{'AVG (kg)':>11}{'RECORDS':>9}")
        for plot, total, average, count in rows:
            self.stdout.write(
                f"{plot.plot_code:<12}{plot.farmer.name[:20]:<22}{total:>12.2f}{average:>11.2f}{count:>9}"
            )
