# config.py - 환경변수를 활용한 시스템 설정

import os
import json
from dotenv import load_dotenv
from langchain_teddynote import logging

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

ENABLED_TOOLS = os.getenv("ENABLED_TOOLS", "vector_search_tool,list_files_tool,water_level_prediction_tool,arduino_water_sensor").split(",")

# PostgreSQL configuration
PG_DB_HOST = os.getenv("PG_DB_HOST", "localhost")
PG_DB_PORT = os.getenv("PG_DB_PORT", "5432")
PG_DB_NAME = os.getenv("PG_DB_NAME", "synergy")
PG_DB_USER = os.getenv("PG_DB_USER", "synergy")
PG_DB_PASSWORD = os.getenv("PG_DB_PASSWORD", "synergy")

def get_available_functions():
    """환경변수에 따라 활성화된 도구만 반환"""
    all_functions = [
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
            "name": "list_files_tool",
            "description": "데이터베이스에 저장된 파일 목록을 조회합니다. 사용자가 업로드한 파일의 이름이나 목록 정보가 필요할 때 사용하세요.",
            "parameters": {
                "type": "object",
                "properties": {},
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
            "description": "아두이노 USB 시리얼 통신을 통해 실시간 수위 센서 값을 읽고 펌프를 제어하는 도구입니다. 실제 센서 하드웨어에서 현재 수위를 측정하고, 펌프1과 펌프2를 개별 제어할 수 있습니다.\n수위 측정 예시: '현재 수위 알려줘', '수위 측정해줘', '아두이노 수위 읽어줘'\n펌프 제어 예시: '펌프1 켜줘', '펌프2 켜줘', '펌프1 꺼줘', '펌프2 꺼줘', '펌프 상태 확인'\n연결 관리 예시: '아두이노 연결해줘', '아두이노 상태 확인'",
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

def generate_function_selection_prompt():
    """활성화된 도구에 따라 프롬프트 템플릿 생성"""
    base_prompt = (
        "사용자 요청을 분석하여 적합한 도구를 선택하고 JSON 형식으로만 응답하세요.\n\n"
        "**핵심 규칙:**\n"
        "1. 사용자 의도 파악 후 필요한 도구와 인자 선택\n"
        "2. 펌프 제어('펌프1/2 켜줘/꺼줘') → arduino_water_sensor 필수 사용\n"
        "3. 여러 도구 필요시 모두 포함\n"
        "4. 일반 대화/인사 → 빈 배열 `[]`\n"
        "5. 오직 JSON 배열만 응답\n\n"
        "**응답 형식:**\n"
        "- 도구 사용: `[{\"name\": \"도구명\", \"arguments\": {\"인자\": \"값\"}}]`\n"
        "- 도구 불필요: `[]`\n\n"
        "**사용 가능한 도구:**\n"
    )
    
    tools_desc = []
    for i, func in enumerate(AVAILABLE_FUNCTIONS, 1):
        # 도구 설명을 더 명확하게 구성
        tools_desc.append(f"{i}. **{func['name']}**: {func['description']}")

    # 더 복합적이고 현실적인 예시를 추가하여 LLM의 이해도를 높임
    example_prompt = """
**## 주요 예시**
- 일반 대화: "안녕? 오늘 기분 어때?" → `[]`
- 단순 문서 검색: "지난 분기 보고서에서 매출 관련 내용 찾아줘" → `[{"name": "vector_search_tool", "arguments": {"query": "지난 분기 매출"}}]`
- 조건부 문서 검색: "'프로젝트A_결과보고서.pdf' 파일에서 '핵심 성과' 부분 상위 5개만 요약해줘" → `[{"name": "vector_search_tool", "arguments": {"query": "핵심 성과 요약", "file_filter": "프로젝트A_결과보고서.pdf", "top_k": 5}}]`
- 실시간 센서 측정: "지금 수위 좀 재줘" → `[{"name": "arduino_water_sensor", "arguments": {"action": "read_water_level"}}]`
- 펌프 제어: "펌프1 켜줘" → `[{"name": "arduino_water_sensor", "arguments": {"action": "pump1_on"}}]`
- 펌프 제어: "펌프2 켜줘" → `[{"name": "arduino_water_sensor", "arguments": {"action": "pump2_on"}}]`
- 펌프 제어: "펌프1 꺼줘" → `[{"name": "arduino_water_sensor", "arguments": {"action": "pump1_off"}}]`
- 펌프 제어: "펌프2 꺼줘" → `[{"name": "arduino_water_sensor", "arguments": {"action": "pump2_off"}}]`
- 펌프 상태: "펌프 상태 확인해줘" → `[{"name": "arduino_water_sensor", "arguments": {"action": "pump_status"}}]`
- 수위 예측: "앞으로 3시간 동안의 수위를 예측해줄래?" → `[{"name": "water_level_prediction_tool", "arguments": {"prediction_hours": 3}}]`
- 복합 요청: "'운영 매뉴얼' 문서를 참고해서 현재 수위를 확인하고, 펌프 2번을 켜줘" → `[{"name": "vector_search_tool", "arguments": {"query": "펌프 2번 제어 방법", "file_filter": "운영 매뉴얼"}}, {"name": "arduino_water_sensor", "arguments": {"action": "pump2_on"}}]`

**## 핵심 키워드 매칭**
- 펌프 관련: "펌프1", "펌프2", "pump1", "pump2", "켜줘", "꺼줘", "가동", "정지", "펌프 상태"
- 수위 관련: "수위", "물위", "현재 수위", "수위 측정", "물 높이", "아두이노 수위"
- 예측 관련: "예측", "미래", "앞으로", "시간 후", "분 후"

**## 사용자 질문**
사용자 질문을 분석하여 위의 규칙과 예시에 따라 JSON 배열로 응답하세요:"""

    return base_prompt + "\n".join(tools_desc) + "\n" + example_prompt

# 도구 선택 프롬프트
FUNCTION_SELECTION_PROMPT = generate_function_selection_prompt()

# 응답 생성 프롬프트 (간소화)
RESPONSE_GENERATION_PROMPT = """
다음 정보를 바탕으로 한국어로 간결하고 명확한 마크다운 답변을 작성하세요.

규칙:
- 도구 결과가 없으면: 일반 대화에 맞게 짧고 공손한 답변만 작성하고, 섹션/표/상태 요약을 만들지 마세요.
- 도구 결과가 있으면: 질문과 가장 관련 있는 핵심 결과만 요약하세요. 불필요한 템플릿(작업 결과/추가 조치/완료 메시지)은 넣지 마세요.
- HTML 태그나 마크다운 코드 블록(```)은 사용하지 말고, 순수 텍스트로만 답변하세요.
- 알 수 없거나 데이터가 부족하면 솔직하게 부족하다고 말하고, 가능한 다음 조치를 간단히 제안하세요.

입력:
- 사용자 질문: {user_query}
- 도구 결과: {tool_results}

출력:
- 최대한 간단한 일반 텍스트 (마크다운 구문 없이)
"""

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