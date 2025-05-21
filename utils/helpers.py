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
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        logger.error(f"최대 재시도 횟수 도달: {func.__name__}, 에러: {str(e)}")
                        raise
                    logger.warning(f"함수 실행 실패: {func.__name__}, 재시도 {retries}/{max_retries}, 에러: {str(e)}")
                    time.sleep(delay)
                    delay *= 2  # 지수 백오프
        return wrapper
    return decorator

def format_tool_results(results):
    """도구 실행 결과를 포맷팅합니다."""
    formatted_results = []
    
    for tool_name, result in results.items():
        formatted_results.append(f"도구: {tool_name}")
        formatted_results.append(f"결과: {result}")
        formatted_results.append("-" * 40)
    
    return "\n".join(formatted_results)

def safe_json_loads(json_str):
    """안전하게 JSON을 파싱합니다."""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 오류: {str(e)}, 내용: {json_str}")
        return None
