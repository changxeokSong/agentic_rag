# 🌊 Agentic RAG - 지능형 수위 관리 시스템

AI 기반 문서 검색(RAG)과 IoT 수위 센서를 통합한 지능형 수위 관리 및 자동화 시스템

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📖 목차

- [주요 특징](#-주요-특징)
- [빠른 시작](#-빠른-시작)
- [시스템 구조](#-시스템-구조)
- [환경 설정](#-환경-설정)
- [사용 방법](#-사용-방법)
- [기술 스택](#-기술-스택)
- [문제 해결](#-문제-해결)

---

## ✨ 주요 특징

### 📚 AI 문서 검색 (RAG)
- **벡터 검색**: Hugging Face BGE-m3-ko 모델 (1024차원)
- **PostgreSQL + pgvector**: 고성능 벡터 데이터베이스
- **다중 형식 지원**: PDF, TXT, DOCX 자동 처리
- **한글 최적화**: 한국어 임베딩 및 PDF 생성

### 🌊 수위 관리
- **실시간 모니터링**: Arduino 센서 연동
- **LSTM 예측**: 딥러닝 기반 수위 예측 (최대 24시간)
- **자동 제어**: 펌프 자동 제어 및 경보
- **다중 배수지**: 가곡, 해룡, 상사 배수지 독립 관리

### 🤖 자율 자동화
- **Agentic AI**: 자율적 의사결정 시스템
- **실시간 대응**: 위험 상황 자동 감지 및 조치
- **학습 기능**: 과거 데이터 기반 시스템 개선
- **웹 대시보드**: 실시간 모니터링 및 제어

---

## 🚀 빠른 시작

### 필수 요구사항

- **Docker Desktop** (필수)
- **LM Studio** (선택 - 로컬 LLM 사용 시)
- **Arduino 하드웨어** (선택 - 실제 센서 사용 시)

### 설치 및 실행

```bash
# 1. 저장소 클론
git clone <repository-url>
cd agentic_rag

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 필요한 설정 입력

# 3. Docker 실행
docker compose up -d

# 4. 로그 확인
docker compose logs -f
```

### 접속

- 🌐 **메인 대시보드**: http://localhost:8501
- 🗄️ **PostgreSQL**: localhost:5432

### 초기 설정

1. 웹 브라우저에서 http://localhost:8501 접속
2. 좌측 사이드바에서 "시스템 초기화" 클릭
3. 문서 업로드 (PDF/TXT/DOCX)
4. 질의응답 시작!

---

## 🏗️ 시스템 구조

```
┌─────────────────────────────────────┐
│     사용자 (웹 브라우저)             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Streamlit UI (포트 8501)          │
│   - 메인 대시보드                    │
│   - 자동화 제어판                    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Orchestrator (오케스트레이터)      │
│   - 쿼리 분석                        │
│   - 도구 관리                        │
│   - 응답 생성                        │
└──────────┬──────────────────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
┌─────────┐   ┌──────────────┐
│  도구들  │   │ 자동화 시스템 │
│  (9개)  │   │  - 의사결정   │
└────┬────┘   └──────┬───────┘
     │               │
     └───────┬───────┘
             ▼
     ┌───────────────┐
     │  PostgreSQL   │
     │  + pgvector   │
     └───────┬───────┘
             │
             ▼
      ┌──────────┐
      │ Arduino  │
      └──────────┘
```

### 핵심 구성 요소

| 구성 요소 | 설명 |
|----------|------|
| **Frontend** | Streamlit 웹 UI |
| **Backend** | Python 비동기 서비스 |
| **Database** | PostgreSQL + pgvector |
| **AI Engine** | LM Studio + LSTM |
| **Hardware** | Arduino 센서/펌프 |

---

## ⚙️ 환경 설정

### .env 파일 설정

```env
# LM Studio 설정
LM_STUDIO_BASE_URL=http://host.docker.internal:1234/v1
LM_STUDIO_MODEL_NAME=exaone-4.0-1.2b
LM_STUDIO_API_KEY=lm-studio

# 임베딩 설정
EMBEDDING_BACKEND=HF
EMBEDDING_MODEL_NAME=dragonkue/BGE-m3-ko
EMBEDDING_DEVICE=cpu
HUGGINGFACEHUB_API_TOKEN=your_token_here

# PostgreSQL 설정
PG_DB_HOST=postgres
PG_DB_PORT=5432
PG_DB_NAME=synergy
PG_DB_USER=synergy
PG_DB_PASSWORD=synergy

# 활성화 도구
ENABLED_TOOLS=vector_search_tool,list_files_tool,water_level_prediction_tool,arduino_water_sensor,water_level_monitoring_tool,real_time_database_control_tool,advanced_water_analysis_tool,automation_control_tool,smart_water_prediction

# 기타 설정
DEBUG_MODE=false
LOG_LEVEL=INFO
CHUNK_SIZE=1000
TOP_K_RESULTS=5
```

### 주요 설정 옵션

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `CHUNK_SIZE` | 1000 | 문서 청크 크기 |
| `CHUNK_OVERLAP` | 200 | 청크 오버랩 |
| `TOP_K_RESULTS` | 5 | 검색 결과 개수 |
| `MAX_TOKENS` | 2048 | 최대 응답 토큰 |
| `RESPONSE_TEMPERATURE` | 0.7 | 응답 생성 온도 |

---

## 💬 사용 방법

### 문서 검색

```
"지난 분기 보고서에서 매출 관련 내용 찾아줘"
"프로젝트A.pdf 파일에서 핵심 성과 요약해줘"
```

### 수위 관리

```
"현재 수위 알려줘"
"가곡 배수지 30분 후 수위 예측해줘"
"24시간 수위 그래프 그려줘"
```

### 펌프 제어

```
"펌프1 켜줘"
"펌프2 꺼줘"
"펌프 상태 확인해줘"
```

### 자동화 제어

```
"자동화 시작해줘"
"자동화 상태 보여줘"
"최근 의사결정 로그 보여줘"
```

---

## 🔧 기술 스택

### Backend
- Python 3.12+
- Streamlit (웹 UI)
- LangChain (LLM 오케스트레이션)
- PostgreSQL 15+ (데이터베이스)
- pgvector (벡터 검색)
- TensorFlow 2.x (LSTM 모델)

### AI/ML
- LM Studio (로컬 LLM 서버)
- Hugging Face Transformers (임베딩)
- LSTM (시계열 예측)
- RAG (문서 검색)

### DevOps
- Docker & Docker Compose
- Multi-service Architecture
- Health Checks

---

## 🗂️ 프로젝트 구조

```
agentic_rag/
├── app.py                      # Streamlit 메인 UI
├── automation_dashboard.py     # 자동화 대시보드
├── water_dashboard.py          # 수위 대시보드
├── config.py                   # 시스템 설정
├── run_backend.py              # 백엔드 실행
│
├── core/                       # 핵심 시스템
│   ├── orchestrator.py         # 오케스트레이터
│   ├── query_analyzer.py       # 쿼리 분석
│   ├── tool_manager.py         # 도구 관리
│   └── response_generator.py   # 응답 생성
│
├── tools/                      # 도구 시스템 (9개)
│   ├── base_tool.py            # 베이스 클래스
│   ├── vector_search_tool.py
│   ├── water_level_prediction_tool.py
│   ├── arduino_water_sensor_tool.py
│   └── ...
│
├── services/                   # 자동화 서비스
│   ├── automation_manager.py   # 자동화 관리
│   ├── decision_engine.py      # 의사결정 엔진
│   └── real_time_monitor.py    # 실시간 모니터
│
├── storage/                    # 데이터베이스
│   └── postgresql_storage.py
│
├── utils/                      # 유틸리티
│   ├── exceptions.py           # 커스텀 예외
│   ├── logger.py               # 로깅
│   └── ...
│
├── arduino/                    # Arduino 스케치
│   └── sketch_jul26a11.ino
│
├── docker-compose.yml          # Docker 설정
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## 🔬 데이터베이스 스키마

### files 테이블
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

### chunks 테이블
```sql
CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
    chunk_index INTEGER,
    content TEXT,
    embedding vector(1024),
    metadata JSONB
);

CREATE INDEX idx_chunks_embedding ON chunks
    USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
```

### water 테이블
```sql
CREATE TABLE water (
    id SERIAL PRIMARY KEY,
    reservoir_id VARCHAR(50),
    current_level FLOAT,
    pump1_status VARCHAR(10),
    pump2_status VARCHAR(10),
    measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🚨 문제 해결

### 임베딩 차원 오류

**증상**: `dimension mismatch` 오류 발생

**해결**:
```bash
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

### Arduino 연결 문제

**증상**: Arduino 디바이스를 찾을 수 없음

**해결**:
1. Windows 장치 관리자에서 COM 포트 확인
2. `docker-compose.yml`에서 디바이스 매핑 확인
```yaml
devices:
  - "/dev/ttyUSB0:/dev/ttyUSB0"  # Linux
  - "COM3:COM3"                   # Windows
```

### 서비스 상태 확인

```bash
# 서비스 상태
docker compose ps

# 로그 확인
docker compose logs -f frontend
docker compose logs -f backend
docker compose logs -f postgres

# 재시작
docker compose restart frontend
```

### 데이터베이스 연결 실패

```bash
# PostgreSQL 상태 확인
docker compose exec postgres pg_isready -U synergy

# 데이터베이스 접속 테스트
docker compose exec postgres psql -U synergy -d synergy -c "SELECT 1;"
```

---

## 🔄 Docker 명령어

```bash
# 시작
docker compose up -d

# 중단
docker compose down

# 완전 재시작 (볼륨 초기화)
docker compose down -v
docker compose build --no-cache
docker compose up -d

# 로그 보기
docker compose logs -f

# 특정 서비스만 재시작
docker compose restart frontend

# 컨테이너 접속
docker compose exec frontend bash
docker compose exec backend bash
docker compose exec postgres bash

# 리소스 정리
docker system prune -a
```

---

## 💎 코드 품질

### 최근 리팩토링 (2025-10-13)

| 항목 | 현황 |
|------|------|
| **타입 힌팅** | 95% ✅ |
| **Docstring** | 90% ✅ |
| **커스텀 예외** | 13개 ✅ |
| **베이스 클래스** | 완료 ✅ |

상세 내용은 [REFACTORING_SUMMARY.md](./REFACTORING_SUMMARY.md) 참조

### 주요 개선사항

1. **타입 안정성**: 모든 함수/메소드 타입 힌팅 완료
2. **에러 처리**: 13개 커스텀 예외 클래스 도입
3. **설정 검증**: 자동 설정 유효성 검사
4. **문서화**: 상세한 docstring 추가

---

## 👨‍💻 개발 가이드

### 로컬 개발 환경

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 개발 도구 설치
pip install pylint black mypy pytest
```

### 코드 스타일

- **PEP 8** 준수
- **타입 힌팅** 필수
- **Docstring** 필수 (Google 스타일)
- **포맷팅**: `black`

### 테스트

```bash
# 타입 체크
mypy agentic_rag/

# 린팅
pylint agentic_rag/

# 포맷팅
black agentic_rag/

# 테스트 실행
pytest tests/
```

---

## 📚 관련 문서

- [리팩토링 요약](./REFACTORING_SUMMARY.md) - 코드 리팩토링 상세 내역
- [Docker Compose 설정](./docker-compose.yml) - 컨테이너 구성
- [환경 변수 예시](./.env.example) - 환경 설정 템플릿

---

## 🤝 기여하기

1. 이슈 생성 및 토론
2. 포크 후 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 변경사항 커밋 (`git commit -m 'feat: Add amazing feature'`)
4. 푸시 (`git push origin feature/amazing-feature`)
5. Pull Request 생성

### 커밋 메시지 규칙

```
feat: 새로운 기능 추가
fix: 버그 수정
docs: 문서 수정
style: 코드 포맷팅
refactor: 리팩토링
test: 테스트 추가
chore: 빌드/설정 변경
```

---

## 📄 라이선스

MIT License

---

## 🙏 감사의 글

이 프로젝트는 다음 오픈소스를 활용합니다:

- [LangChain](https://github.com/langchain-ai/langchain)
- [Streamlit](https://github.com/streamlit/streamlit)
- [PostgreSQL](https://www.postgresql.org/)
- [pgvector](https://github.com/pgvector/pgvector)
- [Hugging Face](https://huggingface.co/)

---

<div align="center">

**Agentic RAG** - AI, IoT, 자동화가 융합된 차세대 스마트 수위 관리 솔루션

🌊 **Water Management** • 🤖 **AI Powered** • 🔧 **Full Automation**

Made with ❤️

</div>
