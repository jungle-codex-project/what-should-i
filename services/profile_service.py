from datetime import datetime
from copy import deepcopy

from db.mongo import get_collection
from services.content_sources import normalize_searchable_content_preferences
from services.personality import (
    TRAIT_META,
    analyze_personality,
    apply_personality_defaults,
    build_default_personality,
    extract_survey_answers,
)
from utils import join_csv, parse_csv, parse_form_list


def build_default_profile(user_id: str):
    return {
        "user_id": user_id,
        "food": {
            "favorites": ["한식", "집밥"],
            "dislikes": [],
            "available_ingredients": ["계란", "양파", "밥"],
            "spice": "any",
        },
        "fashion": {
            "styles": ["캐주얼"],
            "colors": ["화이트", "블랙"],
            "personal_color": "spring warm",
        },
        "content": {
            "genres": ["로맨스", "힐링"],
            "platforms": ["넷플릭스", "영화", "시리즈"],
        },
        "activity": {
            "indoor_outdoor": "mixed",
            "energy": "medium",
            "social": "either",
            "budget": "medium",
        },
        "personality": build_default_personality(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


def _deep_merge(base, override):
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _with_profile_defaults(profile_doc):
    merged = _deep_merge(build_default_profile(profile_doc["user_id"]), profile_doc)
    merged["personality"] = apply_personality_defaults(merged.get("personality"))
    return merged


def _serialize_profile(profile_doc):
    profile = _with_profile_defaults(profile_doc)
    profile["food"]["favorites_text"] = join_csv(profile["food"].get("favorites"))
    profile["food"]["dislikes_text"] = join_csv(profile["food"].get("dislikes"))
    profile["food"]["available_ingredients_text"] = join_csv(profile["food"].get("available_ingredients"))
    profile["fashion"]["styles_text"] = join_csv(profile["fashion"].get("styles"))
    profile["fashion"]["colors_text"] = join_csv(profile["fashion"].get("colors"))
    profile["content"]["genres_text"] = join_csv(profile["content"].get("genres"))
    profile["content"]["platforms_text"] = join_csv(profile["content"].get("platforms"))
    profile["personality"]["dominant_trait_cards"] = [
        {
            "key": trait,
            "label": TRAIT_META[trait]["label"],
            "description": TRAIT_META[trait]["description"],
            "score": profile["personality"]["trait_scores"].get(trait, 50),
        }
        for trait in profile["personality"].get("dominant_traits", [])
    ]
    return profile


def ensure_profile(user_id: str):
    profiles = get_collection("profiles")
    profile = profiles.find_one({"user_id": user_id})
    if profile:
        normalized = _with_profile_defaults(profile)
        if normalized != profile:
            profiles.update_one(
                {"user_id": user_id},
                {"$set": {"personality": normalized["personality"], "updated_at": datetime.utcnow()}},
            )
        return _serialize_profile(normalized)

    profile = build_default_profile(user_id)
    profiles.insert_one(profile)
    return _serialize_profile(profile)


def get_profile(user_id: str):
    return ensure_profile(user_id)


def update_profile_from_form(user_id: str, form_data):
    content_preferences = normalize_searchable_content_preferences(
        genres=parse_form_list(form_data, "content_genres"),
        platforms=parse_form_list(form_data, "content_platforms"),
    )

    payload = {
        "food": {
            "favorites": parse_csv(form_data.get("food_favorites")),
            "dislikes": parse_csv(form_data.get("food_dislikes")),
            "available_ingredients": parse_csv(form_data.get("food_ingredients")),
            "spice": form_data.get("food_spice", "any"),
        },
        "fashion": {
            "styles": parse_csv(form_data.get("fashion_styles")),
            "colors": parse_csv(form_data.get("fashion_colors")),
            "personal_color": form_data.get("fashion_personal_color", "spring warm"),
        },
        "content": {
            "genres": content_preferences["genres"],
            "platforms": content_preferences["platforms"],
        },
        "activity": {
            "indoor_outdoor": form_data.get("activity_indoor_outdoor", "mixed"),
            "energy": form_data.get("activity_energy", "medium"),
            "social": form_data.get("activity_social", "either"),
            "budget": form_data.get("activity_budget", "medium"),
        },
        "updated_at": datetime.utcnow(),
    }

    profiles = get_collection("profiles")
    profiles.update_one(
        {"user_id": user_id},
        {
            "$set": payload,
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": datetime.utcnow(),
            },
        },
        upsert=True,
    )
    return get_profile(user_id)


def update_personality_from_form(user_id: str, form_data):
    mbti = form_data.get("mbti", "")
    answers = extract_survey_answers(form_data)
    personality = analyze_personality(mbti, answers)

    get_collection("profiles").update_one(
        {"user_id": user_id},
        {
            "$set": {
                "personality": personality,
                "updated_at": datetime.utcnow(),
            },
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": datetime.utcnow(),
            },
        },
        upsert=True,
    )
    return get_profile(user_id)
