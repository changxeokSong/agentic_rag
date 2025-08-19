# core/response_generator.py

from config import RESPONSE_GENERATION_PROMPT
from utils.helpers import format_tool_results, clean_ai_response, normalize_markdown_tables, unfence_markdown_tables
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
        
        # 모든 도구 결과를 LLM에 전달하여 완전한 응답 생성
        # Arduino 도구 결과를 포함한 모든 결과를 균등하게 처리
        
        # 도구가 전혀 없으면 일반 대화 프롬프트로 간결 응답
        if not tool_results:
            chat_prompt = (
                "사용자의 질문에 공손한 한국어로 짧고 명확하게 답하세요.\n"
                "- 도구 결과가 없으므로 추정/환상을 금지하고, 알 수 없는 내용은 모른다고 답하세요.\n"
                "- 필요 시 적절한 이모지 1-2개만 사용하세요. 과도한 사용 금지.\n"
                "- HTML 금지, 간결한 마크다운 문장만. 표/섹션/코드블록은 사용하지 마세요.\n\n"
                f"질문: {user_query}"
            )
            try:
                response = self.lm_studio_client.generate_response(chat_prompt)
                return normalize_markdown_tables(unfence_markdown_tables(clean_ai_response(response)))
            except Exception as e:
                logger.error(f"일반 대화 응답 생성 오류: {str(e)}")
                return "죄송합니다. 지금은 답변을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요."

        # 도구 결과 필터링 (대용량/불필요 필드 생략)
        filtered_results = filter_tool_results_for_llm(tool_results)
        formatted_results = format_tool_results(filtered_results)
        
        # 프롬프트 구성 (도구 결과가 있을 때에만 상태/섹션 가이드 사용)
        prompt = RESPONSE_GENERATION_PROMPT.format(
            user_query=user_query,
            tool_results=formatted_results
        )
        
        # 응답 생성
        try:
            response = self.lm_studio_client.generate_response(prompt)
            
            # 응답 후처리: 양끝 따옴표 제거 및 표 정규화
            response = clean_ai_response(response)
            response = unfence_markdown_tables(normalize_markdown_tables(response))
            
            # 오류나 빈 결과 체크: 가짜 응답 방지
            if self._contains_fake_data(response):
                logger.warning("AI가 가짜 데이터로 응답을 시도했습니다. 오류 메시지로 대체합니다.")
                return self._generate_error_response(tool_results)
                
        except Exception as e:
            logger.error(f"응답 생성 오류: {str(e)}")
            return self._generate_error_response(tool_results)
        
        # 파일 다운로드 안내 추가 (PDF 및 그래프)
        pdf_info = None
        graph_infos = []
        vector_sources = set()
        for v in tool_results.values():
            if isinstance(v, dict):
                if v.get("pdf_file_id") and v.get("pdf_filename"):
                    pdf_info = (v["pdf_file_id"], v["pdf_filename"])
                if v.get("graph_file_id") and v.get("graph_filename"):
                    graph_infos.append((v["graph_file_id"], v["graph_filename"]))
            # vector_search_tool 결과에서 파일명 수집
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        fname = item.get("filename") or item.get("file_name")
                        if fname:
                            vector_sources.add(str(fname))

        if pdf_info:
            response += f"\n\n---\n**[PDF 다운로드 안내]**\n아래 PDF 파일을 다운로드하려면 프론트엔드의 다운로드 버튼을 클릭하세요.\n파일명: {pdf_info[1]}\n(file_id: {pdf_info[0]})"

        if graph_infos:
            response += "\n\n---\n**[그래프 파일 정보]**"
            for gid, gname in graph_infos:
                response += f"\n- 생성된 그래프 파일명: {gname}\n  (graph_file_id: {gid})\n  프론트엔드에서 이 ID를 사용하여 그래프를 표시하거나 다운로드할 수 있습니다."

        # 출처 섹션 추가 (vector_search_tool의 파일명을 기반으로)
        if vector_sources:
            response += "\n\n---\n**출처(파일 이름)**\n" + "\n".join(f"- {s}" for s in sorted(vector_sources))


        return response
    
    def _contains_fake_data(self, response):
        """응답에 가짜 데이터가 포함되어 있는지 검사"""
        fake_indicators = [
            "Document1.pdf", "ProjectPlan", "ImageLibrary", 
            "CodeSnippet", "notes_2023", "photo001.jpg",
            "최근 수정된 보고서", "프로젝트 계획 문서", "업무 메모 파일"
        ]
        return any(indicator in response for indicator in fake_indicators)
    
    def _generate_error_response(self, tool_results):
        """도구 실행 결과를 기반으로 적절한 오류 응답 생성 - 마크다운 형식"""
        errors = []
        
        # 파일 목록 도구의 오류 확인
        for tool_name, result in tool_results.items():
            if "list_files" in tool_name:
                if isinstance(result, dict) and "error" in result:
                    errors.append("""## ❌ 데이터베이스 연결 오류

⚠️ **데이터베이스 연결에 문제가 있습니다.**

### 🔧 해결 방법
1. 시스템 초기화를 실행해주세요
2. 관리자에게 문의하세요
3. PostgreSQL 서버 상태를 확인하세요""")
                elif isinstance(result, list) and len(result) == 0:
                    errors.append("""## 📁 파일 상태

📋 **현재 업로드된 파일이 없습니다.**

새로운 파일을 업로드해주세요.""")
            
            # 아두이노 도구 오류 확인
            if "arduino" in tool_name and isinstance(result, dict):
                if "error" in result or "오류" in str(result):
                    errors.append("""## ❌ 아두이노 연결 오류

⚠️ **아두이노 연결에 문제가 있습니다.**

### 🔧 해결 방법
1. '아두이노 연결해줘'를 시도해보세요
2. USB 케이블 연결 상태를 확인하세요
3. 아두이노 전원을 확인하세요""")
        
        if errors:
            return "\n".join(errors)
        
        return """## ❌ 처리 오류

죄송합니다. 요청하신 정보를 처리할 수 없습니다.

### 🔧 권장사항
- 시스템 상태를 확인해주세요
- 잠시 후 다시 시도해주세요"""