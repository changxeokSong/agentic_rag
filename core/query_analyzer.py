# core/query_analyzer.py

from config import FUNCTION_SELECTION_PROMPT, AVAILABLE_FUNCTIONS
from utils.logger import setup_logger
import json
import re

logger = setup_logger(__name__)

class QueryAnalyzer:
    """사용자 질의를 분석하고 적절한 도구를 선택하는 분석기"""
    
    def __init__(self, lm_studio_client):
        """질의 분석기 초기화"""
        self.lm_studio_client = lm_studio_client
        logger.info("질의 분석기 초기화")
    
    def analyze(self, query):
        """사용자 질의를 분석하고 사용할 도구를 결정"""
        logger.info(f"질의 분석: {query}")
        
        def extract_filename_from_query(query):
            # 예: '배수지 수위 데이터 엑셀 파일' → '배수지 수위 데이터'
            m = re.search(r'([\w\d가-힣_\-\.]+)\s*(엑셀|xlsx|xls|파일)', query)
            if m:
                return m.group(1)
            return None
        
        # 프롬프트에 도구 설명, 예시 추가 (config에서 관리)
        prompt = f"{FUNCTION_SELECTION_PROMPT}\n\n사용자 질문: {query}"
        
        # 함수 호출 요청
        try:
            result = self.lm_studio_client.function_call(prompt, AVAILABLE_FUNCTIONS)
            logger.info(f"모델 반환값: {result}")

            # result가 문자열(즉, JSON 문자열)일 경우 파싱 시도
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except Exception as e:
                    logger.error(f"모델 반환값 JSON 파싱 오류: {e}, result: {result}")
                    return {"name": "search_tool", "arguments": {"query": query}}

            # 여러 도구 반환 지원
            if isinstance(result, list):
                # 여러 도구 중 엑셀 미리보기 도구가 있으면 filename 자동 추출
                for call in result:
                    if call["name"] in ["excel_reader_tool"]:
                        if not call["arguments"].get("filename"):
                            filename = extract_filename_from_query(query)
                            if filename:
                                call["arguments"]["filename"] = filename
                return result

            # 반환값 검증 (단일 도구)
            if (
                result is None
                or not isinstance(result, dict)
                or "name" not in result
                or "arguments" not in result
                or not result["name"]
            ):
                logger.warning(f"모델이 올바른 도구를 반환하지 않음: {result}")
                return {"name": "search_tool", "arguments": {"query": query}}

            # db_excel_preview_tool, excel_reader_tool이면 filename 자동 추출
            if result["name"] in ["excel_reader_tool"]:
                if not result["arguments"].get("filename"):
                    filename = extract_filename_from_query(query)
                    if filename:
                        result["arguments"]["filename"] = filename

            # arguments가 비어있을 때도 체크
            if not result["arguments"]:
                # 인자가 필요 없는 도구는 예외적으로 허용
                if result["name"] in ["list_files_tool"]:
                    logger.info(f"인자 없는 도구 정상 허용: {result['name']}")
                    return result
                logger.warning(f"도구 인자가 비어있음: {result}")
                return {"name": "search_tool", "arguments": {"query": query}}

            logger.info(f"선택된 도구: {result['name']}, 인자: {result['arguments']}")
            return result
        except Exception as e:
            logger.error(f"도구 선택 오류: {str(e)}")
            # 오류 발생 시 기본 도구로 폴백
            return {"name": "search_tool", "arguments": {"query": query}}