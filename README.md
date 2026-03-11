# WhatShouldIDo

WhatShouldIDo는 취향, 현재 상황, 날씨, 트렌드를 함께 반영해 하루의 선택을 추천하는 Flask 기반 라이프스타일 대시보드입니다. 음식, 패션, 콘텐츠, 활동 추천을 각각 따로 분리하지 않고 하나의 사용자 프로필과 행동 피드백 위에서 연결합니다.

## 현재 구현 범위

- 음식 추천
- 패션 추천
- 콘텐츠 추천
  - 현재 사용자 노출 기준 스코프: 영화, 시리즈
  - 웹툰은 현재 추천 범위에서 제외
- 활동 추천
- MBTI + 심리 설문 기반 성향 보정
- 추천 히스토리 저장
- 트렌드 보드 / VS 퀴즈

## 기술 스택

- Flask
- Jinja2
- Bootstrap 5
- jQuery / AJAX
- MongoDB
- Gunicorn

## 주요 기능

### 1. 계정 및 프로필

- 회원가입 / 로그인 / 로그아웃
- 음식 / 패션 / 콘텐츠 / 활동 취향 저장
- MBTI와 심리 설문 결과 저장

### 2. 콘텐츠 추천

- Netflix Tudum South Korea Movies Top 10 반영
- KOBIS 주간 박스오피스 반영
- TMDB 주간 트렌딩 영화 / 시리즈 반영
- 좋아요 / 싫어요 피드백 누적 학습
- 현재 검색 가능한 데이터만 기준으로 장르 / 플랫폼 선택
- 웹툰 제외

### 3. 대시보드와 부가 기능

- 메인 대시보드에서 4개 카테고리 추천 요약
- 최근 추천 히스토리 조회
- 트렌드 키워드 보드
- VS 퀴즈 투표

## 프로젝트 구조

```text
lifestyle-app/
├── app.py
├── config.py
├── render.yaml
├── requirements.txt
├── db/
│   └── mongo.py
├── routes/
│   ├── auth.py
│   ├── main.py
│   ├── profile.py
│   └── recommendations.py
├── services/
│   ├── account.py
│   ├── catalog.py
│   ├── content_feedback.py
│   ├── content_sources.py
│   ├── history.py
│   ├── movie_images.py
│   ├── personality.py
│   ├── profile_service.py
│   ├── recommender.py
│   ├── trends.py
│   └── weather.py
├── static/
│   ├── css/style.css
│   └── js/app.js
├── templates/
│   ├── auth/
│   ├── components/
│   └── recommendations/
├── seed/
│   └── sample_seed.py
└── docs/
```

## 실행 방법

### 1. 가상환경 및 의존성 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
```

기본적으로 아래 값을 사용합니다.

```env
SECRET_KEY=whatshouldi-dev-secret
FLASK_DEBUG=true
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
MONGO_URI=mongodb://localhost:27017/
MONGO_DB_NAME=whatshouldi
USE_MOCK_ON_FAILURE=true
DEFAULT_CITY=Seoul
DEFAULT_REGION=KR
KOBIS_API_KEY=...
TMDB_API_KEY=...
```

### 3. MongoDB 준비

로컬 MongoDB 예시:

```bash
brew services start mongodb-community
```

Docker 예시:

```bash
docker run -d --name whatshouldi-mongo -p 27017:27017 mongo:7
```

MongoDB가 없어도 `USE_MOCK_ON_FAILURE=true`면 데모용 mock DB로 실행됩니다.

### 4. 시드 데이터

```bash
python seed/sample_seed.py
```

데모 계정까지 만들려면:

```bash
python seed/sample_seed.py --with-demo-user
```

데모 계정:

- Email: `demo@whatshouldi.local`
- Password: `demo1234`

### 5. 앱 실행

```bash
python app.py
```

브라우저에서 `http://localhost:5000` 접속

배포용 실행 예시:

```bash
gunicorn app:app
```

## 환경변수

| 변수 | 설명 | 기본값 |
| --- | --- | --- |
| `SECRET_KEY` | Flask 세션 키 | `whatshouldi-dev-secret` |
| `FLASK_DEBUG` | 디버그 모드 | `true` |
| `FLASK_HOST` | 바인드 주소 | `0.0.0.0` |
| `FLASK_PORT` | 포트 | `5000` |
| `MONGO_URI` | MongoDB URI | `mongodb://localhost:27017/` |
| `MONGO_DB_NAME` | MongoDB DB 이름 | `whatshouldi` |
| `USE_MOCK_ON_FAILURE` | Mongo 연결 실패 시 mock DB 사용 | `true` |
| `DEFAULT_CITY` | 기본 도시 | `Seoul` |
| `DEFAULT_REGION` | 기본 지역 코드 | `KR` |
| `KOBIS_API_KEY` | KOBIS API 키 | 코드 기본값 존재 |
| `TMDB_API_KEY` | TMDB API 키 | 코드 기본값 존재 |

## 데이터 저장 구조

- `users`
  - 계정 정보
- `profiles`
  - 카테고리별 취향과 심리 성향
- `recommendation_history`
  - 추천 요청 스냅샷과 결과
- `content_feedback`
  - 콘텐츠 좋아요 / 싫어요 피드백
- `trend_cache`
  - 트렌드 캐시
- `quiz_logs`
  - VS 퀴즈 응답 로그
- `content_source_cache`
  - Netflix / KOBIS / TMDB 캐시

## 추천 방식 요약

- 음식: 취향 + 시간대 + 기분 + 매운맛 선호
- 패션: 날씨 + 온도 + 스타일 + 컬러
- 콘텐츠: 장르 + 플랫폼/형식 + 무드 + 피드백 + 인기 흐름
- 활동: 실내외 + 에너지 + 사회성 + 예산 + 날씨

콘텐츠 추천은 현재 검색 가능한 작품 목록에서만 장르와 플랫폼 옵션을 노출합니다.

## Render 배포

이 저장소에는 Render Blueprint용 [`render.yaml`](/Users/donghyunkim/Documents/jungle_12th/jungle_12_2wk_303_05/lifestyle-app/render.yaml)이 포함되어 있습니다.

기본 절차:

1. 저장소를 GitHub에 push
2. Render에서 Blueprint 배포 생성
3. `SECRET_KEY` 설정
4. 필요하면 `MONGO_URI`, `MONGO_DB_NAME` 설정
5. MongoDB 없이 데모 배포만 할 경우 `USE_MOCK_ON_FAILURE=true` 사용

## 참고 문서

- [`AGENTS.md`](/Users/donghyunkim/Documents/jungle_12th/jungle_12_2wk_303_05/lifestyle-app/AGENTS.md)
- [`docs/CONVENTIONS.md`](/Users/donghyunkim/Documents/jungle_12th/jungle_12_2wk_303_05/lifestyle-app/docs/CONVENTIONS.md)
