# 🌊 Agentic RAG - AI 기반 스마트 배수지 관리 시스템

<div align="center">

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**AI 에이전트 + IoT 센서 + 자동화**를 결합한 차세대 배수지 관리 솔루션

[주요 특징](#-주요-특징) • [빠른 시작](#-빠른-시작) • [시스템 구조](#-시스템-구조) • [사용 방법](#-사용-방법)

</div>

---

## 📖 목차

- [개요](#-개요)
- [주요 특징](#-주요-특징)
- [빠른 시작](#-빠른-시작)
- [시스템 구조](#-시스템-구조)
- [배수지 시스템](#-배수지-시스템)
- [환경 설정](#-환경-설정)
- [사용 방법](#-사용-방법)
- [기술 스택](#-기술-스택)
- [API 및 도구](#-api-및-도구)
- [문제 해결](#-문제-해결)
- [개발 가이드](#-개발-가이드)
- [라이선스](#-라이선스)

---

## 🎯 개요

**Agentic RAG**는 AI 기반 문서 검색(RAG), IoT 수위 센서, 자율 의사결정 시스템을 통합한 차세대 배수지 관리 플랫폼입니다.

### 왜 Agentic RAG인가?

- 🤖 **자율 AI 에이전트**: LM Studio 기반으로 30초마다 자율 판단하여 펌프 자동 제어
- 🌊 **실시간 모니터링**: Arduino 센서로 실시간 수위 데이터 수집 및 분석
- 📚 **지능형 문서 검색**: RAG 기술로 과거 데이터 및 문서에서 인사이트 도출
- 🔧 **완전 자동화**: 위험 상황 감지 시 자동 대응 및 알림

---

## ✨ 주요 특징

### 🤖 자율 AI 에이전트 시스템

```
┌─────────────────────────────────────────┐
│  30초마다 자율 판단 및 제어              │
│  ├─ 가곡 수위 < 40m → 펌프1 자동 ON     │
│  ├─ 가곡 수위 > 80m → 펌프1 자동 OFF    │
│  ├─ 해룡 수위 < 40m → 펌프2 자동 ON     │
│  └─ 해룡 수위 > 80m → 펌프2 자동 OFF    │
└─────────────────────────────────────────┘
```

- **자율 의사결정**: LM Studio 기반 LLM이 현재 상황 분석 후 자동 제어
- **실시간 대응**: 위험 수위 감지 시 즉시 펌프 제어 및 알림
- **학습 능력**: 과거 데이터 기반으로 의사결정 개선
- **통합 로깅**: 모든 의사결정 및 액션 기록

### 🌊 배수지 관리 시스템

| 배수지 | 펌프 | 역할 | 제어 로직 |
|--------|------|------|-----------|
| **가곡** | 펌프1 | 외부 → 가곡 급수 | 수위 < 40m: ON, > 80m: OFF |
| **해룡** | 펌프2 | 가곡 → 해룡 이송 | 수위 < 40m: ON, > 80m: OFF |

- ✅ **실시간 수위 모니터링**: Arduino 초음파 센서 연동
- ✅ **LSTM 예측 모델**: 최대 24시간 수위 예측
- ✅ **자동 펌프 제어**: Arduino 릴레이 제어
- ✅ **위험 알림 시스템**: 임계값 초과 시 자동 알림

### 📚 AI 문서 검색 (RAG)

```
질문: "지난달 수위 변화 추이는?"
  ↓
벡터 검색 (BGE-m3-ko)
  ↓
관련 문서/데이터 검색
  ↓
LLM 분석 및 응답 생성
```

- **벡터 검색**: Hugging Face BGE-m3-ko (1024차원)
- **PostgreSQL + pgvector**: 고성능 벡터 데이터베이스
- **다중 형식 지원**: PDF, TXT, DOCX 자동 처리
- **한글 최적화**: 한국어 임베딩 및 응답 생성

### 🎛️ 웹 대시보드

- 📊 **메인 대시보드**: AI 챗봇 인터페이스
- 💧 **수위 대시보드**: 실시간 수위 그래프 및 차트
- 🤖 **자동화 대시보드**: AI 의사결정 로그 및 제어
- 📁 **문서 관리**: 파일 업로드/다운로드/삭제

---

## 🚀 빠른 시작

### 필수 요구사항

| 항목 | 필수 여부 | 설명 |
|------|-----------|------|
| **Docker Desktop** | ✅ 필수 | 컨테이너 실행 환경 |
| **LM Studio** | ⚠️ 권장 | 로컬 LLM 서버 (없으면 OpenAI API 사용) |
| **Arduino** | ⭐ 선택 | 실제 센서 사용 시 (시뮬레이션 모드 지원) |

### 1️⃣ 설치

```bash
# 저장소 클론
git clone https://github.com/yourusername/agentic_rag.git
cd agentic_rag

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 필요한 설정 입력
```

### 2️⃣ LM Studio 설정 (권장)

1. [LM Studio](https://lmstudio.ai/) 다운로드 및 설치
2. 모델 다운로드 (예: `bartowski/exaone-4.0-1.2b-instruct`)
3. 로컬 서버 시작 (포트: 1234)

```bash
# LM Studio에서
Server → Start Server (포트: 1234)
```

### 3️⃣ Docker 실행

```bash
# Docker 컨테이너 시작
docker compose up -d

# 로그 확인
docker compose logs -f frontend
```

### 4️⃣ 접속 및 초기화

1. 🌐 웹 브라우저에서 **http://localhost:8501** 접속
2. 좌측 사이드바에서 **"🔄 시스템 초기화"** 클릭
3. 초기화 완료 후 사용 시작!

---

## 🏗️ 시스템 구조

### 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     사용자 (웹 브라우저)                     │
│              http://localhost:8501 (Streamlit UI)           │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌──────────────┐  ┌─────────────────┐  ┌──────────────┐
│ 메인 대시보드 │  │  수위 대시보드   │  │자동화 대시보드│
│  (챗봇 UI)   │  │  (실시간 그래프) │  │  (AI 로그)   │
└──────┬───────┘  └────────┬────────┘  └──────┬───────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │    Orchestrator        │
              │  (오케스트레이터)       │
              │  - 쿼리 분석           │
              │  - 도구 선택 및 실행   │
              │  - 응답 생성           │
              └───────────┬────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   도구 시스템 │  │ 자율 AI 에이전트│  │ 데이터베이스 │
│   (9개 도구)  │  │ (30초마다 판단)│  │  PostgreSQL  │
│              │  │              │  │  + pgvector  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │
       └─────────────────┼──────────────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ Arduino 하드웨어 │
                │ - 초음파 센서    │
                │ - 릴레이 모듈    │
                │ - 펌프 제어      │
                └─────────────────┘
```

### 핵심 구성 요소

| 구성 요소 | 기술 스택 | 설명 |
|-----------|-----------|------|
| **Frontend** | Streamlit | 반응형 웹 UI |
| **Backend** | Python 3.12+ | 비동기 처리 |
| **Database** | PostgreSQL 15 + pgvector | 벡터 및 시계열 데이터 |
| **AI Engine** | LM Studio + LSTM | LLM 추론 및 예측 |
| **Hardware** | Arduino Uno | 센서/펌프 제어 |
| **Automation** | Autonomous Agent | 자율 의사결정 |

---

## 💧 배수지 시스템

### 시스템 구성도

```
      [외부 수원]
           │
           ▼
      ┌────────┐
      │ 펌프 1 │ ← AI 에이전트 제어
      └────┬───┘
           │
           ▼
   ┌──────────────────┐
   │  가곡 배수지      │
   │  - 용량: 100m    │
   │  - 임계값: 40-80m│
   │  - 센서: 초음파   │
   └────────┬─────────┘
            │
            ▼
       ┌────────┐
       │ 펌프 2 │ ← AI 에이전트 제어
       └────┬───┘
            │
            ▼
   ┌──────────────────┐
   │  해룡 배수지      │
   │  - 용량: 100m    │
   │  - 임계값: 40-80m│
   │  - 센서: 초음파   │
   └──────────────────┘
```

### 자동 제어 로직

#### 펌프 1 (가곡 배수지 급수)

```python
IF 가곡_수위 < 40m:
    펌프1 ON  # 외부에서 물 공급
ELIF 가곡_수위 > 80m:
    펌프1 OFF # 과충수 방지
ELSE:
    상태 유지 # 정상 범위
```

#### 펌프 2 (해룡 배수지 급수)

```python
IF 해룡_수위 < 40m:
    펌프2 ON  # 가곡에서 물 이송
ELIF 해룡_수위 > 80m:
    펌프2 OFF # 과충수 방지
ELSE:
    상태 유지 # 정상 범위
```

### AI 에이전트 의사결정 프로세스

```
1. 데이터 수집 (매 30초)
   ├─ PostgreSQL에서 최신 수위 데이터 조회
   ├─ 펌프 상태 확인
   └─ 시스템 건강 상태 점검

2. AI 분석
   ├─ LM Studio LLM에 현재 상황 전달
   ├─ 제어 규칙 기반 판단
   └─ 액션 결정 (PUMP_ON/PUMP_OFF/STABLE)

3. 액션 실행
   ├─ Arduino로 펌프 제어 명령 전송
   ├─ PostgreSQL에 상태 업데이트
   └─ 로그 기록

4. 모니터링
   ├─ 자동화 대시보드에서 실시간 확인
   └─ 위험 상황 시 알림 발송
```

---

## ⚙️ 환경 설정

### .env 파일 설정

```env
# ========================================
# LM Studio 설정
# ========================================
LM_STUDIO_BASE_URL=http://host.docker.internal:1234/v1
LM_STUDIO_MODEL_NAME=bartowski/exaone-4.0-1.2b-instruct
LM_STUDIO_API_KEY=lm-studio

# ========================================
# 임베딩 모델 설정
# ========================================
EMBEDDING_BACKEND=HF
EMBEDDING_MODEL_NAME=dragonkue/BGE-m3-ko
EMBEDDING_DEVICE=cpu
HUGGINGFACEHUB_API_TOKEN=your_hf_token_here

# ========================================
# PostgreSQL 데이터베이스
# ========================================
PG_DB_HOST=postgres
PG_DB_PORT=5432
PG_DB_NAME=agentic_rag
PG_DB_USER=postgres
PG_DB_PASSWORD=0000

# ========================================
# 활성화 도구 (쉼표로 구분)
# ========================================
ENABLED_TOOLS=vector_search_tool,list_files_tool,water_level_prediction_tool,arduino_water_sensor_tool,water_level_monitoring_tool,real_time_database_control_tool,advanced_water_analysis_tool,automation_control_tool,smart_water_prediction_tool

# ========================================
# 시스템 설정
# ========================================
DEBUG_MODE=false
LOG_LEVEL=INFO
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
TOP_K_RESULTS=5
MAX_TOKENS=2048
RESPONSE_TEMPERATURE=0.7
```

### 주요 설정 옵션

| 카테고리 | 설정 | 기본값 | 설명 |
|----------|------|--------|------|
| **RAG** | `CHUNK_SIZE` | 1000 | 문서 청크 크기 |
| **RAG** | `CHUNK_OVERLAP` | 200 | 청크 오버랩 크기 |
| **RAG** | `TOP_K_RESULTS` | 5 | 검색 결과 개수 |
| **LLM** | `MAX_TOKENS` | 2048 | 최대 응답 토큰 |
| **LLM** | `RESPONSE_TEMPERATURE` | 0.7 | 응답 생성 온도 (창의성) |
| **시스템** | `DEBUG_MODE` | false | 디버그 모드 |
| **시스템** | `LOG_LEVEL` | INFO | 로그 레벨 |

---

## 💬 사용 방법

### AI 챗봇 사용 예시

#### 1. 문서 검색

```
👤 "지난 분기 보고서에서 매출 관련 내용 찾아줘"
🤖 [RAG 검색 수행 → 관련 문서 찾기 → 요약 제공]

👤 "프로젝트A.pdf 파일에서 핵심 성과 요약해줘"
🤖 [파일 검색 → 내용 분석 → 핵심 성과 요약]
```

#### 2. 수위 모니터링

```
👤 "현재 배수지 수위 알려줘"
🤖 현재 배수지 수위 정보:
   - 가곡: 45.2m (정상)
   - 해룡: 62.8m (정상)

👤 "가곡 배수지 30분 후 수위 예측해줘"
🤖 [LSTM 모델 예측 수행]
   예측 결과: 30분 후 47.8m (±2.3m)
```

#### 3. 펌프 제어

```
👤 "펌프1 켜줘"
🤖 ✅ 펌프1을 켰습니다.
   - 상태: ON
   - 배수지: 가곡
   - 현재 수위: 35.2m

👤 "펌프 상태 확인해줘"
🤖 현재 펌프 상태:
   - 펌프1 (가곡): OFF
   - 펌프2 (해룡): ON
```

#### 4. 자동화 제어

```
👤 "자동화 시작해줘"
🤖 ✅ 통합 자동화 시스템을 시작했습니다.
   - 기본 자동화: 활성
   - AI 자율 에이전트: 활성
   - 모니터링 주기: 30초

👤 "자동화 상태 보여줘"
🤖 현재 자동화 상태:
   - 상태: 🟢 완전 활성
   - 마지막 판단: 1분 전
   - 최근 액션: 펌프2 OFF (해룡 수위 85m 초과)
```

#### 5. 데이터 분석

```
👤 "지난 24시간 수위 변화 그래프 그려줘"
🤖 [24시간 수위 데이터 조회 → 그래프 생성]
   📊 [수위 변화 그래프 표시]

👤 "이번 주 펌프 가동 시간 통계 내줘"
🤖 이번 주 펌프 가동 통계:
   - 펌프1: 42시간 15분
   - 펌프2: 38시간 52분
   - 총 에너지 소비: 약 120kWh
```

---

## 🔧 기술 스택

### Backend

```
Python 3.12+
├── Streamlit         # 웹 UI 프레임워크
├── LangChain         # LLM 오케스트레이션
├── asyncio           # 비동기 처리
├── PostgreSQL        # 데이터베이스
├── pgvector          # 벡터 검색 확장
├── TensorFlow 2.x    # LSTM 모델
└── pySerial          # Arduino 통신
```

### AI/ML

```
LM Studio
├── 로컬 LLM 서버 (포트: 1234)
├── 지원 모델: GGUF 형식
└── OpenAI API 호환

Hugging Face Transformers
├── BGE-m3-ko (임베딩)
└── 1024차원 벡터

LSTM 모델
├── TensorFlow/Keras
└── 시계열 예측
```

### DevOps

```
Docker Compose
├── frontend (Streamlit)
├── postgres (PostgreSQL 15)
└── Multi-container orchestration

Arduino
├── Arduino Uno
├── 초음파 센서 (HC-SR04)
└── 릴레이 모듈 (2채널)
```

---

## 🛠️ API 및 도구

### 도구 시스템 (9개)

| 도구 | 설명 | 주요 기능 |
|------|------|-----------|
| **vector_search_tool** | 벡터 검색 | 문서 유사도 검색 |
| **list_files_tool** | 파일 목록 | 업로드된 파일 조회 |
| **water_level_prediction_tool** | 수위 예측 | LSTM 기반 예측 |
| **arduino_water_sensor_tool** | Arduino 센서 | 실시간 수위 읽기 |
| **water_level_monitoring_tool** | 수위 모니터링 | 히스토리 조회 |
| **real_time_database_control_tool** | DB 제어 | 실시간 데이터 CRUD |
| **advanced_water_analysis_tool** | 수위 분석 | 통계 및 인사이트 |
| **automation_control_tool** | 자동화 제어 | 시작/중지/상태 |
| **smart_water_prediction_tool** | 스마트 예측 | AI 기반 예측 |

### 도구 사용 예시

```python
from tools.arduino_water_sensor_tool import arduino_water_sensor_tool

# 펌프 제어
result = arduino_water_sensor_tool(
    action="pump1_on",
    duration=60  # 60초 동안 작동
)

# 수위 읽기
result = arduino_water_sensor_tool(
    action="read_water_level",
    reservoir_id="gagok"
)
```

---

## 🗂️ 프로젝트 구조

```
agentic_rag/
├── 📱 Frontend (Streamlit UI)
│   ├── app.py                      # 메인 대시보드
│   ├── automation_dashboard.py     # 자동화 대시보드
│   └── water_dashboard.py          # 수위 대시보드 (구버전)
│
├── 🧠 Core (핵심 시스템)
│   ├── orchestrator.py             # 오케스트레이터
│   ├── query_analyzer.py           # 쿼리 분석기
│   ├── tool_manager.py             # 도구 관리자
│   └── response_generator.py       # 응답 생성기
│
├── 🛠️ Tools (도구 시스템)
│   ├── base_tool.py                # 베이스 클래스
│   ├── vector_search_tool.py       # 벡터 검색
│   ├── water_level_prediction_tool.py
│   ├── arduino_water_sensor_tool.py
│   ├── water_level_monitoring_tool.py
│   ├── real_time_database_control_tool.py
│   ├── advanced_water_analysis_tool.py
│   ├── automation_control_tool.py
│   ├── smart_water_prediction_tool.py
│   └── list_files_tool.py
│
├── 🤖 Services (자동화 서비스)
│   ├── autonomous_agent.py         # 자율 AI 에이전트
│   ├── logging_system.py           # 로깅 시스템
│   ├── database_connector.py       # DB 커넥터
│   ├── real_time_database_updater.py
│   └── water_level_logger.py       # 수위 로거
│
├── 🗄️ Storage (데이터베이스)
│   └── postgresql_storage.py       # PostgreSQL 인터페이스
│
├── 🔧 Utils (유틸리티)
│   ├── exceptions.py               # 커스텀 예외 (13개)
│   ├── logger.py                   # 로거 설정
│   ├── helpers.py                  # 헬퍼 함수
│   ├── pdf_generator.py            # PDF 생성
│   ├── state_manager.py            # 상태 관리
│   └── async_helpers.py            # 비동기 헬퍼
│
├── 🔌 Arduino
│   └── sketch_jul26a11.ino         # Arduino 스케치
│
├── 📊 Models
│   └── lm_studio.py                # LM Studio 클라이언트
│
├── 📦 Data Loader
│   └── generator_data.py           # 데이터 생성
│
├── ⚙️ Configuration
│   ├── config.py                   # 시스템 설정
│   ├── .env                        # 환경 변수
│   ├── docker-compose.yml          # Docker 설정
│   ├── Dockerfile                  # 컨테이너 이미지
│   └── requirements.txt            # Python 의존성
│
└── 📚 Documentation
    ├── README.md                   # 이 파일
    ├── TOOLS_DOCUMENTATION.md      # 도구 문서
    └── .streamlit/config.toml      # Streamlit 설정
```

---

## 🚨 문제 해결

### 1. 임베딩 차원 불일치 오류

**증상**: `dimension mismatch: expected 1024, got XXX`

**원인**: 임베딩 모델 변경 시 기존 벡터 데이터와 차원 불일치

**해결**:
```bash
# 데이터베이스 볼륨 초기화 후 재시작
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

### 2. Arduino 연결 실패

**증상**: `Arduino 디바이스를 찾을 수 없습니다`

**해결**:

#### Windows
```yaml
# docker-compose.yml
devices:
  - "COM3:COM3"  # Windows 장치 관리자에서 COM 포트 확인
```

#### Linux
```yaml
# docker-compose.yml
devices:
  - "/dev/ttyUSB0:/dev/ttyUSB0"
```

```bash
# 권한 설정 (Linux)
sudo chmod 666 /dev/ttyUSB0
```

### 3. LM Studio 연결 실패

**증상**: `LM Studio API에 연결할 수 없습니다`

**확인 사항**:
1. LM Studio가 실행 중인지 확인
2. 로컬 서버가 시작되었는지 확인 (포트: 1234)
3. 모델이 로드되었는지 확인

**해결**:
```bash
# .env 파일에서 URL 확인
LM_STUDIO_BASE_URL=http://host.docker.internal:1234/v1

# Windows: host.docker.internal
# Linux: 172.17.0.1
# Mac: host.docker.internal
```

### 4. 데이터베이스 연결 실패

**증상**: `PostgreSQL 데이터베이스에 연결할 수 없습니다`

**해결**:
```bash
# PostgreSQL 상태 확인
docker compose exec postgres pg_isready -U postgres

# 데이터베이스 접속 테스트
docker compose exec postgres psql -U postgres -d agentic_rag -c "SELECT 1;"

# 로그 확인
docker compose logs postgres
```

### 5. 자동화 에이전트가 작동하지 않음

**증상**: AI가 펌프를 제어하지 않음

**확인 사항**:
1. 자동화가 시작되었는지 확인
2. LM Studio가 연결되었는지 확인
3. 로그에서 오류 확인

**해결**:
```bash
# 로그 확인
docker compose logs -f frontend | grep "autonomous_agent"

# 자동화 재시작
# 웹 UI에서: 자동화 중지 → 자동화 시작
```

### 6. 스트리밍 응답이 깨짐

**증상**: 새 질문 후 이전 메시지 포맷팅 깨짐

**해결**: 최신 버전으로 업데이트 (2025-10-16 수정 완료)

---

## 🔄 Docker 명령어 참고

### 기본 명령어

```bash
# 시작
docker compose up -d

# 중단
docker compose down

# 재시작
docker compose restart

# 로그 보기 (실시간)
docker compose logs -f

# 특정 서비스 로그
docker compose logs -f frontend
docker compose logs -f postgres
```

### 고급 명령어

```bash
# 완전 재시작 (볼륨 초기화)
docker compose down -v
docker compose build --no-cache
docker compose up -d

# 컨테이너 접속
docker compose exec frontend bash
docker compose exec postgres bash

# 리소스 사용량 확인
docker compose stats

# 불필요한 리소스 정리
docker system prune -a
docker volume prune
```

### 데이터베이스 관리

```bash
# PostgreSQL 접속
docker compose exec postgres psql -U postgres -d agentic_rag

# 데이터베이스 백업
docker compose exec postgres pg_dump -U postgres agentic_rag > backup.sql

# 데이터베이스 복원
docker compose exec -T postgres psql -U postgres -d agentic_rag < backup.sql
```

---

## 👨‍💻 개발 가이드

### 로컬 개발 환경 설정

```bash
# 1. 가상환경 생성
python -m venv venv

# 2. 가상환경 활성화
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 개발 도구 설치
pip install pylint black mypy pytest

# 5. Streamlit 실행
streamlit run app.py
```

### 코드 스타일 가이드

#### PEP 8 준수

```python
# Good
def calculate_water_level(reservoir_id: str, duration: int = 60) -> float:
    """배수지 수위 계산.

    Args:
        reservoir_id: 배수지 ID
        duration: 측정 기간 (초)

    Returns:
        계산된 수위 (미터)
    """
    pass

# Bad
def calc(x,y):
    pass
```

#### 타입 힌팅 필수

```python
from typing import Dict, List, Optional

def get_reservoir_data(
    reservoir_id: str,
    start_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """타입 힌팅 예시"""
    pass
```

#### Docstring 작성 (Google 스타일)

```python
def process_water_data(data: List[float]) -> Dict[str, float]:
    """수위 데이터 처리.

    이 함수는 원시 수위 데이터를 받아 통계를 계산합니다.

    Args:
        data: 수위 데이터 리스트 (미터 단위)

    Returns:
        통계 딕셔너리:
        - mean: 평균
        - std: 표준편차
        - min: 최소값
        - max: 최대값

    Raises:
        ValueError: 데이터가 비어있을 경우

    Example:
        >>> data = [45.2, 46.1, 44.8, 45.9]
        >>> result = process_water_data(data)
        >>> print(result['mean'])
        45.5
    """
    if not data:
        raise ValueError("데이터가 비어있습니다")

    return {
        "mean": sum(data) / len(data),
        "std": ...,
        "min": min(data),
        "max": max(data)
    }
```

### 코드 품질 검사

```bash
# 타입 체크
mypy agentic_rag/

# 린팅
pylint agentic_rag/

# 포맷팅
black agentic_rag/

# 테스트 실행
pytest tests/ -v
```

### 새로운 도구 추가하기

```python
# tools/my_new_tool.py
from tools.base_tool import BaseTool
from typing import Dict, Any

class MyNewTool(BaseTool):
    """새로운 도구 예시"""

    def __init__(self):
        super().__init__(
            name="my_new_tool",
            description="이 도구는 XXX를 수행합니다",
            parameters={
                "param1": {
                    "type": "string",
                    "description": "파라미터 1 설명",
                    "required": True
                }
            }
        )

    def execute(self, param1: str, **kwargs) -> Dict[str, Any]:
        """도구 실행 로직"""
        try:
            # 실행 로직
            result = self._do_something(param1)

            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _do_something(self, param: str) -> Any:
        """내부 로직"""
        pass

# 도구 인스턴스 생성
my_new_tool = MyNewTool()
```

---

## 📊 데이터베이스 스키마

### files 테이블 (문서 저장)

```sql
CREATE TABLE files (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    length INTEGER,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    content BYTEA
);
```

### chunks 테이블 (벡터 검색)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
    chunk_index INTEGER,
    content TEXT,
    embedding vector(1024),  -- BGE-m3-ko 임베딩
    metadata JSONB
);

-- 벡터 검색 인덱스
CREATE INDEX idx_chunks_embedding ON chunks
    USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
```

### water 테이블 (수위 데이터)

```sql
CREATE TABLE water (
    id SERIAL PRIMARY KEY,
    measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 가곡 배수지
    gagok_water_level DOUBLE PRECISION,
    gagok_pump_a DOUBLE PRECISION,  -- 1.0 = ON, 0.0 = OFF

    -- 해룡 배수지
    haeryong_water_level DOUBLE PRECISION,
    haeryong_pump_a DOUBLE PRECISION,

    -- 메타데이터
    metadata JSONB
);

-- 시계열 인덱스
CREATE INDEX idx_water_measured_at ON water(measured_at DESC);
```

### automation_logs 테이블 (자동화 로그)

```sql
CREATE TABLE automation_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level VARCHAR(20),      -- INFO, WARNING, ERROR, CRITICAL
    event_type VARCHAR(50), -- DECISION, ACTION, ERROR, etc.
    reservoir_id VARCHAR(50),
    message TEXT,
    metadata JSONB
);

CREATE INDEX idx_automation_logs_timestamp ON automation_logs(timestamp DESC);
```

---

## 📚 관련 문서

- [도구 상세 문서](./TOOLS_DOCUMENTATION.md) - 9개 도구 API 레퍼런스
- [Docker Compose 설정](./docker-compose.yml) - 컨테이너 구성
- [환경 변수 예시](./.env.example) - 환경 설정 템플릿
- [Streamlit 설정](./.streamlit/config.toml) - UI 설정

---

## 🤝 기여하기

프로젝트에 기여해 주셔서 감사합니다!

### 기여 방법

1. **이슈 생성**: 버그 리포트 또는 기능 제안
2. **포크**: 저장소를 포크합니다
3. **브랜치 생성**: `git checkout -b feature/amazing-feature`
4. **변경사항 커밋**: `git commit -m 'feat: Add amazing feature'`
5. **푸시**: `git push origin feature/amazing-feature`
6. **Pull Request 생성**: PR 템플릿 작성

### 커밋 메시지 규칙 (Conventional Commits)

```bash
# 새로운 기능
feat: Add autonomous decision logging

# 버그 수정
fix: Resolve Arduino connection timeout issue

# 문서 수정
docs: Update README with new features

# 코드 포맷팅
style: Apply black formatting to all files

# 리팩토링
refactor: Simplify water level calculation logic

# 테스트 추가
test: Add unit tests for orchestrator

# 빌드/설정 변경
chore: Update Docker compose configuration
```

### 코드 리뷰 체크리스트

- [ ] 타입 힌팅 추가
- [ ] Docstring 작성 (Google 스타일)
- [ ] 유닛 테스트 작성
- [ ] 에러 처리 구현
- [ ] 로깅 추가
- [ ] 문서 업데이트

---

## 📈 로드맵

### 완료된 기능 ✅

- [x] RAG 문서 검색 시스템
- [x] Arduino 센서/펌프 통합
- [x] LSTM 수위 예측
- [x] 자율 AI 에이전트
- [x] 실시간 모니터링 대시보드
- [x] 자동화 제어 시스템
- [x] PostgreSQL + pgvector
- [x] Docker 컨테이너화

### 개발 중 🚧

- [ ] 모바일 반응형 UI
- [ ] 알림 시스템 (이메일/SMS)
- [ ] 고급 분석 대시보드
- [ ] 다중 사용자 인증

### 향후 계획 📝

- [ ] 클라우드 배포 (AWS/GCP)
- [ ] 멀티 테넌시 지원
- [ ] RESTful API 제공
- [ ] 모바일 앱 (React Native)
- [ ] 강화학습 기반 최적화

---

## 📄 라이선스

이 프로젝트는 **MIT License** 하에 배포됩니다.

```
MIT License

Copyright (c) 2025 Agentic RAG Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 🙏 감사의 글

이 프로젝트는 다음 오픈소스 프로젝트들의 도움으로 만들어졌습니다:

### 핵심 기술

- [**LangChain**](https://github.com/langchain-ai/langchain) - LLM 애플리케이션 프레임워크
- [**Streamlit**](https://github.com/streamlit/streamlit) - 데이터 앱 프레임워크
- [**PostgreSQL**](https://www.postgresql.org/) - 오픈소스 관계형 데이터베이스
- [**pgvector**](https://github.com/pgvector/pgvector) - PostgreSQL 벡터 확장
- [**LM Studio**](https://lmstudio.ai/) - 로컬 LLM 서버

### AI/ML

- [**Hugging Face**](https://huggingface.co/) - Transformers 및 모델 허브
- [**TensorFlow**](https://www.tensorflow.org/) - 머신러닝 프레임워크
- [**PyTorch**](https://pytorch.org/) - 딥러닝 프레임워크

### 도구 및 라이브러리

- [**Docker**](https://www.docker.com/) - 컨테이너 플랫폼
- [**Arduino**](https://www.arduino.cc/) - 오픈소스 하드웨어 플랫폼
- [**pySerial**](https://github.com/pyserial/pyserial) - Python 시리얼 통신

---

## 📞 문의 및 지원

- **이슈 트래커**: [GitHub Issues](https://github.com/yourusername/agentic_rag/issues)
- **이메일**: your.email@example.com
- **문서**: [프로젝트 위키](https://github.com/yourusername/agentic_rag/wiki)

---

<div align="center">

## 🌊 Agentic RAG

**AI • IoT • Automation**

차세대 스마트 배수지 관리 솔루션

---

Made with ❤️ by the Agentic RAG Team

⭐ **이 프로젝트가 유용하다면 Star를 눌러주세요!** ⭐

</div>
