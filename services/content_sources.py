import html
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
from urllib.request import Request, urlopen

from db.mongo import get_collection


NETFLIX_TUDUM_SOURCES = [
    {
        "cache_key": "netflix_top10_kr_movies",
        "url": "https://www.netflix.com/tudum/top10/south-korea",
        "platform": "넷플릭스",
        "provider": "Netflix",
        "content_type": "영화",
        "country_label": "South Korea",
        "list_label": "Top 10 Movies in South Korea",
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
    "netflix_top10_kr_movies": [
        ("01", "Ballerina", "2"),
        ("02", "Concrete Market", "1"),
        ("03", "The Electric State", "1"),
        ("04", "Plankton: The Movie", "1"),
        ("05", "Kraven the Hunter", "1"),
        ("06", "Venom: The Last Dance", "6"),
        ("07", "Moana 2", "4"),
        ("08", "Despicable Me 4", "9"),
        ("09", "John Wick: Chapter 4", "1"),
        ("10", "No Other Choice", "1"),
    ],
}

NETFLIX_TITLE_HINTS = {
    "Ballerina": {
        "genres": ["액션", "스릴러", "범죄"],
        "moods": ["focus", "dark", "reward"],
        "description": "강한 액션 텐션과 추격 서사를 선호할 때 잘 맞는 넷플릭스 인기 영화입니다.",
    },
    "Concrete Market": {
        "genres": ["드라마", "범죄", "스릴러"],
        "moods": ["focus", "dark", "depth"],
        "description": "도시적 긴장감과 범죄 드라마 결을 좋아할 때 선택하기 좋은 영화입니다.",
    },
    "The Electric State": {
        "genres": ["SF", "모험", "드라마"],
        "moods": ["adventure", "reward", "focus"],
        "description": "세계관과 비주얼 중심의 SF 로드무비 감성을 원할 때 어울립니다.",
    },
    "Plankton: The Movie": {
        "genres": ["애니메이션", "가족", "코미디"],
        "moods": ["light", "comfort", "refresh"],
        "description": "부담 없이 웃고 싶을 때 잘 맞는 가벼운 애니메이션 영화입니다.",
    },
    "Kraven the Hunter": {
        "genres": ["액션", "모험", "히어로"],
        "moods": ["reward", "focus", "adventure"],
        "description": "거친 액션과 안티히어로 계열 전개를 선호할 때 무난하게 강합니다.",
    },
    "Venom: The Last Dance": {
        "genres": ["액션", "SF", "히어로"],
        "moods": ["reward", "adventure", "focus"],
        "description": "프랜차이즈형 볼거리와 빠른 전개를 기대할 때 고르기 좋은 영화입니다.",
    },
    "Moana 2": {
        "genres": ["애니메이션", "모험", "가족"],
        "moods": ["light", "adventure", "comfort"],
        "description": "밝은 에너지와 모험 감각을 함께 챙기고 싶을 때 잘 맞습니다.",
    },
    "Despicable Me 4": {
        "genres": ["애니메이션", "코미디", "가족"],
        "moods": ["light", "refresh", "comfort"],
        "description": "짧게 기분 전환하고 싶은 날 안정적으로 고를 수 있는 코미디 애니메이션입니다.",
    },
    "John Wick: Chapter 4": {
        "genres": ["액션", "범죄", "스릴러"],
        "moods": ["focus", "dark", "reward"],
        "description": "높은 완성도의 액션과 묵직한 분위기를 원할 때 가장 선명한 선택지입니다.",
    },
    "No Other Choice": {
        "genres": ["드라마", "스릴러", "미스터리"],
        "moods": ["depth", "focus", "dark"],
        "description": "서사 밀도와 심리적 긴장감을 함께 보고 싶을 때 어울리는 영화입니다.",
    },
}


def _slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return slug.strip("-")


class _VisibleTextHTMLParser(HTMLParser):
    BLOCK_TAGS = {
        "article",
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "p",
        "section",
        "td",
        "th",
        "tr",
    }

    def __init__(self):
        super().__init__()
        self.tokens = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "img":
            attrs_map = dict(attrs)
            alt = (attrs_map.get("alt") or "").strip()
            if alt:
                self.tokens.append(f"Image: {html.unescape(alt)}")
        if tag in self.BLOCK_TAGS:
            self.tokens.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in self.BLOCK_TAGS:
            self.tokens.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = re.sub(r"\s+", " ", html.unescape(data)).strip()
        if text:
            self.tokens.append(text)


def _extract_visible_tokens(page_html):
    parser = _VisibleTextHTMLParser()
    parser.feed(page_html)

    tokens = []
    for token in parser.tokens:
        if token == "\n":
            if tokens and tokens[-1] != "\n":
                tokens.append(token)
            continue
        if not tokens or tokens[-1] != token:
            tokens.append(token)
    return [token for token in tokens if token]


def _looks_like_week_range(token):
    return bool(re.fullmatch(r"South Korea \| \d{1,2}/\d{1,2}/\d{2} - \d{1,2}/\d{1,2}/\d{2}", token))


def _fallback_title_hints(title, content_type):
    lower = title.lower()
    genres = ["드라마", "영화"] if content_type == "영화" else ["드라마"]
    moods = ["comfort", "focus", "reward"]
    description = "지금 넷플릭스 한국 영화 Top 10에서 주목받는 작품입니다."

    if any(keyword in lower for keyword in ["wick", "ballerina", "kraven", "venom"]):
        genres = ["액션", "스릴러", "모험"]
        moods = ["focus", "reward", "adventure"]
        description = "속도감과 장르 몰입이 강한 넷플릭스 한국 인기 영화입니다."
    if any(keyword in lower for keyword in ["moana", "despicable", "plankton"]):
        genres = ["애니메이션", "가족", "판타지"]
        moods = ["light", "refresh", "comfort"]
        description = "가볍고 선명한 무드로 즐기기 좋은 넷플릭스 한국 인기 애니메이션입니다."
    if "electric" in lower:
        genres = ["SF", "모험", "드라마"]
        moods = ["adventure", "focus", "reward"]
        description = "비주얼과 세계관 몰입이 강한 넷플릭스 한국 인기 영화입니다."

    return {
        "genres": genres,
        "moods": moods,
        "description": description,
    }


def _build_netflix_item(source, row):
    rank, title, weeks = row
    hints = NETFLIX_TITLE_HINTS.get(title, _fallback_title_hints(title, source["content_type"]))
    weeks_int = int(weeks)

    return {
        "id": f"netflix:{source['cache_key']}:{_slugify(title)}",
        "name": title,
        "description": hints["description"],
        "genres": hints["genres"],
        "platforms": [source["platform"]],
        "provider": source["provider"],
        "content_type": source["content_type"],
        "moods": hints["moods"],
        "trend_keywords": [title, "Netflix Korea Top 10", "넷플릭스", "한국 Top 10"],
        "duration_label": "한국 Top 10 영화",
        "freshness_boost": max(2, 11 - int(rank)),
        "source": "netflix_tudum",
        "source_url": source["url"],
        "stats": {
            "rank": int(rank),
            "weeks_in_top10": weeks_int,
            "country": source["country_label"],
        },
    }


def _parse_tudum_top10_rows(page_html, source):
    tokens = _extract_visible_tokens(page_html)
    rows = []
    period = None
    in_overview = False
    pending_rank = None
    pending_title = None

    for token in tokens:
        if token == source["list_label"]:
            continue
        if _looks_like_week_range(token) and not period:
            period = token
            continue
        if token == f"{source['list_label']} overview":
            in_overview = True
            continue
        if not in_overview:
            continue
        if token in {"Catch the Latest", "Plans start at KRW 5,500"}:
            break
        if token in {"Ranking", "Title", "Weeks in Top 10", "\n"}:
            continue
        if re.fullmatch(r"\d{2}", token):
            pending_rank = token
            pending_title = None
            continue
        if pending_rank and pending_title is None:
            if token.startswith("Image: "):
                pending_title = token.replace("Image: ", "", 1).strip()
            else:
                pending_title = token.strip()
            continue
        if pending_rank and pending_title and re.fullmatch(r"\d+", token):
            rows.append((pending_rank, pending_title, token))
            pending_rank = None
            pending_title = None
            if len(rows) == 10:
                break

    return rows, period


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
            rows, period_label = _parse_tudum_top10_rows(page_html, source)
            if not rows:
                raise ValueError("No South Korea Top 10 movie rows parsed from Tudum page")
        except Exception:
            rows = NETFLIX_FALLBACK_ROWS[source["cache_key"]]
            period_label = None

        items = [_build_netflix_item(source, row) for row in rows[:10]]
        payload = {
            "cache_key": source["cache_key"],
            "source_url": source["url"],
            "generated_at": now,
            "period_label": period_label,
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
    cache = get_collection("content_source_cache").find_one({"cache_key": "netflix_top10_kr_movies"})
    if not cache:
        refresh_netflix_cache(force=False)
        cache = get_collection("content_source_cache").find_one({"cache_key": "netflix_top10_kr_movies"})
    return {
        "generated_at": cache.get("generated_at") if cache else None,
        "period_label": cache.get("period_label") if cache else None,
        "source_label": "Netflix Tudum South Korea Movies Top 10",
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
