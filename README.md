# AgenticRAG - AI 기반 멀티모달 챗봇 시스템

## 📌 프로젝트 개요

AgenticRAG는 LM Studio와 PostgreSQL을 기반으로 한 고도로 통합된 지능형 챗봇 시스템입니다. 아두이노 하드웨어 제어, LSTM 딥러닝 예측, 웹 검색, 문서 관리 등 8가지 전문 도구를 하나의 대화형 인터페이스에서 제공하며, 복합 명령어를 자동으로 분석하여 멀티 도구를 동시 실행할 수 있습니다.

## ⚡ 주요 기능

- **🔍 웹 검색**: Tavily API를 통한 실시간 웹 정보 검색
- **🧮 계산기**: 안전한 수학 표현식 평가, 수학 함수 지원
- **🌤️ 날씨 조회**: OpenWeatherMap API 기반 전 세계 실시간 날씨 정보
- **💧 아두이노 수위센서**: USB 시리얼 통신을 통한 실시간 수위 센서 값 읽기 및 펌프 제어
- **📈 LSTM 수위 예측**: TensorFlow/Keras 기반 딥러닝 모델을 활용한 수위 예측 시스템
- **🔎 벡터 검색**: PostgreSQL + pgvector 기반 의미 검색
- **📂 파일 관리**: 파일 업로드, 벡터화, 저장 및 검색
- **💬 자연어 처리**: 복합 요청 자동 분석 및 멀티 도구 병렬 실행

## 🛠️ 기술 스택

### Backend
- **Python 3.8+**
- **LM Studio**: 로컬 LLM 모델 서빙 (EXAONE-3.5-7.8B-Instruct)
- **PostgreSQL + pgvector**: 메인 데이터베이스 및 벡터 검색
- **LangChain**: LLM 체인 관리 및 문서 처리
- **TensorFlow/Keras**: LSTM 수위 예측 모델
- **PySerial**: 아두이노 USB 시리얼 통신
- **Sentence Transformers**: 임베딩 모델

### Frontend
- **Streamlit**: 웹 인터페이스
- **nest_asyncio**: 비동기 처리 지원

### 외부 API
- **Tavily API**: 웹 검색 서비스
- **OpenWeatherMap API**: 날씨 정보 조회
- **OpenAI API**: 텍스트 임베딩 생성

## 🔧 사용 가능한 도구

### 1. 웹 검색 도구 (`WebSearchTool`)
- Tavily API를 통한 실시간 웹 정보 검색
- 최신 뉴스, 일반 상식, 트렌드 정보 제공
- 기본 3개 결과 반환
- **예시**: "최신 AI 트렌드 알려줘"

### 2. 계산기 도구 (`CalculatorTool`)
- 안전한 수학 표현식 평가 (`_safe_eval`)
- 수학 함수 지원 (sqrt, sin, cos, tan, log, pi, e)
- 보안 검증으로 안전하지 않은 함수 호출 차단
- 6자리 반올림 처리
- **예시**: "sqrt(144) + sin(pi/2) 계산해줘"

### 3. 날씨 도구 (`WeatherTool`)
- OpenWeatherMap Current Weather API 연동
- 온도, 습도, 기압, 풍속, 구름량, 강수량 등 상세 기상 데이터
- 위도/경도, 국가, 타임존, 일출/일몰, 가시거리, 이슬점 정보
- 모의 데이터 모드 지원
- **예시**: "서울 날씨 상세히 알려줘"

### 4. 벡터 검색 도구 (`VectorSearchTool`)
- PostgreSQL + pgvector 기반 의미 검색
- OpenAI 임베딩 모델 사용
- 파일 필터링 및 태그 필터링
- L2 거리 기반 유사도 계산
- PDF, TXT, DOCX 문서 지원
- **예시**: "업로드한 문서에서 AI 관련 내용 찾아줘"

### 5. 파일 목록 도구 (`ListFilesTool`)
- PostgreSQL에 저장된 파일 목록 조회
- 파일명, 크기, 업로드 날짜 정보 제공
- **예시**: "업로드된 파일 목록 보여줘"

### 6. 아두이노 수위센서 도구 (`ArduinoWaterSensorTool`)
- USB 시리얼 통신 (pyserial, 115200 baud)
- 실시간 수위 센서 값 읽기
- 2개 펌프 개별 제어 (pump1, pump2)
- 펌프 상태 실시간 모니터링
- WSL2 환경에서 usbipd-win 지원
- 아두이노 Mega 2560 최적화, 자동 포트 감지
- **지원 액션**: read_water_level, pump1_on/off, pump2_on/off, connect, status, test_communication
- **예시**: "수위 센서 값 읽어줘", "펌프1 켜줘", "아두이노 연결 상태 확인해줘"

### 7. LSTM 수위 예측 도구 (`WaterLevelPredictionTool`)
- TensorFlow/Keras 기반 LSTM 딥러닝 모델
- 학습된 모델 파일: `lstm_model/lstm_water_level_model.h5`
- 60개 시계열 데이터 입력으로 미래 수위 예측
- 슬라이딩 윈도우 방식 다중 스텝 예측
- 데이터 자동 변환 및 정제, 정규화/역정규화 처리
- 6자리 정밀도, 텍스트에서 데이터 자동 추출
- **예시**: "수위 예측해줘", "[10.5, 11.2, 12.1] 데이터로 다음 30분 수위 예측해줘"

## 📁 프로젝트 구조

```
agentic_rag_good/
├── app.py                              # Streamlit 메인 애플리케이션
├── config.py                           # 환경변수 기반 시스템 설정
├── requirements.txt                    # Python 패키지 의존성
├── core/                              # 핵심 시스템 아키텍처
│   ├── orchestrator.py                # 전체 시스템 오케스트레이션 (Orchestrator)
│   ├── query_analyzer.py              # 사용자 쿼리 분석 및 도구 선택 (QueryAnalyzer)
│   ├── response_generator.py          # 최종 응답 생성 (ResponseGenerator)
│   └── tool_manager.py                # 8개 도구 동적 등록 및 실행 (ToolManager)
├── models/                            # LLM 클라이언트
│   └── lm_studio.py                   # LM Studio API 클라이언트 (LMStudioClient)
├── tools/                             # 8가지 전문 도구 구현
│   ├── arduino_water_sensor_tool.py   # 아두이노 수위센서 및 펌프제어
│   ├── calculator_tool.py             # 수학 계산기
│   ├── list_files_tool.py            # 파일 목록 조회
│   ├── search_tool.py                 # 웹 검색
│   ├── vector_search_tool.py          # 벡터 검색
│   ├── water_level_prediction_tool.py # LSTM 수위 예측
│   └── weather_tool.py                # 날씨 조회
├── lstm_model/                        # 딥러닝 모델
│   └── lstm_water_level_model.h5      # 학습된 LSTM 수위 예측 모델
├── storage/                           # 데이터 저장소
│   └── postgresql_storage.py          # PostgreSQL + pgvector 연동
├── retrieval/                         # 문서 처리
│   └── document_loader.py             # 문서 로더 및 청크 분할
├── utils/                             # 유틸리티
│   ├── helpers.py                     # 헬퍼 함수들
│   └── logger.py                      # 로깅 시스템
└── img/                               # 시스템 스크린샷
    ├── 도구_목록.png
    ├── 시스템_초기_화면.png
    └── 시스템_초기화_후.png
```

## 🚀 설치 및 실행

### 1. 환경 설정

```bash
# 저장소 클론
git clone <repository-url>
cd agentic_rag_good

# 가상환경 생성 (선택사항)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

### 2. 환경변수 설정

`.env` 파일을 생성하고 다음과 같이 구성:

```env
# LM Studio 설정
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_API_KEY=lm-studio
LM_STUDIO_MODEL_NAME=exaone-3.5-7.8b-instruct

# 외부 API 키
TAVILY_API_KEY=your_tavily_api_key
WEATHER_API_KEY=your_openweathermap_api_key
OPENAI_API_KEY=your_openai_api_key

# PostgreSQL 설정
PG_DB_HOST=localhost
PG_DB_PORT=5432
PG_DB_NAME=synergy
PG_DB_USER=synergy
PG_DB_PASSWORD=synergy

# 시스템 설정
DEBUG_MODE=false
ENABLED_TOOLS=search_tool,calculator_tool,weather_tool,list_files_tool,vector_search_tool,arduino_water_sensor,water_level_prediction_tool
```

### 3. PostgreSQL 설정

```sql
-- 데이터베이스 및 사용자 생성
CREATE DATABASE synergy;
CREATE USER synergy WITH PASSWORD 'synergy';
GRANT ALL PRIVILEGES ON DATABASE synergy TO synergy;

-- pgvector 확장 설치
CREATE EXTENSION IF NOT EXISTS vector;
```

### 4. LM Studio 설정

1. [LM Studio](https://lmstudio.ai/) 다운로드 및 설치
2. EXAONE-3.5-7.8B-Instruct 모델 다운로드
3. 로컬 서버 시작 (기본 포트: 1234)

### 5. 아두이노 설정 (선택사항)

#### 기본 설정
1. 아두이노에 수위센서 및 펌프 제어 코드 업로드
2. USB 케이블로 아두이노와 컴퓨터 연결
3. 시리얼 포트 권한 설정: `sudo usermod -a -G dialout $USER`

#### WSL2 환경 (Windows)
1. Windows에 usbipd-win 설치
2. USB 디바이스를 WSL2로 포워딩:
   ```bash
   # Windows PowerShell (관리자 권한)
   usbipd wsl list
   usbipd wsl attach --busid <busid>
   
   # WSL2에서 확인
   lsusb
   ls /dev/ttyACM*
   ```

### 6. 애플리케이션 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속

## 💡 사용 방법

### 기본 사용법

1. 웹 브라우저에서 `http://localhost:8501` 접속
2. 사이드바에서 "🔄 시스템 초기화" 버튼 클릭
3. 채팅창에 질문 입력

### 예시 명령어

#### 단일 도구 사용
```
# 웹 검색
"최신 AI 트렌드 검색해줘"
"파이썬 머신러닝 최신 뉴스 찾아줘"

# 계산기
"sqrt(144) + sin(pi/2) 계산해줘"
"log(100) * cos(0) 값은?"

# 날씨 조회
"서울 날씨 상세히 알려줘"
"부산 현재 기상 상태는?"

# 아두이노 수위센서 및 펌프 제어
"수위 센서 값 읽어줘"
"펌프1 켜줘"
"펌프2 꺼줘"
"아두이노 연결 상태 확인해줘"
"모든 펌프 상태 확인해줘"

# LSTM 수위 예측
"수위 예측해줘"
"[10.5, 11.2, 12.1, 13.0, 12.8] 데이터로 다음 30분 수위 예측해줘"
"수위 모델 상태 확인해줘"

# 파일 및 벡터 검색
"업로드된 파일 목록 보여줘"
"문서에서 AI 관련 내용 검색해줘"
"보고서에서 매출 정보 찾아줘"
```

#### 복합 명령어 (멀티 도구 동시 실행)
```
"서울 날씨와 2+2 계산해줘"
"펌프1 켜주고 수위 센서 값 읽어줘"
"최신 AI 뉴스 검색하고 현재 온도 알려줘"
"펌프 상태 확인하고 수위 예측해줘"
```

### 파일 업로드 및 벡터 검색

1. 우측 사이드바의 "📤 파일 업로드" 섹션 사용
2. 지원 형식: PDF, TXT, DOCX, XLSX, PNG, JPG 등
3. 업로드된 파일은 자동으로 청크 분할 및 벡터화
4. OpenAI 임베딩으로 의미 검색 가능

## 🎯 시스템 아키텍처

### 처리 플로우
```
사용자 요청
    ↓
QueryAnalyzer (LLM 기반 쿼리 분석)
    ↓
ToolManager (8개 도구 중 필요한 도구 선택 및 실행)
    ↓
ResponseGenerator (결과 통합 및 자연어 응답 생성)
    ↓
Streamlit UI (결과 표시)
```

### 핵심 컴포넌트

1. **Orchestrator**: 전체 시스템 조율, 비동기/동기 처리 지원
2. **QueryAnalyzer**: LLM 기반 도구 선택, JSON 파싱
3. **ToolManager**: 8개 도구 동적 등록 및 병렬 실행
4. **ResponseGenerator**: 멀티 도구 결과 통합 및 자연어 응답 생성

## 🔒 보안 고려사항

- **계산기 도구**: 안전한 수학 표현식만 처리, 위험한 함수 호출 차단
- **API 키 관리**: 환경변수로 분리, 코드에 하드코딩 금지
- **파일 업로드**: 타입 검증 및 크기 제한
- **PostgreSQL**: 연결 보안 설정 및 SQL 인젝션 방지
- **아두이노 통신**: 시리얼 포트 권한 관리

## 🛟 문제해결

### 자주 발생하는 문제

#### 1. LM Studio 연결 오류
- LM Studio가 실행 중인지 확인
- 포트 번호 (1234) 및 모델 로드 상태 확인
- 방화벽 설정 확인

#### 2. PostgreSQL 연결 오류
- PostgreSQL 서비스 실행 상태 확인
- 데이터베이스 및 사용자 권한 확인
- pgvector 확장 설치 여부 확인

#### 3. 아두이노 연결 오류
- USB 케이블 연결 상태 확인
- 시리얼 포트 권한 설정: `sudo usermod -a -G dialout $USER`
- WSL2에서 usbipd-win USB 포워딩 확인
- 아두이노 IDE에서 시리얼 모니터로 통신 테스트

#### 4. LSTM 모델 오류
- `lstm_model/lstm_water_level_model.h5` 파일 존재 확인
- TensorFlow 버전 호환성 확인
- 입력 데이터 형식 (60개 시계열 데이터) 확인

#### 5. API 키 오류
- `.env` 파일의 API 키 확인
- Tavily, OpenWeatherMap, OpenAI 계정 상태 및 사용량 확인

## 📈 향후 계획

- [ ] **IoT 확장**: 더 많은 센서 지원 (온도, 습도, pH, 유량계 등)
- [ ] **실시간 대시보드**: 센서 데이터 실시간 모니터링 및 시각화
- [ ] **딥러닝 모델 개선**: 더 정교한 수위 예측 모델 및 다변수 예측
- [ ] **알림 시스템**: 임계값 기반 자동 알림 (이메일, SMS, 푸시)
- [ ] **모바일 앱**: React Native 기반 모바일 제어 앱
- [ ] **클라우드 연동**: AWS IoT Core, Azure IoT Hub 연동
- [ ] **사용자 관리**: 멀티 사용자 인증 및 권한 관리
- [ ] **REST API**: 외부 시스템 연동을 위한 API 제공
- [ ] **다국어 지원**: 영어, 중국어, 일본어 지원
- [ ] **성능 최적화**: 캐싱, 배치 처리, 로드 밸런싱

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 있습니다.

## 👥 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📞 문의사항

프로젝트 관련 문의사항이나 버그 리포트는 이슈로 등록해 주세요.

---

> **AgenticRAG**는 AI, IoT, 웹 서비스를 통합한 차세대 지능형 멀티모달 챗봇 플랫폼입니다.
> 하나의 대화형 인터페이스에서 하드웨어 제어부터 딥러닝 예측까지 모든 것을 제공합니다.