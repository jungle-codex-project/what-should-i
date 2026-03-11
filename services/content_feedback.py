from datetime import datetime

from db.mongo import get_collection


FEEDBACK_VALUES = {
    "like": 1,
    "dislike": -1,
}


def save_content_feedback(user_id, item, sentiment):
    if sentiment not in FEEDBACK_VALUES:
        raise ValueError("유효하지 않은 피드백입니다.")

    document = {
        "user_id": user_id,
        "content_id": item["id"],
        "sentiment": sentiment,
        "value": FEEDBACK_VALUES[sentiment],
        "item_name": item["name"],
        "provider": item.get("provider"),
        "platforms": item.get("platforms", []),
        "content_type": item.get("content_type"),
        "genres": item.get("genres", []),
        "source": item.get("source"),
        "updated_at": datetime.utcnow(),
    }

    get_collection("content_feedback").update_one(
        {"user_id": user_id, "content_id": item["id"]},
        {
            "$set": document,
            "$setOnInsert": {"created_at": datetime.utcnow()},
        },
        upsert=True,
    )
    return document


def get_content_feedback_profile(user_id):
    cursor = get_collection("content_feedback").find({"user_id": user_id})
    direct = {}
    genre_scores = {}
    provider_scores = {}
    platform_scores = {}
    type_scores = {}
    liked = 0
    disliked = 0

    for feedback in cursor:
        value = feedback["value"]
        direct[feedback["content_id"]] = value

        liked += 1 if value > 0 else 0
        disliked += 1 if value < 0 else 0

        for genre in feedback.get("genres", []):
            genre_scores[genre.lower()] = genre_scores.get(genre.lower(), 0) + (6 * value)
        for platform in feedback.get("platforms", []):
            platform_scores[platform.lower()] = platform_scores.get(platform.lower(), 0) + (7 * value)
        provider = (feedback.get("provider") or "").lower()
        if provider:
            provider_scores[provider] = provider_scores.get(provider, 0) + (8 * value)
        content_type = (feedback.get("content_type") or "").lower()
        if content_type:
            type_scores[content_type] = type_scores.get(content_type, 0) + (5 * value)

    return {
        "direct": direct,
        "genre_scores": genre_scores,
        "provider_scores": provider_scores,
        "platform_scores": platform_scores,
        "type_scores": type_scores,
        "liked_count": liked,
        "disliked_count": disliked,
        "has_feedback": bool(direct),
    }
