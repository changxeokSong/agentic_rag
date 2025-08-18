# core/tool_manager.py

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
        # 웹 검색 도구 제거됨
        

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
                
        # 인자 정규화 (camelCase → snake_case 등)
        normalized_kwargs = self._normalize_arguments(tool_name, kwargs or {})
        logger.info(f"도구 실행: {tool_name}, 인자: {normalized_kwargs}")
        tool = self.tools[tool_name]
        
        try:
            result = tool.execute(**normalized_kwargs)
            return result
        except Exception as e:
            logger.error(f"도구 실행 오류 ({tool_name}): {str(e)}")
            return f"도구 실행 중 오류가 발생했습니다: {str(e)}"

    def _normalize_arguments(self, tool_name: str, kwargs: dict) -> dict:
        """LLM이 반환하는 다양한 키 스타일을 표준 키로 정규화한다."""
        if not isinstance(kwargs, dict):
            return {}

        # 공통 camelCase → snake_case 매핑 후보
        common_map = {
            'fileFilter': 'file_filter',
            'tagsFilter': 'tags_filter',
            'topK': 'top_k',
        }

        normalized = dict(kwargs)
        for src, dst in common_map.items():
            if src in normalized and dst not in normalized:
                normalized[dst] = normalized.pop(src)

        # 툴별 특이 타입 보정
        if tool_name == 'vector_search_tool':
            # file_filter: str | list[str] → str (첫 번째 값 사용)
            ff = normalized.get('file_filter')
            if isinstance(ff, list):
                if len(ff) > 0:
                    logger.warning(f"vector_search_tool.file_filter 리스트 인자 감지. 첫 항목만 사용: {ff[0]}")
                    normalized['file_filter'] = ff[0]
                else:
                    normalized['file_filter'] = None

            # tags_filter: str → [str]
            tf = normalized.get('tags_filter')
            if isinstance(tf, str):
                normalized['tags_filter'] = [tf]

            # top_k: 문자열일 수 있음 → int 변환 시도
            tk = normalized.get('top_k')
            if isinstance(tk, str) and tk.isdigit():
                normalized['top_k'] = int(tk)

        return normalized
    
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