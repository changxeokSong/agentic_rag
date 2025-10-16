# utils/helpers.py

import json
import time
from datetime import datetime
from functools import wraps
from utils.logger import setup_logger

logger = setup_logger(__name__)

def get_current_timestamp(format_string="%Y-%m-%d %H:%M:%S"):
    """현재 시간을 지정된 형식으로 반환"""
    return time.strftime(format_string)

def get_datetime_now():
    """현재 datetime 객체 반환"""
    return datetime.now()

def format_timestamp(dt=None, format_string="%Y-%m-%d %H:%M:%S"):
    """datetime 객체를 문자열로 포맷팅"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime(format_string)

_arduino_tool_instance = None

def get_arduino_tool():
    """Arduino 도구 인스턴스를 안전하게 가져오기 (싱글톤 패턴)"""
    global _arduino_tool_instance
    if _arduino_tool_instance is None:
        try:
            from tools.arduino_water_sensor_tool import ArduinoWaterSensorTool
            _arduino_tool_instance = ArduinoWaterSensorTool()
            logger.info("새로운 ArduinoWaterSensorTool 인스턴스 생성")
        except ImportError as e:
            logger.error(f"Arduino 도구 임포트 실패: {e}")
            return None
        except Exception as e:
            logger.error(f"Arduino 도구 초기화 실패: {e}")
            return None
    return _arduino_tool_instance

def get_database_connector():
    """데이터베이스 연결자를 안전하게 가져오기"""
    try:
        from services.database_connector import get_database_connector as _get_db
        return _get_db()
    except ImportError as e:
        logger.error(f"데이터베이스 연결자 임포트 실패: {e}")
        return None
    except Exception as e:
        logger.error(f"데이터베이스 연결자 초기화 실패: {e}")
        return None

def get_state_manager():
    """상태 관리자를 안전하게 가져오기"""
    try:
        from utils.state_manager import get_state_manager as _get_state
        return _get_state()
    except ImportError as e:
        logger.error(f"상태 관리자 임포트 실패: {e}")
        return None
    except Exception as e:
        logger.error(f"상태 관리자 초기화 실패: {e}")
        return None

def create_error_response(error_message, error_type="일반 오류", timestamp=None):
    """표준화된 오류 응답 생성"""
    return {
        "success": False,
        "error": f"❌ **{error_type}**\n• {error_message}",
        "timestamp": timestamp or get_current_timestamp()
    }

def create_success_response(message, data=None, timestamp=None):
    """표준화된 성공 응답 생성"""
    result = {
        "success": True,
        "message": f"✅ {message}",
        "timestamp": timestamp or get_current_timestamp()
    }
    if data:
        result.update(data)
    return result

def create_warning_response(message, data=None, timestamp=None):
    """표준화된 경고 응답 생성"""
    result = {
        "success": True,
        "warning": f"⚠️ {message}",
        "timestamp": timestamp or get_current_timestamp()
    }
    if data:
        result.update(data)
    return result

def get_session_state_value(key, default=None):
    """안전하게 Streamlit 세션 상태 값 가져오기"""
    try:
        import streamlit as st
        return getattr(st.session_state, key, default)
    except (ImportError, AttributeError):
        return default

def set_session_state_value(key, value):
    """안전하게 Streamlit 세션 상태 값 설정하기"""
    try:
        import streamlit as st
        setattr(st.session_state, key, value)
        return True
    except (ImportError, AttributeError):
        return False

def get_lm_studio_client():
    """LM Studio 클라이언트를 안전하게 가져오기"""
    return get_session_state_value('lm_studio_client')

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
            if isinstance(s, str) and len(s) > 16000:
                return s[:16000] + "… [truncated]"
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
    
    import re
    
    response = response.strip()
    
    # 중복 제거 - 연속된 동일한 내용 제거
    response = re.sub(r'(.+?)(\1)+', r'\1', response, flags=re.DOTALL)
    
    # 불필요한 마크다운 기호 정리
    response = re.sub(r'#{3,}', '##', response)
    response = re.sub(r'#{1,2}([^#\n]+)#{1,2}', r'## \1', response)
    
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
    
    # 코드 블록 제거 (일반 답변에서 코드 블록이 잘못 사용된 경우)
    response = remove_unwanted_code_blocks(response)
    
    return response

def apply_consistent_formatting(text):
    """스트리밍과 비스트리밍 응답에 동일한 후처리 적용"""
    if not text:
        return text
    
    # 1. 기본 정리
    cleaned = clean_ai_response(text)
    
    # 2. 마크다운 테이블 정규화
    normalized = normalize_markdown_tables(cleaned)
    
    # 3. 코드 펜스 제거
    unfenced = unfence_markdown_tables(normalized)
    
    # 4. 구조화 강화 - 제목 일관성 보장
    structured = ensure_structured_format(unfenced)
    
    return structured

def ensure_structured_format(text):
    """응답의 구조화된 형식을 보장"""
    if not text:
        return text
    
    import re
    
    # 제목 레벨 정규화
    text = re.sub(r'^#{4,}', '###', text, flags=re.MULTILINE)
    
    # 연속된 빈 줄 정리 (최대 2개)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 제목 앞뒤 공백 정리
    text = re.sub(r'\n(#{2,3})\s*', r'\n\1 ', text)
    
    # 불릿 포인트 정리
    text = re.sub(r'\n-\s+', '\n- ', text)
    
    # 제목에서 이모지 완전 제거 (더 강력한 정규식)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        if line.strip().startswith('##') or line.strip().startswith('###'):
            # 제목에서 이모지와 특수문자 제거, 텍스트만 남기기
            cleaned_title = re.sub(r'^#{2,3}\s*[^\w\s가-힣]*\s*', '', line.strip())
            cleaned_title = re.sub(r'^#{2,3}\s*', '', cleaned_title)
            # 제목 레벨과 텍스트만 남기기
            level = '##' if line.strip().startswith('##') else '###'
            cleaned_line = f"{level} {cleaned_title}"
            cleaned_lines.append(cleaned_line)
        else:
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    
    # 표 정리 (파이프 앞뒤 공백)
    lines = text.split('\n')
    cleaned_lines = []
    in_table = False
    
    for line in lines:
        if '|' in line:
            in_table = True
            # 파이프 앞뒤 공백 정리
            parts = line.split('|')
            cleaned_parts = [part.strip() for part in parts]
            cleaned_line = '|'.join(cleaned_parts)
            cleaned_lines.append(cleaned_line)
        else:
            if in_table and line.strip() == '':
                # 표 다음 빈 줄은 유지
                cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)
            in_table = False
    
    return '\n'.join(cleaned_lines)

def remove_unwanted_code_blocks(text: str) -> str:
    """일반 답변에서 잘못 사용된 코드 블록을 제거합니다."""
    if not text or '```' not in text:
        return text
    
    import re
    
    # 코드 블록 패턴 찾기
    pattern = re.compile(r"```[\w]*\n?(.*?)\n?```", re.DOTALL)
    
    def replace_code_block(match):
        content = match.group(1).strip()
        
        # JSON이나 실제 코드가 아닌 일반 텍스트인 경우 코드 블록 제거
        if not _looks_like_code_or_json(content):
            return content
        else:
            # 실제 코드나 JSON인 경우 유지
            return match.group(0)
    
    try:
        result = pattern.sub(replace_code_block, text)
        return result
    except Exception:
        # 정규식 처리 실패시 원본 반환
        return text

def _looks_like_code_or_json(content: str) -> bool:
    """내용이 실제 코드나 JSON인지 판단합니다."""
    content = content.strip()
    
    # JSON 형태인지 확인
    if (content.startswith('{') and content.endswith('}')) or \
       (content.startswith('[') and content.endswith(']')):
        try:
            import json
            json.loads(content)
            return True
        except:
            pass
    
    # 코드 특징 확인
    code_indicators = [
        'def ', 'class ', 'import ', 'from ', '#!/',
        'function ', 'var ', 'const ', 'let ',
        '<?php', '<html', '<script', 'SELECT ', 'INSERT '
    ]
    
    if any(indicator in content for indicator in code_indicators):
        return True
    
    # 일반 텍스트로 판단 (한국어 포함, 마크다운 형식 등)
    import re
    korean_chars = re.search(r'[가-힣]', content)
    markdown_patterns = re.search(r'^#+\s|^\*\s|^-\s|^\d+\.\s', content, re.MULTILINE)
    
    if korean_chars or markdown_patterns:
        return False
    
    return False

def normalize_markdown_tables(text: str) -> str:
    """마크다운 표를 표준 형태로 정규화합니다.
    - 헤더 구분선(| --- | --- |) 자동 생성/수정
    - 행의 셀 개수를 헤더와 일치하도록 패딩/병합
    - 앞뒤 불필요한 파이프 정리
    - 깨진 구분선 줄 교체
    실패 시 원본을 유지합니다.
    """
    if not text or '|' not in text:
        return text

    import re

    def is_separator_line(line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        # 파이프, 하이픈, 콜론, 스페이스만으로 구성된 경우
        return all(ch in '|-: ' for ch in s) and '-' in s

    def split_cells(raw_line: str):
        parts = [p.strip() for p in raw_line.strip().split('|')]
        # 양끝 공백 셀 제거
        parts = [p for p in parts if p != '']
        return parts

    def join_cells(cells):
        return '| ' + ' | '.join(cells) + ' |'

    lines = text.splitlines()
    output_lines = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        # 표 헤더 후보: 파이프 포함 + 두 셀 이상
        if '|' in line and re.search(r'\S\s*\|\s*\S', line):
            header_cells = split_cells(line)
            if len(header_cells) >= 2:
                block_lines = [line]
                j = i + 1
                # 표 블록 수집
                while j < n and '|' in lines[j] and not lines[j].startswith('```'):
                    block_lines.append(lines[j])
                    j += 1

                # 정규화 처리
                normalized_block = []
                # 헤더
                normalized_block.append(join_cells(header_cells))

                # 구분선 생성/수정
                sep_line = None
                body_start = 1
                if len(block_lines) > 1 and is_separator_line(block_lines[1]):
                    sep_line = block_lines[1]
                    body_start = 2
                # 헤더 셀 수에 맞춘 구분선 생성
                separator = '| ' + ' | '.join(['---'] * len(header_cells)) + ' |'
                normalized_block.append(separator)

                # 본문 행 정규화
                for k in range(body_start, len(block_lines)):
                    row = block_lines[k]
                    # 구분선이 본문에 섞여 있으면 무시
                    if is_separator_line(row):
                        continue
                    row_cells = split_cells(row)
                    if not row_cells:
                        continue
                    # 헤더 길이에 맞춰 패딩/병합
                    if len(row_cells) < len(header_cells):
                        row_cells = row_cells + [''] * (len(header_cells) - len(row_cells))
                    elif len(row_cells) > len(header_cells):
                        head = row_cells[:len(header_cells)-1]
                        tail = ' '.join(row_cells[len(header_cells)-1:])
                        row_cells = head + [tail]
                    normalized_block.append(join_cells(row_cells))

                output_lines.extend(normalized_block)
                i = j
                continue

        # 표가 아니면 그대로 추가
        output_lines.append(line)
        i += 1

    return "\n".join(output_lines)

def unfence_markdown_tables(text: str) -> str:
    """코드 펜스(``` ... ```) 안에 들어간 마크다운 표를 꺼내어 일반 표로 변환합니다.
    - info string이 없거나(markdown, md 포함) 표 형태('|')가 감지되면 펜스를 제거합니다.
    - json 코드블록은 그대로 유지합니다.
    실패 시 원본 유지.
    """
    if not text or '```' not in text:
        return text

    import re

    pattern = re.compile(r"```([a-zA-Z0-9_-]*)\n([\s\S]*?)\n```", re.MULTILINE)

    def replace_block(match):
        lang = (match.group(1) or '').strip().lower()
        body = match.group(2)
        # JSON 블록은 유지
        if lang == 'json':
            return match.group(0)
        # 표 형태 감지: 파이프 포함 행이 2개 이상
        table_like_lines = [line for line in body.splitlines() if '|' in line]
        if len(table_like_lines) >= 2:
            # 펜스 제거하고 본문만 반환
            return body
        return match.group(0)

    try:
        return pattern.sub(replace_block, text)
    except Exception:
        return text

# -----------------------
# Parsing utilities (common)
# -----------------------

def extract_float_numbers(text: str, min_count: int = 0, min_value: float = 0.0, max_value: float = 0.0) -> list:
    """문자열에서 실수/정수 숫자를 추출해 float 리스트로 반환.
    - min_count: 최소 추출 개수 조건. 0이면 무시
    - min_value/max_value: 값 범위 필터 (None이면 무시)
    """
    if not isinstance(text, str) or not text:
        return []

    import re
    numbers = re.findall(r"-?\d+\.?\d*", text)
    try:
        floats = [float(n) for n in numbers]
    except Exception:
        floats = []

    if min_value != 0.0 or max_value != 0.0:
        filtered = []
        for v in floats:
            if (min_value == 0.0 or v >= min_value) and (max_value == 0.0 or v <= max_value):
                filtered.append(v)
        floats = filtered

    if min_count and len(floats) < min_count:
        return []

    return floats

def parse_time_info_from_text(text: str) -> dict:
    """한국어 자연어에서 시간 정보를 추출해 딕셔너리로 반환.
    지원: X분/시간/일 뒤|후|이후, 내일/다음날
    반환 예: {"minutes": 30} 또는 {"hours": 2} 또는 {"days": 1}
    """
    if not isinstance(text, str) or not text:
        return {}

    import re
    q = text.lower()
    patterns = [
        (r"(\d+)\s*분\s*(뒤|후|이후)", lambda m: {"minutes": int(m.group(1))}),
        (r"(\d+)\s*시간\s*(뒤|후|이후)", lambda m: {"hours": int(m.group(1))}),
        (r"(\d+)\s*일\s*(뒤|후|이후)", lambda m: {"days": int(m.group(1))}),
        (r"내일|다음날", lambda m: {"tomorrow": True}),
    ]

    for pattern, extractor in patterns:
        match = re.search(pattern, q)
        if match:
            return extractor(match)

    return {}

def time_info_to_minutes(info: dict) -> int:
    """시간 정보 딕셔너리를 총 분(min) 단위로 변환.
    지원 키: minutes/hours/days
    """
    if not isinstance(info, dict):
        return 0
    if 'minutes' in info and isinstance(info['minutes'], (int, float)):
        return int(info['minutes'])
    if 'hours' in info and isinstance(info['hours'], (int, float)):
        return int(info['hours']) * 60
    if 'days' in info and isinstance(info['days'], (int, float)):
        return int(info['days']) * 24 * 60
    return 0