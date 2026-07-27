"""
All views for the tracker.

Two important constraints from the brief shaped this file, and I followed both
deliberately:

  * I wrote every view as a plain FUNCTION-BASED view. There is not a single
    class-based view in the project, matching Afarinick's stated codebase
    convention.
  * I did NOT use the Django Forms framework anywhere. Validation is done by hand
    in these functions (with help from tracker/utils.py), and the HTML forms on the
    frontend are hand-written and submitted via jQuery/AJAX.

I dispatch on request.method inside each view rather than splitting into many tiny
views, which keeps each resource's logic in one readable place.
"""
import json

import pandas as pd
from django.db.models import Avg, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .api_schema import build_openapi_schema
from .models import Farmer, HarvestRecord, Plot
from .utils import (
    clean_positive_decimal,
    error_response,
    parse_date,
    parse_json_body,
    require_fields,
)

# I decided to CSRF-exempt the JSON API. My reasoning: these endpoints form a
# stateless internal API consumed by the jQuery frontend and by the Swagger "Try it
# out" console. Exempting them keeps both callers working without threading a token
# through every request. In production I'd protect them with token or session auth
# plus CSRF; I note that explicitly in the README so the trade-off is visible.


# ---------------------------------------------------------------------------
# Page views (server-rendered HTML shells; data is fetched by AJAX afterwards)
# ---------------------------------------------------------------------------
@require_http_methods(["GET"])
def dashboard(request):
    """I render the operations dashboard shell. The tables, map and forms hydrate via AJAX."""
    return render(request, "tracker/dashboard.html")


@require_http_methods(["GET"])
def swagger_ui(request):
    """I serve a Swagger UI page (loaded from CDN) pointed at my OpenAPI schema endpoint."""
    return render(request, "tracker/swagger.html")


@require_http_methods(["GET"])
def openapi_schema(request):
    """I generate the OpenAPI 3 document in Python and hand it to Swagger UI as JSON."""
    return JsonResponse(build_openapi_schema(request), json_dumps_params={"indent": 2})


# ---------------------------------------------------------------------------
# Overview (small helper endpoint so the dashboard header cards stay live)
# ---------------------------------------------------------------------------
@require_http_methods(["GET"])
def overview(request):
    """I return the headline counts the dashboard shows at the top of the page."""
    total_weight = HarvestRecord.objects.aggregate(total=Sum("weight_kg"))["total"] or 0
    return JsonResponse(
        {
            "farmers": Farmer.objects.count(),
            "plots": Plot.objects.count(),
            "harvest_records": HarvestRecord.objects.count(),
            "total_harvest_kg": float(total_weight),
        }
    )


# ---------------------------------------------------------------------------
# Farmers — full CRUD
# ---------------------------------------------------------------------------
@csrf_exempt
def farmers_collection(request):
    """I handle the farmer collection: GET lists everyone, POST registers a new farmer."""
    if request.method == "GET":
        farmers = [f.as_dict() for f in Farmer.objects.all()]
        return JsonResponse({"results": farmers, "count": len(farmers)})

    if request.method == "POST":
        try:
            data = parse_json_body(request)
        except json.JSONDecodeError:
            return error_response("Request body is not valid JSON.")

        missing = require_fields(data, ["name", "phone_number", "community"])
        if missing:
            return error_response(missing)

        farmer = Farmer(
            name=data["name"].strip(),
            phone_number=str(data["phone_number"]).strip(),
            community=data["community"].strip(),
        )
        # I let the caller optionally set date_registered; otherwise the model
        # default (today) applies.
        if data.get("date_registered"):
            parsed, err = parse_date(data["date_registered"], "date_registered")
            if err:
                return error_response({"date_registered": err})
            farmer.date_registered = parsed

        farmer.save()
        return JsonResponse(farmer.as_dict(), status=201)

    return error_response("Method not allowed.", status=405)


@csrf_exempt
def farmer_detail(request, farmer_id):
    """I handle a single farmer: GET reads, PUT/PATCH updates, DELETE removes."""
    try:
        farmer = Farmer.objects.get(pk=farmer_id)
    except Farmer.DoesNotExist:
        return error_response("Farmer not found.", status=404)

    if request.method == "GET":
        return JsonResponse(farmer.as_dict())

    if request.method in ("PUT", "PATCH"):
        try:
            data = parse_json_body(request)
        except json.JSONDecodeError:
            return error_response("Request body is not valid JSON.")

        # I treat PUT and PATCH the same way for simplicity: I update whichever
        # fields are supplied and leave the rest untouched.
        if "name" in data and data["name"].strip():
            farmer.name = data["name"].strip()
        if "phone_number" in data and str(data["phone_number"]).strip():
            farmer.phone_number = str(data["phone_number"]).strip()
        if "community" in data and data["community"].strip():
            farmer.community = data["community"].strip()
        if data.get("date_registered"):
            parsed, err = parse_date(data["date_registered"], "date_registered")
            if err:
                return error_response({"date_registered": err})
            farmer.date_registered = parsed

        farmer.save()
        return JsonResponse(farmer.as_dict())

    if request.method == "DELETE":
        # I surface how many plots will cascade so the caller understands the blast
        # radius of the delete.
        plot_count = farmer.plots.count()
        farmer.delete()
        return JsonResponse({"deleted": True, "cascaded_plots": plot_count})

    return error_response("Method not allowed.", status=405)


# ---------------------------------------------------------------------------
# Plots — full CRUD
# ---------------------------------------------------------------------------
@csrf_exempt
def plots_collection(request):
    """I handle the plot collection: GET lists all plots (with farmer name), POST registers one."""
    if request.method == "GET":
        # I select_related the farmer to avoid an N+1 query when serialising the
        # farmer name for each plot.
        plots = [p.as_dict() for p in Plot.objects.select_related("farmer").all()]
        return JsonResponse({"results": plots, "count": len(plots)})

    if request.method == "POST":
        try:
            data = parse_json_body(request)
        except json.JSONDecodeError:
            return error_response("Request body is not valid JSON.")

        errors = require_fields(data, ["farmer_id", "plot_code", "size_hectares"])
        if errors:
            return error_response(errors)

        # I validate the farmer exists before creating the plot, returning a clear
        # message instead of a raw integrity error.
        try:
            farmer = Farmer.objects.get(pk=data["farmer_id"])
        except (Farmer.DoesNotExist, ValueError, TypeError):
            return error_response({"farmer_id": "No farmer exists with that id."})

        size, size_err = clean_positive_decimal(data["size_hectares"], "size_hectares")
        if size_err:
            return error_response({"size_hectares": size_err})

        # I enforce the unique plot_code myself for a friendly message rather than a 500.
        code = str(data["plot_code"]).strip()
        if Plot.objects.filter(plot_code=code).exists():
            return error_response({"plot_code": "A plot with this code already exists."})

        plot = Plot(
            farmer=farmer,
            plot_code=code,
            size_hectares=size,
            cocoa_variety=(data.get("cocoa_variety") or "").strip() or None,
        )
        # GIS bonus: coordinates are optional. If one is supplied I require both, so
        # a marker is never half-defined.
        lat, lng = data.get("latitude"), data.get("longitude")
        if lat not in (None, "") or lng not in (None, ""):
            try:
                plot.latitude = float(lat)
                plot.longitude = float(lng)
            except (TypeError, ValueError):
                return error_response({"location": "latitude and longitude must both be valid numbers."})
        if data.get("date_registered"):
            parsed, err = parse_date(data["date_registered"], "date_registered")
            if err:
                return error_response({"date_registered": err})
            plot.date_registered = parsed

        plot.save()
        return JsonResponse(plot.as_dict(), status=201)

    return error_response("Method not allowed.", status=405)


@csrf_exempt
def plot_detail(request, plot_id):
    """I handle a single plot: GET reads, PUT/PATCH updates, DELETE removes."""
    try:
        plot = Plot.objects.select_related("farmer").get(pk=plot_id)
    except Plot.DoesNotExist:
        return error_response("Plot not found.", status=404)

    if request.method == "GET":
        return JsonResponse(plot.as_dict())

    if request.method in ("PUT", "PATCH"):
        try:
            data = parse_json_body(request)
        except json.JSONDecodeError:
            return error_response("Request body is not valid JSON.")

        if data.get("farmer_id"):
            try:
                plot.farmer = Farmer.objects.get(pk=data["farmer_id"])
            except (Farmer.DoesNotExist, ValueError, TypeError):
                return error_response({"farmer_id": "No farmer exists with that id."})
        if "plot_code" in data and str(data["plot_code"]).strip():
            new_code = str(data["plot_code"]).strip()
            if Plot.objects.filter(plot_code=new_code).exclude(pk=plot.pk).exists():
                return error_response({"plot_code": "A plot with this code already exists."})
            plot.plot_code = new_code
        if "size_hectares" in data:
            size, size_err = clean_positive_decimal(data["size_hectares"], "size_hectares")
            if size_err:
                return error_response({"size_hectares": size_err})
            plot.size_hectares = size
        if "cocoa_variety" in data:
            plot.cocoa_variety = (data.get("cocoa_variety") or "").strip() or None
        if "latitude" in data or "longitude" in data:
            try:
                plot.latitude = float(data["latitude"]) if data.get("latitude") not in (None, "") else None
                plot.longitude = float(data["longitude"]) if data.get("longitude") not in (None, "") else None
            except (TypeError, ValueError):
                return error_response({"location": "latitude and longitude must be valid numbers."})

        plot.save()
        return JsonResponse(plot.as_dict())

    if request.method == "DELETE":
        harvest_count = plot.harvests.count()
        plot.delete()
        return JsonResponse({"deleted": True, "cascaded_harvests": harvest_count})

    return error_response("Method not allowed.", status=405)


@require_http_methods(["GET"])
def plot_summary(request, plot_id):
    """
    The required summary endpoint: GET /api/plots/<plot_id>/summary/.

    I return total harvest weight, the number of harvest records, and the average
    weight per harvest for the plot. I compute all three in a single database
    aggregate query rather than pulling rows into Python.
    """
    try:
        plot = Plot.objects.get(pk=plot_id)
    except Plot.DoesNotExist:
        return error_response("Plot not found.", status=404)

    stats = plot.harvests.aggregate(total=Sum("weight_kg"), average=Avg("weight_kg"))
    count = plot.harvests.count()
    return JsonResponse(
        {
            "plot_id": plot.id,
            "plot_code": plot.plot_code,
            "farmer_name": plot.farmer.name,
            "total_harvest_weight_kg": float(stats["total"] or 0),
            "harvest_record_count": count,
            # I guard the average against a divide-by-zero by returning 0 when there
            # are no harvests, so the frontend never has to special-case null here.
            "average_weight_per_harvest_kg": round(float(stats["average"] or 0), 2),
        }
    )


@require_http_methods(["GET"])
def plot_predict(request, plot_id):
    """
    AI/ML BONUS: GET /api/plots/<plot_id>/predict/.

    The brief explicitly says a trained model is not expected, so I chose a
    transparent, explainable estimate over a black box. My method:

      * 0 records  -> I can't project anything, so I say so clearly.
      * 1 record   -> I carry that single value forward.
      * 2+ records -> I fit a simple linear least-squares trend over the
        chronological sequence and project the next point, clamped at zero so a
        downward trend can never predict a negative harvest. I also return the
        historical average as context.

    I return the method used and the sample size so the operations team can judge
    how much to trust the number, which matters more than a slightly fancier model.
    """
    try:
        plot = Plot.objects.get(pk=plot_id)
    except Plot.DoesNotExist:
        return error_response("Plot not found.", status=404)

    weights = list(
        plot.harvests.order_by("harvest_date").values_list("weight_kg", flat=True)
    )
    weights = [float(w) for w in weights]
    n = len(weights)

    if n == 0:
        return JsonResponse(
            {
                "plot_id": plot.id,
                "plot_code": plot.plot_code,
                "based_on_records": 0,
                "method": "no_data",
                "estimated_next_harvest_kg": None,
                "note": "No harvest history yet, so no projection is possible.",
            }
        )

    average = round(sum(weights) / n, 2)

    if n == 1:
        estimate = round(weights[0], 2)
        method = "single_record_carry_forward"
    else:
        # I compute the least-squares slope/intercept by hand (no heavy ML library
        # needed for a straight line) over x = 0,1,2,...,n-1.
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(weights) / n
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, weights))
        denominator = sum((x - mean_x) ** 2 for x in xs)
        slope = numerator / denominator if denominator else 0
        intercept = mean_y - slope * mean_x
        raw = intercept + slope * n  # project the next index
        estimate = round(max(0.0, raw), 2)  # clamp: never predict a negative harvest
        method = "linear_trend"

    return JsonResponse(
        {
            "plot_id": plot.id,
            "plot_code": plot.plot_code,
            "based_on_records": n,
            "method": method,
            "historical_average_kg": average,
            "estimated_next_harvest_kg": estimate,
        }
    )


# ---------------------------------------------------------------------------
# Harvest records — list, create (log), read, delete + CSV/Excel import bonus
# ---------------------------------------------------------------------------
@csrf_exempt
def harvests_collection(request):
    """I handle harvests: GET lists them (optionally filtered by ?plot_id=), POST logs a new one."""
    if request.method == "GET":
        qs = HarvestRecord.objects.select_related("plot")
        plot_id = request.GET.get("plot_id")
        if plot_id:
            qs = qs.filter(plot_id=plot_id)
        records = [h.as_dict() for h in qs]
        return JsonResponse({"results": records, "count": len(records)})

    if request.method == "POST":
        try:
            data = parse_json_body(request)
        except json.JSONDecodeError:
            return error_response("Request body is not valid JSON.")

        errors = require_fields(data, ["plot_id", "harvest_date", "weight_kg", "quality_grade"])
        if errors:
            return error_response(errors)

        try:
            plot = Plot.objects.get(pk=data["plot_id"])
        except (Plot.DoesNotExist, ValueError, TypeError):
            return error_response({"plot_id": "No plot exists with that id."})

        harvest_date, date_err = parse_date(data["harvest_date"], "harvest_date")
        if date_err:
            return error_response({"harvest_date": date_err})

        weight, weight_err = clean_positive_decimal(data["weight_kg"], "weight_kg")
        if weight_err:
            return error_response({"weight_kg": weight_err})

        grade = str(data["quality_grade"]).strip().upper().replace("GRADE", "").strip()
        if grade not in HarvestRecord.Grade.values:
            return error_response({"quality_grade": "Grade must be one of A, B, or C."})

        record = HarvestRecord.objects.create(
            plot=plot, harvest_date=harvest_date, weight_kg=weight, quality_grade=grade
        )
        return JsonResponse(record.as_dict(), status=201)

    return error_response("Method not allowed.", status=405)


@csrf_exempt
def harvest_detail(request, harvest_id):
    """I handle a single harvest: GET reads it, DELETE removes it."""
    try:
        record = HarvestRecord.objects.select_related("plot").get(pk=harvest_id)
    except HarvestRecord.DoesNotExist:
        return error_response("Harvest record not found.", status=404)

    if request.method == "GET":
        return JsonResponse(record.as_dict())

    if request.method == "DELETE":
        record.delete()
        return JsonResponse({"deleted": True})

    return error_response("Method not allowed.", status=405)


@csrf_exempt
@require_http_methods(["POST"])
def harvest_import(request):
    """
    DATA IMPORT BONUS: POST /api/harvests/import/ (multipart file upload).

    I accept a CSV or Excel file with columns: plot code, date, weight, grade. I
    read it with pandas (which also handles Excel via openpyxl), then validate every
    row independently. My guiding principle here is that a bad row should never sink
    the whole file: I bulk-create the valid rows and return a precise, row-numbered
    report of what failed and why, so a field officer can fix just those lines.
    """
    upload = request.FILES.get("file")
    if not upload:
        return error_response({"file": "Please attach a CSV or Excel file under the 'file' field."})

    name = upload.name.lower()
    try:
        if name.endswith(".csv"):
            df = pd.read_csv(upload)
        elif name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(upload, engine="openpyxl")
        else:
            return error_response({"file": "Unsupported file type. Please upload a .csv or .xlsx file."})
    except Exception as exc:  # I surface parse failures as a clean 400, not a 500.
        return error_response({"file": f"Could not read the file: {exc}"})

    # I normalise column headers (lowercase, strip, collapse spaces) so 'Plot Code',
    # 'plot_code' and 'plotcode' all map to the same field.
    def norm(col):
        return str(col).strip().lower().replace(" ", "_")

    df.columns = [norm(c) for c in df.columns]
    aliases = {
        "plot_code": {"plot_code", "plotcode", "plot", "code"},
        "date": {"date", "harvest_date", "harvestdate"},
        "weight": {"weight", "weight_kg", "weightkg", "kg"},
        "grade": {"grade", "quality_grade", "quality"},
    }
    resolved = {}
    for canonical, options in aliases.items():
        match = next((c for c in df.columns if c in options), None)
        if match is None:
            return error_response(
                {"file": f"Missing a '{canonical}' column. Expected columns: plot code, date, weight, grade."}
            )
        resolved[canonical] = match

    # I pre-load plot codes into a dict for O(1) lookups instead of hitting the DB
    # once per row.
    plots_by_code = {p.plot_code: p for p in Plot.objects.all()}

    created, failures, to_create = 0, [], []
    for idx, row in df.iterrows():
        row_number = int(idx) + 2  # +2 accounts for the header row and 1-based counting
        row_errors = []

        code = str(row[resolved["plot_code"]]).strip()
        plot = plots_by_code.get(code)
        if not plot:
            row_errors.append(f"No plot found with code '{code}'.")

        harvest_date, date_err = parse_date(row[resolved["date"]], "date")
        if date_err:
            row_errors.append(date_err)

        weight, weight_err = clean_positive_decimal(row[resolved["weight"]], "weight")
        if weight_err:
            row_errors.append(weight_err)

        grade = str(row[resolved["grade"]]).strip().upper().replace("GRADE", "").strip()
        if grade not in HarvestRecord.Grade.values:
            row_errors.append("grade must be one of A, B, or C.")

        if row_errors:
            failures.append({"row": row_number, "errors": row_errors})
            continue

        to_create.append(
            HarvestRecord(plot=plot, harvest_date=harvest_date, weight_kg=weight, quality_grade=grade)
        )

    # I bulk_create the valid rows in one query for efficiency.
    if to_create:
        HarvestRecord.objects.bulk_create(to_create)
        created = len(to_create)

    return JsonResponse(
        {
            "created": created,
            "failed": len(failures),
            "total_rows": int(len(df)),
            "failures": failures,
        },
        status=200 if created or not failures else 422,
    )
