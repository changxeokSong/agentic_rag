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
        """사용자 질의 처리 파이프라인"""
        logger.info(f"질의 처리 시작: {query}")
        
        # 1. 질의 분석 및 도구 선택
        tool_call = self.query_analyzer.analyze(query)
        
        # 2. 선택된 도구 실행
        tool_results = {}
        if tool_call:
            # query_analyzer는 이제 항상 리스트를 반환함
            tool_calls = tool_call if isinstance(tool_call, list) else [tool_call]
            
            for i, call in enumerate(tool_calls):
                tool_name = call["name"]
                arguments = call["arguments"]
                logger.info(f"도구 실행 [{i+1}/{len(tool_calls)}]: {tool_name}, 인자: {arguments}")
                
                # 수위 예측 도구의 경우 사용자 질문을 추가로 전달
                if tool_name == "water_level_prediction_tool":
                    arguments["user_query"] = query
                
                result = self.tool_manager.execute_tool(tool_name, **arguments)
                logger.info(f"도구 실행 결과: {result}")
                
                # 같은 도구가 여러 번 호출될 수 있으므로 키를 고유하게 만듦
                result_key = f"{tool_name}_{i}" if f"{tool_name}_0" in tool_results else tool_name
                tool_results[result_key] = result
        else:
            logger.info("도구가 선택되지 않음 - 일반 대화로 처리")
        
        # 3. 최종 응답 생성
        final_response = self.response_generator.generate(query, tool_results)
        
        return {
            "query": query,
            "tool_calls": tool_call,
            "tool_results": tool_results,
            "response": final_response # ResponseGenerator가 생성한 텍스트 응답
        }
    
    def process_query_sync(self, query):
        """동기 방식의 질의 처리 (비동기 래퍼)"""
        import asyncio
        return asyncio.run(self.process_query(query))