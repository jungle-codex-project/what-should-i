from datetime import datetime
from functools import wraps

from flask import flash, redirect, request, session, url_for


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            flash("로그인이 필요한 서비스입니다.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped_view


def parse_csv(raw_value: str):
    if not raw_value:
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def parse_form_list(form_data, field_name: str):
    if hasattr(form_data, "getlist"):
        values = [item.strip() for item in form_data.getlist(field_name) if item and item.strip()]
        if values:
            return values
    return parse_csv(form_data.get(field_name))


def join_csv(values):
    return ", ".join(values or [])


def get_time_slot(now=None):
    now = now or datetime.now()
    hour = now.hour
    if 5 <= hour < 10:
        return "breakfast"
    if 10 <= hour < 15:
        return "lunch"
    if 15 <= hour < 21:
        return "dinner"
    return "late-night"


def time_slot_label(slot: str):
    labels = {
        "breakfast": "아침",
        "lunch": "점심",
        "dinner": "저녁",
        "late-night": "야식",
    }
    return labels.get(slot, "오늘")
