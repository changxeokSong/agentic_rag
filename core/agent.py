import json
from core.query_analyzer import QueryAnalyzer
from utils.logger import setup_logger
from config import MAX_RETRIES, TIMEOUT # 설정 값 임포트
# 도구 함수들을 임포트
from tools.search_tool import search_tool
from tools.calculator_tool import calculator_tool
from tools.weather_tool import weather_tool
# MongoDB 관련 도구 임포트
from tools.mongodb_tools import list_mongodb_files_tool, get_mongodb_file_content_tool
# internal_vector_search 도구 임포트
from tools.internal_vector_search import internal_vector_search

logger = setup_logger(__name__)

class Agent:
    """사용자 질의를 받아 분석하고 도구를 사용하여 응답을 생성하는 에이전트"""

    def __init__(self, lm_studio_client):
        """
        에이전트 초기화.
        Args:
            lm_studio_client: LM Studio 클라이언트 인스턴스.
        """
        self.query_analyzer = QueryAnalyzer(lm_studio_client)
        self.lm_studio_client = lm_studio_client
        # 사용 가능한 도구 매핑 정의
        self.available_tools = {
            "search_tool": search_tool,
            "calculator_tool": calculator_tool,
            "weather_tool": weather_tool,
            "list_mongodb_files_tool": list_mongodb_files_tool,
            "get_mongodb_file_content_tool": get_mongodb_file_content_tool,
            "internal_vector_search": internal_vector_search, # internal_vector_search 도구 매핑 추가
        }
        logger.info("에이전트 초기화 및 도구 매핑 완료")

    def run(self, user_query):
        """
        에이전트 실행.
        Args:
            user_query (str): 사용자의 입력 질의.

        Returns:
            str: 사용자 질의에 대한 최종 응답.
        """
        logger.info(f"에이전트 실행 시작. 사용자 질의: {user_query}")
        tool_calls = []
        tool_results = []

        try:
            # 1. 질의 분석 및 도구 선택
            # 질의 분석기는 하나 이상의 도구 호출을 반환할 수 있습니다 (JSON 또는 JSON 배열)
            selected_tools = self.query_analyzer.analyze(user_query)
            logger.info(f"질의 분석 결과: {selected_tools}")

            # 단일 도구 호출을 배열로 변환하여 일괄 처리
            if not isinstance(selected_tools, list):
                selected_tools = [selected_tools]

            # 2. 도구 실행
            # 각 도구 호출에 대해 반복
            for tool_call_info in selected_tools:
                tool_name = tool_call_info.get("name")
                tool_arguments = tool_call_info.get("arguments", {})

                if tool_name and tool_name in self.available_tools:
                    logger.info(f"도구 실행: {tool_name} (인자: {tool_arguments})")
                    try:
                        # 도구 함수를 찾아서 인자와 함께 호출
                        tool_function = self.available_tools[tool_name]
                        # 인자 전달 시 **tool_arguments를 사용하여 딕셔너리를 키워드 인자로 언팩
                        result = tool_function(**tool_arguments)
                        tool_results.append({
                            "tool": tool_name,
                            "arguments": tool_arguments,
                            "result": result
                        })
                        logger.info(f"도구 실행 결과 ({tool_name}): {result}")
                    except Exception as e:
                        logger.error(f"도구 실행 중 오류 발생 ({tool_name}): {e}")
                        tool_results.append({
                             "tool": tool_name,
                             "arguments": tool_arguments,
                             "result": f"오류 발생: {e}"
                        })
                else:
                    logger.warning(f"알 수 없거나 비활성화된 도구 호출 감지: {tool_name}")
                    tool_results.append({
                        "tool": tool_name,
                        "arguments": tool_arguments,
                        "result": f"알 수 없거나 비활성화된 도구: {tool_name}"
                    })

            # 3. 도구 실행 결과를 바탕으로 최종 응답 생성
            # 모든 도구 결과 수집
            formatted_tool_results = "\n".join([f"도구: {r['tool']}\\n인자: {r['arguments']}\\n결과: {r['result']}\\n" for r in tool_results])

            response_prompt = f"""
            {RESPONSE_GENERATION_PROMPT.format(user_query=user_query, tool_results=formatted_tool_results)}
            """
            logger.info("최종 응답 생성을 위해 LLM 호출")
            final_response = self.lm_studio_client.completion(response_prompt)
            logger.info(f"최종 응답: {final_response}")

            return final_response

        except Exception as e:
            logger.error(f"에이전트 실행 중 전체 오류 발생: {e}")
            return f"죄송합니다. 질의를 처리하는 중 오류가 발생했습니다: {e}"

# 참고: 실제 실행 코드는 별도의 main 또는 app.py 파일에 있을 수 있습니다.
# Agent 클래스는 질의 분석, 도구 실행, 응답 생성의 핵심 로직을 담당합니다. 