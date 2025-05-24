import os
from langchain_community.tools.tavily_search import TavilySearchResults
from tools.base_tool import BaseTool
from config import TAVILY_API_KEY
from utils.logger import setup_logger

logger = setup_logger(__name__)

class WebSearchTool(BaseTool):
    """웹 검색 도구"""
    
    def __init__(self, api_key=None, max_results=3):
        """
        웹 검색 도구 초기화
        
        Args:
            api_key (str, optional): Tavily API 키. 기본값은 환경변수에서 가져옵니다.
            max_results (int, optional): 반환할 최대 검색 결과 수. 기본값 3.
        """
        super().__init__(
            name="search_web",
            description="웹에서 정보를 검색합니다. 최신 정보, 뉴스, 일반적인 질문에 유용합니다."
        )
        self.api_key = api_key or TAVILY_API_KEY
        self.max_results = max_results
        
        # 환경변수에 API 키가 없으면 경고
        if not self.api_key:
            logger.warning("Tavily API 키가 설정되어 있지 않습니다. .env 또는 환경변수를 확인하세요.")
        
        try:
            self.search_tool = TavilySearchResults(max_results=self.max_results)
            logger.info("Tavily 웹 검색 도구 초기화 완료")
        except Exception as e:
            logger.error(f"Tavily 검색 도구 초기화 오류: {str(e)}")
            self.search_tool = None
    def execute(self, query):
        """
        웹 검색 실행
        
        Args:
            query (str): 검색할 쿼리
            
        Returns:
            list | dict: 검색 결과 (json 직렬화 가능)
        """
        logger.info(f"웹 검색 실행: {query}")
        
        if not self.search_tool:
            return {"error": "검색 도구가 초기화되지 않았습니다."}
        
        try:
            results = self.search_tool.invoke({"query": query})
            return results
        except Exception as e:
            logger.error(f"웹 검색 오류: {str(e)}")
            return {"error": f"검색 중 오류가 발생했습니다: {str(e)}"}
