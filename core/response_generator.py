# core/response_generator.py

from config import RESPONSE_GENERATION_PROMPT
from utils.helpers import format_tool_results
from utils.logger import setup_logger

logger = setup_logger(__name__)

def filter_tool_results_for_llm(tool_results):
    """LLM에 전달하기 전 대용량/불필요 필드를 생략 처리"""
    def filter_value(v):
        if isinstance(v, dict):
            v = v.copy()
            for key in list(v.keys()):
                # PDF 보고서의 raw markdown 필드 제외
                if key == "markdown":
                    del v[key]
                    continue # 다음 키로 건너뛰기

                if key in ["image_base64", "pdf_base64"]:
                    v[key] = "[생략됨]"
                elif isinstance(v[key], (list, dict)) and len(str(v[key])) > 3000:
                    v[key] = "[내용이 너무 커서 생략됨]"
            return v
        elif isinstance(v, list) and len(v) > 10:
            return "[리스트가 너무 커서 생략됨]"
        elif isinstance(v, str) and len(v) > 1000:
            return v[:500] + "... [이후 생략]"
        return v
    return {k: filter_value(v) for k, v in tool_results.items()}

class ResponseGenerator:
    """최종 응답 생성 담당"""
    
    def __init__(self, lm_studio_client):
        """응답 생성기 초기화"""
        self.lm_studio_client = lm_studio_client
        logger.info("응답 생성기 초기화")
    
    def generate(self, user_query, tool_results):
        """도구 실행 결과와 원래 질의를 바탕으로 최종 응답 생성"""
        logger.info("최종 응답 생성")
        
        # Arduino 도구의 상세 메시지가 있는지 확인
        detailed_messages = []
        for tool_name, result in tool_results.items():
            if tool_name == "arduino_water_sensor" and isinstance(result, dict):
                if result.get("detailed_message"):
                    detailed_messages.append(result["detailed_message"])
        
        # Arduino 상세 메시지가 있으면 직접 사용
        if detailed_messages:
            return "\n\n".join(detailed_messages)
        
        # 도구 결과 필터링 (대용량/불필요 필드 생략)
        filtered_results = filter_tool_results_for_llm(tool_results)
        formatted_results = format_tool_results(filtered_results)
        
        # 프롬프트 구성
        prompt = RESPONSE_GENERATION_PROMPT.format(
            user_query=user_query,
            tool_results=formatted_results
        )
        
        # 응답 생성
        try:
            response = self.lm_studio_client.generate_response(prompt)
            
            # 파일 다운로드 안내 추가 (PDF 및 그래프)
            pdf_info = None
            graph_infos = []
            for v in tool_results.values():
                if isinstance(v, dict):
                    if v.get("pdf_file_id") and v.get("pdf_filename"):
                        pdf_info = (v["pdf_file_id"], v["pdf_filename"])
                    if v.get("graph_file_id") and v.get("graph_filename"):
                        graph_infos.append((v["graph_file_id"], v["graph_filename"]))

            if pdf_info:
                response += f"\n\n---\n**[PDF 다운로드 안내]**\n아래 PDF 파일을 다운로드하려면 프론트엔드의 다운로드 버튼을 클릭하세요.\n파일명: {pdf_info[1]}\n(file_id: {pdf_info[0]})"

            if graph_infos:
                response += "\n\n---\n**[그래프 파일 정보]**"
                for gid, gname in graph_infos:
                    response += f"\n- 생성된 그래프 파일명: {gname}\n  (graph_file_id: {gid})\n  프론트엔드에서 이 ID를 사용하여 그래프를 표시하거나 다운로드할 수 있습니다."

            return response
        except Exception as e:
            logger.error(f"응답 생성 오류: {str(e)}")
            return f"응답을 생성하는 중 오류가 발생했습니다. 검색 결과: {formatted_results}"