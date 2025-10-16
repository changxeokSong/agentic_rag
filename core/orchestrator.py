# core/orchestrator.py

from typing import Dict, Any, List, Optional, Generator, Union
from core.query_analyzer import QueryAnalyzer
from core.tool_manager import ToolManager
from core.response_generator import ResponseGenerator
from utils.logger import setup_logger
from utils.exceptions import AgenticRAGException

logger = setup_logger(__name__)


class Orchestrator:
    """전체 AgenticRAG 시스템 오케스트레이션

    사용자 질의를 받아 분석, 도구 실행, 응답 생성의 전체 파이프라인을 관리합니다.

    Attributes:
        lm_studio_client: LM Studio 클라이언트 인스턴스
        query_analyzer: 쿼리 분석기
        tool_manager: 도구 관리자
        response_generator: 응답 생성기
    """

    def __init__(self, lm_studio_client):
        """오케스트레이터 초기화

        Args:
            lm_studio_client: LM Studio 클라이언트 인스턴스
        """
        self.lm_studio_client = lm_studio_client
        self.query_analyzer = QueryAnalyzer(lm_studio_client)
        self.tool_manager = ToolManager()
        self.response_generator = ResponseGenerator(lm_studio_client)
        logger.info("오케스트레이터 초기화 완료")
    
    async def process_query(
        self,
        query: str,
        stream: bool = True
    ) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]:
        """사용자 질의 처리 파이프라인 - 스트리밍 지원

        Args:
            query: 사용자 질문
            stream: 스트리밍 여부 (기본 True)

        Returns:
            Union[Dict[str, Any], Generator]: stream=False면 dict, stream=True면 generator

        Raises:
            AgenticRAGException: 질의 처리 중 오류 발생 시
        """
        logger.info(f"질의 처리 시작: {query} (스트리밍: {stream})")

        # 1. 질의 분석 및 도구 선택
        tool_call_raw = self.query_analyzer.analyze(query)

        # 1.5. 도구 호출 정규화
        if tool_call_raw:
            tool_calls = tool_call_raw if isinstance(tool_call_raw, list) else [tool_call_raw]
            tool_calls = self._normalize_tool_calls(tool_calls)
        else:
            tool_calls = []

        # 2. 선택된 도구 실행
        tool_results = {}
        if tool_calls:
            execution_context = {
                "query": query,
                "previous_results": {},
                "shared_data": {}
            }

            for i, call in enumerate(tool_calls):
                tool_name = call["name"]
                arguments = call["arguments"]
                logger.info(f"도구 실행 [{i+1}/{len(tool_calls)}]: {tool_name}, 인자: {arguments}")

                enhanced_arguments = arguments.copy()
                enhanced_arguments["query"] = query
                enhanced_arguments["execution_context"] = execution_context
                enhanced_arguments = self._prepare_tool_arguments(tool_name, enhanced_arguments, execution_context)

                result = self.tool_manager.execute_tool(tool_name, **enhanced_arguments)
                logger.info(f"도구 실행 결과 요약: {self._summarize_result(result)}")

                base_key = tool_name
                result_key = base_key
                counter = 0
                while result_key in tool_results:
                    counter += 1
                    result_key = f"{base_key}_{counter}"

                tool_results[result_key] = result
                execution_context["previous_results"][result_key] = result
                self._update_shared_context(execution_context, tool_name, result)

        else:
            logger.info("도구가 선택되지 않음 - 일반 대화로 처리")

        # 3. 최종 응답 생성
        final_response = self.response_generator.generate(query, tool_results, stream=stream)

        if stream:
            # 스트리밍 모드: 응답을 청크로 나누어 전송
            def stream_result():
                # final_response는 이미 generator이므로 직접 yield
                for chunk in final_response:
                    yield {"type": "chunk", "content": chunk}
                
                # 스트리밍 완료 후 메타데이터 전송
                yield {
                    "type": "done",
                    "query": query,
                    "tool_calls": tool_call_raw,
                    "tool_results": tool_results
                }
            return stream_result()
        else:
            # 비스트리밍 모드: dict 반환
            return {
                "query": query,
                "tool_calls": tool_call_raw,
                "tool_results": tool_results,
                "response": final_response
            }
    
    def _normalize_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """LLM이 반환한 도구 호출을 정규화하고 인자를 수정합니다."""
        if not tool_calls:
            return tool_calls

        from datetime import datetime, timedelta
        import re

        # tool_calls를 순회하면서 수정해야 하므로 인덱스를 사용합니다.
        for i in range(len(tool_calls)):
            tool = tool_calls[i]

            # prediction_tool 도구 정규화
            if tool['name'] == 'prediction_tool':
                args = tool['arguments']
                
                # simple 예측으로 기본 설정
                if 'action' not in args:
                    args['action'] = 'predict_simple'

                # predict_simple 액션에 대한 정규화
                if args['action'] == 'predict_simple':
                    if 'reservoir' not in args:
                        if 'dam' in args:
                            args['reservoir'] = args.pop('dam')
                        else:
                            args['reservoir'] = 'gagok'
                            logger.info("prediction_tool에 배수지가 지정되지 않아 기본값 'gagok'을 사용합니다.")

                    if 'time_minutes' not in args:
                        time_arg = args.pop('time', None) or args.pop('prediction_time', None)
                        if time_arg:
                            pass


            # water_level_monitoring_tool 정규화 및 리디렉션
            if tool['name'] == 'water_level_monitoring_tool':
                args = tool['arguments']
                
                if 'period' in args or 'metric' in args:
                    logger.info("'water_level_monitoring_tool' 호출을 'advanced_water_analysis_tool'로 리디렉션합니다.")
                    tool['name'] = 'advanced_water_analysis_tool'
                    args['action'] = 'pump_history'
                    
                    if 'dam' in args:
                        dam = args.pop('dam')
                        if '가곡' in dam: args['reservoir_id'] = 'gagok'
                        elif '해룡' in dam: args['reservoir_id'] = 'haeryong'
                        elif '상사' in dam: args['reservoir_id'] = 'sangsa'

                    if 'period' in args:
                        period = args.pop('period')
                        now = datetime.now()
                        if period == 'last_week':
                            today = now.date()
                            start_of_this_week = today - timedelta(days=today.weekday())
                            start_of_last_week = start_of_this_week - timedelta(days=7)
                            end_of_last_week = start_of_this_week - timedelta(days=1)
                            args['start_time'] = datetime.combine(start_of_last_week, datetime.min.time()).isoformat()
                            args['end_time'] = datetime.combine(end_of_last_week, datetime.max.time()).isoformat()
                    continue

                if 'action' in args and args['action'] in ['get_current_level', 'current_level', 'level_now']:
                    logger.info(f"'{args['action']}' 액션을 'current_status'로 정규화합니다.")
                    args['action'] = 'current_status'

        logger.info(f"✓ 정규화된 도구 호출: {tool_calls}")
        return tool_calls

    def _prepare_tool_arguments(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        execution_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """도구별 인수 전처리 및 최적화

        Args:
            tool_name: 도구 이름
            arguments: 원본 인수 딕셔너리
            execution_context: 실행 컨텍스트

        Returns:
            Dict[str, Any]: 전처리된 인수 딕셔너리
        """
        enhanced_args = arguments.copy()
        
        if tool_name == "water_level_prediction_tool":
            # 수위 예측 도구 전용 인수 추가
            enhanced_args["user_query"] = execution_context["query"]
            
            # 이전에 아두이노 센서 데이터가 수집되었다면 활용
            if "arduino_water_sensor" in execution_context["previous_results"]:
                arduino_result = execution_context["previous_results"]["arduino_water_sensor"]
                if isinstance(arduino_result, dict) and "current_water_level" in arduino_result:
                    enhanced_args["current_level"] = arduino_result["current_water_level"]
                    
        elif tool_name == "vector_search_tool":
            # 벡터 검색 도구에 query 누락 시 보정
            if "query" not in enhanced_args:
                enhanced_args["query"] = execution_context["query"]
                
        elif tool_name == "advanced_water_analysis_tool":
            # 고급 분석 도구에 이전 결과 데이터 전달
            if "water_level_prediction_tool" in execution_context["previous_results"]:
                pred_result = execution_context["previous_results"]["water_level_prediction_tool"]
                if isinstance(pred_result, dict) and "predictions" in pred_result:
                    enhanced_args["prediction_data"] = pred_result
                    
            # 아두이노 데이터도 있다면 추가
            if "arduino_water_sensor" in execution_context["previous_results"]:
                enhanced_args["sensor_data"] = execution_context["previous_results"]["arduino_water_sensor"]
                
        return enhanced_args
    
    def _update_shared_context(
        self,
        execution_context: Dict[str, Any],
        tool_name: str,
        result: Any
    ) -> None:
        """실행 컨텍스트에 도구 결과 반영

        Args:
            execution_context: 실행 컨텍스트
            tool_name: 도구 이름
            result: 도구 실행 결과
        """
        shared_data = execution_context["shared_data"]
        
        try:
            if tool_name == "arduino_water_sensor" and isinstance(result, dict):
                # 아두이노 센서 데이터 공유
                if "current_water_level" in result:
                    shared_data["current_water_level"] = result["current_water_level"]
                if "pump1_status" in result:
                    shared_data["pump1_status"] = result["pump1_status"]
                if "pump2_status" in result:
                    shared_data["pump2_status"] = result["pump2_status"]
                    
            elif tool_name == "water_level_prediction_tool" and isinstance(result, dict):
                # 예측 결과 공유
                if "predictions" in result:
                    shared_data["predictions"] = result["predictions"]
                if "prediction_summary" in result:
                    shared_data["prediction_summary"] = result["prediction_summary"]
                    
            elif tool_name == "advanced_water_analysis_tool" and isinstance(result, dict):
                # 분석 결과 공유
                if "trend_analysis" in result:
                    shared_data["trend_analysis"] = result["trend_analysis"]
                if "comparison_analysis" in result:
                    shared_data["comparison_analysis"] = result["comparison_analysis"]
                    
        except Exception as e:
            logger.warning(f"컨텍스트 업데이트 중 오류 ({tool_name}): {e}")
    
    def _summarize_result(self, result: Any) -> str:
        """결과 요약 생성 (로깅용)

        Args:
            result: 도구 실행 결과

        Returns:
            str: 결과 요약 문자열
        """
        if isinstance(result, dict):
            if "error" in result:
                return f"오류: {result['error'][:100]}..."
            elif "predictions" in result:
                pred_count = len(result["predictions"]) if isinstance(result["predictions"], list) else 1
                return f"예측 완료 ({pred_count}개 결과)"
            elif "current_water_level" in result:
                return f"수위: {result['current_water_level']}"
            elif "documents" in result:
                doc_count = len(result["documents"]) if isinstance(result["documents"], list) else 0
                return f"문서 검색 완료 ({doc_count}개)"
            else:
                return f"성공 (키: {', '.join(list(result.keys())[:3])}...)"
        elif isinstance(result, str):
            return result[:100] + ("..." if len(result) > 100 else "")
        else:
            return f"결과 타입: {type(result)}"
    
    def process_query_sync(
        self,
        query: str,
        stream: bool = True
    ) -> Union[Dict[str, Any], Generator[Dict[str, Any], None, None]]:
        """동기 방식의 질의 처리 (비동기 래퍼)

        Args:
            query: 사용자 질문
            stream: 스트리밍 여부 (기본 True)

        Returns:
            Union[Dict[str, Any], Generator]: stream 옵션에 따라 반환
        """
        import asyncio
        return asyncio.run(self.process_query(query, stream=stream))