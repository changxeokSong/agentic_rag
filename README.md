# 🌊 Agentic RAG - 지능형 수위 관리 시스템

**Agentic RAG**는 AI 기반 문서 검색(RAG)과 IoT 수위 센서를 통합한 지능형 수위 관리 및 자동화 시스템입니다. Docker를 활용한 멀티 서비스 아키텍처로 구성되어 있으며, 실시간 수위 모니터링, 예측, 자동 제어 기능을 제공합니다.

## 🚀 주요 특징

### 📚 AI 문서 검색 시스템
- **벡터 임베딩**: Hugging Face `dragonkue/BGE-m3-ko` (1024차원) 모델 사용
- **벡터 데이터베이스**: PostgreSQL + pgvector (L2 distance)
- **문서 지원**: PDF, TXT, DOCX 자동 청크 분할 및 임베딩
- **지능형 검색**: 의미론적 유사도 기반 문서 검색
- **한글 최적화**: 나눔고딕 폰트 적용된 PDF 보고서 생성

### 🌊 수위 관리 시스템
- **실시간 모니터링**: Arduino 기반 수위 센서 연동
- **LSTM 예측**: 딥러닝을 통한 수위 예측 (최대 24시간)
- **자동 제어**: 펌프 자동 제어 및 경보 시스템
- **다중 배수지**: 가곡, 해룡, 상사 배수지 독립 관리
- **그래프 시각화**: 실시간 수위 변화 그래프

### 🤖 자율 자동화 시스템
- **Agentic AI**: 자율적 의사결정 및 제어
- **실시간 대응**: 위험 상황 자동 감지 및 대응
- **로그 시스템**: 모든 자동화 활동 추적 및 기록
- **원격 제어**: 웹 기반 펌프 제어 및 모니터링

## 🏗️ 시스템 아키텍처

```
사용자 → Streamlit UI (앱.py) → 오케스트레이터 → 도구들 → 저장소 → PostgreSQL
                               ↓
                        자율 자동화 시스템
                               ↓
                        Arduino 하드웨어
```

### 핵심 구성요소
- **Frontend**: Streamlit 기반 웹 인터페이스
- **Backend**: 비동기 서비스 및 데이터 처리
- **Database**: PostgreSQL + pgvector (벡터 검색)
- **AI Models**: LM Studio + LSTM + Embedding
- **Hardware**: Arduino 기반 센서 및 펌프

## 📁 프로젝트 구조

```
agentic_rag/
├── 🎯 메인 애플리케이션
│   ├── app.py                     # Streamlit 메인 UI
│   ├── automation_dashboard.py    # 자동화 시스템 대시보드
│   ├── water_dashboard.py         # 수위 모니터링 대시보드
│   └── config.py                  # 시스템 설정
├── 🧠 핵심 시스템
│   ├── core/
│   │   ├── orchestrator.py        # 요청 오케스트레이션
│   │   ├── query_analyzer.py      # 쿼리 분석
│   │   ├── response_generator.py  # 응답 생성
│   │   └── tool_manager.py        # 도구 관리
├── 🛠️ 도구 시스템
│   ├── tools/
│   │   ├── vector_search_tool.py           # 벡터 검색
│   │   ├── water_level_prediction_tool.py  # 수위 예측
│   │   ├── arduino_water_sensor_tool.py    # 아두이노 센서
│   │   ├── water_level_monitoring_tool.py  # 수위 모니터링
│   │   ├── automation_control_tool.py      # 자동화 제어
│   │   ├── advanced_water_analysis_tool.py # 고급 수위 분석
│   │   └── real_time_database_control_tool.py # 실시간 DB 제어
├── 🤖 자동화 서비스
│   ├── services/
│   │   ├── automation_manager.py   # 자동화 관리
│   │   ├── autonomous_agent.py     # 자율 에이전트
│   │   ├── decision_engine.py      # 의사결정 엔진
│   │   └── logging_system.py       # 로깅 시스템
├── 💾 데이터 및 모델
│   ├── storage/
│   │   └── postgresql_storage.py   # PostgreSQL 연동
│   ├── models/
│   │   └── lm_studio.py           # LM Studio 클라이언트
│   ├── lstm_model/
│   │   └── lstm_water_level_model.h5 # LSTM 모델
│   └── retrieval/
│       └── document_loader.py      # 문서 로더
├── 🔧 유틸리티
│   ├── utils/
│   │   ├── logger.py              # 로깅 유틸
│   │   ├── pdf_generator.py       # PDF 생성
│   │   ├── state_manager.py       # 상태 관리
│   │   └── arduino_direct.py      # 아두이노 직접 통신
├── 🐳 Docker 설정
│   ├── docker-compose.yml         # 멀티 서비스 구성
│   ├── Dockerfile                 # 컨테이너 빌드
│   ├── docker/
│   │   └── postgres/init.sql      # DB 초기화 스크립트
│   └── scripts/                   # 실행 스크립트
└── 📋 설정 파일
    ├── requirements.txt           # Python 패키지
    ├── requirements.lock.txt      # 고정 버전
    └── ENV_EXAMPLE.txt           # 환경변수 템플릿
```

## 🚀 빠른 시작

### 1. 시스템 요구사항
- **Docker Desktop** (필수)
- **LM Studio** (선택, 로컬 LLM 사용 시)
- **Arduino 하드웨어** (선택, 실제 센서 사용 시)
- **Python 3.12+** (개발 환경)

### 2. 환경 설정
```bash
# 저장소 클론
git clone [repository-url]
cd agentic_rag

# 환경변수 파일 생성
cp ENV_EXAMPLE.txt .env

# .env 파일 편집 (필요한 토큰 및 설정 입력)
```

### 3. Docker 실행 (권장)
```bash
# 초기 실행 (볼륨 초기화)
docker compose down -v
docker compose build --no-cache
docker compose up -d

# 서비스 상태 확인
docker compose ps
```

### 4. 접속
- **메인 대시보드**: http://localhost:8501
- **자동화 대시보드**: http://localhost:8501 (페이지 전환)

### 5. 기본 사용법
1. **시스템 초기화**: 좌측 제어판에서 "시스템 초기화" 실행
2. **문서 업로드**: 우측 "파일 업로드"로 PDF/TXT/DOCX 업로드
3. **질의응답**: 중앙 채팅창에 질문 입력
4. **수위 모니터링**: "수위 현황 보여줘", "그래프 그려줘" 등 명령
5. **자동화 제어**: "자동화 시작해줘", "펌프1 켜줘" 등 명령

## ⚙️ 환경변수 설정

`.env` 파일 예시:
```env
# LM Studio 설정
LM_STUDIO_BASE_URL=http://host.docker.internal:1234/v1
LM_STUDIO_API_KEY=lm-studio
LM_STUDIO_MODEL_NAME=exaone-4.0-1.2b

# 임베딩 설정
EMBEDDING_BACKEND=HF
EMBEDDING_MODEL_NAME=dragonkue/BGE-m3-ko
EMBEDDING_DEVICE=cpu
HUGGINGFACEHUB_API_TOKEN=your_hf_token

# 데이터베이스 설정
PG_DB_HOST=postgres
PG_DB_PORT=5432
PG_DB_NAME=synergy
PG_DB_USER=synergy
PG_DB_PASSWORD=synergy

# 활성화 도구 (쉼표로 구분)
ENABLED_TOOLS=vector_search_tool,list_files_tool,water_level_prediction_tool,arduino_water_sensor,water_level_monitoring_tool,real_time_database_control_tool,advanced_water_analysis_tool,automation_control_tool

# 기타 설정
DEBUG_MODE=false
OPENAI_API_KEY=your_openai_key
```

## 🛠️ 주요 기능

### 📖 문서 검색 및 QA
- **벡터 검색**: "지난 분기 보고서에서 매출 관련 내용 찾아줘"
- **파일 필터링**: "'프로젝트A.pdf' 파일에서 핵심 성과 요약해줘"
- **태그 검색**: 특정 태그로 문서 분류 및 검색

### 🌊 수위 관리
- **실시간 측정**: "현재 수위 알려줘"
- **예측**: "앞으로 3시간 수위 예측해줘"
- **모니터링**: "24시간 수위 그래프 그려줘"
- **경보**: 위험 수위 자동 감지 및 알림

### 🔧 펌프 제어
- **수동 제어**: "펌프1 켜줘", "펌프2 꺼줘"
- **자동 제어**: 수위 기반 자동 펌프 작동
- **상태 확인**: "펌프 상태 확인해줘"

### 🤖 자동화 시스템
- **시작/중지**: "자동화 시작해줘", "자율 시스템 꺼줘"
- **상태 모니터링**: "자동화 상태 보여줘"
- **로그 조회**: "최근 의사결정 로그 보여줘"
- **하드웨어 진단**: "Arduino 연결 상태 확인해줘"

## 🔧 기술 스택

### Backend
- **Python 3.12+**: 메인 런타임
- **Streamlit**: 웹 UI 프레임워크
- **LangChain**: LLM 오케스트레이션
- **PostgreSQL + pgvector**: 벡터 데이터베이스
- **TensorFlow/Keras**: LSTM 수위 예측 모델

### AI/ML
- **LM Studio**: 로컬 LLM 서버
- **Hugging Face Transformers**: 임베딩 모델
- **LSTM**: 시계열 수위 예측
- **RAG (Retrieval-Augmented Generation)**: 문서 기반 QA

### Hardware/IoT
- **Arduino**: 수위 센서 및 펌프 제어
- **Serial Communication**: USB 시리얼 통신
- **Real-time Data Collection**: 실시간 센서 데이터 수집

### DevOps
- **Docker & Docker Compose**: 컨테이너화
- **Multi-service Architecture**: 분리된 프론트엔드/백엔드
- **Health Checks**: 서비스 상태 모니터링

## 🚨 트러블슈팅

### 임베딩 차원 오류
```bash
# 볼륨 초기화 (권장)
docker compose down -v
docker compose build --no-cache
docker compose up -d

# 또는 수동 마이그레이션
docker compose exec -T postgres psql -U synergy -d synergy -c "
  DROP INDEX IF EXISTS idx_chunks_embedding;
  ALTER TABLE chunks DROP COLUMN IF EXISTS embedding;
  ALTER TABLE chunks ADD COLUMN embedding vector(1024);
  CREATE INDEX idx_chunks_embedding ON chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
"
```

### Arduino 연결 문제
```bash
# 컨테이너 내에서 USB 디바이스 확인
docker compose exec backend ls -la /dev/tty*

# Windows에서 시리얼 포트 확인
# 장치 관리자 → 포트(COM & LPT) 확인
```

### 서비스 상태 확인
```bash
# 모든 서비스 상태
docker compose ps

# 로그 확인
docker compose logs frontend
docker compose logs backend
docker compose logs postgres

# 헬스체크
curl http://localhost:8501
```

### 메모리 부족
```bash
# 사용하지 않는 이미지 정리
docker image prune -a

# 볼륨 정리
docker volume prune

# 시스템 전체 정리
docker system prune -a
```

## 📊 데이터베이스 스키마

### files 테이블
- 업로드된 파일 메타데이터 저장
- 파일 이름, 크기, 업로드 시간 등

### chunks 테이블
- 문서 청크 및 임베딩 벡터 저장
- 1024차원 벡터 (dragonkue/BGE-m3-ko)

### water 테이블
- 실시간 수위 데이터 저장
- 배수지별 수위, 펌프 상태, 측정 시간

### automation_logs 테이블
- 자동화 시스템 로그 저장
- 의사결정 과정, 실행 결과 추적

## 🤝 기여하기

1. 이슈 생성 및 토론
2. 포크 후 브랜치 생성
3. 변경사항 커밋
4. 풀 리퀘스트 생성

## 📜 라이선스

MIT License

## 📞 지원

- **이슈 등록**: GitHub Issues
- **문서**: 프로젝트 Wiki
- **개발자**: [개발팀 연락처]

---

**Agentic RAG**는 AI, IoT, 자동화가 융합된 차세대 스마트 수위 관리 솔루션입니다. 🌊🤖✨