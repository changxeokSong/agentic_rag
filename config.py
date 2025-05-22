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
LM_STUDIO_MODEL_NAME = os.getenv("LM_STUDIO_MODEL_NAME", "qwen2.5-7b-instruct")

# 온도(temperature) 설정
TOOL_SELECTION_TEMPERATURE = float(os.getenv("TOOL_SELECTION_TEMPERATURE", "0.0"))
RESPONSE_TEMPERATURE = float(os.getenv("RESPONSE_TEMPERATURE", "0.7"))

# RAG 설정
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./vector_db")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
TOP_K_RESULTS = int(os.getenv("TOP_K_RESULTS", "5"))

# 외부 API 키
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
SEARCH_ENGINE_API_KEY = os.getenv("SEARCH_ENGINE_API_KEY", "")

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
ENABLED_TOOLS = os.getenv("ENABLED_TOOLS", "search_tool,calculator_tool,weather_tool,list_mongodb_files_tool,get_mongodb_file_content_tool,internal_vector_search").split(",")

# 도구 정의 - 활성화된 도구만 포함
def get_available_functions():
    """환경변수에 따라 활성화된 도구만 반환"""
    all_functions = [
        {
            "name": "search_tool",
            "description": "웹에서 정보를 검색합니다. 최신 뉴스, 일반 상식, 외부 정보, 실시간 이슈 등 인터넷에서 찾을 수 있는 정보가 필요할 때 사용하세요.\n예시: '최신 AI 트렌드 알려줘', '오늘의 주요 뉴스 알려줘'",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색할 쿼리"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "internal_vector_search",
            "description": "업로드된 내부 문서(예: PDF, 텍스트 파일 등)에서 벡터 검색을 통해 정보를 검색합니다. 특정 파일 내용, 사내 문서, 업로드한 보고서 등 내부 자료 검색이 필요할 때 사용하세요. 필요한 경우 특정 파일 이름이나 태그로 검색을 필터링할 수 있습니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "내부 문서에서 검색할 쿼리"
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
            "name": "list_mongodb_files_tool",
            "description": "MongoDB GridFS에 저장된 파일 목록을 조회합니다. 사용자가 업로드한 파일의 이름이나 목록 정보가 필요할 때 사용하세요.",
            "parameters": {
                "type": "object",
                "properties": {}, # 매개변수 없음
                "required": []
            }
        },
        {
            "name": "get_mongodb_file_content_tool",
            "description": "MongoDB GridFS에 저장된 특정 파일의 내용을 가져옵니다. 사용자가 업로드한 파일의 내용을 확인하거나 응답에 활용해야 할 때 사용하세요. 파일 이름을 입력받습니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "내용을 가져올 파일의 이름"
                    }
                },
                "required": ["filename"]
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
        "당신은 사용자의 질문을 분석하고 어떤 도구를 사용해야 할지 결정해야 합니다.\n"
        "여러 도구가 필요하다면 반드시 아래와 같이 JSON 배열로 반환하세요.\n"
        "예시:\n"
        "[\n"
        "  {\"name\": \"weather_tool\", \"arguments\": {\"location\": \"순천\"}},\n"
        "  {\"name\": \"calculator_tool\", \"arguments\": {\"expression\": \"2322+2242\"}}\n"
        "]\n"
        "단일 도구만 필요하다면 단일 객체로 반환하세요.\n"
        "사용 가능한 도구:\n"
    )
    tools_desc = []
    for i, func in enumerate(AVAILABLE_FUNCTIONS, 1):
        tools_desc.append(f"{i}. {func['name']}: {func['description']}")
    example_prompt = """
예시)
- 사용자: '현재 순천 날씨 알려주고 2322+2242 계산해줘'
  → [
      {"name": "weather_tool", "arguments": {"location": "순천"}},
      {"name": "calculator_tool", "arguments": {"expression": "2322+2242"}}
    ]
- 사용자: '최신 AI 논문 찾아줘'
  → search_tool
- 사용자: '내부 문서 저장소에서 AI 관련 자료 검색해줘'
  → internal_vector_search
- 사용자: '123 곱하기 456은 얼마야?'
  → calculator_tool
- 사용자: '서울의 오늘 날씨 알려줘'
  → weather_tool
"""
    prompt = base_prompt + "\n".join(tools_desc) + example_prompt + "\n사용자 질문을 분석하고 필요한 도구를 호출하세요. 여러 도구가 필요하다면 모두 사용하세요."
    return prompt

# 도구 선택 프롬프트
FUNCTION_SELECTION_PROMPT = generate_function_selection_prompt()

# 응답 생성 프롬프트
RESPONSE_GENERATION_PROMPT = """
당신은 도구의 실행 결과와 원래 사용자 질문을 바탕으로 빠지는 내용없이 최종 답변을 생성해야 합니다.
모든 답변은 반드시 한국어로만 작성하세요. 중국어, 영어 등 외국어를 사용하지 마세요.
도구 실행 결과를 분석하고, 사용자 질문에 가장 적합한 답변을 작성하세요.
답변은 명확하고 구체적이어야 하며, 도구 실행 결과에서 얻은 정보를 잘 통합해야 합니다.

원본 사용자 질문: {user_query}

사용된 도구 및 결과:
{tool_results}

이 정보를 바탕으로 사용자의 질문에 대한 종합적인 답변을 작성하세요.
"""

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
        # MongoDB 관련 정보 추가
        "MongoDB": {
             "Database Name": DATABASE_NAME,
             "Vector Collection Name": VECTOR_COLLECTION_NAME # config 파일에 추가
        },
        "Embedding": { # 임베딩 설정 정보 추가
            "Model Name": EMBEDDING_MODEL_NAME
        }
    }
    
    return config_info

# MongoDB 벡터 컬렉션 이름을 config에 추가
VECTOR_COLLECTION_NAME = "document_chunks" # storage/mongodb_storage.py와 동일하게 설정