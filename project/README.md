# AI Academic Document Validator

학사 결석 증빙 문서를 OCR과 규칙 검증으로 자동 판별하는 최소 기능 제품(MVP)입니다.

## 1. 프로젝트 구조

```text
project/
├── app/
│   ├── __init__.py
│   ├── document_parser.py
│   ├── routes.py
│   ├── services.py
│   └── utils.py
├── db/
│   ├── __init__.py
│   └── mongo.py
├── ocr/
│   ├── __init__.py
│   └── extractor.py
├── rules/
│   ├── __init__.py
│   ├── engine.py
│   └── rules.json
├── sample_docs/
│   ├── sample_medical_receipt.txt
│   ├── sample_medical_certificate.pdf
│   └── sample_medical_certificate.txt
├── static/
│   ├── css/
│   │   └── styles.css
│   └── js/
│       └── app.js
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── detail.html
│   └── index.html
├── uploads/
├── wsgi.py
├── .env.example
├── Dockerfile
├── README.md
├── app.py
├── config.py
├── docker-compose.yml
└── requirements.txt
```

## 2. 핵심 기능

- 학생 문서 업로드: PDF, PNG, JPG, JPEG
- OCR 추출: 전처리 + Tesseract 다중 영역 OCR
- 문서 파싱: OpenAI API 또는 휴리스틱 기반 구조화
- 의료 영수증 / 결제내역서 인식: `medical_receipt` 유형 지원
- 규칙 엔진: 날짜, 기관명, 기간 기준 자동 검증
- 관리자 대시보드: 업로드 목록, 상태, 상세 결과 조회
- 개인정보 보호: `AUTO_DELETE_ORIGINAL=True` 시 원본 파일과 OCR 원문 미저장
- 로컬 실행 및 AWS 배포 준비: Flask + Gunicorn + Docker 구성

## 3. 문서 처리 흐름

1. 학생이 문서를 업로드합니다.
2. 서버가 파일을 저장합니다.
3. OCR 모듈이 문서 보정, 표선 제거, 영역 분할 후 텍스트를 추출합니다.
4. LLM 또는 휴리스틱 파서가 구조화 데이터를 만듭니다.
5. 규칙 엔진이 자동 승인 여부를 판단합니다.
6. 관리자 대시보드에서 결과를 검토합니다.

## 4. 구조화 데이터 예시

```json
{
  "name": "김정글",
  "document_type": "medical_receipt",
  "organization": "정글대학교병원",
  "issue_date": "2026년 03월 10일",
  "valid_period": "2026년 03월 10일"
}
```

## 5. 규칙 엔진

기본 규칙은 [`rules/rules.json`](./rules/rules.json)에 있습니다.

- 발급일이 있어야 함
- 기관명이 있어야 함
- 발급일이 최근 `90일` 이내여야 함
- 유효기간이 `14일`을 넘으면 자동 승인 불가
- 신뢰도가 `0.70` 이상이어야 자동 승인

의료 영수증 계열 문서는 `issue_date`를 당일 `valid_period`로 간주해 처리합니다.

## 6. 사전 준비

### macOS

```bash
brew install tesseract tesseract-lang poppler mongodb-community
```

### Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-kor poppler-utils mongodb
```

MongoDB를 따로 설치하지 않으면 앱은 메모리 모드로 동작합니다. 이 경우 재시작 시 데이터가 유지되지 않습니다.

## 7. 설치 방법

```bash
cd project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`에서 필요한 값을 조정합니다.

- `OPENAI_API_KEY`: 설정하면 LLM 파싱 사용
- `AUTO_DELETE_ORIGINAL=True`: 원본 파일과 OCR 원문을 저장하지 않음
- `MONGO_URI`, `MONGO_DB_NAME`: MongoDB 연결 정보

## 8. 로컬 실행 방법

### 일반 실행

```bash
cd project
source .venv/bin/activate
python app.py
```

브라우저에서 `http://127.0.0.1:5000` 접속

### Docker 실행

```bash
cd project
docker compose up --build
```

브라우저에서 `http://127.0.0.1:5000` 접속

## 9. 관리자 화면

- `/`: 학생 업로드 페이지
- `/dashboard`: 관리자 대시보드
- `/documents/<id>`: 문서 상세 결과

상세 페이지에서 아래 정보를 볼 수 있습니다.

- 원본 문서 미리보기
- OCR 추출 텍스트
- 구조화 데이터
- 자동 승인 상태 및 사유

단, `AUTO_DELETE_ORIGINAL=True`이면 원본 문서와 OCR 텍스트는 저장되지 않습니다.

## 10. 샘플 테스트 문서

샘플 텍스트는 [`sample_docs/sample_medical_certificate.txt`](./sample_docs/sample_medical_certificate.txt)와
[`sample_docs/sample_medical_receipt.txt`](./sample_docs/sample_medical_receipt.txt)에 있습니다.
샘플 PDF는 `sample_docs/sample_medical_certificate.pdf`로 제공합니다.

테스트 방법:

1. 텍스트를 복사해 워드/메모장에 붙여 넣습니다.
2. PDF로 저장하거나 캡처 이미지로 만듭니다.
3. 업로드 페이지에서 업로드합니다.

## 11. AWS 배포 포인트

- Flask 앱은 `gunicorn`으로 실행 가능
- Dockerfile 포함
- MongoDB는 Amazon DocumentDB 또는 MongoDB Atlas로 대체 가능
- 업로드 파일은 추후 S3로 분리 가능
- OCR/LLM 호출은 비동기 큐로 확장 가능

## 12. 향후 개선 아이디어

- 학사 시스템 결석 신청 정보와 유효기간 직접 대조
- 관리자 승인 로그와 이력 관리
- 다중 페이지 PDF 상태 표시
- 사용자 인증 및 역할 분리
- S3 저장 및 Lambda 기반 OCR 분리
