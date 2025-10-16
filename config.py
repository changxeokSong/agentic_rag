# config.py - 환경변수를 활용한 시스템 설정

import os
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from langchain_teddynote import logging
from utils.exceptions import ConfigurationError

# .env 파일 로드
load_dotenv()

# 프로젝트 이름을 입력합니다.
logging.langsmith("AgenticRAG")

# 시스템 상수
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_TOP_K_RESULTS = 5
DEFAULT_MAX_TOKENS = 2048
DEFAULT_REQUEST_TIMEOUT = 45
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
DEFAULT_TOOL_SELECTION_TEMP = 0.0
DEFAULT_RESPONSE_TEMP = 0.7
MIN_PORT = 1
MAX_PORT = 65535

# LM Studio 설정
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "lm-studio")
LM_STUDIO_MODEL_NAME = os.getenv("LM_STUDIO_MODEL_NAME", "exaone-4.0.1-32b")

# 온도(temperature) 설정
TOOL_SELECTION_TEMPERATURE = float(os.getenv("TOOL_SELECTION_TEMPERATURE", str(DEFAULT_TOOL_SELECTION_TEMP)))
RESPONSE_TEMPERATURE = float(os.getenv("RESPONSE_TEMPERATURE", str(DEFAULT_RESPONSE_TEMP)))

# 성능 최적화 설정
MAX_TOKENS = int(os.getenv("MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))  # 응답 길이 제한
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", str(DEFAULT_REQUEST_TIMEOUT)))  # API 요청 타임아웃

# RAG 설정
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./vector_db")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", str(DEFAULT_CHUNK_SIZE)))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", str(DEFAULT_CHUNK_OVERLAP)))
TOP_K_RESULTS = int(os.getenv("TOP_K_RESULTS", str(DEFAULT_TOP_K_RESULTS)))

# 임베딩 백엔드/모델 설정
OPENAI_API_KEY_ENV_VAR = "OPENAI_API_KEY"
EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "HF").upper()  # OPENAI | HF
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "dragonkue/BGE-m3-ko")
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")  # HF 사용 시 device 지정
HUGGINGFACEHUB_API_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN", None)

# 로깅 설정
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# 시스템 설정
def _get_int_env(key: str, default: str) -> int:
    """환경변수를 안전하게 정수로 변환

    Args:
        key: 환경변수 키
        default: 기본값 (문자열)

    Returns:
        int: 변환된 정수값

    Raises:
        ConfigurationError: 기본값도 정수로 변환할 수 없는 경우
    """
    try:
        value = os.getenv(key, default)
        return int(value)
    except ValueError as e:
        logging.warning(f"잘못된 환경변수 값 {key}={os.getenv(key)}, 기본값 {default} 사용")
        try:
            return int(default)
        except ValueError:
            raise ConfigurationError(
                f"환경변수 {key}의 기본값 {default}을(를) 정수로 변환할 수 없습니다.",
                {"key": key, "value": os.getenv(key), "default": default}
            ) from e

MAX_RETRIES = _get_int_env("MAX_RETRIES", str(DEFAULT_MAX_RETRIES))
TIMEOUT = _get_int_env("TIMEOUT", str(DEFAULT_TIMEOUT))

DATABASE_NAME = os.getenv("DATABASE_NAME", "document")

ENABLED_TOOLS = [tool.strip() for tool in os.getenv("ENABLED_TOOLS", "vector_search_tool,list_files_tool,prediction_tool,arduino_water_sensor,water_level_monitoring_tool,real_time_database_control_tool,advanced_water_analysis_tool,automation_control_tool").split(",") if tool.strip()]

# PostgreSQL configuration
PG_DB_HOST = os.getenv("PG_DB_HOST", "localhost")
PG_DB_PORT = _get_int_env("PG_DB_PORT", "5432")
PG_DB_NAME = os.getenv("PG_DB_NAME", "synergy")
PG_DB_USER = os.getenv("PG_DB_USER", "synergy")
PG_DB_PASSWORD = os.getenv("PG_DB_PASSWORD", "synergy")


def validate_config() -> bool:
    """설정 검증

    시스템 설정값의 유효성을 검증합니다.

    Returns:
        bool: 검증 성공 여부

    Raises:
        ConfigurationError: 필수 설정이 누락되었거나 잘못된 경우
    """
    # 필수 환경변수 검증
    required_vars = ["LM_STUDIO_BASE_URL", "EMBEDDING_MODEL_NAME"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logging.warning(f"필수 환경변수가 설정되지 않음: {missing_vars}")

    # PostgreSQL 포트 검증
    if not (MIN_PORT <= PG_DB_PORT <= MAX_PORT):
        raise ConfigurationError(
            f"잘못된 PostgreSQL 포트: {PG_DB_PORT}",
            {"port": PG_DB_PORT, "valid_range": f"{MIN_PORT}-{MAX_PORT}"}
        )

    # Temperature 값 검증
    if not (0.0 <= TOOL_SELECTION_TEMPERATURE <= 2.0):
        raise ConfigurationError(
            f"잘못된 TOOL_SELECTION_TEMPERATURE 값: {TOOL_SELECTION_TEMPERATURE}",
            {"value": TOOL_SELECTION_TEMPERATURE, "valid_range": "0.0-2.0"}
        )

    if not (0.0 <= RESPONSE_TEMPERATURE <= 2.0):
        raise ConfigurationError(
            f"잘못된 RESPONSE_TEMPERATURE 값: {RESPONSE_TEMPERATURE}",
            {"value": RESPONSE_TEMPERATURE, "valid_range": "0.0-2.0"}
        )

    # CHUNK_SIZE 검증
    if CHUNK_SIZE <= 0:
        raise ConfigurationError(
            f"CHUNK_SIZE는 양수여야 합니다: {CHUNK_SIZE}",
            {"value": CHUNK_SIZE}
        )

    if CHUNK_OVERLAP >= CHUNK_SIZE:
        raise ConfigurationError(
            f"CHUNK_OVERLAP({CHUNK_OVERLAP})은 CHUNK_SIZE({CHUNK_SIZE})보다 작아야 합니다",
            {"chunk_size": CHUNK_SIZE, "chunk_overlap": CHUNK_OVERLAP}
        )

    # TOP_K_RESULTS 검증
    if TOP_K_RESULTS <= 0:
        raise ConfigurationError(
            f"TOP_K_RESULTS는 양수여야 합니다: {TOP_K_RESULTS}",
            {"value": TOP_K_RESULTS}
        )

    return True

def get_available_functions() -> List[Dict[str, Any]]:
    """환경변수에 따라 활성화된 도구만 반환"""
    all_functions = [
        {
            "name": "water_level_monitoring_tool",
            "description": "📊 수위 모니터링 도구입니다. DB에 저장된 과거 데이터를 조회하거나 현재 상태를 확인합니다. 자연어 질문 예시: '현재 수위 보여줘', '24시간 수위 그래프 그려줘', '지난 12시간 수위 데이터', '가곡 상태 알려줘', '수위 현황 확인'",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["current_status", "historical_data", "generate_graph", "add_sample_data"],
                        "description": "실행할 액션 - current_status: 현재 수위 상태 조회, historical_data: 과거 데이터 조회, generate_graph: 그래프 생성, add_sample_data: 테스트 데이터 추가"
                    },
                    "hours": {
                        "type": "integer",
                        "description": "과거 데이터 조회 시간 범위 (시간 단위, 기본값: 24시간, 최대: 168시간)",
                        "default": 24
                    }
                },
                "required": ["action"]
            }
        },
        {
            "name": "arduino_water_sensor",
            "description": "🔧 아두이노 하드웨어 직접 제어 도구입니다 (실시간). 자연어 질문 예시: '펌프1 켜줘', '펌프2 꺼줘', '펌프 상태 확인', '아두이노 연결해줘'. 주의: DB 기반 수위 조회는 water_level_monitoring_tool 사용",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read_water_level", "read_water_level_channel", "read_current_level", "pump1_on", "pump1_off", "pump2_on", "pump2_off", "connect", "disconnect", "status", "test_communication", "pump_status", "read_pump_status"],
                        "description": "실행할 액션 - 센서 읽기, 펌프 제어, 연결 관리"
                    },
                    "channel": {
                        "type": "integer",
                        "description": "센서 채널 번호 (0-7)",
                        "minimum": 0,
                        "maximum": 7
                    },
                    "port": {
                        "type": "string",
                        "description": "시리얼 포트 (예: COM3, /dev/ttyUSB0). 자동 감지 가능"
                    },
                    "duration": {
                        "type": "integer",
                        "description": "펌프 작동 시간 (초, 1-300)",
                        "minimum": 1,
                        "maximum": 300
                    }
                },
                "required": ["action"]
            }
        },
        {
            "name": "smart_water_prediction",
            "description": "🔮 미래 수위 예측 도구입니다. DB에서 자동으로 최신 데이터를 가져와 예측합니다. 자연어 질문 예시: '점심 먹을 때쯤 수위가 어떻게 될까?', '가곡 30분 후 수위는?', '해룡 1시간 뒤 예측해줘', '가곡 언제 100m 도달해?', '저녁때 수위 알려줘'. time_expression 파라미터로 '점심', '30분 후', '1시간 후' 등 자연어 시간 표현 지원.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reservoir": {
                        "type": "string",
                        "enum": ["gagok", "haeryong", "가곡", "해룡"],
                        "description": "예측할 배수지 (가곡 또는 해룡)"
                    },
                    "time_minutes": {
                        "type": "integer",
                        "description": "예측 시간 (분 단위). 예: 1, 5, 30, 60, 360. target_level이 설정되지 않은 경우 사용"
                    },
                    "target_level": {
                        "type": "number",
                        "description": "목표 수위 (m 단위). 예: 100m 도달 시간을 알고 싶으면 100 입력. 설정 시 time_minutes는 무시됨"
                    },
                    "lookback_hours": {
                        "type": "integer",
                        "description": "과거 데이터 조회 시간 (시간 단위, 기본값: 24시간)",
                        "default": 24
                    }
                },
                "required": ["reservoir"]
            }
        },
        {
            "name": "water_level_prediction_tool",
            "description": "🧮 사용자가 직접 제공한 수위 데이터를 기반으로 LSTM 딥러닝 모델로 미래 수위를 예측하는 도구입니다. (DB 자동 조회가 아닌 수동 데이터 입력용)",
            "parameters": {
                "type": "object",
                "properties": {
                    "water_levels": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "과거 수위 데이터 배열"
                    },
                    "prediction_steps": {
                        "type": "integer",
                        "description": "예측할 스텝 수",
                        "default": 1
                    }
                },
                "required": ["water_levels"]
            }
        },
        {
            "name": "advanced_water_analysis_tool",
            "description": "📈 고급 수위 분석 도구입니다. 예시 질문: '지금 속도로 올라가면 언제 경보 수위 넘길까?', '어제 펌프 돌았나?', '어제 오전이랑 오후 수위 추세 비교해줘', '어느 쪽이 더 안정적이었어?', '현재 수위 상승 속도는?'",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["current_trend", "predict_alert", "simulate_pump", "compare_periods", "pump_history", "parse_time"],
                        "description": "실행할 액션"
                    },
                    "reservoir_id": {
                        "type": "string",
                        "enum": ["gagok", "haeryong", "sangsa"],
                        "description": "배수지 ID (기본값: gagok)",
                        "default": "gagok"
                    },
                    "hours": {
                        "type": "integer",
                        "description": "분석 시간 범위 또는 펌프 이력 조회 시간 (기본값: 24시간)"
                    },
                    "alert_threshold": {
                        "type": "number",
                        "description": "경보 수위 임계값 (기본값: 100cm)",
                        "default": 100.0
                    },
                    "pump_flow_rate": {
                        "type": "number",
                        "description": "펌프 유량 (기본값: 10 cm/hour)",
                        "default": 10.0
                    },
                    "time_expression": {
                        "type": "string",
                        "description": "시간 표현 (예: '어제', '오늘', '지난주', '이번주'). compare_periods 액션에서 기간 비교 시 사용. '어제 오전/오후', '오늘 오전/오후' 등으로 사용 가능"
                    }
                },
                "required": ["action"]
            }
        },
        {
            "name": "automation_control_tool",
            "description": "🤖 AI 자동화 에이전트 제어 도구입니다. 자연어 질문 예시: '자동화 시작해줘', '시스템 상태 보여줘', '최근 로그 50개', 'Arduino 연결 확인', '자동화 중지해줘'",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "status", "debug_arduino", "test_arduino_connection", "get_logs"],
                        "description": "실행할 액션"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "로그 조회 개수 (기본값: 50)",
                        "default": 50
                    },
                    "level": {
                        "type": "string",
                        "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        "description": "로그 레벨 필터",
                        "default": "INFO"
                    },
                    "reservoir_id": {
                        "type": "string",
                        "description": "특정 배수지 로그만 조회"
                    }
                },
                "required": ["action"]
            }
        },
        {
            "name": "real_time_database_control_tool",
            "description": "⏱️ 실시간 데이터 수집 서비스를 제어하는 도구입니다. 아두이노에서 자동으로 데이터를 수집하여 DB에 저장합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "status", "manual_collect", "restart"],
                        "description": "실행할 액션"
                    },
                    "update_interval": {
                        "type": "integer",
                        "description": "수집 간격 (초, 기본값: 60초, 범위: 10-3600)",
                        "default": 60
                    }
                },
                "required": ["action"]
            }
        },
        {
            "name": "vector_search_tool",
            "description": "🔍 업로드된 문서에서 벡터 기반 검색을 수행하는 도구입니다. PDF, 텍스트 파일에서 의미 기반 검색을 합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색 질의문"
                    },
                    "file_filter": {
                        "type": "string",
                        "description": "특정 파일 이름 필터"
                    },
                    "tags_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "태그 배열로 필터링"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "반환할 최대 결과 개수 (기본값: 5)",
                        "default": 5
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["auto", "vector", "context"],
                        "description": "검색 모드 (기본값: auto)",
                        "default": "auto"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "list_files_tool",
            "description": "📁 업로드된 파일 목록을 조회하는 도구입니다. 파일명, 크기, 업로드 시간 등을 확인할 수 있습니다.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    ]
    return [func for func in all_functions if func["name"] in ENABLED_TOOLS]

# 사용 가능한 함수 목록
AVAILABLE_FUNCTIONS = get_available_functions()

def generate_function_selection_prompt() -> str:
    """활성화된 도구에 따라 프롬프트 템플릿 생성

    Returns:
        str: 생성된 프롬프트 템플릿
    """
    # 개선된 프롬프트 - 더 명확한 지시사항과 예시
    prompt = f"""당신은 사용자의 자연어 질문을 정확히 이해하고 적절한 도구를 선택하는 고도로 지능적인 AI 어시스턴트입니다.

핵심 지침:
1. **의도 파악 우선**: 사용자의 진짜 의도를 파악하세요. 키워드 매칭이 아닌 의미적 이해가 중요합니다.
2. **한국어 자연어 처리**: "점심때", "30분 후", "1시간 뒤" 같은 시간 표현을 정확히 해석하세요.
3. **데이터베이스 우선**: 현재/최신 데이터 조회는 DB 기반 도구를 사용하세요.
4. **컨텍스트 이해**: 질문의 맥락을 파악하여 적절한 도구와 파라미터를 선택하세요.

도구 선택 예시:
- "현재 가곡 수위 상태" → advanced_water_analysis_tool(action="current_trend", reservoir_id="gagok", hours=1)
- "지금 속도로 올라가면 언제 경보 수위 넘길까?" → advanced_water_analysis_tool(action="predict_alert")
- "점심 먹을 때쯤 수위 어떻게 될까?" → smart_water_prediction(reservoir="gagok", time_expression="점심")
- "어제 펌프 돌았나?" → advanced_water_analysis_tool(action="pump_history", time_expression="어제")
- "어제 오전이랑 오후 비교해줘" → advanced_water_analysis_tool(action="compare_periods", time_expression="어제")
- "파일 목록 보여줘" → list_files_tool()
- "아두이노 연결해줘" → arduino_water_sensor(action="connect")

응답 형식: JSON 배열로 도구 호출을 반환하세요. 도구가 필요 없으면 []를 반환하세요.

**사용 가능한 도구:**
```json
{json.dumps(AVAILABLE_FUNCTIONS, indent=2, ensure_ascii=False)}
```

중요: 사용자의 의도와 각 도구 설명의 예시 질문에 집중하세요. 키워드가 아닌 의미적 매칭이 핵심입니다!
"""
    return prompt

# 도구 선택 프롬프트
FUNCTION_SELECTION_PROMPT = generate_function_selection_prompt()

# 개선된 구조화 응답 생성 프롬프트 (가독성 향상)
RESPONSE_GENERATION_PROMPT = """
당신은 전문적인 AI 어시스턴트입니다. 도구 실행 결과를 바탕으로 구조화되고 명확한 한국어 답변을 제공하세요.

핵심 원칙:
1. **정확성**: 도구 결과에 있는 정보만 사용, 추측 금지
2. **구조화**: 반드시 아래 구조를 따라 답변
3. **완전성**: 모든 관련 정보를 빠짐없이 포함
4. **가독성**: 명확하고 이해하기 쉬운 형태로 제시

필수 답변 구조 (반드시 이 순서로 작성):
## 핵심 요약
[질문에 대한 직접적이고 명확한 답변]

### 상세 정보
[구체적인 수치, 상태, 결과 등을 표나 목록으로 제시]

### 추가 정보
[관련 배경, 해석, 권장사항 등]

### 출처
[데이터 소스, 파일명, 시간 등]

형식 규칙:
- 제목: ## (메인), ### (서브) - 이모지 사용 금지
- 목록: - (불릿), 1. (번호)
- 표: | 헤더1 | 헤더2 |
      | 값1   | 값2   |
- 강조: **중요내용**, *기울임*
- 이모지: 제목에 절대 사용하지 말고, 본문에서만 최소한 사용
- 코드블록(```) 절대 사용 금지

특별 처리 가이드:
- **수위 데이터**: 배수지별 수치를 표로 명확히 구분
- **시간 데이터**: 구체적인 시간대와 변화 추이를 표로 제시
- **오류 상황**: 오류 원인과 해결 방법을 구조화하여 제시
- **예측 결과**: 신뢰도와 함께 결과를 표로 정리
- **벡터 검색**: 검색된 문서 내용을 인용 형식으로 제시

입력 정보:
- 사용자 질문: {user_query}
- 도구 실행 결과: {tool_results}

출력: 위 구조를 정확히 따라 구조화된 마크다운 답변을 작성하세요.
"""

def print_config() -> Dict[str, Any]:
    """현재 설정 정보를 출력

    Returns:
        Dict[str, Any]: 시스템 설정 정보 딕셔너리
    """
    config_info = {
        "LM Studio": {
            "Base URL": LM_STUDIO_BASE_URL,
            "Model": LM_STUDIO_MODEL_NAME
        },
        "Temperature": {
            "Tool Selection": TOOL_SELECTION_TEMPERATURE,
            "Response": RESPONSE_TEMPERATURE
        },
        "RAG": {
            "Vector DB Path": VECTOR_DB_PATH,
            "Chunk Size": CHUNK_SIZE,
            "Chunk Overlap": CHUNK_OVERLAP,
            "Top K Results": TOP_K_RESULTS
        },
        "System": {
            "Debug Mode": DEBUG_MODE,
            "Log Level": LOG_LEVEL,
            "Max Retries": MAX_RETRIES,
            "Timeout": TIMEOUT
        },
        "Enabled Tools": ENABLED_TOOLS,
        "Embedding": {
            "Model Name": EMBEDDING_MODEL_NAME
        },
        "PostgreSQL": {
            "Host": PG_DB_HOST,
            "Port": PG_DB_PORT,
            "Database": PG_DB_NAME,
            "User": PG_DB_USER,
            "Password": PG_DB_PASSWORD
        }
    }
    
    return config_info