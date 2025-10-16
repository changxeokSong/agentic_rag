# 🌊 Agentic RAG - AI 기반 스마트 배수지 관리 시스템

**AI 에이전트 + IoT 센서 + 자동화**를 결합한 배수지 관리 솔루션

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📖 목차

- [개요](#-개요)
- [주요 특징](#-주요-특징)
- [빠른 시작](#-빠른-시작)
- [환경 설정](#-환경-설정)
- [사용 방법](#-사용-방법)
- [문제 해결](#-문제-해결)

---

## 🎯 개요

AI 기반 문서 검색(RAG), IoT 수위 센서, 자율 의사결정 시스템을 통합한 배수지 관리 플랫폼

### 핵심 기능

- 🤖 **자율 AI 에이전트**: 30초마다 배수지 수위 분석 및 펌프 자동 제어
- 🌊 **실시간 모니터링**: Arduino 센서로 수위 실시간 측정
- 📚 **AI 문서 검색**: RAG 기술로 과거 데이터 분석
- 🔧 **완전 자동화**: 위험 감지 시 자동 대응

---

## ✨ 주요 특징

### 배수지 시스템

| 배수지 | 펌프 | 제어 로직 |
|--------|------|-----------|
| **가곡** | 펌프1 | 수위 < 40m → ON, > 80m → OFF |
| **해룡** | 펌프2 | 수위 < 40m → ON, > 80m → OFF |

### 기술 스택

- **Frontend**: Streamlit
- **Backend**: Python 3.12+
- **Database**: PostgreSQL 15 + pgvector
- **AI**: LM Studio + Hugging Face
- **Hardware**: Arduino Uno

---

## 🚀 빠른 시작

### 1. 필수 요구사항

- Docker Desktop (필수)
- LM Studio (권장)
- Arduino (선택)

### 2. 설치

```bash
# 저장소 클론
git clone https://github.com/yourusername/agentic_rag.git
cd agentic_rag

# 환경 변수 설정
cp .env.example .env
# .env 파일 편집
```

### 3. LM Studio 설정

1. [LM Studio](https://lmstudio.ai/) 다운로드
2. 모델 다운로드 (예: `bartowski/exaone-4.0-1.2b-instruct`)
3. 로컬 서버 시작 (포트: 1234)

### 4. 실행

```bash
# Docker 시작
docker compose up -d

# 로그 확인
docker compose logs -f frontend
```

### 5. 접속

- 웹 브라우저에서 **http://localhost:8501** 접속
- 좌측에서 **"🔄 시스템 초기화"** 클릭
- 사용 시작!

---

## ⚙️ 환경 설정

### .env 파일 주요 설정

```env
# LM Studio
LM_STUDIO_BASE_URL=http://host.docker.internal:1234/v1
LM_STUDIO_MODEL_NAME=bartowski/exaone-4.0-1.2b-instruct

# 임베딩
EMBEDDING_MODEL_NAME=dragonkue/BGE-m3-ko
HUGGINGFACEHUB_API_TOKEN=your_token_here

# PostgreSQL
PG_DB_HOST=postgres
PG_DB_PORT=5432
PG_DB_NAME=agentic_rag
PG_DB_USER=postgres
PG_DB_PASSWORD=0000
```

---

## 💬 사용 방법

### AI 챗봇 사용

```
👤 "현재 배수지 수위 알려줘"
🤖 가곡: 45.2m (정상), 해룡: 62.8m (정상)

👤 "펌프1 켜줘"
🤖 ✅ 펌프1을 켰습니다. (가곡 배수지)

👤 "자동화 시작해줘"
🤖 ✅ 통합 자동화 시스템을 시작했습니다.

👤 "24시간 수위 그래프 그려줘"
🤖 📊 [그래프 표시]
```

---

## 🚨 문제 해결

### 임베딩 차원 오류

```bash
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

### Arduino 연결 실패

**Windows**:
```yaml
# docker-compose.yml
devices:
  - "COM3:COM3"  # 장치 관리자에서 포트 확인
```

**Linux**:
```bash
sudo chmod 666 /dev/ttyUSB0
```

### LM Studio 연결 실패

1. LM Studio 실행 확인
2. 로컬 서버 시작 (포트: 1234)
3. .env에서 URL 확인:
   - Windows/Mac: `host.docker.internal:1234`
   - Linux: `172.17.0.1:1234`

### 데이터베이스 연결 실패

```bash
# 상태 확인
docker compose exec postgres pg_isready -U postgres

# 로그 확인
docker compose logs postgres
```

---

## 📁 프로젝트 구조

```
agentic_rag/
├── app.py                      # 메인 UI
├── automation_dashboard.py     # 자동화 대시보드
├── config.py                   # 설정
├── core/                       # 핵심 시스템
│   ├── orchestrator.py
│   ├── query_analyzer.py
│   └── response_generator.py
├── tools/                      # 도구 시스템 (9개)
├── services/                   # 자동화 서비스
│   ├── autonomous_agent.py     # AI 에이전트
│   └── database_connector.py
├── storage/                    # 데이터베이스
└── docker-compose.yml
```

---

## 🔄 Docker 명령어

```bash
# 시작
docker compose up -d

# 중단
docker compose down

# 재시작
docker compose restart

# 로그
docker compose logs -f

# 완전 초기화
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

---

## 📚 관련 문서

- [도구 문서](./TOOLS_DOCUMENTATION.md) - 9개 도구 API
- [Docker Compose](./docker-compose.yml) - 컨테이너 구성

---

## 📄 라이선스

MIT License - 자유롭게 사용 가능

---

<div align="center">

**Agentic RAG** - AI 기반 스마트 배수지 관리 솔루션

Made with ❤️

</div>
