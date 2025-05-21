# core/response_generator.py

from config import RESPONSE_GENERATION_PROMPT
from utils.helpers import format_tool_results
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ResponseGenerator:
    """최종 응답 생성 담당"""
    
    def __init__(self, lm_studio_client):
        """응답 생성기 초기화"""
        self.lm_studio_client = lm_studio_client
        logger.info("응답 생성기 초기화")
    
    def generate(self, user_query, tool_results):
        """도구 실행 결과와 원래 질의를 바탕으로 최종 응답 생성"""
        logger.info("최종 응답 생성")
        
        # 도구 결과 포맷팅
        formatted_results = format_tool_results(tool_results)
        
        # 프롬프트 구성
        prompt = RESPONSE_GENERATION_PROMPT.format(
            user_query=user_query,
            tool_results=formatted_results
        )
        
        # 응답 생성
        try:
            response = self.lm_studio_client.generate_response(prompt)
            return response
        except Exception as e:
            logger.error(f"응답 생성 오류: {str(e)}")
            return f"응답을 생성하는 중 오류가 발생했습니다. 검색 결과: {formatted_results}"