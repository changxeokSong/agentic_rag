# core/query_analyzer.py

from config import FUNCTION_SELECTION_PROMPT, AVAILABLE_FUNCTIONS
from utils.logger import setup_logger
import json

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
        
        # LLM에 도구 선택 요청
        prompt = f"{FUNCTION_SELECTION_PROMPT}\n\n사용자 질문: {query}"
        logger.info(f"도구 선택 프롬프트: {prompt}")
        
        # 함수 호출 요청
        try:
            result = self.lm_studio_client.function_call(prompt, AVAILABLE_FUNCTIONS)
            logger.info(f"모델 원본 반환값: {result}")

            # result가 문자열(즉, JSON 문자열)일 경우 파싱 시도
            if isinstance(result, str):
                logger.info(f"문자열 결과 파싱 시도: {result}")
                try:
                    result = json.loads(result)
                    logger.info(f"JSON 파싱 성공: {result}")
                except Exception as e:
                    logger.error(f"모델 반환값 JSON 파싱 오류: {e}, result: {result}")
                    return None

            # 결과 검증 및 정규화
            if isinstance(result, list):
                # 빈 배열인 경우 (도구가 필요하지 않음)
                if len(result) == 0:
                    logger.info("도구가 필요하지 않은 일반 대화로 판단됨")
                    return None
                
                # 배열인 경우 각 항목 검증
                validated_results = []
                for item in result:
                    if isinstance(item, dict) and "name" in item and "arguments" in item:
                        validated_results.append(item)
                    else:
                        logger.warning(f"잘못된 도구 항목: {item}")
                
                if validated_results:
                    logger.info(f"선택된 도구들: {[r['name'] for r in validated_results]}")
                    return validated_results
                else:
                    logger.warning("유효한 도구가 없음")
                    return None
            
            elif isinstance(result, dict) and "name" in result and "arguments" in result:
                # 단일 객체인 경우 배열로 변환
                logger.info(f"선택된 도구: {result['name']}")
                return [result]
            
            else:
                # 잘못된 형태인 경우
                logger.warning(f"모델이 올바른 도구를 반환하지 않음: {result}")
                return None
            
        except Exception as e:
            logger.error(f"도구 선택 오류: {str(e)}", exc_info=True)
            # 오류 발생 시 도구 없음으로 반환
            return None