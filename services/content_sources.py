import html
import re
from datetime import datetime, timedelta
from urllib.request import Request, urlopen

from db.mongo import get_collection


NETFLIX_TUDUM_SOURCES = [
    {
        "cache_key": "netflix_top10_tv",
        "url": "https://www.netflix.com/tudum/top10/tv",
        "platform": "넷플릭스",
        "provider": "Netflix",
        "content_type": "시리즈",
    },
    {
        "cache_key": "netflix_top10_movie",
        "url": "https://www.netflix.com/tudum/top10",
        "platform": "넷플릭스",
        "provider": "Netflix",
        "content_type": "영화",
    },
]

LOCAL_CONTENT_LIBRARY = [
    {
        "id": "local:yumi-cells",
        "name": "유미의 세포들",
        "description": "하루의 감정선을 가볍고 재치 있게 따라갈 수 있는 대표적인 일상 로맨스 웹툰입니다.",
        "genres": ["로맨스", "일상", "코미디"],
        "platforms": ["웹툰"],
        "provider": "네이버웹툰",
        "content_type": "웹툰",
        "moods": ["comfort", "light", "refresh"],
        "trend_keywords": ["힐링웹툰", "일상로맨스"],
        "duration_label": "회차당 10분",
        "freshness_boost": 4,
    },
    {
        "id": "local:omniscient-reader",
        "name": "전지적 독자 시점",
        "description": "세계관 몰입과 전개 속도를 한 번에 챙기고 싶을 때 좋은 판타지형 웹툰입니다.",
        "genres": ["판타지", "액션", "모험"],
        "platforms": ["웹툰"],
        "provider": "네이버웹툰",
        "content_type": "웹툰",
        "moods": ["focus", "adventure", "reward"],
        "trend_keywords": ["판타지웹툰", "세계관"],
        "duration_label": "회차당 12분",
        "freshness_boost": 5,
    },
    {
        "id": "local:maru-dog",
        "name": "마루는 강쥐",
        "description": "짧게 웃고 싶을 때 부담 없이 고를 수 있는 감정 회복형 웹툰입니다.",
        "genres": ["코미디", "일상", "힐링"],
        "platforms": ["웹툰"],
        "provider": "카카오웹툰",
        "content_type": "웹툰",
        "moods": ["light", "comfort", "refresh"],
        "trend_keywords": ["짧은콘텐츠", "힐링웹툰"],
        "duration_label": "회차당 7분",
        "freshness_boost": 4,
    },
    {
        "id": "local:moving",
        "name": "무빙",
        "description": "감정선과 액션이 동시에 살아 있어 몰입감 높은 밤 시간을 만들어주는 드라마입니다.",
        "genres": ["액션", "드라마", "판타지"],
        "platforms": ["드라마"],
        "provider": "OTT",
        "content_type": "시리즈",
        "moods": ["focus", "reward", "adventure"],
        "trend_keywords": ["액션드라마", "세계관"],
        "duration_label": "회당 55분",
        "freshness_boost": 3,
    },
    {
        "id": "local:daily-office-romcom",
        "name": "오피스 로맨틱 코미디",
        "description": "하루를 가볍게 정리하고 싶은 저녁에 어울리는 리듬감 있는 로맨틱 코미디입니다.",
        "genres": ["로맨스", "코미디", "드라마"],
        "platforms": ["드라마"],
        "provider": "OTT",
        "content_type": "시리즈",
        "moods": ["comfort", "light", "reward"],
        "trend_keywords": ["로코", "감성드라마"],
        "duration_label": "회당 60분",
        "freshness_boost": 3,
    },
    {
        "id": "local:crime-archive",
        "name": "심야 범죄 수사극",
        "description": "어두운 텐션과 추리 포인트를 좋아할 때 안정적으로 만족도가 높은 장르형 드라마입니다.",
        "genres": ["범죄", "스릴러", "미스터리"],
        "platforms": ["드라마"],
        "provider": "OTT",
        "content_type": "시리즈",
        "moods": ["dark", "focus", "reward"],
        "trend_keywords": ["범죄스릴러", "추리드라마"],
        "duration_label": "회당 55분",
        "freshness_boost": 2,
    },
    {
        "id": "local:cozy-food-film",
        "name": "한 끼가 따뜻해지는 요리 영화",
        "description": "먹는 즐거움과 정서적 안정감을 동시에 주는 편안한 영화 타입입니다.",
        "genres": ["드라마", "힐링", "음식"],
        "platforms": ["영화"],
        "provider": "OTT",
        "content_type": "영화",
        "moods": ["comfort", "light", "foodie"],
        "trend_keywords": ["푸드필름", "힐링무비"],
        "duration_label": "1시간 48분",
        "freshness_boost": 2,
    },
    {
        "id": "local:twist-thriller-film",
        "name": "반전 밀도 높은 스릴러 영화",
        "description": "집중해서 한 편을 끝내고 싶을 때 후회 없는 몰입형 선택지입니다.",
        "genres": ["스릴러", "범죄", "미스터리"],
        "platforms": ["영화"],
        "provider": "OTT",
        "content_type": "영화",
        "moods": ["focus", "dark", "reward"],
        "trend_keywords": ["반전영화", "범죄스릴러"],
        "duration_label": "2시간 4분",
        "freshness_boost": 3,
    },
    {
        "id": "local:visual-travel-vlog",
        "name": "시네마틱 여행 브이로그",
        "description": "깊게 몰입하지 않아도 감각적으로 기분을 환기할 수 있는 유튜브 포맷입니다.",
        "genres": ["여행", "브이로그", "힐링"],
        "platforms": ["유튜브"],
        "provider": "YouTube",
        "content_type": "영상",
        "moods": ["refresh", "light", "comfort"],
        "trend_keywords": ["여행브이로그", "감성영상"],
        "duration_label": "20분",
        "freshness_boost": 4,
    },
    {
        "id": "local:productivity-reset",
        "name": "루틴 재정비 생산성 유튜브",
        "description": "의욕을 올리거나 다음 날을 정리하고 싶을 때 클릭하기 좋은 자기계발형 콘텐츠입니다.",
        "genres": ["자기계발", "정보", "브이로그"],
        "platforms": ["유튜브"],
        "provider": "YouTube",
        "content_type": "영상",
        "moods": ["focus", "refresh", "light"],
        "trend_keywords": ["생산성", "루틴영상"],
        "duration_label": "18분",
        "freshness_boost": 5,
    },
    {
        "id": "local:youtube-deep-dive",
        "name": "문화 해설 딥다이브 유튜브",
        "description": "단순 소비보다 맥락과 해설을 좋아하는 사용자에게 잘 맞는 콘텐츠입니다.",
        "genres": ["정보", "문화", "에세이"],
        "platforms": ["유튜브"],
        "provider": "YouTube",
        "content_type": "영상",
        "moods": ["depth", "focus", "comfort"],
        "trend_keywords": ["해설영상", "인사이트"],
        "duration_label": "26분",
        "freshness_boost": 4,
    },
    {
        "id": "local:sf-mini-series",
        "name": "짧고 강한 SF 미니시리즈",
        "description": "호흡은 짧지만 후반부 회수력이 강한 SF 계열 시리즈입니다.",
        "genres": ["SF", "스릴러", "드라마"],
        "platforms": ["드라마"],
        "provider": "OTT",
        "content_type": "시리즈",
        "moods": ["focus", "dark", "adventure"],
        "trend_keywords": ["SF드라마", "떡밥회수"],
        "duration_label": "회당 45분",
        "freshness_boost": 4,
    },
    {
        "id": "local:romance-webtoon-short",
        "name": "짧게 읽는 감정선 웹툰",
        "description": "너무 무겁지 않으면서도 감정선이 살아 있는 짧은 웹툰 추천입니다.",
        "genres": ["로맨스", "힐링", "일상"],
        "platforms": ["웹툰"],
        "provider": "카카오웹툰",
        "content_type": "웹툰",
        "moods": ["comfort", "depth", "light"],
        "trend_keywords": ["감정선", "힐링웹툰"],
        "duration_label": "회차당 8분",
        "freshness_boost": 4,
    },
    {
        "id": "local:weekend-anime-film",
        "name": "주말용 애니메이션 영화",
        "description": "가벼운 설렘과 색감, 음악을 함께 챙기고 싶은 날에 적합합니다.",
        "genres": ["애니메이션", "판타지", "로맨스"],
        "platforms": ["영화"],
        "provider": "OTT",
        "content_type": "영화",
        "moods": ["adventure", "comfort", "aesthetic"],
        "trend_keywords": ["애니영화", "감성무비"],
        "duration_label": "1시간 55분",
        "freshness_boost": 4,
    },
    {
        "id": "local:docu-sports-intensity",
        "name": "스포츠 다큐 시리즈",
        "description": "에너지를 끌어올리고 싶을 때 작동하는 추진형 콘텐츠입니다.",
        "genres": ["다큐", "스포츠", "리얼리티"],
        "platforms": ["드라마"],
        "provider": "OTT",
        "content_type": "시리즈",
        "moods": ["energy", "focus", "reward"],
        "trend_keywords": ["스포츠다큐", "몰입콘텐츠"],
        "duration_label": "회당 40분",
        "freshness_boost": 3,
    },
    {
        "id": "local:cozy-house-vlog",
        "name": "집 정리와 플레이리스트 브이로그",
        "description": "에너지가 낮을 때도 무리 없이 틀어둘 수 있는 정리형 브이로그입니다.",
        "genres": ["브이로그", "라이프", "힐링"],
        "platforms": ["유튜브"],
        "provider": "YouTube",
        "content_type": "영상",
        "moods": ["comfort", "light", "refresh"],
        "trend_keywords": ["방꾸미기", "플리추천"],
        "duration_label": "15분",
        "freshness_boost": 4,
    },
]

NETFLIX_FALLBACK_ROWS = {
    "netflix_top10_tv": [
        ("01", "Bridgerton: Season 4", "6", "13,100,000", "8:53", "116,400,000"),
        ("02", "The Dinosaurs: Season 1", "1", "10,400,000", "3:06", "32,300,000"),
        ("03", "The Night Agent: Season 3", "3", "5,200,000", "8:43", "45,000,000"),
        ("04", "Vladimir: Limited Series", "1", "4,200,000", "4:01", "17,000,000"),
        ("05", "Formula 1: Drive to Survive: Season 8", "2", "3,000,000", "6:04", "18,500,000"),
        ("06", "Raw: 2026 - March 2, 2026", "1", "3,000,000", "1:41", "5,400,000"),
        ("07", "Gabby's Dollhouse: Season 13", "1", "2,500,000", "2:02", "5,100,000"),
        ("08", "Bridgerton: Season 1", "20", "2,200,000", "8:12", "18,300,000"),
        ("09", "The Mentalist: Season 1", "1", "2,200,000", "16:36", "36,800,000"),
        ("10", "Love Is Blind: Ohio", "4", "2,000,000", "12:06", "24,100,000"),
    ],
    "netflix_top10_movie": [
        ("01", "War Machine", "1", "39,300,000", "1:49", "71,400,000"),
        ("02", "Jurassic World Rebirth", "2", "6,700,000", "2:14", "14,900,000"),
        ("03", "KPop Demon Hunters", "38", "4,700,000", "1:40", "7,900,000"),
        ("04", "Trap House", "2", "4,400,000", "1:42", "7,500,000"),
        ("05", "The Boss Baby", "23", "3,300,000", "1:38", "5,400,000"),
        ("06", "Jurassic World", "4", "3,200,000", "2:04", "6,700,000"),
        ("07", "Hierarchy", "2", "3,200,000", "1:40", "5,300,000"),
        ("08", "Jurassic World: Dominion", "2", "2,800,000", "2:27", "6,900,000"),
        ("09", "The Karate Kid", "1", "2,700,000", "2:20", "6,200,000"),
        ("10", "Jurassic World: Fallen Kingdom", "2", "2,500,000", "2:08", "5,400,000"),
    ],
}

NETFLIX_TITLE_HINTS = {
    "Bridgerton: Season 4": {
        "genres": ["로맨스", "드라마", "시대극"],
        "moods": ["comfort", "reward", "light"],
        "description": "감정선과 비주얼 모두 챙기고 싶을 때 잘 맞는 넷플릭스 로맨스 대작입니다.",
    },
    "Bridgerton: Season 1": {
        "genres": ["로맨스", "드라마", "시대극"],
        "moods": ["comfort", "reward", "light"],
        "description": "초기 시즌부터 다시 정주행해도 만족도가 높은 대표 로맨스 시리즈입니다.",
    },
    "The Dinosaurs: Season 1": {
        "genres": ["다큐", "모험", "가족"],
        "moods": ["adventure", "focus", "light"],
        "description": "거대한 볼거리와 설명형 재미를 함께 주는 다큐 계열 신작입니다.",
    },
    "The Night Agent: Season 3": {
        "genres": ["스릴러", "액션", "첩보"],
        "moods": ["focus", "dark", "reward"],
        "description": "속도감 있는 전개와 긴장감을 원하는 저녁 시간에 강한 선택지입니다.",
    },
    "Vladimir: Limited Series": {
        "genres": ["드라마", "심리", "스릴러"],
        "moods": ["depth", "dark", "focus"],
        "description": "심리적인 압력과 서사 밀도가 높은 한정 시리즈형 작품입니다.",
    },
    "Formula 1: Drive to Survive: Season 8": {
        "genres": ["다큐", "스포츠", "리얼리티"],
        "moods": ["energy", "focus", "reward"],
        "description": "몰입감과 추진력이 필요한 날 잘 작동하는 스포츠 다큐 시리즈입니다.",
    },
    "Raw: 2026 - March 2, 2026": {
        "genres": ["스포츠", "라이브", "예능"],
        "moods": ["energy", "social", "reward"],
        "description": "실시간 경기형 에너지와 현장감을 선호할 때 어울리는 엔터테인먼트 콘텐츠입니다.",
    },
    "Gabby's Dollhouse: Season 13": {
        "genres": ["애니메이션", "가족", "키즈"],
        "moods": ["light", "comfort", "refresh"],
        "description": "가볍고 선명한 톤으로 부담 없이 보기 좋은 가족형 애니메이션입니다.",
    },
    "The Mentalist: Season 1": {
        "genres": ["범죄", "미스터리", "드라마"],
        "moods": ["focus", "comfort", "dark"],
        "description": "오래된 시리즈 특유의 안정감과 사건 해결형 재미를 함께 줍니다.",
    },
    "Love Is Blind: Ohio": {
        "genres": ["리얼리티", "로맨스", "예능"],
        "moods": ["social", "light", "comfort"],
        "description": "가볍게 틀어두기 좋으면서도 대화 포인트가 많은 넷플릭스 예능 계열입니다.",
    },
    "War Machine": {
        "genres": ["액션", "SF", "전쟁"],
        "moods": ["reward", "focus", "adventure"],
        "description": "이번 주 넷플릭스에서 가장 빠르게 뜨고 있는 하이텐션 액션 영화입니다.",
    },
    "Jurassic World Rebirth": {
        "genres": ["액션", "SF", "모험"],
        "moods": ["adventure", "reward", "focus"],
        "description": "거대한 스케일과 익숙한 프랜차이즈 재미를 찾을 때 적합합니다.",
    },
    "KPop Demon Hunters": {
        "genres": ["애니메이션", "액션", "판타지", "음악"],
        "moods": ["adventure", "light", "reward"],
        "description": "K-팝 감성과 판타지 액션을 함께 즐기고 싶을 때 잘 맞는 작품입니다.",
    },
    "Trap House": {
        "genres": ["범죄", "스릴러", "액션"],
        "moods": ["dark", "focus", "reward"],
        "description": "짧고 강한 장르 몰입을 원하는 사용자에게 잘 맞는 범죄 스릴러 영화입니다.",
    },
    "The Boss Baby": {
        "genres": ["애니메이션", "가족", "코미디"],
        "moods": ["light", "comfort", "refresh"],
        "description": "가볍게 웃고 싶거나 부담 없는 선택이 필요할 때 좋은 가족형 작품입니다.",
    },
    "Jurassic World": {
        "genres": ["액션", "SF", "모험"],
        "moods": ["adventure", "reward", "focus"],
        "description": "속도감 있는 볼거리와 프랜차이즈 익숙함을 함께 주는 영화입니다.",
    },
    "Hierarchy": {
        "genres": ["드라마", "스릴러", "학원"],
        "moods": ["dark", "focus", "reward"],
        "description": "관계 긴장감과 분위기 중심의 전개를 좋아할 때 잘 맞는 작품입니다.",
    },
    "Jurassic World: Dominion": {
        "genres": ["액션", "SF", "모험"],
        "moods": ["adventure", "reward", "focus"],
        "description": "큰 스케일과 추격감이 필요한 날 무난하게 강한 선택지입니다.",
    },
    "The Karate Kid": {
        "genres": ["액션", "드라마", "스포츠"],
        "moods": ["reward", "comfort", "energy"],
        "description": "성장 서사와 스포츠 훈련의 리듬을 좋아한다면 잘 맞습니다.",
    },
    "Jurassic World: Fallen Kingdom": {
        "genres": ["액션", "SF", "모험"],
        "moods": ["adventure", "reward", "focus"],
        "description": "전형적인 블록버스터 리듬을 원하는 밤 시간에 보기 좋습니다.",
    },
}


def _slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return slug.strip("-")


def _parse_number(raw_value):
    return int(raw_value.replace(",", "").strip())


def _normalize_runtime_label(raw_runtime):
    return raw_runtime.replace(":", "시간 ", 1) + "분" if ":" in raw_runtime else raw_runtime


def _fallback_title_hints(title, content_type):
    lower = title.lower()
    genres = ["드라마"]
    moods = ["comfort", "focus"]
    description = "지금 넷플릭스에서 주목받는 작품으로, 트렌드 신호를 강하게 받는 후보입니다."

    if "season" in lower or "series" in lower:
        genres = ["드라마", "시리즈"]
        description = "현재 넷플릭스 Top 10에 오른 시리즈형 작품입니다."
    if any(keyword in lower for keyword in ["jurassic", "war", "karate", "agent"]):
        genres = ["액션", "스릴러", "모험"]
        moods = ["focus", "reward", "adventure"]
        description = "속도감과 장르 몰입이 강한 넷플릭스 인기작입니다."
    if any(keyword in lower for keyword in ["love", "bridgerton"]):
        genres = ["로맨스", "드라마"]
        moods = ["comfort", "light", "reward"]
        description = "감정선과 무드 중심으로 즐기기 좋은 넷플릭스 인기작입니다."
    if any(keyword in lower for keyword in ["formula", "raw"]):
        genres = ["스포츠", "리얼리티", "다큐"]
        moods = ["energy", "focus", "reward"]
        description = "현장감과 몰입도가 강한 스포츠/리얼리티 계열 작품입니다."
    if any(keyword in lower for keyword in ["boss baby", "gabby", "dollhouse", "demon"]):
        genres = ["애니메이션", "가족", "판타지"]
        moods = ["light", "refresh", "comfort"]
        description = "가볍고 선명한 무드로 즐기기 좋은 애니메이션 계열 작품입니다."
    if content_type == "영화" and "series" not in lower and "season" not in lower:
        genres = genres if genres != ["드라마"] else ["영화", "드라마"]

    return {
        "genres": genres,
        "moods": moods,
        "description": description,
    }


def _build_netflix_item(source, row):
    rank, title, weeks, views, runtime, hours = row
    hints = NETFLIX_TITLE_HINTS.get(title, _fallback_title_hints(title, source["content_type"]))
    views_int = _parse_number(views)
    weeks_int = int(weeks)
    hours_int = _parse_number(hours)

    return {
        "id": f"netflix:{source['cache_key']}:{_slugify(title)}",
        "name": title,
        "description": hints["description"],
        "genres": hints["genres"],
        "platforms": [source["platform"]],
        "provider": source["provider"],
        "content_type": source["content_type"],
        "moods": hints["moods"],
        "trend_keywords": [title, "Netflix Top 10", "넷플릭스"],
        "duration_label": _normalize_runtime_label(runtime),
        "freshness_boost": max(2, 11 - int(rank)),
        "source": "netflix_tudum",
        "source_url": source["url"],
        "stats": {
            "rank": int(rank),
            "weeks_in_top10": weeks_int,
            "views": views_int,
            "hours_viewed": hours_int,
        },
    }


def _parse_tudum_top10_rows(page_html):
    rows = re.findall(
        r'<tr><td class="title"[^>]*><span class="rank">(.*?)</span>.*?<button>(.*?)</button></td>'
        r'<td[^>]*>(.*?)</td><td class="views"[^>]*>(.*?)</td>'
        r'<td class="desktop-only(?: runtime-varies)?"[^>]*>(.*?)</td>'
        r'<td class="desktop-only"[^>]*>(.*?)</td></tr>',
        page_html,
        re.DOTALL,
    )
    parsed = []
    for rank, title, weeks, views, runtime, hours in rows:
        parsed.append(
            (
                rank.strip(),
                html.unescape(title.strip()),
                weeks.strip(),
                views.strip(),
                runtime.strip(),
                hours.strip(),
            )
        )
    return parsed


def _fetch_tudum_html(url):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urlopen(request, timeout=15).read().decode("utf-8", "ignore")


def refresh_netflix_cache(force=False):
    collection = get_collection("content_source_cache")
    now = datetime.utcnow()
    stale_cutoff = now - timedelta(hours=18)
    refreshed = {}

    for source in NETFLIX_TUDUM_SOURCES:
        cached = collection.find_one({"cache_key": source["cache_key"]})
        if cached and cached.get("generated_at") and cached["generated_at"] > stale_cutoff and not force:
            refreshed[source["cache_key"]] = cached
            continue

        try:
            page_html = _fetch_tudum_html(source["url"])
            start_idx = page_html.find('data-uia="top10-table"')
            table_chunk = page_html[start_idx:start_idx + 25000] if start_idx != -1 else page_html
            rows = _parse_tudum_top10_rows(table_chunk)
        except Exception:
            rows = NETFLIX_FALLBACK_ROWS[source["cache_key"]]

        items = [_build_netflix_item(source, row) for row in rows[:10]]
        payload = {
            "cache_key": source["cache_key"],
            "source_url": source["url"],
            "generated_at": now,
            "items": items,
        }
        collection.update_one({"cache_key": source["cache_key"]}, {"$set": payload}, upsert=True)
        refreshed[source["cache_key"]] = payload

    return refreshed


def get_netflix_content(force_refresh=False):
    cached_map = refresh_netflix_cache(force=force_refresh)
    items = []
    for source in NETFLIX_TUDUM_SOURCES:
        payload = cached_map.get(source["cache_key"])
        if payload:
            items.extend(payload.get("items", []))
    return items


def get_netflix_status():
    cache = get_collection("content_source_cache").find_one({"cache_key": "netflix_top10_tv"})
    if not cache:
        refresh_netflix_cache(force=False)
        cache = get_collection("content_source_cache").find_one({"cache_key": "netflix_top10_tv"})
    return {
        "generated_at": cache.get("generated_at") if cache else None,
        "source_label": "Netflix Tudum Top 10",
        "source_urls": [source["url"] for source in NETFLIX_TUDUM_SOURCES],
    }


def get_content_inventory(force_refresh=False):
    netflix_items = get_netflix_content(force_refresh=force_refresh)
    return LOCAL_CONTENT_LIBRARY + netflix_items


def find_content_item(content_id, force_refresh=False):
    for item in get_content_inventory(force_refresh=force_refresh):
        if item["id"] == content_id:
            return item
    return None
