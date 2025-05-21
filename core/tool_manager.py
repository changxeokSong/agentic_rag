# core/tool_manager.py

import os
from tools.search_tool import WebSearchTool
from tools.vector_tool import VectorSearchTool
from tools.calculator_tool import CalculatorTool
from tools.weather_tool import WeatherTool
from config import ENABLED_TOOLS
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ToolManager:
    """도구 관리 및 실행 담당"""
    
    def __init__(self, vector_store=None):
        """
        도구 관리자 초기화
        
        Args:
            vector_store (VectorStore, optional): 벡터 데이터베이스 인스턴스
        """
        self.tools = {}
        self._register_tools(vector_store)
        logger.info(f"도구 관리자 초기화 완료 (활성화된 도구: {', '.join(self.tools.keys())})")
    
    def _register_tools(self, vector_store):
        """
        환경변수 설정에 따라 활성화된 도구만 등록
        
        Args:
            vector_store (VectorStore): 벡터 데이터베이스 인스턴스
        """
        # 웹 검색 도구
        if "search_tool" in ENABLED_TOOLS:
            self.tools["search_tool"] = WebSearchTool()
        
        # 벡터 검색 도구 (벡터 저장소가 제공된 경우)
        if "vector_tool" in ENABLED_TOOLS and vector_store:
            self.tools["vector_tool"] = VectorSearchTool(vector_store)
        
        # 계산 도구
        if "calculator_tool" in ENABLED_TOOLS:
            self.tools["calculator_tool"] = CalculatorTool()
        
        # 날씨 도구
        if "weather_tool" in ENABLED_TOOLS:
            self.tools["weather_tool"] = WeatherTool()
        
        logger.info(f"등록된 도구: {', '.join(self.tools.keys())}")
    
    def execute_tool(self, tool_name, **kwargs):
        """
        지정된 도구 실행
        
        Args:
            tool_name (str): 실행할 도구 이름
            **kwargs: 도구에 전달할 인자
            
        Returns:
            str: 도구 실행 결과
        """
        if tool_name not in self.tools:
            logger.error(f"알 수 없는 도구: {tool_name}")
            return f"오류: '{tool_name}'은(는) 존재하지 않거나 활성화되지 않은 도구입니다."
        
        logger.info(f"도구 실행: {tool_name}, 인자: {kwargs}")
        tool = self.tools[tool_name]
        
        try:
            result = tool.execute(**kwargs)
            return result
        except Exception as e:
            logger.error(f"도구 실행 오류 ({tool_name}): {str(e)}")
            return f"도구 실행 중 오류가 발생했습니다: {str(e)}"
    
    def get_all_tools(self):
        """모든 도구 목록 반환"""
        return list(self.tools.values())
    
    def get_tool_info(self):
        """도구 정보 반환"""
        return {
            name: {
                "name": tool.name,
                "description": tool.description,
                "active": True
            }
            for name, tool in self.tools.items()
        }