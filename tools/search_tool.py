# tools/search_tool.py

import os
from langchain.tools import DuckDuckGoSearchRun
from tools.base_tool import BaseTool
from config import SEARCH_ENGINE_API_KEY
from utils.logger import setup_logger

logger = setup_logger(__name__)

class WebSearchTool(BaseTool):
    """웹 검색 도구"""
    
    def __init__(self, api_key=None):
        """
        웹 검색 도구 초기화
        
        Args:
            api_key (str, optional): 검색 엔진 API 키. 기본값은 환경변수에서 가져옵니다.
        """
        super().__init__(
            name="search_web",
            description="웹에서 정보를 검색합니다. 최신 정보, 뉴스, 일반적인 질문에 유용합니다."
        )
        self.api_key = api_key or SEARCH_ENGINE_API_KEY
        
        # 검색 도구 설정
        # API 키가 있으면 해당 API를 사용하고, 없으면 기본 검색 사용
        try:
            if self.api_key:
                # 실제로는 Serper, SerpAPI 등을 사용할 수 있음
                # 예시: self.search_tool = SerpAPIWrapper(serpapi_api_key=self.api_key)
                self.search_tool = DuckDuckGoSearchRun()
                logger.info("웹 검색 도구 초기화 (API 키 사용)")
            else:
                self.search_tool = DuckDuckGoSearchRun()
                logger.info("웹 검색 도구 초기화 (기본 검색 사용)")
        except Exception as e:
            logger.error(f"검색 도구 초기화 오류: {str(e)}")
            self.search_tool = None
    
    def execute(self, query):
        """
        웹 검색 실행
        
        Args:
            query (str): 검색할 쿼리
            
        Returns:
            str: 검색 결과
        """
        logger.info(f"웹 검색 실행: {query}")
        
        if not self.search_tool:
            return "검색 도구가 초기화되지 않았습니다."
        
        try:
            result = self.search_tool.run(query)
            # 결과 길이 제한 (너무 길면 모델 처리에 부담)
            max_length = 2000
            if len(result) > max_length:
                result = result[:max_length] + "... (결과가 너무 길어 일부만 표시됩니다)"
            return result
        except Exception as e:
            logger.error(f"웹 검색 오류: {str(e)}")
            return f"검색 중 오류가 발생했습니다: {str(e)}"