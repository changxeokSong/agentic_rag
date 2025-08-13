# config.py - 환경변수를 활용한 시스템 설정

import os
import json
from dotenv import load_dotenv
from langchain_teddynote import logging
import weave

# .env 파일 로드
load_dotenv()

# 프로젝트 이름을 입력합니다.
logging.langsmith("AgenticRAG")

# LM Studio 설정
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "lm-studio")
LM_STUDIO_MODEL_NAME = os.getenv("LM_STUDIO_MODEL_NAME", "exaone-3.5-7.8b-instruct")

# 온도(temperature) 설정
TOOL_SELECTION_TEMPERATURE = float(os.getenv("TOOL_SELECTION_TEMPERATURE", "0.0"))
RESPONSE_TEMPERATURE = float(os.getenv("RESPONSE_TEMPERATURE", "0.7"))

# RAG 설정
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./vector_db")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
TOP_K_RESULTS = int(os.getenv("TOP_K_RESULTS", "10"))

# 외부 API 키
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
SEARCH_ENGINE_API_KEY = os.getenv("SEARCH_ENGINE_API_KEY", "")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# 임베딩 모델 설정 추가
OPENAI_API_KEY_ENV_VAR = "OPENAI_API_KEY"
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-ada-002")

# 로깅 설정
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# 시스템 설정
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
TIMEOUT = int(os.getenv("TIMEOUT", "30"))

DATABASE_NAME = os.getenv("DATABASE_NAME", "document")

# 활성화된 도구 확인
# MongoDB 도구 추가
ENABLED_TOOLS = os.getenv("ENABLED_TOOLS", "vector_search_tool,calculator_tool,weather_tool,list_files_tool,water_level_prediction_tool,arduino_water_sensor").split(",")

# PostgreSQL configuration
PG_DB_HOST = os.getenv("PG_DB_HOST", "localhost")
PG_DB_PORT = os.getenv("PG_DB_PORT", "5432")
PG_DB_NAME = os.getenv("PG_DB_NAME", "synergy") # 필수 설정
PG_DB_USER = os.getenv("PG_DB_USER", "synergy") # 필수 설정
PG_DB_PASSWORD = os.getenv("PG_DB_PASSWORD", "synergy") # 필수 설정

# 도구 정의 - 활성화된 도구만 포함
def get_available_functions():
    """환경변수에 따라 활성화된 도구만 반환"""
    all_functions = [
        # 검색(웹) 도구 제거됨
        {
            "name": "vector_search_tool",
            "description": "업로드된 내부 문서(예: PDF, 텍스트 파일 등)에서 벡터 검색을 통해 정보를 검색합니다. 특정 파일 내용, 사내 문서, 업로드한 보고서 등 내부 자료 검색이 필요할 때 사용하세요. 필요한 경우 특정 파일 이름이나 태그로 검색을 필터링할 수 있습니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색 대상 파일 내용 중 찾을 핵심 내용 또는 질문"
                    },
                    "file_filter": {
                        "type": "string",
                        "description": "검색 결과를 필터링할 특정 파일 이름 (선택 사항)"
                    },
                    "tags_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "검색 결과를 필터링할 태그 목록 (선택 사항)"
                    },
                     "top_k": {
                        "type": "integer",
                        "description": f"반환할 검색 결과의 최대 개수 (기본값: {TOP_K_RESULTS})",
                         "default": TOP_K_RESULTS
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["auto", "vector", "context"],
                        "description": "검색 모드: auto(기본), vector(임베딩 유사도), context(키워드)",
                        "default": "auto"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "calculator_tool",
            "description": "수학 계산, 단위 변환, 공식 계산 등 수치 연산이 필요할 때 사용합니다.\n예시: '123 * 45 계산해줘', '섭씨 30도를 화씨로 변환해줘', '삼각형 넓이 공식 계산해줘'",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "계산할 수학 표현식"
                    }
                },
                "required": ["expression"]
            }
        },
        {
            "name": "weather_tool",
            "description": "특정 도시나 지역의 현재 날씨 정보를 알려줍니다.\n예시: '서울 날씨 알려줘', '부산의 오늘 기온 알려줘'",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "날씨를 확인할 위치(도시 이름)"
                    }
                },
                "required": ["location"]
            }
        },
        # MongoDB 도구 정의 추가
        {
            "name": "list_files_tool",
            "description": "데이터베이스에 저장된 파일 목록을 조회합니다. 사용자가 업로드한 파일의 이름이나 목록 정보가 필요할 때 사용하세요.",
            "parameters": {
                "type": "object",
                "properties": {}, # 매개변수 없음
                "required": []
            }
        },
        {
            "name": "water_level_prediction_tool",
            "description": "LSTM 모델을 사용하여 수위를 예측합니다. 과거 수위 데이터를 입력받아 미래 수위를 예측합니다.\n예시: '수위 예측해줘', '[10.5, 11.2, 12.1] 데이터로 수위 예측', '다음 5시간 수위 예측', '30분 후 수위 예측'",
            "parameters": {
                "type": "object",
                "properties": {
                    "water_levels": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "과거 수위 데이터 리스트 (시계열 순서)"
                    },
                    "dataPoints": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "과거 수위 데이터 리스트 (water_levels와 동일, 호환성용)"
                    },
                    "data": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "과거 수위 데이터 리스트 (water_levels와 동일, 호환성용)"
                    },
                    "prediction_steps": {
                        "type": "integer",
                        "description": "예측할 미래 시점 개수 (기본값: 1)",
                        "minimum": 1,
                        "maximum": 24,
                        "default": 1
                    },
                    "prediction_hours": {
                        "type": "integer",
                        "description": "예측할 시간 수 (prediction_steps와 동일, 시간 기반 예측용)",
                        "minimum": 1,
                        "maximum": 24,
                        "default": 1
                    },
                    "time_horizon": {
                        "type": "object",
                        "description": "시간 범위 설정 (예: {minutes: 30}, {hours: 2})",
                        "properties": {
                            "minutes": {"type": "integer", "minimum": 1, "maximum": 1440},
                            "hours": {"type": "integer", "minimum": 1, "maximum": 24}
                        }
                    }
                },
                "required": []
            }
        },
        {
            "name": "arduino_water_sensor",
            "description": "아두이노 USB 시리얼 통신을 통해 실시간 수위 센서 값을 읽고 펌프를 제어하는 도구입니다. 실제 센서 하드웨어에서 현재 수위를 측정합니다.\n예시: '현재 수위 알려줘', '수위 측정해줘', '아두이노 수위 읽어줘', '아두이노 수위 레벨 확인해줘', '펌프1 켜줘', '펌프2 꺼줘', '아두이노 연결해줘'",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read_water_level", "read_water_level_channel", "read_current_level", "pump1_on", "pump1_off", "pump2_on", "pump2_off", "connect", "disconnect", "status", "test_communication", "pump_status", "read_pump_status"],
                        "description": "실행할 액션 (read_water_level: 모든 센서 읽기, read_water_level_channel: 특정 채널 읽기, read_current_level: 수위 읽기, pump1_on/off: 펌프1 제어, pump2_on/off: 펌프2 제어, connect: 연결, disconnect: 연결 해제, status: 상태 확인, test_communication: 통신 테스트, pump_status/read_pump_status: 펌프 상태 확인)"
                    },
                    "channel": {
                        "type": "integer",
                        "description": "센서 채널 번호 (read_water_level_channel 액션에서 사용)",
                        "minimum": 0,
                        "maximum": 7
                    },
                    "port": {
                        "type": "string",
                        "description": "아두이노 시리얼 포트 (예: COM3, /dev/ttyUSB0). 자동 감지를 위해 생략 가능"
                    },
                    "duration": {
                        "type": "integer",
                        "description": "펌프 작동 시간 (초). 펌프 제어 시 사용",
                        "minimum": 1,
                        "maximum": 300
                    }
                },
                "required": ["action"]
            }
        }
    ]
    
    # 활성화된 도구만 필터링
    return [func for func in all_functions if func["name"] in ENABLED_TOOLS]

# 사용 가능한 함수 목록
AVAILABLE_FUNCTIONS = get_available_functions()

# 프롬프트 템플릿 동적 생성
def generate_function_selection_prompt():
    """활성화된 도구에 따라 프롬프트 템플릿 생성"""
    base_prompt = (
        "사용자 요청을 분석하여 필요한 도구들을 JSON 배열로 반환하세요.\n\n"
        "**중요:** 도구가 명확히 필요한 경우에만 선택하세요. 일반 대화나 인사말 등에는 도구를 사용하지 마세요.\n\n"
        "**규칙:**\n"
        "1. 명확하게 특정 기능이 필요한 경우에만 도구 선택\n"
        "2. 여러 작업이 있으면 배열 [] 형태로 응답\n"
        "3. 단일 작업이라도 배열 형태로 응답 (일관성 유지)\n"
        "4. 도구가 필요하지 않으면 빈 배열 [] 반환\n"
        "5. JSON 형태로만 응답, 다른 텍스트 금지\n"
        "6. **펌프 번호를 정확히 구분하세요**: 펌프1 → pump1_on/pump1_off, 펌프2 → pump2_on/pump2_off\n\n"
        "**응답 형식:**\n"
        "- 도구 필요: [{\"name\": \"도구명\", \"arguments\": {\"인자\": \"값\"}}]\n"
        "- 도구 불필요: []\n\n"
        "**사용 가능한 도구:**\n"
    )
    tools_desc = []
    for i, func in enumerate(AVAILABLE_FUNCTIONS, 1):
        tools_desc.append(f"{i}. {func['name']}: {func['description']}")

    # 도구 사용 가이드 (특히 vector_search_tool)
    vector_guide = """
**vector_search_tool 사용 가이드**

- 언제 사용: 사용자가 업로드한 문서/보고서/PDF/텍스트 등 내부 자료에서 답을 찾으려는 의도가 분명할 때.
- 필수 파라미터: snake_case 키만 사용하세요. `query`는 반드시 포함.
- 선택 파라미터:
  - `file_filter`(string): 특정 파일명이 질문에 명시되면 그대로 설정. 파일명이 명확하지 않으면 생략.
  - `tags_filter`(array[string]): 질문에 태그/키워드가 명시된 경우 리스트로 설정.
  - `top_k`(integer): 기본 10. 상위 몇 개 결과가 필요한지 질문에 있으면 반영.
  - `mode`(string): `auto`(기본) | `vector` | `context`.
    - 파일 내용의 의미/요약 질의 → `auto` 권장(먼저 vector 후 context 폴백)
    - 단순 키워드 포함 여부 확인 → `context`
- 금지: camelCase 키(`fileFilter`, `tagsFilter`, `topK`)는 사용하지 마세요.
- 예: 파일명이 따옴표로 언급되면 그대로 `file_filter`에 넣습니다. 예: "내부 보고서.pdf" → `file_filter: "내부 보고서.pdf"`.
"""

    # 예시 추가
    example_prompt = """
**예시:**

1. "안녕하세요" 또는 "어떻게 지내세요?"
   → []

2. "고마워요" 또는 "잘했어"
   → []

3. "1+1 계산해줘"
   → [{"name": "calculator_tool", "arguments": {"expression": "1+1"}}]

4. "서울 날씨 알려줘"
   → [{"name": "weather_tool", "arguments": {"location": "서울"}}]

5. "서울 날씨와 2+2 계산해줘"  
   → [{"name": "weather_tool", "arguments": {"location": "서울"}}, {"name": "calculator_tool", "arguments": {"expression": "2+2"}}]

 6. "업로드한 보고서에서 삼성의 자체 개발 AI 이름 찾아줘"
    → [{"name": "vector_search_tool", "arguments": {"query": "삼성 자체 개발 AI 이름", "mode": "auto", "top_k": 10}}]

 6-1. "'내부 보고서.pdf'에서 삼성 자체 개발 AI 이름 찾아줘"
    → [{"name": "vector_search_tool", "arguments": {"query": "삼성 자체 개발 AI 이름", "file_filter": "내부 보고서.pdf", "mode": "auto"}}]

 6-2. "태그에 '삼성','AI'가 붙은 문서에서 자체 개발 AI 이름 찾아줘 (상위 5개)"
    → [{"name": "vector_search_tool", "arguments": {"query": "자체 개발 AI 이름", "tags_filter": ["삼성", "AI"], "top_k": 5, "mode": "auto"}}]

7. "펌프1 켜줘" 또는 "아두이노 펌프1 켜줘"
   → [{"name": "arduino_water_sensor", "arguments": {"action": "pump1_on"}}]

8. "펌프1 꺼줘" 또는 "아두이노 펌프1 꺼줘"
   → [{"name": "arduino_water_sensor", "arguments": {"action": "pump1_off"}}]

9. "펌프2 켜줘" 또는 "아두이노 펌프2 켜줘"
   → [{"name": "arduino_water_sensor", "arguments": {"action": "pump2_on"}}]

10. "펌프2 꺼줘" 또는 "아두이노 펌프2 꺼줘"
   → [{"name": "arduino_water_sensor", "arguments": {"action": "pump2_off"}}]

11. "[10.5, 11.2, 12.1] 데이터로 수위 예측해줘"
   → [{"name": "water_level_prediction_tool", "arguments": {"water_levels": [10.5, 11.2, 12.1]}}]

12. "현재 수위 알려줘" 또는 "수위 측정해줘" 또는 "아두이노 수위 읽어줘" 또는 "아두이노 수위 레벨 확인해줘"
   → [{"name": "arduino_water_sensor", "arguments": {"action": "read_water_level"}}]

13. "COM4로 아두이노 연결해줘"
   → [{"name": "arduino_water_sensor", "arguments": {"action": "connect", "port": "COM4"}}]

14. "현재 펌프 상태 알려줘" 또는 "아두이노 펌프 상태 확인해줘"
   → [{"name": "arduino_water_sensor", "arguments": {"action": "pump_status"}}]

15. "현재 아두이노 수위 상태 알려줘" 또는 "아두이노 수위 확인해줘" 또는 "지금 수위 어떤지 알려줘"
   → [{"name": "arduino_water_sensor", "arguments": {"action": "read_water_level"}}]

16. "아두이노 통신 테스트해줘"
   → [{"name": "arduino_water_sensor", "arguments": {"action": "test_communication"}}]

17. "채널 1 수위 알려줘" 또는 "센서 1번 수위 확인해줘"
   → [{"name": "arduino_water_sensor", "arguments": {"action": "read_water_level_channel", "channel": 1}}]

18. "채널 2 수위 측정해줘" 또는 "센서 2번 수위 읽어줘"
   → [{"name": "arduino_water_sensor", "arguments": {"action": "read_water_level_channel", "channel": 2}}]

"""
    prompt = base_prompt + "\n".join(tools_desc) + "\n\n" + vector_guide + example_prompt + "\n사용자 질문 분석하여 JSON 배열로 응답:"
    return prompt

# 도구 선택 프롬프트
FUNCTION_SELECTION_PROMPT = generate_function_selection_prompt()

# 응답 생성 프롬프트
RESPONSE_GENERATION_PROMPT = """
당신은 친근한 AI 어시스턴트입니다. 도구 실행 결과를 바탕으로 사용자에게 자연스럽고 간결한 답변을 제공하세요.

**답변 규칙:**
1. 헤더나 제목 없이 바로 본문으로 시작
2. 핵심 결과만 간단히 요약해서 먼저 제시
3. 여러 작업이 있으면 자연스럽게 연결해서 설명
4. "다운로드 방법", "활용 방안" 같은 불필요한 안내 제거
5. 과도한 상세 정보는 피하고 필요한 정보만 간결하게

**좋은 답변 예시:**
- 단일 작업: "1+1은 2입니다."
- 다중 작업: "1+1은 2이고, 서울 날씨는 맑음이며 기온은 25.8°C입니다."
- 날씨: "서울은 현재 맑음이고 기온은 25.8°C입니다."

**피해야 할 표현:**
- "요약 및 결과 안내"
- "자세한 결과 설명"
- "다운로드 방법"
- "성공적으로", "정확히" 같은 과도한 수식어

사용자 질문: {user_query}
도구 실행 결과: {tool_results}

위 결과를 바탕으로 자연스럽고 간결한 답변을 작성하세요:"""

# 설정 정보 출력 (디버깅용)
def print_config():
    """현재 설정 정보를 출력"""
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
            "Vector DB Path (Not used for MongoDB)": VECTOR_DB_PATH, # MongoDB 사용 시에는 이 경로를 사용하지 않음을 명시
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
        "Embedding": { # 임베딩 설정 정보 추가
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