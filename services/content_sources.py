import html
import hashlib
import json
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import quote
from urllib.request import Request, urlopen

from flask import current_app

from db.mongo import get_collection
from services.movie_images import get_tmdb_movie_poster, get_wikipedia_webtoon_image

SEARCHABLE_CONTENT_PROVIDER_BLOCKLIST = {"ott", "youtube", "네이버웹툰", "카카오웹툰"}
SEARCHABLE_CONTENT_TYPE_BLOCKLIST = {"웹툰", "영상"}
SEARCHABLE_CONTENT_PLATFORM_BLOCKLIST = {"웹툰", "유튜브"}
CONTENT_PLATFORM_ALIASES = {"드라마": "시리즈"}


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

KOBIS_WEEKLY_SOURCE = {
    "cache_key": "kobis_weekly_boxoffice",
    "platform": "영화",
    "provider": "KOBIS",
    "content_type": "영화",
}

TMDB_SOURCES = [
    {
        "cache_key": "tmdb_trending_movies",
        "url_template": "https://api.themoviedb.org/3/trending/movie/week?api_key={api_key}&language=ko-KR",
        "platform": "영화",
        "provider": "TMDB",
        "content_type": "영화",
    },
    {
        "cache_key": "tmdb_trending_tv",
        "url_template": "https://api.themoviedb.org/3/trending/tv/week?api_key={api_key}&language=ko-KR",
        "platform": "시리즈",
        "provider": "TMDB",
        "content_type": "시리즈",
    },
]

KOBIS_WEEKLY_URL = (
    "http://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchWeeklyBoxOfficeList.xml"
    "?key={api_key}&weekGb=0&targetDt={target_date}"
)
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

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

KOBIS_FALLBACK_ROWS = [
    {"rank": "1", "movieNm": "파묘", "openDt": "2024-02-22", "audiAcc": "11984571"},
    {"rank": "2", "movieNm": "듄: 파트2", "openDt": "2024-02-28", "audiAcc": "1942731"},
    {"rank": "3", "movieNm": "웡카", "openDt": "2024-01-31", "audiAcc": "3321185"},
    {"rank": "4", "movieNm": "건국전쟁", "openDt": "2024-02-01", "audiAcc": "1129319"},
    {"rank": "5", "movieNm": "존 오브 인터레스트", "openDt": "2024-06-05", "audiAcc": "201531"},
]

TMDB_FALLBACK_RESULTS = {
    "tmdb_trending_movies": [
        {
            "id": 693134,
            "title": "Dune: Part Two",
            "overview": "운명을 건 전쟁과 사막 행성의 거대한 세계관이 이어지는 SF 대작.",
            "genre_ids": [878, 12, 28],
            "poster_path": None,
            "vote_average": 8.3,
            "release_date": "2024-02-27",
            "popularity": 220.0,
        },
        {
            "id": 823464,
            "title": "Godzilla x Kong: The New Empire",
            "overview": "거대한 몬스터 세계관과 블록버스터 액션을 전면에 둔 화제작.",
            "genre_ids": [28, 878, 12],
            "poster_path": None,
            "vote_average": 7.2,
            "release_date": "2024-03-27",
            "popularity": 210.0,
        },
    ],
    "tmdb_trending_tv": [
        {
            "id": 94997,
            "name": "House of the Dragon",
            "overview": "권력과 혈통, 전쟁이 얽히는 판타지 시리즈의 대표작.",
            "genre_ids": [10765, 18, 10759],
            "poster_path": None,
            "vote_average": 8.4,
            "first_air_date": "2022-08-21",
            "popularity": 198.0,
        },
        {
            "id": 1434,
            "name": "Family Guy",
            "overview": "가볍게 보기에 좋은 장수 애니메이션 시리즈.",
            "genre_ids": [16, 35],
            "poster_path": None,
            "vote_average": 7.4,
            "first_air_date": "1999-01-31",
            "popularity": 160.0,
        },
    ],
}

TMDB_GENRE_MAP = {
    12: "모험",
    14: "판타지",
    16: "애니메이션",
    18: "드라마",
    27: "공포",
    28: "액션",
    35: "코미디",
    53: "스릴러",
    80: "범죄",
    878: "SF",
    9648: "미스터리",
    10749: "로맨스",
    10751: "가족",
    10759: "액션",
    10765: "판타지",
    99: "다큐",
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
    normalized = (value or "").strip().lower()
    slug = re.sub(r"[^\w]+", "-", normalized, flags=re.UNICODE).strip("-_").replace("_", "-")
    if slug:
        return slug
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def _visual_palette(item):
    provider = (item.get("provider") or "").lower()
    content_type = (item.get("content_type") or "").lower()

    if item.get("source") == "netflix_tudum" or provider == "netflix":
        return {
            "start": "#250909",
            "mid": "#7f1018",
            "end": "#f04452",
            "accent": "#ffd6db",
            "label": "NETFLIX",
        }
    if "웹툰" in content_type:
        return {
            "start": "#072f1f",
            "mid": "#0d7a4b",
            "end": "#91f6b8",
            "accent": "#d7ffe7",
            "label": "WEBTOON",
        }
    if "영상" in content_type or provider == "youtube":
        return {
            "start": "#171717",
            "mid": "#6d1117",
            "end": "#ff6b6b",
            "accent": "#ffe0e0",
            "label": "VIDEO",
        }
    if "시리즈" in content_type:
        return {
            "start": "#0f172a",
            "mid": "#205375",
            "end": "#8cc7df",
            "accent": "#dff6ff",
            "label": "SERIES",
        }
    return {
        "start": "#221b14",
        "mid": "#8c6239",
        "end": "#f0d7a1",
        "accent": "#fff2d6",
        "label": "FEATURE",
    }


def _wrap_poster_title(title, limit=14, lines=3):
    words = title.split()
    if not words:
        return [title[:limit]]
    if len(words) == 1 and len(title) > limit:
        sliced = [title[index:index + limit] for index in range(0, len(title), limit)]
        if len(sliced) > lines:
            sliced = sliced[:lines]
            sliced[-1] = f"{sliced[-1][: max(0, limit - 1)]}…"
        return sliced

    wrapped = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > limit:
            wrapped.append(current)
            current = word
        else:
            current = candidate
    if current:
        wrapped.append(current)

    if len(wrapped) <= lines:
        return wrapped

    visible = wrapped[:lines]
    visible[-1] = f"{visible[-1][: max(0, limit - 1)]}…"
    return visible


def _build_svg_poster(item):
    palette = _visual_palette(item)
    title_lines = _wrap_poster_title(item["name"])
    provider_text = html.escape((item.get("provider") or "").upper()[:18])
    type_text = html.escape((item.get("content_type") or "").upper()[:16])
    accent = palette["accent"]
    genres = [genre.lower() for genre in item.get("genres", [])]
    provider = (item.get("provider") or "").lower()
    content_type = (item.get("content_type") or "").lower()

    title_nodes = []
    start_y = 152
    for index, line in enumerate(title_lines[:3]):
        safe_line = html.escape(line)
        y = start_y + (index * 22)
        title_nodes.append(
            f"<text x='22' y='{y}' fill='white' font-size='20' font-family='Arial, sans-serif' font-weight='700'>{safe_line}</text>"
        )

    scene_elements = [
        "<rect x='22' y='70' width='276' height='238' rx='24' fill='rgba(10,10,10,0.18)' stroke='rgba(255,255,255,0.22)'/>"
    ]
    if "웹툰" in content_type:
        scene_elements.extend(
            [
                "<rect x='38' y='92' width='112' height='150' rx='18' fill='rgba(255,255,255,0.16)'/>",
                "<rect x='168' y='92' width='112' height='92' rx='18' fill='rgba(255,255,255,0.11)'/>",
                "<rect x='168' y='198' width='112' height='44' rx='18' fill='rgba(255,255,255,0.18)'/>",
                "<path d='M63 210 C72 168, 122 148, 136 106' fill='none' stroke='rgba(255,255,255,0.34)' stroke-width='7' stroke-linecap='round'/>",
                "<circle cx='228' cy='132' r='20' fill='rgba(255,255,255,0.22)'/>",
            ]
        )
    elif provider == "youtube" or "영상" in content_type:
        scene_elements.extend(
            [
                "<rect x='48' y='104' width='224' height='136' rx='22' fill='rgba(255,255,255,0.12)' stroke='rgba(255,255,255,0.18)'/>",
                "<circle cx='160' cy='172' r='42' fill='rgba(255,255,255,0.20)'/>",
                "<path d='M145 148 L188 172 L145 196 Z' fill='rgba(255,255,255,0.88)'/>",
                "<rect x='64' y='258' width='192' height='10' rx='5' fill='rgba(255,255,255,0.18)'/>",
            ]
        )
    elif any(genre in genres for genre in ["액션", "스릴러", "범죄"]):
        scene_elements.extend(
            [
                "<path d='M36 274 L92 214 L132 248 L186 160 L252 248 L284 196 L284 308 L36 308 Z' fill='rgba(255,255,255,0.16)'/>",
                "<path d='M84 110 L116 142 L84 174' fill='none' stroke='rgba(255,255,255,0.28)' stroke-width='10' stroke-linecap='round' stroke-linejoin='round'/>",
                "<path d='M236 104 L260 132 L236 160' fill='none' stroke='rgba(255,255,255,0.2)' stroke-width='8' stroke-linecap='round' stroke-linejoin='round'/>",
            ]
        )
    elif any(genre in genres for genre in ["판타지", "sf", "모험"]):
        scene_elements.extend(
            [
                "<circle cx='88' cy='138' r='26' fill='rgba(255,255,255,0.24)'/>",
                "<path d='M56 258 C104 188, 148 164, 216 188 C246 198, 266 222, 286 256 L286 308 L36 308 Z' fill='rgba(255,255,255,0.14)'/>",
                "<path d='M140 112 L154 140 L184 144 L162 166 L168 196 L140 182 L112 196 L118 166 L96 144 L126 140 Z' fill='rgba(255,255,255,0.28)'/>",
            ]
        )
    else:
        scene_elements.extend(
            [
                "<path d='M48 284 L92 214 L132 248 L186 160 L252 248 L280 206 L280 310 L48 310 Z' fill='rgba(255,255,255,0.18)'/>",
                "<circle cx='94' cy='144' r='24' fill='rgba(255,255,255,0.18)'/>",
            ]
        )

    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 320 420'>"
        "<defs>"
        f"<linearGradient id='poster-base' x1='0' y1='0' x2='1' y2='1'><stop offset='0%' stop-color='{palette['start']}'/>"
        f"<stop offset='52%' stop-color='{palette['mid']}'/><stop offset='100%' stop-color='{palette['end']}'/></linearGradient>"
        f"<linearGradient id='poster-bg' x1='0' y1='0' x2='1' y2='1'><stop offset='0%' stop-color='{accent}' stop-opacity='0.15'/>"
        "<stop offset='100%' stop-color='#ffffff' stop-opacity='0'/></linearGradient>"
        "</defs>"
        "<rect width='320' height='420' rx='30' fill='url(#poster-base)'/>"
        "<circle cx='266' cy='76' r='92' fill='url(#poster-bg)' opacity='0.9'/>"
        "<rect x='22' y='24' width='124' height='30' rx='15' fill='rgba(255,255,255,0.16)'/>"
        f"<text x='36' y='44' fill='{accent}' font-size='14' font-family='Arial, sans-serif' font-weight='700'>{palette['label']}</text>"
        f"{''.join(scene_elements)}"
        f"{''.join(title_nodes)}"
        f"<text x='22' y='364' fill='{accent}' font-size='13' font-family='Arial, sans-serif'>{provider_text}</text>"
        f"<text x='22' y='389' fill='rgba(255,255,255,0.85)' font-size='15' font-family='Arial, sans-serif'>{type_text}</text>"
        "</svg>"
    )
    return f"data:image/svg+xml;charset=UTF-8,{quote(svg)}"


def _decorate_content_item(item):
    decorated = dict(item)
    poster_url = decorated.get("image_url")
    external_url = decorated.get("external_url") or decorated.get("source_url")

    if not poster_url and decorated.get("content_type") == "웹툰":
        poster_url = get_wikipedia_webtoon_image(decorated["name"], force_refresh=False)
    if (
        not poster_url
        and decorated.get("content_type") == "영화"
        and (decorated.get("source") == "netflix_tudum" or (decorated.get("provider") or "").lower() == "netflix")
    ):
        poster_url = get_tmdb_movie_poster(decorated["name"], force_refresh=False)
    if (decorated.get("provider") or "").lower() == "youtube":
        external_url = external_url or f"https://www.youtube.com/results?search_query={quote(decorated['name'])}"

    decorated["image_url"] = poster_url or _build_svg_poster(decorated)
    decorated["image_alt"] = decorated.get("image_alt") or f"{decorated['name']} 포스터"
    decorated["external_url"] = external_url
    return decorated


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


def _last_week_target_date():
    return (datetime.utcnow() - timedelta(days=7)).strftime("%Y%m%d")


def _parse_json_url(url):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _tmdb_genres(genre_ids):
    genres = [TMDB_GENRE_MAP.get(genre_id) for genre_id in genre_ids or [] if TMDB_GENRE_MAP.get(genre_id)]
    return genres or ["드라마"]


def _moods_from_genres(genres):
    lowered = {genre.lower() for genre in genres}
    moods = []
    if lowered & {"액션", "스릴러", "범죄"}:
        moods.extend(["focus", "reward", "dark"])
    if lowered & {"코미디", "애니메이션", "가족"}:
        moods.extend(["light", "comfort", "refresh"])
    if lowered & {"판타지", "sf", "모험"}:
        moods.extend(["adventure", "focus", "reward"])
    if lowered & {"로맨스", "드라마"}:
        moods.extend(["comfort", "depth", "light"])
    if not moods:
        moods.extend(["focus", "comfort"])
    ordered = []
    for mood in moods:
        if mood not in ordered:
            ordered.append(mood)
    return ordered[:3]


def _tmdb_item_description(title, genres, overview, content_type):
    if overview:
        return overview.strip()
    genre_text = ", ".join(genres[:2])
    if content_type == "시리즈":
        return f"{genre_text} 결을 중심으로 지금 화제가 되는 시리즈입니다."
    return f"{genre_text} 분위기를 좋아할 때 보기 좋은 화제의 영화입니다."


def _build_kobis_item(row):
    title = row.get("movieNm", "").strip()
    if not title:
        return None
    poster_url = get_tmdb_movie_poster(title, force_refresh=False)
    genres = ["드라마", "영화"]
    lower = title.lower()
    if any(keyword in lower for keyword in ["듄", "dune", "godzilla", "kong"]):
        genres = ["SF", "모험", "액션"]
    elif any(keyword in lower for keyword in ["파묘", "존", "wick", "crime"]):
        genres = ["스릴러", "미스터리", "드라마"]
    elif any(keyword in lower for keyword in ["웡카", "애니", "moana"]):
        genres = ["가족", "판타지", "코미디"]

    rank = int(row.get("rank") or 10)
    audience_acc = int((row.get("audiAcc") or "0").replace(",", "") or 0)
    return {
        "id": f"kobis:weekly:{_slugify(title)}",
        "name": title,
        "description": f"국내 주간 박스오피스에서 강하게 반응한 작품입니다. 누적 관객 {audience_acc:,}명.",
        "genres": genres,
        "platforms": ["영화"],
        "provider": "KOBIS",
        "content_type": "영화",
        "moods": _moods_from_genres(genres),
        "trend_keywords": [title, "박스오피스", "KOBIS", "주간 흥행"],
        "duration_label": "극장 화제작",
        "freshness_boost": max(3, 12 - rank),
        "source": "kobis_weekly",
        "image_url": poster_url,
        "source_url": KOBIS_WEEKLY_URL.format(
            api_key=current_app.config["KOBIS_API_KEY"],
            target_date=_last_week_target_date(),
        ),
        "stats": {
            "rank": rank,
            "audience_acc": audience_acc,
            "open_date": row.get("openDt"),
        },
    }


def _build_tmdb_item(source, row):
    title = (row.get("title") or row.get("name") or "").strip()
    if not title:
        return None
    genres = _tmdb_genres(row.get("genre_ids"))
    poster_path = row.get("poster_path")
    poster_url = f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else None
    content_type = source["content_type"]
    release_label = row.get("release_date") or row.get("first_air_date") or ""
    score = row.get("vote_average") or 0
    popularity = int(row.get("popularity") or 0)
    return {
        "id": f"{source['cache_key']}:{row.get('id')}",
        "name": title,
        "description": _tmdb_item_description(title, genres, row.get("overview"), content_type),
        "genres": genres,
        "platforms": [source["platform"]],
        "provider": source["provider"],
        "content_type": content_type,
        "moods": _moods_from_genres(genres),
        "trend_keywords": [title, "TMDB", "화제작", "추천"],
        "duration_label": "TMDB 인기작",
        "freshness_boost": 5,
        "source": "tmdb_trending",
        "image_url": poster_url,
        "source_url": f"https://www.themoviedb.org/{'movie' if content_type == '영화' else 'tv'}/{row.get('id')}",
        "stats": {
            "vote_average": score,
            "popularity": popularity,
            "release_label": release_label,
        },
    }


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


def refresh_kobis_cache(force=False):
    collection = get_collection("content_source_cache")
    now = datetime.utcnow()
    stale_cutoff = now - timedelta(hours=12)
    source = KOBIS_WEEKLY_SOURCE
    cached = collection.find_one({"cache_key": source["cache_key"]})
    if cached and cached.get("generated_at") and cached["generated_at"] > stale_cutoff and not force:
        return cached

    target_date = _last_week_target_date()
    source_url = KOBIS_WEEKLY_URL.format(
        api_key=current_app.config["KOBIS_API_KEY"],
        target_date=target_date,
    )

    try:
        request = Request(source_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=15) as response:
            root = html.unescape(response.read().decode("utf-8", "ignore"))
        row_matches = re.findall(
            r"<weeklyBoxOffice>.*?<rank>(.*?)</rank>.*?<movieNm>(.*?)</movieNm>.*?<openDt>(.*?)</openDt>.*?<audiAcc>(.*?)</audiAcc>.*?</weeklyBoxOffice>",
            root,
            re.DOTALL,
        )
        rows = [
            {"rank": rank.strip(), "movieNm": name.strip(), "openDt": open_dt.strip(), "audiAcc": audi_acc.strip()}
            for rank, name, open_dt, audi_acc in row_matches[:10]
        ]
        if not rows:
            raise ValueError("No KOBIS rows parsed")
    except Exception:
        rows = KOBIS_FALLBACK_ROWS

    items = [item for item in (_build_kobis_item(row) for row in rows) if item]
    payload = {
        "cache_key": source["cache_key"],
        "source_url": source_url,
        "generated_at": now,
        "target_date": target_date,
        "items": items,
    }
    collection.update_one({"cache_key": source["cache_key"]}, {"$set": payload}, upsert=True)
    return payload


def refresh_tmdb_cache(force=False):
    collection = get_collection("content_source_cache")
    now = datetime.utcnow()
    stale_cutoff = now - timedelta(hours=12)
    refreshed = {}

    for source in TMDB_SOURCES:
        cached = collection.find_one({"cache_key": source["cache_key"]})
        if cached and cached.get("generated_at") and cached["generated_at"] > stale_cutoff and not force:
            refreshed[source["cache_key"]] = cached
            continue

        api_key = current_app.config["TMDB_API_KEY"]
        source_url = source["url_template"].format(api_key=api_key)
        try:
            payload_json = _parse_json_url(source_url)
            rows = payload_json.get("results", [])[:10]
            if not rows:
                raise ValueError("No TMDB rows parsed")
        except Exception:
            rows = TMDB_FALLBACK_RESULTS[source["cache_key"]]

        items = [item for item in (_build_tmdb_item(source, row) for row in rows) if item]
        payload = {
            "cache_key": source["cache_key"],
            "source_url": source_url,
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
            items.extend(_decorate_content_item(item) for item in payload.get("items", []))
    return items


def get_kobis_content(force_refresh=False):
    payload = refresh_kobis_cache(force=force_refresh)
    return [_decorate_content_item(item) for item in payload.get("items", [])]


def get_tmdb_content(force_refresh=False):
    cached_map = refresh_tmdb_cache(force=force_refresh)
    items = []
    for source in TMDB_SOURCES:
        payload = cached_map.get(source["cache_key"])
        if payload:
            items.extend(_decorate_content_item(item) for item in payload.get("items", []))
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
    kobis_items = get_kobis_content(force_refresh=force_refresh)
    tmdb_items = get_tmdb_content(force_refresh=force_refresh)
    local_items = [_decorate_content_item(item) for item in LOCAL_CONTENT_LIBRARY]
    return local_items + netflix_items + kobis_items + tmdb_items


def is_searchable_content_item(item):
    provider = (item.get("provider") or "").strip().lower()
    content_type = (item.get("content_type") or "").strip().lower()
    platforms = {
        CONTENT_PLATFORM_ALIASES.get(platform, platform).strip().lower()
        for platform in item.get("platforms", [])
        if platform
    }

    if provider in SEARCHABLE_CONTENT_PROVIDER_BLOCKLIST:
        return False
    if content_type in SEARCHABLE_CONTENT_TYPE_BLOCKLIST:
        return False
    if platforms & SEARCHABLE_CONTENT_PLATFORM_BLOCKLIST:
        return False
    return True


def _ranked_option_list(counts, preferred_order=None):
    preferred_order = preferred_order or []
    ordered = []
    seen = set()

    for label in preferred_order:
        if label in counts:
            ordered.append(label)
            seen.add(label)

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    for label, _count in ranked:
        if label not in seen:
            ordered.append(label)
            seen.add(label)
    return ordered


def get_searchable_content_options(force_refresh=False):
    genre_counts = {}
    platform_counts = {}

    for item in get_content_inventory(force_refresh=force_refresh):
        if not is_searchable_content_item(item):
            continue

        for genre in item.get("genres", []):
            if genre:
                genre_counts[genre] = genre_counts.get(genre, 0) + 1

        for platform in item.get("platforms", []):
            normalized = CONTENT_PLATFORM_ALIASES.get(platform, platform)
            if normalized and normalized not in {"웹툰", "유튜브"}:
                platform_counts[normalized] = platform_counts.get(normalized, 0) + 1

    return {
        "genres": _ranked_option_list(genre_counts),
        "platforms": _ranked_option_list(platform_counts, preferred_order=["넷플릭스", "영화", "시리즈"]),
    }


def _normalize_selected_values(values, options, aliases=None):
    aliases = aliases or {}
    allowed = set(options or [])
    normalized_values = []
    seen = set()

    for value in values or []:
        normalized = aliases.get(value, value)
        if normalized in allowed and normalized not in seen:
            normalized_values.append(normalized)
            seen.add(normalized)
    return normalized_values


def normalize_searchable_content_preferences(genres=None, platforms=None, options=None, force_refresh=False):
    options = options or get_searchable_content_options(force_refresh=force_refresh)
    return {
        "genres": _normalize_selected_values(genres, options["genres"]),
        "platforms": _normalize_selected_values(platforms, options["platforms"], aliases=CONTENT_PLATFORM_ALIASES),
    }


def find_content_item(content_id, force_refresh=False):
    for item in get_content_inventory(force_refresh=force_refresh):
        if item["id"] == content_id:
            return item
    return None
