import unittest
from datetime import datetime
from unittest.mock import patch

from services.content_feedback import get_content_feedback_profile, save_content_feedback
from services.content_sources import get_searchable_content_options, normalize_searchable_content_preferences
from services.history import ensure_dashboard_daily_history
from services.personality import build_default_personality
from services.profile_service import build_default_profile, get_profile
from services.recommender import (
    build_dashboard_bundle,
    recommend_content,
    recommend_fashion,
    recommend_food,
)
from services.trends import build_quiz_board, get_quiz_questions, get_trends_by_category, record_quiz_vote
from services.weather import get_weather_snapshot
from db.mongo import get_collection
from tests.test_support import TEST_APP, create_test_user, reset_database


class ServiceTests(unittest.TestCase):
    def setUp(self):
        reset_database()
        self.app = TEST_APP

    def test_get_profile_returns_default_serialized_fields(self):
        with self.app.app_context():
            user = create_test_user()
            profile = get_profile(user["id"])

        self.assertIn("favorites_text", profile["food"])
        self.assertIn("styles_text", profile["fashion"])
        self.assertEqual(profile["content"]["platforms"], ["넷플릭스", "영화", "시리즈"])

    def test_get_searchable_content_options_excludes_unsupported_items(self):
        with self.app.app_context():
            options = get_searchable_content_options()

        self.assertIn("넷플릭스", options["platforms"])
        self.assertIn("시리즈", options["platforms"])
        self.assertNotIn("웹툰", options["platforms"])
        self.assertNotIn("유튜브", options["platforms"])

    def test_normalize_searchable_content_preferences_filters_and_aliases_values(self):
        options = {"genres": ["액션", "범죄"], "platforms": ["넷플릭스", "영화", "시리즈"]}

        normalized = normalize_searchable_content_preferences(
            genres=["액션", "웹툰", "액션"],
            platforms=["드라마", "웹툰", "넷플릭스"],
            options=options,
        )

        self.assertEqual(normalized["genres"], ["액션"])
        self.assertEqual(normalized["platforms"], ["시리즈", "넷플릭스"])

    def test_recommend_food_prefers_spicy_match(self):
        custom_catalog = [
            {
                "name": "순한 덮밥",
                "description": "테스트용 순한 메뉴",
                "tags": ["한식", "밥"],
                "moods": ["comfort"],
                "meal_times": ["dinner"],
                "spicy": "mild",
                "ingredients": ["밥"],
                "trend_keywords": [],
            },
            {
                "name": "매운 덮밥",
                "description": "테스트용 매운 메뉴",
                "tags": ["한식", "밥"],
                "moods": ["comfort"],
                "meal_times": ["dinner"],
                "spicy": "spicy",
                "ingredients": ["밥"],
                "trend_keywords": [],
            },
        ]
        profile = build_default_profile("user-1")
        profile["personality"] = build_default_personality()

        with patch("services.recommender.FOOD_CATALOG", new=custom_catalog):
            result = recommend_food(
                profile,
                {"mood": "comfort", "time_slot": "dinner", "spicy": "yes", "ingredients": []},
                trends=[],
                recent_history=[],
            )

        self.assertEqual(result["top_pick"]["name"], "매운 덮밥")
        self.assertIn("매운맛 선호 반영", result["top_pick"]["reasons"])

    def test_recommend_fashion_prefers_temperature_and_color_match(self):
        custom_catalog = [
            {
                "name": "쿨 네이비 코디",
                "description": "테스트용 네이비 코디",
                "styles": ["미니멀"],
                "colors": ["네이비"],
                "personal_colors": ["winter cool"],
                "temp_min": 10,
                "temp_max": 20,
                "conditions": ["clear"],
                "trend_keywords": [],
            },
            {
                "name": "웜 베이지 코디",
                "description": "테스트용 베이지 코디",
                "styles": ["캐주얼"],
                "colors": ["베이지"],
                "personal_colors": ["spring warm"],
                "temp_min": 23,
                "temp_max": 28,
                "conditions": ["rainy"],
                "trend_keywords": [],
            },
        ]
        profile = build_default_profile("user-2")
        profile["personality"] = build_default_personality()

        with patch("services.recommender.FASHION_CATALOG", new=custom_catalog):
            result = recommend_fashion(
                profile,
                {
                    "styles": ["미니멀"],
                    "colors": ["네이비"],
                    "personal_color": "winter cool",
                    "temperature": 15,
                    "condition": "clear",
                },
                trends=[],
                recent_history=[],
            )

        self.assertEqual(result["top_pick"]["name"], "쿨 네이비 코디")
        self.assertIn("현재 온도에 적합", result["top_pick"]["reasons"])

    @patch("services.recommender.get_netflix_content")
    @patch("services.recommender.get_content_inventory")
    def test_recommend_content_filters_unsupported_items(self, inventory_mock, netflix_mock):
        supported = {
            "id": "movie-1",
            "name": "액션 무비",
            "description": "지원되는 영화",
            "genres": ["액션"],
            "platforms": ["넷플릭스"],
            "provider": "Netflix",
            "content_type": "영화",
            "moods": ["focus"],
            "trend_keywords": ["액션"],
            "duration_label": "2시간",
            "freshness_boost": 3,
            "source": "netflix_tudum",
            "image_url": "https://example.com/movie.jpg",
            "image_alt": "액션 무비 포스터",
            "external_url": "https://example.com/movie",
            "stats": {"rank": 1, "weeks_in_top10": 1},
        }
        unsupported = {
            "id": "webtoon-1",
            "name": "비지원 웹툰",
            "description": "지원되지 않는 웹툰",
            "genres": ["판타지"],
            "platforms": ["웹툰"],
            "provider": "네이버웹툰",
            "content_type": "웹툰",
            "moods": ["light"],
            "trend_keywords": [],
            "duration_label": "10분",
            "freshness_boost": 3,
            "source": "curated",
            "image_url": "https://example.com/webtoon.jpg",
            "image_alt": "비지원 웹툰 포스터",
        }
        inventory_mock.return_value = [supported, unsupported]
        netflix_mock.return_value = [supported]
        profile = build_default_profile("user-3")
        profile["personality"] = build_default_personality()

        result = recommend_content(
            profile,
            {"genres": ["액션"], "platforms": ["넷플릭스"], "mood": "focus"},
            trends=[{"category": "content", "keyword": "액션"}],
            recent_history=[],
            feedback_profile={
                "direct": {},
                "genre_scores": {},
                "provider_scores": {},
                "platform_scores": {},
                "type_scores": {},
                "liked_count": 0,
                "disliked_count": 0,
                "has_feedback": False,
            },
        )

        self.assertEqual(result["top_pick"]["name"], "액션 무비")
        self.assertEqual(len(result["feed"]), 1)

    @patch("services.recommender.get_netflix_content")
    @patch("services.recommender.get_content_inventory")
    def test_recommend_content_applies_feedback_boost(self, inventory_mock, netflix_mock):
        liked_item = {
            "id": "liked-item",
            "name": "좋아요 작품",
            "description": "좋아요 대상",
            "genres": ["범죄"],
            "platforms": ["넷플릭스"],
            "provider": "Netflix",
            "content_type": "영화",
            "moods": ["dark"],
            "trend_keywords": [],
            "duration_label": "2시간",
            "freshness_boost": 0,
            "source": "netflix_tudum",
            "image_url": "https://example.com/liked.jpg",
            "image_alt": "좋아요 작품 포스터",
            "external_url": "https://example.com/liked",
            "stats": {"rank": 3, "weeks_in_top10": 2},
        }
        neutral_item = {
            "id": "neutral-item",
            "name": "중립 작품",
            "description": "중립 대상",
            "genres": ["범죄"],
            "platforms": ["넷플릭스"],
            "provider": "Netflix",
            "content_type": "영화",
            "moods": ["dark"],
            "trend_keywords": [],
            "duration_label": "2시간",
            "freshness_boost": 0,
            "source": "netflix_tudum",
            "image_url": "https://example.com/neutral.jpg",
            "image_alt": "중립 작품 포스터",
            "external_url": "https://example.com/neutral",
            "stats": {"rank": 2, "weeks_in_top10": 2},
        }
        inventory_mock.return_value = [neutral_item, liked_item]
        netflix_mock.return_value = [neutral_item, liked_item]
        profile = build_default_profile("user-4")
        profile["personality"] = build_default_personality()

        result = recommend_content(
            profile,
            {"genres": ["범죄"], "platforms": ["넷플릭스"], "mood": "dark"},
            trends=[],
            recent_history=[],
            feedback_profile={
                "direct": {"liked-item": 1},
                "genre_scores": {"범죄": 6},
                "provider_scores": {"netflix": 8},
                "platform_scores": {"넷플릭스": 7},
                "type_scores": {"영화": 5},
                "liked_count": 1,
                "disliked_count": 0,
                "has_feedback": True,
            },
        )

        self.assertEqual(result["top_pick"]["id"], "liked-item")
        self.assertEqual(result["top_pick"]["feedback_state"], "like")

    def test_save_content_feedback_aggregates_profile_counts(self):
        item = {
            "id": "netflix:test:midnight-run",
            "name": "미드나이트 런",
            "provider": "Netflix",
            "platforms": ["넷플릭스"],
            "content_type": "영화",
            "genres": ["액션", "범죄"],
            "source": "netflix_tudum",
        }

        with self.app.app_context():
            user = create_test_user()
            save_content_feedback(user["id"], item, "like")
            profile = get_content_feedback_profile(user["id"])

        self.assertEqual(profile["liked_count"], 1)
        self.assertEqual(profile["disliked_count"], 0)
        self.assertEqual(profile["direct"]["netflix:test:midnight-run"], 1)

    def test_ensure_dashboard_daily_history_is_idempotent(self):
        with self.app.app_context():
            user = create_test_user()
            profile = get_profile(user["id"])
            trends = [
                {"category": "food", "keyword": "헬시플레이트"},
                {"category": "fashion", "keyword": "오피스코어"},
                {"category": "content", "keyword": "넷플릭스영화"},
                {"category": "activity", "keyword": "전시회"},
            ]
            weather = get_weather_snapshot(city="Seoul", temperature_override=18, condition_override="clear")
            bundle = build_dashboard_bundle(profile, weather, trends, recent_history=[], feedback_profile=None)

            ensure_dashboard_daily_history(user["id"], bundle)
            ensure_dashboard_daily_history(user["id"], bundle)

            count = get_collection("recommendation_history").count_documents(
                {"user_id": user["id"], "context": "dashboard-daily"}
            )

        self.assertEqual(count, 4)

    def test_build_dashboard_bundle_returns_all_categories(self):
        with self.app.app_context():
            user = create_test_user()
            profile = get_profile(user["id"])
            trends = [
                {"category": "food", "keyword": "헬시플레이트"},
                {"category": "fashion", "keyword": "오피스코어"},
                {"category": "content", "keyword": "넷플릭스영화"},
                {"category": "activity", "keyword": "전시회"},
            ]
            weather = get_weather_snapshot(city="Seoul", temperature_override=20, condition_override="clear")
            bundle = build_dashboard_bundle(profile, weather, trends, recent_history=[], feedback_profile=None)

        self.assertEqual(set(bundle.keys()), {"food", "fashion", "content", "activity"})
        self.assertIn("top_pick", bundle["content"])

    def test_get_trends_by_category_returns_all_groups(self):
        with self.app.app_context():
            grouped = get_trends_by_category()

        self.assertEqual(set(grouped.keys()), {"food", "fashion", "content", "activity"})
        self.assertTrue(grouped["food"])
        self.assertTrue(grouped["content"])

    def test_get_quiz_questions_uses_google_trends_traffic_for_baseline(self):
        with self.app.app_context():
            get_collection("trend_cache").update_one(
                {"cache_key": "google_trends:KR"},
                {
                    "$set": {
                        "cache_key": "google_trends:KR",
                        "source": "hybrid_live_trends",
                        "region": "KR",
                        "generated_at": datetime.utcnow(),
                        "is_live": True,
                        "source_url": "https://trends.google.com/trending/rss?geo=KR",
                        "google_url": "https://trends.google.com/trending/rss?geo=KR",
                        "keywords": [
                            {
                                "keyword": "마라탕",
                                "category": "food",
                                "score": 70,
                                "headline": "매운 음식 관심 상승",
                                "traffic": "100,000+",
                                "source": "google_trends_rss",
                                "source_url": "https://example.com/malatang",
                            },
                            {
                                "keyword": "탕후루",
                                "category": "food",
                                "score": 60,
                                "headline": "디저트 검색 급증",
                                "traffic": "300,000+",
                                "source": "google_trends_rss",
                                "source_url": "https://example.com/tanghulu",
                            },
                            {
                                "keyword": "고프코어",
                                "category": "fashion",
                                "score": 80,
                                "headline": "아웃도어 룩 강세",
                                "traffic": "50,000+",
                                "source": "google_trends_rss",
                                "source_url": "https://example.com/gorpcore",
                            },
                            {
                                "keyword": "미니멀룩",
                                "category": "fashion",
                                "score": 78,
                                "headline": "정돈된 코디 재부상",
                                "traffic": "40,000+",
                                "source": "google_trends_rss",
                                "source_url": "https://example.com/minimal",
                            },
                            {
                                "keyword": "전시회",
                                "category": "activity",
                                "score": 77,
                                "headline": "문화생활 검색 증가",
                                "traffic": "90,000+",
                                "source": "google_trends_rss",
                                "source_url": "https://example.com/exhibition",
                            },
                            {
                                "keyword": "러닝크루",
                                "category": "activity",
                                "score": 76,
                                "headline": "야외 활동 관심 상승",
                                "traffic": "30,000+",
                                "source": "google_trends_rss",
                                "source_url": "https://example.com/running",
                            },
                        ],
                    }
                },
                upsert=True,
            )

            quiz = get_quiz_questions()[0]

        self.assertEqual(quiz["left_traffic"], "100,000+")
        self.assertEqual(quiz["right_traffic"], "300,000+")
        self.assertEqual(quiz["source_label"], "Google Trends 실시간 대결")
        self.assertLess(quiz["baseline_left"], quiz["baseline_right"])

    def test_record_quiz_vote_updates_result(self):
        with self.app.app_context():
            user = create_test_user()
            quiz_id = build_quiz_board()[0]["id"]
            result = record_quiz_vote(user["id"], quiz_id, "left")

        self.assertEqual(result["quiz_id"], quiz_id)
        self.assertGreaterEqual(result["left_votes"], 1)
        self.assertEqual(result["user_votes_total"], 1)


if __name__ == "__main__":
    unittest.main()
