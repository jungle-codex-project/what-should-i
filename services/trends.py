import hashlib
import json
import re
from datetime import datetime, timedelta
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from flask import current_app

from db.mongo import get_collection
from services.movie_images import get_tmdb_movie_poster


DEFAULT_TRENDS = [
    {"keyword": "헬시플레이트", "category": "food", "score": 96, "headline": "가벼운 점심 트렌드", "source": "fallback"},
    {"keyword": "마라", "category": "food", "score": 93, "headline": "매운 음식 키워드 급상승", "source": "fallback"},
    {"keyword": "고프코어", "category": "fashion", "score": 91, "headline": "윈드브레이커 스타일 강세", "source": "fallback"},
    {"keyword": "오피스코어", "category": "fashion", "score": 84, "headline": "정돈된 셋업 룩 재부상", "source": "fallback"},
    {"keyword": "넷플릭스영화", "category": "content", "score": 88, "headline": "가볍게 보기 좋은 영화 관심 상승", "source": "fallback"},
    {"keyword": "범죄스릴러", "category": "content", "score": 86, "headline": "몰입형 저녁 콘텐츠 수요", "source": "fallback"},
    {"keyword": "전시회", "category": "activity", "score": 79, "headline": "가벼운 문화생활 탐색 증가", "source": "fallback"},
    {"keyword": "러닝크루", "category": "activity", "score": 77, "headline": "저녁 야외 활동 관심 상승", "source": "fallback"},
]

GOOGLE_TRENDS_RSS_URL = "https://trends.google.com/trending/rss?geo={region}"
GOOGLE_SEARCH_URL = "https://www.google.com/search?q={query}"
KOBIS_WEEKLY_BOXOFFICE_URL = (
    "http://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchWeeklyBoxOfficeList.xml"
    "?key={api_key}&weekGb=0&targetDt={target_date}"
)
THEMEALDB_SEARCH_URL = "https://www.themealdb.com/api/json/v1/1/search.php?s={query}"
CATEGORY_RULES = {
    "food": [
        "맛집", "음식", "요리", "식당", "카페", "커피", "디저트", "레시피", "마라", "라면", "치킨",
        "burger", "pizza", "cafe", "coffee", "restaurant", "recipe", "food",
    ],
    "fashion": [
        "패션", "코디", "룩", "착장", "브랜드", "스니커즈", "런웨이", "옷", "가방", "슈즈",
        "fashion", "style", "outfit", "runway", "sneaker", "brand",
    ],
    "content": [
        "영화", "드라마", "예능", "넷플릭스", "애니", "시리즈", "ott", "콘서트",
        "movie", "series", "drama", "netflix", "anime", "show", "trailer",
    ],
    "activity": [
        "전시", "축제", "여행", "산책", "러닝", "운동", "캠핑", "공연", "팝업", "마라톤",
        "travel", "running", "workout", "camping", "exhibition", "festival", "popup", "trip",
    ],
}

DEFAULT_QUIZ_QUESTIONS = [
    {
        "id": "food_faceoff",
        "title": "오늘의 푸드 밸런스 게임",
        "prompt": "퇴근 후 한 입, 마라탕 vs 탕후루",
        "left_label": "마라탕",
        "right_label": "탕후루",
        "baseline_left": 58,
        "baseline_right": 42,
    },
    {
        "id": "fashion_faceoff",
        "title": "오늘의 코디 밸런스 게임",
        "prompt": "미니멀 셋업 vs 스트릿 윈드브레이커",
        "left_label": "미니멀 셋업",
        "right_label": "스트릿 윈드브레이커",
        "baseline_left": 51,
        "baseline_right": 49,
    },
    {
        "id": "weekend_faceoff",
        "title": "주말 무드 밸런스 게임",
        "prompt": "집콕 정주행 vs 야외 산책",
        "left_label": "집콕 정주행",
        "right_label": "야외 산책",
        "baseline_left": 47,
        "baseline_right": 53,
    },
]

FOOD_QUERY_HINTS = {
    "마라": ["Arrabiata", "Curry"],
    "헬시": ["Salad", "Chicken"],
    "플레이트": ["Salad", "Chicken"],
    "포케": ["Salmon", "Tuna"],
    "연어": ["Salmon"],
    "파스타": ["Pasta", "Arrabiata"],
    "라면": ["Noodle"],
    "면": ["Pasta"],
    "치킨": ["Chicken"],
    "커피": ["Coffee"],
    "카페": ["Cake", "Tart"],
    "디저트": ["Cake", "Pie"],
    "버거": ["Burger"],
    "피자": ["Pizza"],
    "집밥": ["Beef", "Chicken"],
    "국물": ["Soup", "Stew"],
}

FASHION_TREND_PROFILES = [
    {
        "tokens": ["고프코어", "윈드브레이커", "아웃도어"],
        "styles": ["스트릿", "스포티"],
        "colors": ["카키", "블랙", "그레이"],
        "personal_colors": ["autumn warm", "winter cool"],
        "temp_min": 8,
        "temp_max": 21,
        "conditions": ["clear", "cloudy", "windy"],
    },
    {
        "tokens": ["오피스코어", "셋업", "블레이저"],
        "styles": ["포멀", "미니멀"],
        "colors": ["네이비", "블랙", "화이트"],
        "personal_colors": ["summer cool", "winter cool"],
        "temp_min": 10,
        "temp_max": 23,
        "conditions": ["clear", "cloudy"],
    },
    {
        "tokens": ["데님", "청청", "클린핏"],
        "styles": ["캐주얼", "미니멀"],
        "colors": ["블루", "화이트", "그레이"],
        "personal_colors": ["summer cool", "winter cool"],
        "temp_min": 14,
        "temp_max": 27,
        "conditions": ["clear", "cloudy"],
    },
    {
        "tokens": ["러닝룩", "애슬레저", "운동화"],
        "styles": ["스포티", "캐주얼"],
        "colors": ["블랙", "차콜", "화이트"],
        "personal_colors": ["spring warm", "summer cool", "winter cool"],
        "temp_min": 12,
        "temp_max": 28,
        "conditions": ["clear", "cloudy", "windy"],
    },
]

ACTIVITY_TREND_PROFILES = [
    {
        "tokens": ["전시", "뮤지엄", "갤러리", "팝업"],
        "indoor_outdoor": "mixed",
        "energy": "medium",
        "social": "either",
        "budget": "medium",
    },
    {
        "tokens": ["러닝", "마라톤", "산책", "트레킹"],
        "indoor_outdoor": "outdoor",
        "energy": "high",
        "social": "either",
        "budget": "low",
    },
    {
        "tokens": ["캠핑", "여행", "축제"],
        "indoor_outdoor": "outdoor",
        "energy": "medium",
        "social": "group",
        "budget": "high",
    },
    {
        "tokens": ["공연", "콘서트", "연극"],
        "indoor_outdoor": "indoor",
        "energy": "medium",
        "social": "group",
        "budget": "high",
    },
]


def _local_name(tag):
    return tag.split("}", 1)[-1]


def _child_text(element, local_name, default=""):
    for child in list(element):
        if _local_name(child.tag) == local_name:
            return (child.text or "").strip()
    return default


def _child_texts(element, local_name):
    values = []
    for child in element.iter():
        if _local_name(child.tag) == local_name:
            text = (child.text or "").strip()
            if text:
                values.append(text)
    return values


def _normalize_traffic(raw_value):
    if not raw_value:
        return 0
    digits = re.sub(r"[^0-9]", "", raw_value)
    return int(digits or "0")


def _score_from_rank(index, traffic):
    rank_score = max(55, 100 - (index * 5))
    traffic_bonus = min(18, traffic // 20000) if traffic else 0
    return min(99, rank_score + traffic_bonus)


def _slugify(value):
    normalized = (value or "").strip().lower()
    slug = re.sub(r"[^\w]+", "-", normalized, flags=re.UNICODE).strip("-_").replace("_", "-")
    if slug:
        return slug
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def _json_url(url):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _first_present(values, default=""):
    for value in values:
        if value:
            return value
    return default


def _meal_ingredients(meal):
    ingredients = []
    for index in range(1, 21):
        ingredient = (meal.get(f"strIngredient{index}") or "").strip()
        if ingredient:
            ingredients.append(ingredient)
    return ingredients


def _meal_moods(meal):
    category = (meal.get("strCategory") or "").lower()
    area = (meal.get("strArea") or "").lower()
    moods = ["reward", "comfort"]
    if category in {"dessert", "breakfast"}:
        moods = ["light", "comfort", "refresh"]
    elif category in {"seafood", "vegetarian", "vegan"}:
        moods = ["light", "focus", "refresh"]
    elif category in {"beef", "lamb", "pork"}:
        moods = ["reward", "comfort", "stress"]
    elif category in {"pasta", "chicken"}:
        moods = ["reward", "focus", "comfort"]
    if area in {"japanese", "french"} and "adventure" not in moods:
        moods.append("adventure")
    return moods[:3]


def _meal_time_hints(meal):
    category = (meal.get("strCategory") or "").lower()
    if category in {"dessert"}:
        return ["breakfast", "late-night"]
    if category in {"breakfast"}:
        return ["breakfast", "lunch"]
    return ["lunch", "dinner"]


def _guess_spicy(meal, keyword=""):
    haystack = " ".join(_meal_ingredients(meal) + [meal.get("strMeal", ""), keyword]).lower()
    spicy_tokens = ["spicy", "chili", "pepper", "curry", "hot", "harissa", "gochujang"]
    return "spicy" if any(token in haystack for token in spicy_tokens) else "mild"


def _crop_text(value, limit=120):
    text = re.sub(r"\s+", " ", (value or "").strip())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _trend_search_url(keyword):
    return GOOGLE_SEARCH_URL.format(query=quote(keyword))


def _trend_source_url(item):
    return item.get("source_url") or _trend_search_url(item.get("keyword", ""))


def _match_profile(keyword, profiles):
    lowered = (keyword or "").lower()
    for profile in profiles:
        if any(token in lowered for token in profile["tokens"]):
            return profile
    return None


def _build_live_food_item(meal, seed_keyword, source_url):
    meal_name = meal.get("strMeal")
    if not meal_name:
        return None

    category = meal.get("strCategory") or "Meal"
    area = meal.get("strArea") or "Global"
    ingredients = _meal_ingredients(meal)[:6]
    tags = [category, area] + ingredients[:3]
    instructions = _crop_text(meal.get("strInstructions") or f"{seed_keyword} 흐름과 맞는 실제 레시피입니다.")
    external_url = _first_present([meal.get("strSource"), meal.get("strYoutube"), source_url])

    return {
        "name": meal_name,
        "description": f"{seed_keyword} 키워드와 연결된 실제 메뉴입니다. {instructions}",
        "tags": tags,
        "moods": _meal_moods(meal),
        "meal_times": _meal_time_hints(meal),
        "spicy": _guess_spicy(meal, seed_keyword),
        "ingredients": ingredients or [category],
        "trend_keywords": [seed_keyword, category],
        "image_url": meal.get("strMealThumb"),
        "image_alt": f"{meal_name} 음식 사진",
        "source": "themealdb_search",
        "source_label": "TheMealDB + Google Trends",
        "source_url": source_url,
        "external_url": external_url,
    }


def _build_live_fashion_item(trend):
    keyword = trend.get("keyword", "")
    profile = _match_profile(keyword, FASHION_TREND_PROFILES) or {
        "styles": ["캐주얼", "미니멀"],
        "colors": ["블랙", "화이트", "그레이"],
        "personal_colors": ["spring warm", "summer cool", "autumn warm", "winter cool"],
        "temp_min": 12,
        "temp_max": 24,
        "conditions": ["clear", "cloudy"],
    }
    return {
        "name": f"{keyword} 무드 코디",
        "description": _crop_text(trend.get("headline") or "실시간 패션 키워드 기반 코디 제안입니다."),
        "styles": profile["styles"],
        "colors": profile["colors"],
        "personal_colors": profile["personal_colors"],
        "temp_min": profile["temp_min"],
        "temp_max": profile["temp_max"],
        "conditions": profile["conditions"],
        "trend_keywords": [keyword],
        "image_url": trend.get("image_url"),
        "image_alt": trend.get("image_alt") or f"{keyword} 관련 이미지",
        "source": "google_trends_fashion",
        "source_label": "Google Trends",
        "source_url": _trend_source_url(trend),
        "external_url": _trend_source_url(trend),
    }


def _build_live_activity_item(trend):
    keyword = trend.get("keyword", "")
    profile = _match_profile(keyword, ACTIVITY_TREND_PROFILES) or {
        "indoor_outdoor": "mixed",
        "energy": "medium",
        "social": "either",
        "budget": "medium",
    }
    return {
        "name": f"{keyword} 일정 잡기",
        "description": _crop_text(trend.get("headline") or "실시간 관심이 오른 활동 키워드입니다."),
        "indoor_outdoor": profile["indoor_outdoor"],
        "energy": profile["energy"],
        "social": profile["social"],
        "budget": profile["budget"],
        "trend_keywords": [keyword],
        "image_url": trend.get("image_url"),
        "image_alt": trend.get("image_alt") or f"{keyword} 관련 이미지",
        "source": "google_trends_activity",
        "source_label": "Google Trends",
        "source_url": _trend_source_url(trend),
        "external_url": _trend_source_url(trend),
    }


def _load_cached_live_items(cache_key, max_age_hours=6):
    cached = get_collection("recommendation_source_cache").find_one({"cache_key": cache_key})
    if not cached:
        return None
    generated_at = cached.get("generated_at")
    if generated_at and generated_at > datetime.utcnow() - timedelta(hours=max_age_hours):
        return cached.get("items", [])
    return None


def _save_cached_live_items(cache_key, source, items):
    get_collection("recommendation_source_cache").update_one(
        {"cache_key": cache_key},
        {
            "$set": {
                "cache_key": cache_key,
                "source": source,
                "items": items,
                "generated_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )


def _food_queries_from_trends(food_trends):
    queries = []
    seen = set()
    for trend in food_trends:
        keyword = trend.get("keyword", "")
        matched = False
        for token, candidates in FOOD_QUERY_HINTS.items():
            if token in keyword:
                for candidate in candidates:
                    key = candidate.lower()
                    if key not in seen:
                        queries.append((candidate, keyword, _trend_source_url(trend)))
                        seen.add(key)
                matched = True
        if matched:
            continue
        english_hint = re.sub(r"[^a-zA-Z ]", " ", keyword).strip()
        if english_hint:
            key = english_hint.lower()
            if key not in seen:
                queries.append((english_hint, keyword, _trend_source_url(trend)))
                seen.add(key)
    defaults = [
        ("Arrabiata", "마라"),
        ("Chicken", "헬시플레이트"),
        ("Salmon", "헬시플레이트"),
        ("Pasta", "파스타"),
    ]
    for query, keyword in defaults:
        key = query.lower()
        if key not in seen:
            queries.append((query, keyword, _trend_search_url(keyword)))
            seen.add(key)
    return queries[:8]


def _classify_trend(keyword, headline):
    haystack = f"{keyword} {headline}".lower()
    for category, keywords in CATEGORY_RULES.items():
        if any(token in haystack for token in keywords):
            return category
    return "content"


def _fallback_for_missing_categories(items):
    grouped = {"food": [], "fashion": [], "content": [], "activity": []}
    for item in items:
        grouped.setdefault(item["category"], []).append(item)

    filled = list(items)
    for category in grouped:
        if grouped[category]:
            continue
        fallback = next((entry for entry in DEFAULT_TRENDS if entry["category"] == category), None)
        if fallback:
            filled.append({**fallback, "headline": f"{fallback['headline']} · fallback"})
    return filled


def _last_week_target_date():
    return (datetime.utcnow() - timedelta(days=7)).strftime("%Y%m%d")


def _fetch_google_trends(region="KR"):
    url = GOOGLE_TRENDS_RSS_URL.format(region=region)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=15) as response:
        root = ET.fromstring(response.read())

    channel = root.find("./channel")
    if channel is None:
        raise ValueError("Google Trends RSS channel not found")

    items = []
    for index, item in enumerate(channel.findall("./item"), start=1):
        keyword = _child_text(item, "title")
        traffic_text = _child_text(item, "approx_traffic")
        news_titles = _child_texts(item, "news_item_title")
        news_urls = _child_texts(item, "news_item_url")
        picture = _child_text(item, "picture")
        picture_source = _child_text(item, "picture_source")
        headline = " / ".join(news_titles[:2]) if news_titles else "Google Trends 실시간 검색어"
        traffic = _normalize_traffic(traffic_text)

        items.append(
            {
                "keyword": keyword,
                "category": _classify_trend(keyword, headline),
                "score": _score_from_rank(index, traffic),
                "headline": headline,
                "traffic": traffic_text or None,
                "image_url": picture or None,
                "image_alt": f"{keyword} 관련 뉴스 이미지" if picture else None,
                "image_source": picture_source or None,
                "source_url": news_urls[0] if news_urls else _trend_search_url(keyword),
                "source": "google_trends_rss",
            }
        )

    if not items:
        raise ValueError("Google Trends RSS items missing")

    return _fallback_for_missing_categories(items), url


def _fetch_kobis_weekly_boxoffice():
    target_date = _last_week_target_date()
    url = KOBIS_WEEKLY_BOXOFFICE_URL.format(
        api_key=current_app.config["KOBIS_API_KEY"],
        target_date=target_date,
    )
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=15) as response:
        root = ET.fromstring(response.read())

    items = []
    for rank, item in enumerate(root.findall(".//weeklyBoxOffice"), start=1):
        movie_name = _child_text(item, "movieNm")
        if not movie_name:
            continue
        open_date = _child_text(item, "openDt")
        audience_acc = _child_text(item, "audiAcc")
        rank_text = _child_text(item, "rank", str(rank))
        rank_change = _child_text(item, "rankInten")
        poster_url = get_tmdb_movie_poster(movie_name, force_refresh=False)

        headline_bits = [f"주간 박스오피스 {rank_text}위"]
        if open_date:
            headline_bits.append(f"개봉 {open_date}")
        if rank_change and rank_change not in {"0", ""}:
            direction = "상승" if not rank_change.startswith("-") else "하락"
            headline_bits.append(f"전주 대비 {abs(int(rank_change))}계단 {direction}")

        items.append(
            {
                "keyword": movie_name,
                "category": "content",
                "score": max(60, 100 - ((rank - 1) * 6)),
                "headline": " · ".join(headline_bits),
                "traffic": f"누적 {audience_acc}명" if audience_acc else None,
                "image_url": poster_url,
                "image_alt": f"{movie_name} 포스터" if poster_url else None,
                "source": "kobis_weekly_boxoffice",
                "target_date": target_date,
            }
        )

    if not items:
        raise ValueError("KOBIS weekly box office items missing")

    return items, url, target_date


def ensure_runtime_seed(region="KR"):
    trends = get_collection("trend_cache")
    if trends.count_documents({"region": region}, limit=1) == 0:
        trends.insert_one(
            {
                "cache_key": f"google_trends:{region}",
                "source": "sample_google_trends",
                "region": region,
                "generated_at": datetime.utcnow(),
                "is_live": False,
                "source_url": GOOGLE_TRENDS_RSS_URL.format(region=region),
                "keywords": DEFAULT_TRENDS,
            }
        )


def refresh_trends_cache(force=False, region="KR"):
    collection = get_collection("trend_cache")
    ensure_runtime_seed(region=region)

    cache_key = f"google_trends:{region}"
    cached = collection.find_one({"cache_key": cache_key})
    now = datetime.utcnow()
    stale_cutoff = now - timedelta(hours=2)

    if cached and cached.get("generated_at") and cached["generated_at"] > stale_cutoff and not force:
        return cached

    google_url = GOOGLE_TRENDS_RSS_URL.format(region=region)
    kobis_url = None
    kobis_target_date = None
    is_google_live = False
    is_kobis_live = False

    try:
        keywords, google_url = _fetch_google_trends(region=region)
        is_google_live = True
    except Exception:
        keywords = list(DEFAULT_TRENDS)

    try:
        kobis_items, kobis_url, kobis_target_date = _fetch_kobis_weekly_boxoffice()
        keywords = [item for item in keywords if item["category"] != "content"] + kobis_items
        is_kobis_live = True
    except Exception:
        pass

    keywords = _fallback_for_missing_categories(keywords)

    payload = {
        "cache_key": cache_key,
        "source": "hybrid_live_trends",
        "region": region,
        "generated_at": now,
        "is_live": is_google_live or is_kobis_live,
        "source_url": google_url,
        "google_url": google_url,
        "kobis_url": kobis_url,
        "kobis_target_date": kobis_target_date,
        "keywords": keywords,
    }

    collection.update_one({"cache_key": cache_key}, {"$set": payload}, upsert=True)
    return payload


def get_latest_trends(limit=8, region="KR", force_refresh=False):
    latest = refresh_trends_cache(force=force_refresh, region=region)
    return (latest or {}).get("keywords", [])[:limit]


def get_trends_by_category(region="KR", force_refresh=False):
    grouped = {"food": [], "fashion": [], "content": [], "activity": []}
    for trend in get_latest_trends(limit=24, region=region, force_refresh=force_refresh):
        grouped.setdefault(trend["category"], []).append(trend)
    return grouped


def get_trend_status(region="KR"):
    cache_key = f"google_trends:{region}"
    cache = get_collection("trend_cache").find_one({"cache_key": cache_key})
    if not cache:
        cache = refresh_trends_cache(force=False, region=region)
    return {
        "generated_at": cache.get("generated_at") if cache else None,
        "source_label": "Google Trends RSS + KOBIS Weekly Box Office",
        "source_url": cache.get("source_url") if cache else GOOGLE_TRENDS_RSS_URL.format(region=region),
        "google_url": cache.get("google_url") if cache else GOOGLE_TRENDS_RSS_URL.format(region=region),
        "kobis_url": cache.get("kobis_url") if cache else None,
        "kobis_target_date": cache.get("kobis_target_date") if cache else None,
        "region": region,
        "is_live": cache.get("is_live", False) if cache else False,
    }


def get_live_food_catalog(region="KR", force_refresh=False):
    cache_key = f"live_food_catalog:{region}"
    if not force_refresh:
        cached_items = _load_cached_live_items(cache_key, max_age_hours=8)
        if cached_items is not None:
            return cached_items

    grouped = get_trends_by_category(region=region, force_refresh=force_refresh)
    food_trends = grouped.get("food", [])
    items = []
    seen_names = set()

    try:
        for query, keyword, source_url in _food_queries_from_trends(food_trends):
            payload = _json_url(THEMEALDB_SEARCH_URL.format(query=quote(query)))
            for meal in payload.get("meals") or []:
                live_item = _build_live_food_item(meal, keyword, source_url)
                if not live_item:
                    continue
                meal_name = live_item["name"].strip().lower()
                if meal_name in seen_names:
                    continue
                items.append(live_item)
                seen_names.add(meal_name)
                if len(items) >= 10:
                    break
            if len(items) >= 10:
                break
    except Exception:
        cached_items = _load_cached_live_items(cache_key, max_age_hours=72)
        if cached_items is not None:
            return cached_items

    if items:
        _save_cached_live_items(cache_key, "themealdb_search", items)
    return items


def get_live_fashion_catalog(region="KR", force_refresh=False):
    grouped = get_trends_by_category(region=region, force_refresh=force_refresh)
    items = []
    seen = set()
    for trend in grouped.get("fashion", [])[:8]:
        keyword = trend.get("keyword", "").strip().lower()
        if not keyword or keyword in seen:
            continue
        items.append(_build_live_fashion_item(trend))
        seen.add(keyword)
    return items


def get_live_activity_catalog(region="KR", force_refresh=False):
    grouped = get_trends_by_category(region=region, force_refresh=force_refresh)
    items = []
    seen = set()
    for trend in grouped.get("activity", [])[:8]:
        keyword = trend.get("keyword", "").strip().lower()
        if not keyword or keyword in seen:
            continue
        items.append(_build_live_activity_item(trend))
        seen.add(keyword)
    return items


def _quiz_from_pair(quiz_id, title, prompt, left, right):
    left_score = max(1, left.get("score", 50))
    right_score = max(1, right.get("score", 50))
    total = left_score + right_score
    baseline_left = max(20, min(80, round((left_score / total) * 100)))
    baseline_right = 100 - baseline_left
    return {
        "id": quiz_id,
        "title": title,
        "prompt": prompt,
        "left_label": left.get("keyword") or left.get("name"),
        "right_label": right.get("keyword") or right.get("name"),
        "baseline_left": baseline_left,
        "baseline_right": baseline_right,
        "source_label": "Google Trends 기반 실시간 대결",
    }


def get_quiz_questions(region="KR", force_refresh=False):
    grouped = get_trends_by_category(region=region, force_refresh=force_refresh)
    questions = []

    food_items = grouped.get("food", [])[:2]
    if len(food_items) == 2:
        questions.append(
            _quiz_from_pair(
                f"food-{_slugify(food_items[0]['keyword'])}-{_slugify(food_items[1]['keyword'])}",
                "오늘의 푸드 밸런스 게임",
                "지금 더 끌리는 푸드 키워드는?",
                food_items[0],
                food_items[1],
            )
        )

    fashion_items = grouped.get("fashion", [])[:2]
    if len(fashion_items) == 2:
        questions.append(
            _quiz_from_pair(
                f"fashion-{_slugify(fashion_items[0]['keyword'])}-{_slugify(fashion_items[1]['keyword'])}",
                "오늘의 코디 밸런스 게임",
                "오늘 더 입어보고 싶은 무드는?",
                fashion_items[0],
                fashion_items[1],
            )
        )

    activity_items = grouped.get("activity", [])[:2]
    if len(activity_items) == 2:
        questions.append(
            _quiz_from_pair(
                f"activity-{_slugify(activity_items[0]['keyword'])}-{_slugify(activity_items[1]['keyword'])}",
                "주말 액티비티 밸런스 게임",
                "이번 주말에는 어느 쪽이 더 끌리나요?",
                activity_items[0],
                activity_items[1],
            )
        )

    return questions or DEFAULT_QUIZ_QUESTIONS


def get_quiz_result(quiz_id, region="KR"):
    quiz = next((item for item in get_quiz_questions(region=region) if item["id"] == quiz_id), None)
    if not quiz:
        return None

    logs = list(get_collection("quiz_logs").find({"quiz_id": quiz_id}))
    left_votes = quiz["baseline_left"]
    right_votes = quiz["baseline_right"]

    for log in logs:
        if log["choice"] == "left":
            left_votes += 1
        else:
            right_votes += 1

    total = left_votes + right_votes
    left_rate = round((left_votes / total) * 100) if total else 50
    right_rate = 100 - left_rate

    return {
        "quiz_id": quiz_id,
        "left_label": quiz["left_label"],
        "right_label": quiz["right_label"],
        "left_votes": left_votes,
        "right_votes": right_votes,
        "left_rate": left_rate,
        "right_rate": right_rate,
    }


def build_quiz_board():
    board = []
    for quiz in get_quiz_questions():
        result = get_quiz_result(quiz["id"])
        board.append({**quiz, "result": result})
    return board


def record_quiz_vote(user_id, quiz_id, choice):
    quiz = next((item for item in get_quiz_questions() if item["id"] == quiz_id), None)
    if not quiz:
        return None

    get_collection("quiz_logs").insert_one(
        {
            "quiz_id": quiz_id,
            "choice": choice,
            "user_id": user_id,
            "left_label": quiz["left_label"],
            "right_label": quiz["right_label"],
            "created_at": datetime.utcnow(),
        }
    )
    return get_quiz_result(quiz_id)
