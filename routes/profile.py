from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from services.content_sources import get_searchable_content_options, normalize_searchable_content_preferences
from services.personality import get_likert_options, get_mbti_types, get_survey_questions
from services.profile_service import get_profile, update_personality_from_form, update_profile_from_form
from utils import login_required


profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = session["user_id"]

    if request.method == "POST":
        update_profile_from_form(user_id, request.form)
        flash("프로필 취향이 저장되었습니다. 다음 추천부터 바로 반영됩니다.", "success")

    profile_data = get_profile(user_id)
    content_options = get_searchable_content_options(force_refresh=False)
    profile_data["content"].update(
        normalize_searchable_content_preferences(
            genres=profile_data["content"].get("genres", []),
            platforms=profile_data["content"].get("platforms", []),
            options=content_options,
        )
    )
    return render_template("profile.html", profile=profile_data, content_options=content_options)


@profile_bp.route("/survey", methods=["GET", "POST"])
@login_required
def survey():
    user_id = session["user_id"]

    if request.method == "POST":
        update_personality_from_form(user_id, request.form)
        flash("MBTI와 심리 설문 결과가 저장되었습니다. 자동 추천에 바로 반영됩니다.", "success")
        return redirect(url_for("profile.survey"))

    profile_data = get_profile(user_id)
    return render_template(
        "survey.html",
        profile=profile_data,
        survey_questions=get_survey_questions(),
        likert_options=get_likert_options(),
        mbti_types=get_mbti_types(),
    )
