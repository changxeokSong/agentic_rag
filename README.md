# 🌊 Agentic RAG - AI 기반 스마트 배수지 관리 시스템

**자율 AI 에이전트, RAG, IoT 센서를 결합하여 배수지 운영을 자동화하고 최적화하는 지능형 관리 솔루션입니다.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📖 목차

- [1. 프로젝트 개요](#1-프로젝트-개요)
- [2. 주요 기능](#2-주요-기능)
- [3. 시스템 아키텍처](#3-시스템-아키텍처)
- [4. AI 에이전트 및 도구](#4-ai-에이전트-및-도구)
- [5. 시작하기](#5-시작하기)
- [6. 사용 방법](#6-사용-방법)
- [7. 문제 해결](#7-문제-해결)

---

## 1. 프로젝트 개요

본 프로젝트는 최신 AI 기술을 활용하여 배수지 관리의 효율성과 안전성을 극대화하는 것을 목표로 합니다. **자율 AI 에이전트**가 실시간으로 수위 데이터를 분석하고, **RAG(검색 증강 생성)** 기술로 관련 문서나 과거 데이터를 참조하며, **IoT 센서**와 연동된 펌프를 제어하여 최적의 의사결정을 내립니다.

- **Agentic RAG**: 단순 정보 제공을 넘어, 스스로 도구를 사용하여 문제를 해결하는 능동적인 AI 시스템입니다.
- **IoT Integration**: Arduino 기반 수위 센서와 펌프를 실시간으로 제어하여 물리적 환경과 상호작용합니다.
- **Automation**: 수위 예측, 위험 감지, 자동 펌프 작동 등 운영 전반을 자동화합니다.

---

## 2. 주요 기능

- 🤖 **자율 AI 에이전트**: 설정된 주기에 따라 수위를 자동 분석하고 펌프를 제어하는 자율 운영 시스템.
- 🌊 **실시간 모니터링 및 제어**: Arduino 센서를 통한 실시간 수위 측정 및 원격 펌프 제어.
- 📈 **AI 기반 수위 예측**: LSTM 및 하이브리드 모델을 사용하여 단기 및 중장기 수위를 예측하고 선제적으로 대응.
- 📊 **고급 데이터 분석**: 수위 변화 추세, 위험 경보 도달 시간 예측, 펌프 작동 시뮬레이션 등 심층 분석 제공.
- 📚 **문서 기반 질의응답 (RAG)**: PDF, TXT 등 업로드된 문서 내용을 기반으로 질문에 답변.

---

## 3. 시스템 아키텍처

- **Frontend**: Streamlit (실시간 대시보드 및 챗봇 UI)
- **Backend**: Python, FastAPI (API 서버)
- **AI/LLM**: LM Studio (로컬 거대 언어 모델 연동)
- **Database**: PostgreSQL + pgvector (시계열 데이터 및 벡터 임베딩 저장)
- **Hardware**: Arduino Uno (수위 센서 및 펌프 제어)
- **Orchestration**: Docker Compose (전체 시스템 컨테이너화)

---

## 4. AI 에이전트 및 도구

### 자율 AI 에이전트 (Autonomous AI Agent)

이 시스템의 핵심 두뇌로, `services/autonomous_agent.py`에 구현되어 있습니다. 에이전트는 다음과 같은 역할을 수행합니다.
- **주기적 상태 분석**: 30초마다 배수지의 현재 및 예측 수위를 분석합니다.
- **자동 의사결정**: 분석 결과를 바탕으로 펌프를 켜거나 끄는 등 자동화된 제어 로직을 수행합니다.
- **도구 활용**: 아래에 설명된 다양한 도구들을 상황에 맞게 호출하여 복잡한 작업을 처리합니다.

### 사용 가능한 도구 (Tools)

AI 에이전트는 총 9개의 특화된 도구를 사용하여 다양한 임무를 수행합니다.

| 카테고리 | 도구 이름 | 주요 기능 |
| :--- | :--- | :--- |
| 🤖 **자동화 제어** | `automation_control_tool` | AI 자동화 시스템의 시작, 중지, 상태 조회 등 중앙 허브 역할 |
| 📈 **수위 예측** | `smart_water_prediction_tool` | DB 데이터를 자동 분석하여 미래 수위를 예측 (권장) |
| | `water_level_prediction_tool` | 사용자가 제공한 특정 데이터 기반으로 LSTM 모델 예측 |
| 📊 **데이터 조회/분석** | `water_level_monitoring_tool` | 현재 수위, 이력 조회, 시각화 그래프 생성 |
| | `advanced_water_analysis_tool` | 수위 변화 추세, 위험 도달 시간 예측, 펌프 시뮬레이션 등 고급 분석 |
| ⚙️ **하드웨어 제어** | `arduino_water_sensor_tool` | Arduino 센서 값 직접 읽기 및 펌프 제어 |
| | `real_time_database_control_tool` | 센서 데이터의 실시간 DB 저장을 관리하는 서비스 제어 |
| 📚 **문서 검색 (RAG)** | `vector_search_tool` | 업로드된 문서(PDF 등)를 대상으로 의미 기반 검색 |
| | `list_files_tool` | 검색 가능한 파일 목록 조회 |

> 💡 각 도구의 상세한 API 명세는 `TOOLS_DOCUMENTATION.md` 파일에서 확인할 수 있습니다.

---

## 5. 시작하기

### 1. 필수 요구사항

- **Docker Desktop**: 컨테이너화된 전체 시스템을 실행하기 위해 필수입니다.
- **LM Studio**: 로컬 LLM을 구동하기 위해 권장됩니다. (또는 API 방식의 다른 LLM으로 대체 가능)
- **Arduino**: 실제 하드웨어 연동 시 필요합니다. (시뮬레이션 모드로 대체 가능)

### 2. 설치 및 실행

```bash
# 1. 프로젝트 클론
git clone https://github.com/your-username/agentic_rag.git
cd agentic_rag

# 2. 환경 변수 설정
# .env.example 파일을 복사하여 .env 파일을 생성하고, 내부 설정을 자신의 환경에 맞게 수정합니다.
cp .env.example .env

# 3. LM Studio 설정 (권장)
# - LM Studio를 설치하고, 'bartowski/exaone-4.0-1.2b-instruct'와 같은 모델을 다운로드합니다.
# - Local Server를 포트 1234로 실행합니다.

# 4. Docker 컨테이너 실행
# - Docker Desktop이 실행 중인 상태에서 아래 명령어를 입력합니다.
docker compose up -d

# 5. 로그 확인 (선택)
docker compose logs -f
```

### 3. 접속

- 웹 브라우저에서 **http://localhost:8501** 주소로 접속합니다.
- 화면 좌측의 **"🔄 시스템 초기화"** 버튼을 눌러 샘플 데이터를 생성하고 시스템을 준비시킵니다.

---

## 6. 사용 방법

챗봇 인터페이스를 통해 자연어 명령으로 시스템과 상호작용할 수 있습니다.

```
👤 "현재 배수지 수위 알려줘"
🤖 (water_level_monitoring_tool 호출) 가곡: 45.2m (정상), 해룡: 62.8m (정상)

👤 "가곡 배수지 1시간 뒤 수위 예측해줘"
🤖 (smart_water_prediction_tool 호출) 1시간 후 예상 수위는 46.1m 입니다.

👤 "자동화 시스템 시작해"
🤖 (automation_control_tool 호출) ✅ 통합 자동화 시스템을 시작합니다.

👤 "지난 24시간 수위 변화 그래프 그려줘"
🤖 (water_level_monitoring_tool 호출) 📊 [그래프 이미지 표시]

👤 "배수지 관리 매뉴얼에서 비상 대응법 찾아줘"
🤖 (vector_search_tool 호출) 매뉴얼 12페이지에서 관련 내용을 찾았습니다...
```

---

## 7. 문제 해결

### Docker 컨테이너 완전 재시작

오류가 발생하거나 시스템을 초기 상태로 되돌리고 싶을 때 사용합니다.
```bash
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

### Arduino 연결 실패

- **Windows (WSL2)**: `usbipd`를 사용하여 USB 장치를 WSL2에 연결해야 합니다.
- **Linux**: `sudo chmod 666 /dev/ttyUSB0` 와 같이 시리얼 포트 접근 권한을 확인하세요.
- `.env` 파일의 `ARDUINO_SERIAL_PORT` 변수가 올바르게 설정되었는지 확인하세요.

### LM Studio 연결 실패

- LM Studio 프로그램이 실행 중이고, 로컬 서버가 활성화(포트 1234)되었는지 확인하세요.
- `.env` 파일의 `LM_STUDIO_BASE_URL`이 `http://host.docker.internal:1234/v1` (Windows/Mac) 또는 `http://172.17.0.1:1234/v1` (Linux)로 설정되었는지 확인하세요.