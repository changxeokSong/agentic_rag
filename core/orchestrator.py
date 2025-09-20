# core/orchestrator.py

from core.query_analyzer import QueryAnalyzer
from core.tool_manager import ToolManager
from core.response_generator import ResponseGenerator
from utils.logger import setup_logger

logger = setup_logger(__name__)

class Orchestrator:
    """전체 AgenticRAG 시스템 오케스트레이션"""
    
    def __init__(self, lm_studio_client):
        """오케스트레이터 초기화"""
        self.lm_studio_client = lm_studio_client
        self.query_analyzer = QueryAnalyzer(lm_studio_client)
        self.tool_manager = ToolManager()
        self.response_generator = ResponseGenerator(lm_studio_client)
        logger.info("오케스트레이터 초기화 완료")
    
    async def process_query(self, query):
        """사용자 질의 처리 파이프라인 - 개선된 복합 도구 처리"""
        logger.info(f"질의 처리 시작: {query}")
        
        # 1. 질의 분석 및 도구 선택
        tool_call = self.query_analyzer.analyze(query)
        
        # 2. 선택된 도구 실행 - 개선된 상호작용 처리
        tool_results = {}
        if tool_call:
            # query_analyzer는 이제 항상 리스트를 반환함
            tool_calls = tool_call if isinstance(tool_call, list) else [tool_call]
            
            # 복합 질의인 경우 도구 간 데이터 공유를 위한 컨텍스트 생성
            execution_context = {
                "query": query,
                "previous_results": {},
                "shared_data": {}
            }
            
            for i, call in enumerate(tool_calls):
                tool_name = call["name"]
                arguments = call["arguments"]
                logger.info(f"도구 실행 [{i+1}/{len(tool_calls)}]: {tool_name}, 인자: {arguments}")
                
                # 모든 도구에 공통으로 전달할 정보
                enhanced_arguments = arguments.copy()
                enhanced_arguments["query"] = query
                enhanced_arguments["execution_context"] = execution_context
                
                # 도구별 특별 처리
                enhanced_arguments = self._prepare_tool_arguments(tool_name, enhanced_arguments, execution_context)
                
                result = self.tool_manager.execute_tool(tool_name, **enhanced_arguments)
                logger.info(f"도구 실행 결과 요약: {self._summarize_result(result)}")
                
                # 결과 저장 및 컨텍스트 업데이트
                base_key = tool_name
                result_key = base_key
                counter = 0
                while result_key in tool_results:
                    counter += 1
                    result_key = f"{base_key}_{counter}"
                
                tool_results[result_key] = result
                execution_context["previous_results"][result_key] = result
                
                # 다음 도구들이 활용할 수 있도록 중요한 데이터 추출
                self._update_shared_context(execution_context, tool_name, result)
                
        else:
            logger.info("도구가 선택되지 않음 - 일반 대화로 처리")
        
        # 3. 최종 응답 생성 - 컨텍스트 정보 포함
        final_response = self.response_generator.generate(query, tool_results)
        
        return {
            "query": query,
            "tool_calls": tool_call,
            "tool_results": tool_results,
            "response": final_response # ResponseGenerator가 생성한 텍스트 응답
        }
    
    def _prepare_tool_arguments(self, tool_name: str, arguments: dict, execution_context: dict) -> dict:
        """도구별 인수 전처리 및 최적화"""
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
    
    def _update_shared_context(self, execution_context: dict, tool_name: str, result):
        """실행 컨텍스트에 도구 결과 반영"""
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
    
    def _summarize_result(self, result) -> str:
        """결과 요약 생성 (로깅용)"""
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
    
    def process_query_sync(self, query):
        """동기 방식의 질의 처리 (비동기 래퍼)"""
        import asyncio
        return asyncio.run(self.process_query(query))