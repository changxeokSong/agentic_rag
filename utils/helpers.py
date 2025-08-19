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
    
    # 코드 블록 제거 (일반 답변에서 코드 블록이 잘못 사용된 경우)
    response = remove_unwanted_code_blocks(response)
    
    return response

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