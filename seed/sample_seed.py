import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from db.mongo import get_collection
from services.account import create_user, get_user_by_email
from services.content_feedback import save_content_feedback
from services.content_sources import find_content_item, refresh_netflix_cache
from services.history import ensure_dashboard_daily_history, get_recent_history
from services.personality import analyze_personality
from services.profile_service import get_profile
from services.recommender import build_dashboard_bundle
from services.trends import DEFAULT_TRENDS
from services.weather import get_weather_snapshot


DEMO_USER = {
    "name": "Demo User",
    "email": "demo@whatshouldi.local",
    "password": "demo1234",
}

DEMO_SURVEY_ANSWERS = {
    "unplanned_evening": 4,
    "sensory_memory": 5,
    "taste_identity": 5,
    "emotional_subtext": 4,
    "structure_recovery": 4,
    "solitude_value": 3,
    "social_temperature": 4,
    "distinctive_choice": 4,
    "stimulus_release": 3,
    "narrative_rest": 4,
    "flow_consistency": 5,
    "micro_meaning": 5,
}


def seed_base_data():
    get_collection("trend_cache").delete_many({})
    get_collection("trend_cache").insert_one(
        {
            "source": "sample_google_trends",
            "region": "KR",
            "generated_at": datetime.utcnow(),
            "keywords": DEFAULT_TRENDS,
        }
    )

    get_collection("quiz_logs").delete_many({})
    get_collection("quiz_logs").insert_many(
        [
            {
                "quiz_id": "food_faceoff",
                "choice": "left",
                "user_id": "seed",
                "left_label": "마라탕",
                "right_label": "탕후루",
                "created_at": datetime.utcnow(),
            },
            {
                "quiz_id": "fashion_faceoff",
                "choice": "right",
                "user_id": "seed",
                "left_label": "미니멀 셋업",
                "right_label": "스트릿 윈드브레이커",
                "created_at": datetime.utcnow(),
            },
            {
                "quiz_id": "weekend_faceoff",
                "choice": "right",
                "user_id": "seed",
                "left_label": "집콕 정주행",
                "right_label": "야외 산책",
                "created_at": datetime.utcnow(),
            },
        ]
    )


def seed_demo_user():
    user = get_user_by_email(DEMO_USER["email"])
    if not user:
        user = create_user(DEMO_USER["name"], DEMO_USER["email"], DEMO_USER["password"])

    personality = analyze_personality("ENFJ", DEMO_SURVEY_ANSWERS)

    get_collection("profiles").update_one(
        {"user_id": user["id"]},
        {
            "$set": {
                "food.favorites": ["한식", "헬시", "집밥"],
                "food.dislikes": ["고수"],
                "food.available_ingredients": ["계란", "양파", "밥", "김치"],
                "food.spice": "yes",
                "fashion.styles": ["미니멀", "캐주얼"],
                "fashion.colors": ["블랙", "크림", "네이비"],
                "fashion.personal_color": "winter cool",
                "content.genres": ["스릴러", "힐링", "판타지"],
                "content.platforms": ["웹툰", "영화", "유튜브", "넷플릭스"],
                "activity.indoor_outdoor": "mixed",
                "activity.energy": "medium",
                "activity.social": "either",
                "activity.budget": "medium",
                "personality": personality,
                "updated_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )

    profile = get_profile(user["id"])
    weather = get_weather_snapshot()
    trends = DEFAULT_TRENDS
    refresh_netflix_cache(force=False)

    for content_id, sentiment in [
        ("local:twist-thriller-film", "like"),
        ("local:cozy-house-vlog", "like"),
        ("netflix:netflix_top10_tv:love-is-blind-ohio", "dislike"),
    ]:
        item = find_content_item(content_id, force_refresh=False)
        if item:
            save_content_feedback(user["id"], item, sentiment)

    bundle = build_dashboard_bundle(profile, weather, trends, get_recent_history(user["id"], limit=20))
    ensure_dashboard_daily_history(user["id"], bundle)


def main():
    parser = argparse.ArgumentParser(description="Seed sample data for WhatShouldI")
    parser.add_argument("--with-demo-user", action="store_true", help="Create demo user and sample history")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        seed_base_data()
        if args.with_demo_user:
            seed_demo_user()

    print("Seed completed.")
    if args.with_demo_user:
        print(f"Demo login: {DEMO_USER['email']} / {DEMO_USER['password']}")


if __name__ == "__main__":
    main()
