# AgenticRAG - AI 기반 멀티 도구 챗봇 시스템

## 📌 프로젝트 개요

AgenticRAG는 LM Studio와 PostgreSQL을 기반으로 한 지능형 챗봇 시스템으로, 다양한 도구를 활용하여 사용자 요청을 자동으로 분석하고 처리합니다. 웹 검색, 계산, 날씨 조회, 아두이노 수위센서 제어, LSTM 수위 예측, 펌프 제어, 문서 벡터 검색 등 여러 기능을 하나의 대화형 인터페이스에서 제공합니다.

## ⚡ 주요 기능

- **🔍 웹 검색**: Tavily API를 통한 실시간 웹 정보 검색
- **🧮 계산기**: 수학 연산, 단위 변환, 공식 계산
- **🌤️ 날씨 조회**: 전 세계 도시의 실시간 날씨 정보
- **💧 아두이노 수위센서**: USB 시리얼 통신을 통한 실시간 수위 센서 값 읽기
- **📈 LSTM 수위 예측**: 딥러닝 모델을 활용한 수위 예측 시스템
- **⚙️ 펌프 제어**: 가상 펌프 장치의 ON/OFF 제어 시뮬레이션
- **🔎 벡터 검색**: 업로드된 문서에서 의미 기반 검색
- **📂 파일 관리**: PostgreSQL 기반 파일 업로드, 저장, 다운로드
- **💬 자연어 처리**: 복합 요청 자동 분석 및 멀티 도구 실행

## 🛠️ 기술 스택

### Backend
- **Python 3.8+**
- **LM Studio**: 로컬 LLM 모델 서빙 (EXAONE-3.5-7.8B-Instruct)
- **PostgreSQL**: 메인 데이터베이스 및 벡터 검색 (pgvector)
- **LangChain**: LLM 체인 관리 및 문서 처리
- **TensorFlow/Keras**: LSTM 수위 예측 모델 
- **PySerial**: 아두이노 시리얼 통신
- **FastAPI**: API 서버 (선택적)

### Frontend
- **Streamlit**: 웹 인터페이스
- **HTML/CSS**: 사용자 친화적 UI 스타일링

### 외부 API
- **Tavily API**: 웹 검색 서비스
- **OpenWeatherMap API**: 날씨 정보 조회

## 🔧 사용 가능한 도구

### 1. 웹 검색 도구 (search_tool)
- Tavily API를 통한 실시간 웹 정보 검색
- 최신 뉴스, 일반 상식, 트렌드 정보 제공
- 예시: "최신 AI 트렌드 알려줘"

### 2. 계산기 도구 (calculator_tool)
- 수학 연산, 공식 계산
- 단위 변환 지원
- 예시: "123 * 45 계산해줘"

### 3. 날씨 도구 (weather_tool)
- OpenWeatherMap API 연동
- 전 세계 도시별 실시간 날씨 정보
- 예시: "서울 날씨 알려줘"

### 4. 벡터 검색 도구 (vector_search_tool)
- PostgreSQL + pgvector 기반
- 업로드된 문서에서 의미 기반 검색
- 예시: "업로드한 문서에서 AI 관련 내용 찾아줘"

### 5. 파일 목록 도구 (list_files_tool)
- PostgreSQL에 저장된 파일 목록 조회
- 파일 정보 및 메타데이터 제공
- 예시: "업로드된 파일 목록 보여줘"

### 6. 아두이노 수위센서 도구 (arduino_water_sensor_tool)
- USB 시리얼 통신을 통한 아두이노 연동
- 실시간 수위 센서 값 읽기 및 펌프 제어
- WSL2 환경에서 usbipd-win 지원
- 예시: "수위 센서 값 읽어줘", "펌프1 켜줘"

### 7. LSTM 수위 예측 도구 (water_level_prediction_tool)  
- TensorFlow/Keras 기반 LSTM 딥러닝 모델
- 과거 수위 데이터를 기반으로 미래 수위 예측
- 학습된 모델(.h5)을 활용한 실시간 예측
- 예시: "수위 예측해줘", "다음 10분간 수위 변화 예측해줘"

### 8. 펌프 제어 도구 (pump_control_tool)
- 가상 펌프 장치 제어 시뮬레이션
- 개별/전체 펌프 ON/OFF 제어
- 예시: "펌프1 켜줘", "모든 펌프 상태 확인해줘"

## 📁 프로젝트 구조

```
agentic_rag_good/
├── app.py                 # Streamlit 메인 애플리케이션
├── config.py             # 환경 설정 및 도구 정의
├── requirements.txt      # Python 패키지 의존성
├── core/                 # 핵심 시스템 로직
│   ├── orchestrator.py   # 전체 시스템 오케스트레이션
│   ├── query_analyzer.py # 사용자 쿼리 분석 및 도구 선택
│   ├── response_generator.py # 최종 응답 생성
│   └── tool_manager.py   # 도구 실행 관리
├── models/               # LLM 클라이언트
│   └── lm_studio.py     # LM Studio API 클라이언트
├── tools/                # 개별 도구 구현
│   ├── search_tool.py   # 웹 검색 도구
│   ├── calculator_tool.py # 계산기 도구
│   ├── weather_tool.py  # 날씨 조회 도구
│   ├── vector_search_tool.py # 벡터 검색 도구
│   ├── list_files_tool.py # 파일 목록 조회 도구
│   ├── arduino_water_sensor_tool.py # 아두이노 수위센서 도구
│   ├── water_level_prediction_tool.py # LSTM 수위 예측 도구
│   └── pump_control_tool.py # 펌프 제어 도구
├── lstm_model/           # LSTM 모델 파일
│   └── lstm_water_level_model.h5 # 학습된 LSTM 수위 예측 모델
├── storage/              # 데이터 저장소
│   └── postgresql_storage.py # PostgreSQL 연동
├── retrieval/            # 문서 처리
│   └── document_loader.py # 문서 로더
├── utils/                # 유틸리티
│   ├── logger.py        # 로깅 설정
│   └── helpers.py       # 헬퍼 함수
└── img/                  # 스크린샷 및 이미지
    ├── 도구_목록.png
    ├── 시스템_초기_화면.png
    └── 시스템_초기화_후.png
```

## 🚀 설치 및 실행

### 1. 환경 설정

```bash
# 저장소 클론
git clone <repository-url>
cd agentic_rag

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
ENABLED_TOOLS=search_tool,calculator_tool,weather_tool,list_files_tool,vector_search_tool,arduino_water_sensor_tool,water_level_prediction_tool,pump_control_tool
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

1. 아두이노에 수위센서 및 펌프 제어 코드 업로드
2. USB 케이블로 아두이노와 컴퓨터 연결
3. WSL2 사용 시 usbipd-win 설치 및 USB 포워딩 설정
4. 시리얼 포트 권한 설정: `sudo usermod -a -G dialout $USER`

### 6. 애플리케이션 실행

```bash
streamlit run app.py
```

## 💡 사용 방법

### 기본 사용법

1. 웹 브라우저에서 `http://localhost:8501` 접속
2. 사이드바에서 "🔄 시스템 초기화" 버튼 클릭
3. 채팅창에 질문 입력

### 예시 명령어

```
# 단일 도구 사용
"서울 날씨 알려줘"
"1+1 계산해줘"
"최신 AI 트렌드 검색해줘"

# 복합 명령어
"서울 날씨와 2+2 계산해줘"
"펌프1 켜주고 부산 날씨 알려줘"
"Python 검색하고 10*5 계산해줘"

# 아두이노 수위센서 및 펌프 제어
"수위 센서 값 읽어줘"
"펌프1 켜줘"
"펌프2 꺼줘"
"모든 펌프 상태 확인해줘"

# LSTM 수위 예측
"수위 예측해줘"
"다음 10분간 수위 변화 예측해줘"
"수위 모델 상태 확인해줘"

# 파일 검색 (업로드된 문서에서)
"보고서에서 매출 정보 찾아줘"
"문서에서 AI 관련 내용 검색해줘"
```

### 파일 업로드

1. 우측 사이드바의 "📤 파일 업로드" 섹션 사용
2. 지원 형식: PDF, TXT, XLSX, PNG, JPG 등
3. 업로드된 파일은 자동으로 벡터화되어 검색 가능

## 🎯 시스템 아키텍처

```
사용자 요청
    ↓
Query Analyzer (쿼리 분석)
    ↓
Tool Manager (도구 실행)
    ↓
Response Generator (응답 생성)
    ↓
Streamlit UI (결과 표시)
```

### 처리 플로우

1. **쿼리 분석**: LLM이 사용자 요청을 분석하여 필요한 도구 선택
2. **도구 실행**: 선택된 도구들을 순차/병렬로 실행
3. **결과 통합**: 각 도구의 실행 결과를 종합
4. **응답 생성**: LLM이 최종 사용자 친화적 응답 생성

## 🔒 보안 고려사항

- 계산기 도구는 안전한 수학 표현식만 처리
- API 키는 환경변수로 관리
- 파일 업로드 시 타입 검증
- PostgreSQL 연결 보안 설정

## 🛟 문제해결

### 자주 발생하는 문제

1. **LM Studio 연결 오류**
   - LM Studio가 실행 중인지 확인
   - 포트 번호 (1234) 확인
   - 모델이 로드되었는지 확인

2. **PostgreSQL 연결 오류**
   - PostgreSQL 서비스 실행 상태 확인
   - 데이터베이스 및 사용자 권한 확인
   - pgvector 확장 설치 여부 확인

3. **API 키 오류**
   - `.env` 파일의 API 키 확인
   - Tavily, OpenWeatherMap 계정 상태 확인

## 📈 향후 계획

- [ ] 더 많은 IoT 센서 지원 (온도, 습도, pH 등)
- [ ] 실시간 데이터 대시보드 구축
- [ ] 더 정교한 수위 예측 모델 개발
- [ ] 모바일 알림 시스템 연동
- [ ] 대화 히스토리 관리
- [ ] 사용자 인증 시스템
- [ ] REST API 제공
- [ ] 멀티 언어 지원
- [ ] 성능 최적화

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