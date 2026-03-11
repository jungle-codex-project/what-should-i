# WhatShouldI

WhatShouldI는 사용자의 취향, 현재 상황, 날씨, 트렌드를 함께 반영해서 하루의 선택을 추천하는 Flask 기반 라이프스타일 대시보드 MVP입니다. 음식, 패션, 콘텐츠, 활동 추천이 각각 따로 노는 대신 하나의 브랜드 흐름으로 연결되도록 구성했습니다.

## 프로젝트 소개

- 서비스명: `WhatShouldI`
- 목표: "오늘 뭐 먹지?", "오늘 뭐 입지?", "오늘 뭐 보지?", "오늘 뭐 하지?"를 한 번에 보여주는 데모 가능한 웹 서비스 MVP
- 구현 스택: Flask, Jinja2, Bootstrap 5, jQuery/AJAX, MongoDB
- 추천 방식: 규칙 기반 + 점수 기반 추천 엔진
- 배포 고려: 환경변수 기반 설정과 `gunicorn` 지원으로 AWS EC2/Elastic Beanstalk 형태에 바로 올릴 수 있는 구조

## 주요 기능

1. 회원가입 / 로그인 / 로그아웃
2. 메인 대시보드에서 음식 / 패션 / 콘텐츠 / 활동 4종 추천 요약
3. 음식 추천
   - 선호 음식, 못 먹는 음식, 냉장고 재료 입력
   - 기분, 시간대, 매운맛 여부 반영
4. 패션 추천
   - 날씨 / 온도 / 스타일 / 컬러 / 퍼스널 컬러 반영
5. 콘텐츠 추천
   - 웹툰 / 영화 / 유튜브 / 드라마 기반 추천
   - 장르 취향 및 현재 무드 반영
   - Netflix 공식 Tudum Top 10 기반 최신 인기작 자동 병합
   - 좋아요 / 싫어요 피드백 학습
   - `SignalMix v2` 다중 시그널 랭킹 엔진 적용
6. 활동 추천
   - 실내외, 에너지 상태, 혼자/함께, 예산 반영
7. 트렌드 기능
   - `trend_cache` 컬렉션 기반 샘플 데이터 제공
   - 이후 Google Trends 데이터로 교체 가능한 구조
8. VS 퀴즈 기능
   - AJAX 투표
   - baseline 더미 데이터 + 실제 로그 합산 결과 표시
9. MBTI + 심리형 설문 분석
   - `/survey` 페이지에서 MBTI와 고차원 설문 문항 저장
   - 내면 성향을 8개 축으로 분석해 자동 추천 점수에 반영
10. 사용자 프로필 저장
   - 음식 / 패션 / 콘텐츠 / 활동 취향 저장
11. 추천 히스토리
   - 최근 추천 결과 저장
   - 최근 5개 대시보드 노출 및 전체 히스토리 조회

## 실행 방법

### 1. 의존성 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
```

필수 변수:

- `SECRET_KEY`: 세션 암호화 키
- `MONGO_URI`: MongoDB 연결 주소
- `MONGO_DB_NAME`: 사용할 DB 이름
- `USE_MOCK_ON_FAILURE`: MongoDB 연결 실패 시 `mongomock` fallback 사용 여부

### 3. MongoDB 실행 / 연결

로컬 MongoDB 사용 예시:

```bash
brew services start mongodb-community
```

또는 Docker 사용 예시:

```bash
docker run -d --name whatshouldi-mongo -p 27017:27017 mongo:7
```

`.env` 예시:

```env
MONGO_URI=mongodb://localhost:27017/
MONGO_DB_NAME=whatshouldi
```

참고:

- 로컬 MongoDB가 준비되지 않았더라도 `USE_MOCK_ON_FAILURE=true` 상태면 앱은 `mongomock`으로 데모 실행됩니다.
- 실제 과제 제출/배포 시에는 MongoDB를 연결해서 사용하는 것을 권장합니다.

### 4. 시드 데이터 넣기

기본 트렌드/퀴즈 데이터:

```bash
python seed/sample_seed.py
```

데모 계정까지 함께 생성:

```bash
python seed/sample_seed.py --with-demo-user
```

데모 계정:

- Email: `demo@whatshouldi.local`
- Password: `demo1234`

### 5. 서버 실행

```bash
python app.py
```

브라우저에서 [http://localhost:5000](http://localhost:5000) 접속

배포용 실행 예시:

```bash
gunicorn app:app
```

## 환경변수 설명

| 변수 | 설명 | 기본값 |
| --- | --- | --- |
| `SECRET_KEY` | Flask 세션 키 | `whatshouldi-dev-secret` |
| `FLASK_DEBUG` | 디버그 모드 | `true` |
| `FLASK_HOST` | 바인드 호스트 | `0.0.0.0` |
| `FLASK_PORT` | 바인드 포트 | `5000` |
| `MONGO_URI` | MongoDB URI | `mongodb://localhost:27017/` |
| `MONGO_DB_NAME` | DB 이름 | `whatshouldi` |
| `USE_MOCK_ON_FAILURE` | Mongo 실패 시 mock DB fallback | `true` |
| `DEFAULT_CITY` | 기본 도시명 | `Seoul` |
| `DEFAULT_REGION` | 트렌드 지역값 | `KR` |

## MongoDB 컬렉션 구조

- `users`
  - `name`, `email`, `password_hash`, `created_at`
- `profiles`
  - `user_id`
  - `food`, `fashion`, `content`, `activity`
  - `created_at`, `updated_at`
- `recommendation_history`
  - `user_id`, `category`, `request_snapshot`
  - `recommendation`, `alternatives`, `context`, `day_key`, `created_at`
- `trend_cache`
  - `source`, `region`, `generated_at`, `keywords`
- `quiz_logs`
  - `quiz_id`, `choice`, `user_id`, `left_label`, `right_label`, `created_at`

## 폴더 구조

```text
whatshouldi/
├── app.py
├── config.py
├── requirements.txt
├── .env.example
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
│   ├── history.py
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
└── seed/
    └── sample_seed.py
```

## 추천 로직 설명

추천 점수는 아래 요소를 합산하는 방식으로 동작합니다.

```text
추천 점수 = 취향 점수 + 상황 점수 + 트렌드 가중치 - 최근 중복 패널티
```

예시 반영 요소:

- 음식: 선호 태그, 기분, 시간대, 매운맛, 냉장고 재료
- 패션: 온도, 날씨, 스타일 취향, 컬러 취향, 퍼스널 컬러
- 콘텐츠: 장르, 플랫폼, 현재 무드
- 활동: 실내외, 에너지, 사회성, 예산, 날씨

## 데모 시나리오

1. 회원가입 또는 데모 계정으로 로그인
2. `/profile`에서 취향 입력
3. `/dashboard`에서 오늘의 4가지 추천 확인
4. `/food`, `/fashion`, `/content`, `/activity`에서 각각 조건을 바꿔 다시 추천
5. `/survey`에서 MBTI와 심리 설문 저장
6. `/trends`에서 트렌드 키워드 구조 확인
7. `/quiz`에서 VS 투표 후 결과 확인
8. `/history`에서 추천 저장 내역 확인

## 아직 mock 처리된 부분

- 외부 날씨 API 대신 계절 기반 데모 날씨 사용
- Google Trends 실시간 API 대신 `trend_cache` 샘플 데이터 사용
- 실제 AI 비전 / 퍼스널 컬러 분석 대신 사용자 선택형 입력 사용
- 추천 데이터셋은 MVP용 정적 카탈로그 기반
- 심리 설문은 자체 정의 문항 기반이며 임상용 심리검사는 아님
- Netflix 데이터는 공식 Tudum Top 10 페이지를 주기적으로 읽고 캐시하는 방식

## 향후 개선 방향

1. Google Trends, Open-Meteo, OTT/콘텐츠 API 실제 연동
2. 사용자 행동 로그 기반 개인화 점수 보정
3. 추천 결과 즐겨찾기 / 공유 기능 추가
4. 관리자용 트렌드 캐시 업데이트 페이지 추가
5. AWS 배포 시 S3 정적 자산 분리와 Gunicorn + Nginx 구성
6. MongoDB Atlas 연동과 운영용 로그/모니터링 추가

## 추가 문서

- `AGENTS.md`: 에이전트 작업 지침
- `docs/CONVENTIONS.md`: 팀 Git/브랜치/커밋 컨벤션
- `docs/PROJECT_OVERVIEW.md`: 기존 저장소 개요 문서
