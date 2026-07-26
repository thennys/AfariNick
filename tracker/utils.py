"""
Small helpers shared across the views.

I pulled request-parsing and validation out of the views so each view reads as a
short, clear sequence of steps. Keeping this logic in one place also means the API
returns errors in a single consistent shape everywhere.
"""
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse


def parse_json_body(request):
    """
    I accept either a JSON body or a classic form-encoded POST. The jQuery frontend
    sends JSON, but this flexibility means the Swagger console and tools like curl
    can post form data too, and everything still works.
    """
    if request.content_type and "application/json" in request.content_type:
        if not request.body:
            return {}
        return json.loads(request.body.decode("utf-8"))
    return request.POST.dict()


def error_response(errors, status=400):
    """I standardise every failure on {'errors': {...}} so the frontend can rely on one shape."""
    if isinstance(errors, str):
        errors = {"detail": errors}
    return JsonResponse({"errors": errors}, status=status)


def require_fields(data, fields):
    """I return a dict of 'this field is required' messages for anything missing or blank."""
    missing = {}
    for field in fields:
        value = data.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            missing[field] = "This field is required."
    return missing


def clean_positive_decimal(value, field_name):
    """
    I parse and guard positive money/weight/size values in one place. It returns
    (decimal_value, error_message) so callers can collect errors cleanly. This is
    where the 'no negative weights' rule is enforced at the API boundary, on top of
    the model validator and the database CHECK constraint.
    """
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None, f"{field_name} must be a number."
    if parsed <= 0:
        return None, f"{field_name} must be greater than zero."
    return parsed, None


def parse_date(value, field_name):
    """I accept ISO dates (YYYY-MM-DD) and a couple of common variants, and report a clear error otherwise."""
    if isinstance(value, (date, datetime)):
        return (value.date() if isinstance(value, datetime) else value), None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date(), None
        except (ValueError, TypeError):
            continue
    return None, f"{field_name} must be a valid date (YYYY-MM-DD)."
