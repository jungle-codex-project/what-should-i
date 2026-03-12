from copy import deepcopy

from flask import Blueprint, current_app, flash, jsonify, render_template, request, session

from services.content_feedback import get_content_feedback_profile, save_content_feedback
from services.content_sources import (
    find_content_item,
    get_netflix_status,
    get_searchable_content_options,
    normalize_searchable_content_preferences,
)
from services.history import get_full_history, get_recent_history, save_recommendation
from services.profile_service import get_profile
from services.recommender import (
    recommend_activity,
    recommend_content,
    recommend_fashion,
    recommend_food,
)
from services.trends import build_quiz_board, get_trend_status, get_trends_by_category, record_quiz_vote
from services.weather import get_weather_snapshot
from utils import get_time_slot, login_required, parse_csv


recommendation_bp = Blueprint("recommendations", __name__)


@recommendation_bp.route("/food", methods=["GET", "POST"])
@login_required
def food():
    user_id = session["user_id"]
    profile = get_profile(user_id)
    working_profile = deepcopy(profile)
    recent_history = get_recent_history(user_id, limit=12)
    trends = get_trends_by_category(region=current_app.config["DEFAULT_REGION"])["food"]

    form_values = {
        "favorites": request.form.get("favorites", profile["food"]["favorites_text"]),
        "dislikes": request.form.get("dislikes", profile["food"]["dislikes_text"]),
        "ingredients": request.form.get("ingredients", profile["food"]["available_ingredients_text"]),
        "mood": request.form.get("mood", "comfort"),
        "time_slot": request.form.get("time_slot", get_time_slot()),
        "spicy": request.form.get("spicy", profile["food"]["spice"]),
    }

    working_profile["food"]["favorites"] = parse_csv(form_values["favorites"]) or profile["food"]["favorites"]
    working_profile["food"]["dislikes"] = parse_csv(form_values["dislikes"])
    working_profile["food"]["available_ingredients"] = parse_csv(form_values["ingredients"])
    working_profile["food"]["spice"] = form_values["spicy"]

    result = recommend_food(
        working_profile,
        {
            "mood": form_values["mood"],
            "time_slot": form_values["time_slot"],
            "spicy": form_values["spicy"],
            "ingredients": parse_csv(form_values["ingredients"]),
        },
        trends=trends,
        recent_history=recent_history,
    )

    if request.method == "POST":
        save_recommendation(
            user_id,
            "food",
            result["request_snapshot"],
            result["top_pick"],
            result["alternatives"],
            context="category-form",
        )
        flash("음식 추천을 히스토리에 저장했습니다.", "success")

    return render_template("recommendations/food.html", result=result, form_values=form_values)


@recommendation_bp.route("/fashion", methods=["GET", "POST"])
@login_required
def fashion():
    user_id = session["user_id"]
    profile = get_profile(user_id)
    working_profile = deepcopy(profile)
    recent_history = get_recent_history(user_id, limit=12)
    trends = get_trends_by_category(region=current_app.config["DEFAULT_REGION"])["fashion"]

    weather = get_weather_snapshot(
        city=current_app.config["DEFAULT_CITY"],
        temperature_override=request.form.get("temperature"),
        condition_override=request.form.get("condition"),
    )

    form_values = {
        "styles": request.form.get("styles", profile["fashion"]["styles_text"]),
        "colors": request.form.get("colors", profile["fashion"]["colors_text"]),
        "personal_color": request.form.get("personal_color", profile["fashion"]["personal_color"]),
        "temperature": request.form.get("temperature") or str(weather["temperature"]),
        "condition": request.form.get("condition", weather["condition"]),
    }

    working_profile["fashion"]["styles"] = parse_csv(form_values["styles"]) or profile["fashion"]["styles"]
    working_profile["fashion"]["colors"] = parse_csv(form_values["colors"]) or profile["fashion"]["colors"]
    working_profile["fashion"]["personal_color"] = form_values["personal_color"]

    result = recommend_fashion(
        working_profile,
        {
            "styles": parse_csv(form_values["styles"]),
            "colors": parse_csv(form_values["colors"]),
            "personal_color": form_values["personal_color"],
            "temperature": form_values["temperature"],
            "condition": form_values["condition"],
        },
        trends=trends,
        recent_history=recent_history,
    )

    if request.method == "POST":
        save_recommendation(
            user_id,
            "fashion",
            result["request_snapshot"],
            result["top_pick"],
            result["alternatives"],
            context="category-form",
        )
        flash("패션 추천을 히스토리에 저장했습니다.", "success")

    return render_template("recommendations/fashion.html", result=result, form_values=form_values, weather=weather)


@recommendation_bp.route("/content", methods=["GET", "POST"])
@login_required
def content():
    user_id = session["user_id"]
    profile = get_profile(user_id)
    working_profile = deepcopy(profile)
    recent_history = get_recent_history(user_id, limit=12)
    trends = get_trends_by_category(region=current_app.config["DEFAULT_REGION"])["content"]
    feedback_profile = get_content_feedback_profile(user_id)
    force_refresh = request.args.get("refresh") == "1"
    content_options = get_searchable_content_options(force_refresh=force_refresh)
    default_preferences = normalize_searchable_content_preferences(
        genres=profile["content"].get("genres", []),
        platforms=profile["content"].get("platforms", []),
        options=content_options,
    )

    form_values = {
        "genres": request.form.getlist("genres") if request.method == "POST" else default_preferences["genres"],
        "platforms": request.form.getlist("platforms") if request.method == "POST" else default_preferences["platforms"],
        "mood": request.form.get("mood", "light"),
    }

    effective_genres = form_values["genres"] or default_preferences["genres"]
    effective_platforms = form_values["platforms"] or default_preferences["platforms"]

    working_profile["content"]["genres"] = effective_genres
    working_profile["content"]["platforms"] = effective_platforms

    result = recommend_content(
        working_profile,
        {
            "genres": form_values["genres"],
            "platforms": form_values["platforms"],
            "mood": form_values["mood"],
        },
        trends=trends,
        recent_history=recent_history,
        feedback_profile=feedback_profile,
        force_refresh=force_refresh,
    )

    if request.method == "POST":
        save_recommendation(
            user_id,
            "content",
            result["request_snapshot"],
            result["top_pick"],
            result["alternatives"],
            context="category-form",
        )
        flash("콘텐츠 추천을 히스토리에 저장했습니다.", "success")

    return render_template(
        "recommendations/content.html",
        result=result,
        form_values=form_values,
        content_options=content_options,
        netflix_status=get_netflix_status(),
    )


@recommendation_bp.route("/activity", methods=["GET", "POST"])
@login_required
def activity():
    user_id = session["user_id"]
    profile = get_profile(user_id)
    working_profile = deepcopy(profile)
    recent_history = get_recent_history(user_id, limit=12)
    grouped_trends = get_trends_by_category(region=current_app.config["DEFAULT_REGION"])
    weather = get_weather_snapshot(city=current_app.config["DEFAULT_CITY"])

    form_values = {
        "indoor_outdoor": request.form.get("indoor_outdoor", profile["activity"]["indoor_outdoor"]),
        "energy": request.form.get("energy", profile["activity"]["energy"]),
        "social": request.form.get("social", profile["activity"]["social"]),
        "budget": request.form.get("budget", profile["activity"]["budget"]),
    }

    result = recommend_activity(
        working_profile,
        form_values,
        weather=weather,
        trends=grouped_trends["activity"],
        recent_history=recent_history,
    )

    if request.method == "POST":
        save_recommendation(
            user_id,
            "activity",
            result["request_snapshot"],
            result["top_pick"],
            result["alternatives"],
            context="category-form",
        )
        flash("활동 추천을 히스토리에 저장했습니다.", "success")

    return render_template("recommendations/activity.html", result=result, form_values=form_values, weather=weather)


@recommendation_bp.route("/trends")
@login_required
def trends():
    region = current_app.config["DEFAULT_REGION"]
    force_refresh = request.args.get("refresh") == "1"
    grouped_trends = get_trends_by_category(region=region, force_refresh=force_refresh)
    return render_template("trends.html", grouped_trends=grouped_trends, trend_status=get_trend_status(region=region))


@recommendation_bp.route("/quiz")
@login_required
def quiz():
    region = current_app.config["DEFAULT_REGION"]
    force_refresh = request.args.get("refresh") == "1"
    board = build_quiz_board(region=region, force_refresh=force_refresh)
    return render_template("quiz.html", quiz_board=board, trend_status=get_trend_status(region=region))


@recommendation_bp.route("/quiz/vote", methods=["POST"])
@login_required
def quiz_vote():
    payload = request.get_json(silent=True) or {}
    quiz_id = payload.get("quiz_id")
    choice = payload.get("choice")
    if choice not in {"left", "right"}:
        return jsonify({"ok": False, "message": "유효하지 않은 선택입니다."}), 400

    result = record_quiz_vote(session["user_id"], quiz_id, choice, region=current_app.config["DEFAULT_REGION"])
    if not result:
        return jsonify({"ok": False, "message": "퀴즈를 찾을 수 없습니다."}), 404

    return jsonify({"ok": True, "result": result})


@recommendation_bp.route("/history")
@login_required
def history():
    entries = get_full_history(session["user_id"], limit=40)
    return render_template("history.html", history_entries=entries)


@recommendation_bp.route("/content/feedback", methods=["POST"])
@login_required
def content_feedback():
    payload = request.get_json(silent=True) or {}
    content_id = payload.get("content_id")
    sentiment = payload.get("sentiment")

    item = find_content_item(content_id, force_refresh=False)
    if not item:
        return jsonify({"ok": False, "message": "콘텐츠 정보를 찾을 수 없습니다."}), 404

    try:
        save_content_feedback(session["user_id"], item, sentiment)
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400

    feedback_profile = get_content_feedback_profile(session["user_id"])
    return jsonify(
        {
            "ok": True,
            "content_id": content_id,
            "sentiment": sentiment,
            "summary": {
                "liked_count": feedback_profile["liked_count"],
                "disliked_count": feedback_profile["disliked_count"],
            },
        }
    )
