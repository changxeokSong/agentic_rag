# core/tool_manager.py

from typing import Dict, Any, Optional, List, Union, Callable
from tools.list_files_tool import ListFilesTool
from tools.vector_search_tool import VectorSearchTool
from tools.water_level_prediction_tool import WaterLevelPredictionTool
from tools.arduino_water_sensor_tool import ArduinoWaterSensorTool
from tools.water_level_monitoring_tool import water_level_monitoring_tool
from tools.real_time_database_control_tool import real_time_database_control_tool
from tools.advanced_water_analysis_tool import advanced_water_analysis_tool
from tools.automation_control_tool import automation_control_tool
from tools.smart_water_prediction_tool import SmartWaterPredictionTool
from config import ENABLED_TOOLS
from utils.logger import setup_logger
from utils.exceptions import ToolExecutionError

logger = setup_logger(__name__)


class ToolManager:
    """도구 관리 및 실행 담당

    환경변수에 따라 활성화된 도구들을 등록하고 실행합니다.

    Attributes:
        tools: 등록된 도구들의 딕셔너리
    """

    def __init__(self):
        """도구 관리자 초기화"""
        self.tools: Dict[str, Union[Any, Callable]] = {}
        self._register_tools()
        logger.info(f"도구 관리자 초기화 완료 (활성화된 도구: {', '.join(self.tools.keys())})")
    
    def _register_tools(self) -> None:
        """환경변수 설정에 따라 활성화된 도구만 등록

        ENABLED_TOOLS 환경변수에 따라 도구를 선택적으로 등록합니다.
        클래스 기반 도구와 함수형 도구를 모두 지원합니다.
        """
        tool_registry = {
            "list_files_tool": ListFilesTool,
            "vector_search_tool": VectorSearchTool,
            "water_level_prediction_tool": WaterLevelPredictionTool,
            "arduino_water_sensor": ArduinoWaterSensorTool,
            "smart_water_prediction": SmartWaterPredictionTool,
        }

        # 함수형 도구
        function_tools = {
            "water_level_monitoring_tool": water_level_monitoring_tool,
            "real_time_database_control_tool": real_time_database_control_tool,
            "advanced_water_analysis_tool": advanced_water_analysis_tool,
            "automation_control_tool": automation_control_tool,
        }

        # 클래스 기반 도구 등록
        for tool_name, tool_class in tool_registry.items():
            if tool_name in ENABLED_TOOLS:
                try:
                    self.tools[tool_name] = tool_class()
                    logger.debug(f"도구 등록 완료: {tool_name}")
                except Exception as e:
                    logger.error(f"도구 등록 실패: {tool_name} - {e}")

        # 함수형 도구 등록
        for tool_name, tool_func in function_tools.items():
            if tool_name in ENABLED_TOOLS:
                self.tools[tool_name] = tool_func
                logger.debug(f"함수형 도구 등록 완료: {tool_name}")

        logger.info(f"등록된 도구 ({len(self.tools)}개): {', '.join(self.tools.keys())}")
    
    def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """지정된 도구 실행

        Args:
            tool_name: 실행할 도구 이름
            **kwargs: 도구에 전달할 인자

        Returns:
            Any: 도구 실행 결과

        Raises:
            ToolExecutionError: 도구 실행 중 오류 발생 시
        """
        if tool_name not in self.tools:
            error_msg = f"'{tool_name}'은(는) 존재하지 않거나 활성화되지 않은 도구입니다."
            logger.error(error_msg)
            raise ToolExecutionError(error_msg, {"tool_name": tool_name})

        # kwargs가 None이면 빈 dict으로 대체
        if kwargs is None:
            kwargs = {}

        # 인자 정규화 (camelCase → snake_case 등)
        normalized_kwargs = self._normalize_arguments(tool_name, kwargs)
        logger.info(f"도구 실행: {tool_name}, 인자: {normalized_kwargs}")

        tool = self.tools[tool_name]

        try:
            # 함수형 도구 (callable이지만 execute 메소드 없음)
            if callable(tool) and not hasattr(tool, 'execute'):
                result = tool(**normalized_kwargs)
            else:
                # 클래스 기반 도구 (execute 메소드 보유)
                result = tool.execute(**normalized_kwargs)

            logger.debug(f"도구 실행 성공: {tool_name}")
            return result

        except Exception as e:
            error_msg = f"도구 실행 중 오류 발생: {tool_name}"
            logger.error(f"{error_msg} - {str(e)}", exc_info=True)
            raise ToolExecutionError(
                error_msg,
                {"tool_name": tool_name, "error": str(e), "kwargs": normalized_kwargs}
            ) from e

    def _normalize_arguments(self, tool_name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """LLM이 반환하는 다양한 키 스타일을 표준 키로 정규화

        camelCase를 snake_case로 변환하고, 도구별 특수 처리를 수행합니다.

        Args:
            tool_name: 도구 이름
            kwargs: 정규화할 인자 딕셔너리

        Returns:
            Dict[str, Any]: 정규화된 인자 딕셔너리
        """
        if not isinstance(kwargs, dict):
            logger.warning(f"인자가 딕셔너리가 아닙니다: {type(kwargs)}")
            return {}

        # 공통 camelCase → snake_case 매핑 후보
        common_map = {
            'fileFilter': 'file_filter',
            'tagsFilter': 'tags_filter',
            'topK': 'top_k',
            'dataPoints': 'dataPoints',  # 유지 (호환 키)
            'futureTimeSteps': 'futureTimeSteps',  # 유지 (호환 키)
            'predictionHours': 'prediction_hours',
            'timeHorizon': 'time_horizon',
            'predictionSteps': 'prediction_steps',
            'lookbackHours': 'lookback_hours',
            'timeMinutes': 'time_minutes'
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

        if tool_name == 'water_level_prediction_tool':
            # 숫자형으로 정규화
            ps = normalized.get('prediction_steps')
            if isinstance(ps, str) and ps.isdigit():
                normalized['prediction_steps'] = int(ps)
            ph = normalized.get('prediction_hours')
            if isinstance(ph, str) and ph.isdigit():
                normalized['prediction_hours'] = int(ph)

        if tool_name == 'smart_water_prediction':
            # dam → reservoir 매핑
            if 'dam' in normalized and 'reservoir' not in normalized:
                dam_value = normalized.pop('dam')
                # 배수지 이름 매핑
                dam_lower = dam_value.lower() if isinstance(dam_value, str) else str(dam_value).lower()
                if '가곡' in dam_lower or 'gagok' in dam_lower:
                    normalized['reservoir'] = 'gagok'
                elif '해룡' in dam_lower or 'haeryong' in dam_lower:
                    normalized['reservoir'] = 'haeryong'
                else:
                    # 지원하지 않는 배수지 - 기본값으로 가곡 설정
                    logger.warning(f"지원하지 않는 배수지: {dam_value}. 가곡 배수지로 대체합니다.")
                    normalized['reservoir'] = 'gagok'

            # time → time_minutes 매핑 및 파싱
            if 'time' in normalized and 'time_minutes' not in normalized:
                time_value = normalized.pop('time')

                # 시간 문자열 파싱
                if isinstance(time_value, str):
                    time_str = time_value.lower().strip()

                    # 'today_0900', 'today_9:00' 같은 형식 처리
                    if 'today' in time_str or 'now' in time_str:
                        # 현재 시간 기준으로 예측 (기본 30분)
                        normalized['time_minutes'] = 30
                        logger.info(f"시간 '{time_value}'를 30분 후로 해석합니다.")
                    # '1h', '2hour' 같은 형식
                    elif 'h' in time_str or 'hour' in time_str:
                        import re
                        match = re.search(r'(\d+)', time_str)
                        if match:
                            hours = int(match.group(1))
                            normalized['time_minutes'] = hours * 60
                        else:
                            normalized['time_minutes'] = 60
                    # '30m', '45min' 같은 형식
                    elif 'm' in time_str or 'min' in time_str:
                        import re
                        match = re.search(r'(\d+)', time_str)
                        if match:
                            normalized['time_minutes'] = int(match.group(1))
                        else:
                            normalized['time_minutes'] = 30
                    # 숫자 문자열
                    elif time_str.isdigit():
                        normalized['time_minutes'] = int(time_str)
                    else:
                        # 기본값 30분
                        normalized['time_minutes'] = 30
                        logger.warning(f"시간 '{time_value}'를 파싱할 수 없어 30분으로 설정합니다.")
                elif isinstance(time_value, (int, float)):
                    normalized['time_minutes'] = int(time_value)
                else:
                    normalized['time_minutes'] = 30

            # time_minutes 타입 변환
            tm = normalized.get('time_minutes')
            if isinstance(tm, str) and tm.isdigit():
                normalized['time_minutes'] = int(tm)

        return normalized

    def get_all_tools(self) -> List[Union[Any, Callable]]:
        """모든 도구 목록 반환

        Returns:
            List[Union[Any, Callable]]: 등록된 모든 도구의 리스트
        """
        return list(self.tools.values())

    def get_tool(self, tool_name: str) -> Optional[Union[Any, Callable]]:
        """지정된 도구 객체 반환

        Args:
            tool_name: 도구 이름

        Returns:
            Optional[Union[Any, Callable]]: 도구 객체 또는 None
        """
        return self.tools.get(tool_name)

    def get_tool_info(self) -> Dict[str, Dict[str, Any]]:
        """도구 정보 반환

        Returns:
            Dict[str, Dict[str, Any]]: 각 도구의 정보를 담은 딕셔너리
        """
        tool_info: Dict[str, Dict[str, Any]] = {}

        for name, tool in self.tools.items():
            if callable(tool) and not hasattr(tool, 'name'):
                # 함수형 도구
                tool_info[name] = {
                    "name": name,
                    "description": tool.__doc__ or "설명 없음",
                    "type": "function",
                    "active": True
                }
            else:
                # 클래스 기반 도구
                tool_info[name] = {
                    "name": getattr(tool, 'name', name),
                    "description": getattr(tool, 'description', "설명 없음"),
                    "type": "class",
                    "active": True
                }

        return tool_info