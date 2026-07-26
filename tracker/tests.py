"""
A small but meaningful test suite.

The brief calls tests a nice-to-have, so I focused on the areas where a bug would
hurt most: the required summary endpoint's maths, the 'no negative weights' rule,
and the prediction bonus. I write each test to read like a sentence describing the
behaviour I expect.
"""
import json

from django.test import TestCase
from django.urls import reverse

from .models import Farmer, HarvestRecord, Plot


class SummaryEndpointTests(TestCase):
    def setUp(self):
        self.farmer = Farmer.objects.create(name="Ama Owusu", phone_number="+233200000000", community="Kpando")
        self.plot = Plot.objects.create(farmer=self.farmer, plot_code="VR-KP-001", size_hectares=2.5)
        HarvestRecord.objects.create(plot=self.plot, harvest_date="2026-01-01", weight_kg=100, quality_grade="A")
        HarvestRecord.objects.create(plot=self.plot, harvest_date="2026-02-01", weight_kg=200, quality_grade="B")

    def test_summary_returns_total_count_and_average(self):
        # I expect total 300kg across 2 records, averaging 150kg.
        resp = self.client.get(reverse("plot-summary", args=[self.plot.id]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_harvest_weight_kg"], 300.0)
        self.assertEqual(data["harvest_record_count"], 2)
        self.assertEqual(data["average_weight_per_harvest_kg"], 150.0)

    def test_summary_of_missing_plot_is_404(self):
        resp = self.client.get(reverse("plot-summary", args=[9999]))
        self.assertEqual(resp.status_code, 404)


class HarvestValidationTests(TestCase):
    def setUp(self):
        self.farmer = Farmer.objects.create(name="Kojo Boateng", phone_number="+233201111111", community="Hohoe")
        self.plot = Plot.objects.create(farmer=self.farmer, plot_code="VR-HO-002", size_hectares=1.0)

    def test_negative_weight_is_rejected(self):
        # I expect the API to refuse a negative weight with a 400 and a clear message.
        resp = self.client.post(
            reverse("harvests-collection"),
            data=json.dumps({"plot_id": self.plot.id, "harvest_date": "2026-03-01",
                             "weight_kg": -5, "quality_grade": "A"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("weight_kg", resp.json()["errors"])

    def test_missing_fields_are_reported(self):
        resp = self.client.post(
            reverse("harvests-collection"),
            data=json.dumps({"plot_id": self.plot.id}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("weight_kg", resp.json()["errors"])


class PredictionTests(TestCase):
    def setUp(self):
        self.farmer = Farmer.objects.create(name="Efua Sarpong", phone_number="+233202222222", community="Kpando")
        self.plot = Plot.objects.create(farmer=self.farmer, plot_code="VR-KP-003", size_hectares=3.0)

    def test_prediction_with_no_history_is_null(self):
        resp = self.client.get(reverse("plot-predict", args=[self.plot.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["estimated_next_harvest_kg"])

    def test_prediction_projects_an_upward_trend(self):
        # With a rising series I expect a positive projection at least as large as
        # the most recent value's neighbourhood.
        for i, w in enumerate([100, 150, 200]):
            HarvestRecord.objects.create(plot=self.plot, harvest_date=f"2026-0{i+1}-01", weight_kg=w, quality_grade="A")
        resp = self.client.get(reverse("plot-predict", args=[self.plot.id]))
        data = resp.json()
        self.assertEqual(data["method"], "linear_trend")
        self.assertGreater(data["estimated_next_harvest_kg"], 200)
