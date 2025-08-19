# utils/helpers.py

import json
import time
from functools import wraps
from utils.logger import setup_logger

logger = setup_logger(__name__)

def retry(max_retries=3, delay=1):
    """재시도 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        logger.error(f"최대 재시도 횟수 도달: {func.__name__}, 에러: {str(e)}")
                        raise
                    logger.warning(f"함수 실행 실패: {func.__name__}, 재시도 {retries}/{max_retries}, 에러: {str(e)}")
                    time.sleep(current_delay)
                    current_delay *= 2  # 지수 백오프
        return wrapper
    return decorator

def format_tool_results(results):
    """도구 실행 결과를 LLM 친화적 문자열(JSON 유사)로 포맷팅.
    - 중첩 객체를 안전하게 직렬화
    - 비직렬화 타입은 문자열로 대체
    - 너무 큰 값은 요약
    """
    def sanitize(obj, depth=0):
        if depth > 3:
            return "[depth limit]"
        if isinstance(obj, dict):
            safe = {}
            for k, v in obj.items():
                safe[str(k)] = sanitize(v, depth + 1)
            return safe
        if isinstance(obj, list):
            if len(obj) > 50:
                return [sanitize(x, depth + 1) for x in obj[:50]] + ["[truncated]"]
            return [sanitize(x, depth + 1) for x in obj]
        if isinstance(obj, (str, int, float, bool)) or obj is None:
            s = obj if isinstance(obj, str) else obj
            # 너무 긴 문자열 자르기
            if isinstance(s, str) and len(s) > 2000:
                return s[:2000] + "… [truncated]"
            return s
        try:
            return str(obj)
        except Exception:
            return "[unserializable]"

    safe_results = {name: sanitize(result) for name, result in results.items()}
    try:
        return json.dumps(safe_results, ensure_ascii=False, indent=2)
    except Exception:
        # JSON 직렬화 실패 시 폴백
        formatted_lines = []
        for tool_name, result in safe_results.items():
            formatted_lines.append(f"도구: {tool_name}")
            formatted_lines.append(f"결과: {result}")
            formatted_lines.append("-" * 40)
        return "\n".join(formatted_lines)

def safe_json_loads(json_str):
    """안전하게 JSON을 파싱합니다."""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 오류: {str(e)}, 내용: {json_str}")
        return None

def clean_ai_response(response):
    """AI 응답에서 불필요한 따옴표 및 포맷팅 문제 정리"""
    if not response:
        return response
    
    response = response.strip()
    
    # 양끝에 따옴표가 있는 경우 제거
    if len(response) >= 2:
        if (response.startswith('"') and response.endswith('"')) or \
           (response.startswith("'") and response.endswith("'")):
            response = response[1:-1].strip()
    
    # 응답 시작이 "답변:", "응답:" 등으로 시작하는 경우 정리
    prefixes_to_remove = ["답변:", "응답:", "Answer:", "Response:"]
    for prefix in prefixes_to_remove:
        if response.startswith(prefix):
            response = response[len(prefix):].strip()
            break
    
    # 다시 한번 양끝 따옴표 확인 (접두사 제거 후)
    if len(response) >= 2:
        if (response.startswith('"') and response.endswith('"')) or \
           (response.startswith("'") and response.endswith("'")):
            response = response[1:-1].strip()
    
    return response
