# core/tool_manager.py

from tools.search_tool import WebSearchTool
from tools.calculator_tool import CalculatorTool
from tools.weather_tool import WeatherTool
from tools.list_files_tool import ListFilesTool
from tools.vector_search_tool import VectorSearchTool
from tools.water_level_prediction_tool import WaterLevelPredictionTool
from tools.arduino_water_sensor_tool import ArduinoWaterSensorTool
from config import ENABLED_TOOLS
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ToolManager:
    """도구 관리 및 실행 담당"""
    
    def __init__(self):
        """도구 관리자 초기화"""
        self.tools = {}
        self._register_tools()
        logger.info(f"도구 관리자 초기화 완료 (활성화된 도구: {', '.join(self.tools.keys())})")
    
    def _register_tools(self):
        """환경변수 설정에 따라 활성화된 도구만 등록"""
        # 웹 검색 도구
        if "search_tool" in ENABLED_TOOLS:
            self.tools["search_tool"] = WebSearchTool()
        
        # 계산 도구
        if "calculator_tool" in ENABLED_TOOLS:
            self.tools["calculator_tool"] = CalculatorTool()
        
        # 날씨 도구
        if "weather_tool" in ENABLED_TOOLS:
            self.tools["weather_tool"] = WeatherTool()

        # 파일 목록 조회 도구 등록
        if "list_files_tool" in ENABLED_TOOLS:
            self.tools["list_files_tool"] = ListFilesTool()

        # 벡터 검색 도구 등록
        if "vector_search_tool" in ENABLED_TOOLS:
            self.tools["vector_search_tool"] = VectorSearchTool()

        # 수위 예측 도구 등록
        if "water_level_prediction_tool" in ENABLED_TOOLS:
            self.tools["water_level_prediction_tool"] = WaterLevelPredictionTool()

        # 아두이노 수위 센서 도구 등록
        if "arduino_water_sensor" in ENABLED_TOOLS:
            self.tools["arduino_water_sensor"] = ArduinoWaterSensorTool()

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
        
        # kwargs가 None이면 빈 dict으로 대체
        if kwargs is None:
            kwargs = {}
                
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