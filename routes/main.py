from flask import Blueprint, current_app, redirect, render_template, session, url_for

from services.content_feedback import get_content_feedback_profile
from services.history import ensure_dashboard_daily_history, get_recent_history
from services.profile_service import get_profile
from services.recommender import build_dashboard_bundle
from services.trends import get_latest_trends
from services.weather import get_weather_snapshot
from utils import login_required, time_slot_label


main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))

    trends = get_latest_trends(limit=6)
    return render_template("index.html", trends=trends)


@main_bp.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    profile = get_profile(user_id)
    trends = get_latest_trends(limit=8)
    weather = get_weather_snapshot(city=current_app.config["DEFAULT_CITY"])
    recent_history = get_recent_history(user_id, limit=12)
    feedback_profile = get_content_feedback_profile(user_id)
    bundle = build_dashboard_bundle(profile, weather, trends, recent_history, feedback_profile=feedback_profile)
    ensure_dashboard_daily_history(user_id, bundle)
    latest_history = get_recent_history(user_id, limit=5)

    cards = [
        {
            "slug": "food",
            "title": "오늘 뭐 먹지?",
            "link": url_for("recommendations.food"),
            "icon": "bi bi-bowl-hot",
            "accent": "accent-food",
            "result": bundle["food"],
        },
        {
            "slug": "fashion",
            "title": "오늘 뭐 입지?",
            "link": url_for("recommendations.fashion"),
            "icon": "bi bi-stars",
            "accent": "accent-fashion",
            "result": bundle["fashion"],
        },
        {
            "slug": "content",
            "title": "오늘 뭐 보지?",
            "link": url_for("recommendations.content"),
            "icon": "bi bi-play-circle",
            "accent": "accent-content",
            "result": bundle["content"],
        },
        {
            "slug": "activity",
            "title": "오늘 뭐 하지?",
            "link": url_for("recommendations.activity"),
            "icon": "bi bi-compass",
            "accent": "accent-activity",
            "result": bundle["activity"],
        },
    ]

    return render_template(
        "dashboard.html",
        cards=cards,
        profile=profile,
        trends=trends,
        weather=weather,
        recent_history=latest_history,
        current_time_slot_label=time_slot_label(bundle["food"]["request_snapshot"]["time_slot"]),
    )
