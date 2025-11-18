# core/response_generator.py

from config import RESPONSE_GENERATION_PROMPT
from utils.helpers import format_tool_results, clean_ai_response, normalize_markdown_tables, unfence_markdown_tables
from utils.logger import setup_logger

logger = setup_logger(__name__)

def filter_tool_results_for_llm(tool_results):
    """LLM에 전달하기 전 대용량/불필요 필드를 생략 처리 (vector_search는 제외)"""
    def filter_value(v, tool_name=""):
        # vector_search_tool 결과는 필터링하지 않음 (전체 내용 보존)
        if "vector_search" in tool_name.lower():
            if isinstance(v, dict):
                v = v.copy()
                for key in list(v.keys()):
                    # PDF 보고서의 raw markdown 필드만 제외
                    if key == "markdown":
                        del v[key]
                        continue
                    if key in ["image_base64", "pdf_base64"]:
                        v[key] = "[생략됨]"
                return v
            return v  # 리스트나 문자열은 그대로 반환

        # 다른 도구 결과는 기존 로직 적용
        if isinstance(v, dict):
            v = v.copy()
            for key in list(v.keys()):
                if key == "markdown":
                    del v[key]
                    continue
                if key in ["image_base64", "pdf_base64"]:
                    v[key] = "[생략됨]"
                elif isinstance(v[key], (list, dict)) and len(str(v[key])) > 5000:
                    v[key] = "[내용이 너무 커서 생략됨]"
            return v
        elif isinstance(v, list) and len(v) > 20:
            return "[리스트가 너무 커서 생략됨]"
        elif isinstance(v, str) and len(v) > 2000:
            return v[:1000] + "... [이후 생략]"
        return v
    return {k: filter_value(v, k) for k, v in tool_results.items()}

class ResponseGenerator:
    """최종 응답 생성 담당"""
    
    def __init__(self, lm_studio_client):
        """응답 생성기 초기화"""
        self.lm_studio_client = lm_studio_client
        logger.info("응답 생성기 초기화")
    
    
    def generate(self, user_query, tool_results, stream=True):
        """도구 실행 결과와 원래 질의를 바탕으로 최종 응답 생성

        Args:
            user_query: 사용자 질문
            tool_results: 도구 실행 결과
            stream: 스트리밍 여부 (기본 True)

        Returns:
            Generator or str: stream=True면 generator, 아니면 문자열
        """
        logger.info(f"최종 응답 생성 (스트리밍: {stream})")

        # 도구가 전혀 없으면 일반 대화 프롬프트
        if not tool_results or (isinstance(tool_results, dict) and not any(tool_results.values())):
            # --- 개선된 프롬프트 ---
            chat_prompt = f"""<ROLE>
당신은 사용자의 질문에 대해 체계적이고 유용한 답변을 제공하는 전문 AI 어시스턴트입니다.
</ROLE>

<INSTRUCTIONS>
- 사용자의 질문을 명확히 파악하고, 그에 대한 직접적인 답변으로 시작해야 합니다.
- 답변, 상세 설명, 도움말 순서의 구조를 반드시 준수하여 응답을 작성하십시오.
- 정보가 불확실할 경우, 추측하지 말고 "해당 정보는 제가 가지고 있지 않아 답변드리기 어렵습니다."라고 명확히 밝히십시오.
- 전문적이면서도 이해하기 쉬운 어조를 사용하십시오.
</INSTRUCTIONS>

<FORMATTING_RULES>
- 제목: 메인 제목은 `##`, 서브 제목은 `###`를 사용하십시오. (예: `## 답변`)
- 목록: 순서 없는 목록은 `-`, 순서 있는 목록은 `1.`로 시작하십시오.
- 강조: 중요한 내용은 `**`로 감싸십시오. (예: `**중요 내용**`)
- **중요**: 제목에는 절대 이모지를 사용하지 마십시오. 본문에서는 의미 전달에 도움이 될 때만 최소한으로 사용하십시오.
- **중요**: 답변에 코드 블록(```)을 절대 포함하지 마십시오.
</FORMATTING_RULES>

<REQUIRED_STRUCTURE>
## 답변
[사용자 질문에 대한 핵심적이고 직접적인 답변을 여기에 작성하십시오.]

### 상세 설명
[답변에 대한 구체적인 정보, 배경, 예시 등을 논리적으로 설명하십시오.]

### 도움말
[사용자에게 도움이 될 만한 추가 팁, 관련 정보, 권장 사항 등을 제안하십시오.]
</REQUIRED_STRUCTURE>

<CONTEXT>
사용자 질문: {user_query}
</CONTEXT>

이제 위의 지시사항과 구조를 엄격히 준수하여 답변을 생성하십시오:
"""
            try:
                response = self.lm_studio_client.generate_response(chat_prompt, stream=stream)

                if stream:
                    # generator인 경우 후처리 적용하여 yield
                    def process_stream():
                        full_text = ""
                        for chunk in response:
                            full_text += chunk
                            yield chunk
                        
                        # 스트리밍 완료 후 통일된 후처리 적용
                        from utils.helpers import apply_consistent_formatting
                        formatted_text = apply_consistent_formatting(full_text)
                        # 후처리된 결과를 반환 (app.py에서 사용)
                        return formatted_text
                    
                    return process_stream()
                else:
                    from utils.helpers import apply_consistent_formatting
                    return apply_consistent_formatting(response)
            except Exception as e:
                logger.error(f"일반 대화 응답 생성 오류: {str(e)}")
                error_msg = "죄송합니다. 지금은 답변을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요."
                if stream:
                    def error_stream():
                        yield error_msg
                    return error_stream()
                return error_msg

        # 도구 결과 필터링 (대용량/불필요 필드 생략)
        filtered_results = filter_tool_results_for_llm(tool_results)
        formatted_results = format_tool_results(filtered_results)

        # --- 개선된 프롬프트 ---
        retrieval_guard_prompt = f"""<ROLE>
당신은 주어진 도구 실행 결과를 분석하여, 사용자의 질문에 대한 사실 기반의 보고서를 생성하는 데이터 분석 전문가입니다.
</ROLE>

<INSTRUCTIONS>
- **매우 중요**: 당신의 답변은 반드시 아래 `<CONTEXT>`에 제공된 "도구 실행 결과"에만 근거해야 합니다. 절대 외부 지식을 사용하거나 정보를 추측해서는 안 됩니다.
- "도구 실행 결과"의 모든 핵심 정보를 빠짐없이 요약하여 보고서에 포함시키십시오.
- 사용자가 질문의 의도를 파악하고, 그에 맞춰 가장 중요한 정보부터 제시하십시오.
- 보고서는 '핵심 요약', '상세 정보', '추가 정보', '출처'의 순서로 구성되어야 합니다.
</INSTRUCTIONS>

<FORMATTING_RULES>
- 제목: 메인 제목은 `##`, 서브 제목은 `###`를 사용하십시오.
- 표: 데이터를 명확하게 비교하거나 나열해야 할 때 마크다운 표를 사용하십시오.
- 목록: 순서 없는 목록은 `-`, 순서 있는 목록은 `1.`로 시작하십시오.
- 강조: 중요한 수치나 결과는 `**`로 감싸 강조하십시오.
- **중요**: 제목에는 이모지를 절대 사용하지 마십시오.
- **중요**: 답변에 코드 블록(```)을 절대 포함하지 마십시오.
</FORMATTING_RULES>

<REQUIRED_STRUCTURE>
## 핵심 요약
[사용자 질문에 대해 "도구 실행 결과"에서 찾은 가장 중요한 결론이나 답변을 한두 문장으로 요약하여 제시하십시오.]

### 상세 정보
[구체적인 데이터, 수치, 상태 등을 목록이나 표를 사용하여 체계적으로 정리하여 보여주십시오.]

### 추가 정보
[데이터의 의미를 해석하거나, 관련된 배경 정보, 사용자가 알아야 할 사항 등을 설명하십시오.]

### 출처
[정보의 출처(파일명, 도구 이름 등)를 명확하게 기재하십시오.]
</REQUIRED_STRUCTURE>

<CONTEXT>
사용자 질문: {user_query}

도구 실행 결과:
{formatted_results}
</CONTEXT>

이제 위의 지시사항과 구조를 엄격히 준수하여, 제공된 "도구 실행 결과"만을 바탕으로 완전한 마크다운 보고서를 작성하십시오:
"""

        # 추가 정보 수집 (PDF, 그래프, 출처)
        pdf_info = None
        graph_infos = []
        vector_sources = set()
        for v in tool_results.values():
            if isinstance(v, dict):
                if v.get("pdf_file_id") and v.get("pdf_filename"):
                    pdf_info = (v["pdf_file_id"], v["pdf_filename"])
                if v.get("graph_file_id") and v.get("graph_filename"):
                    graph_infos.append((v["graph_file_id"], v["graph_filename"]))
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        fname = item.get("filename") or item.get("file_name")
                        if fname:
                            vector_sources.add(str(fname))

        # 후처리 정보 생성
        suffix = ""
        if pdf_info:
            suffix += f"\n\n---\n**[PDF 다운로드 안내]**\n파일명: {pdf_info[1]}\n(file_id: {pdf_info[0]})"
        if graph_infos:
            suffix += "\n\n---\n**[그래프 파일 정보]**"
            for gid, gname in graph_infos:
                suffix += f"\n- {gname} (graph_file_id: {gid})"
        if vector_sources:
            suffix += "\n\n---\n**[참고된 문서 목록]**"
            for src in vector_sources:
                suffix += f"\n- {src}"

        # 응답 생성
        try:
            response = self.lm_studio_client.generate_response(retrieval_guard_prompt, stream=stream)

            if stream:
                # 스트리밍: generator 반환
                def stream_with_suffix():
                    full_text = ""
                    for chunk in response:
                        full_text += chunk
                        yield chunk

                    # 스트리밍 완료 후 통일된 후처리 적용
                    from utils.helpers import apply_consistent_formatting
                    formatted_text = apply_consistent_formatting(full_text)
                    
                    if self._contains_fake_data(formatted_text):
                        logger.warning("AI가 가짜 데이터로 응답을 시도했습니다.")
                        yield "\n\n" + self._generate_error_response(tool_results)
                    else:
                        # 후처리 정보 추가
                        if suffix:
                            yield suffix
                        
                        # 후처리된 응답을 반환 (app.py에서 사용)
                        return formatted_text

                return stream_with_suffix()
            else:
                # 비스트리밍 - 통일된 후처리 적용
                from utils.helpers import apply_consistent_formatting
                formatted_response = apply_consistent_formatting(response)

                if self._contains_fake_data(formatted_response):
                    logger.warning("AI가 가짜 데이터로 응답을 시도했습니다.")
                    return self._generate_error_response(tool_results)

                return formatted_response + suffix

        except Exception as e:
            logger.error(f"응답 생성 오류: {str(e)}")
            error_response = self._generate_error_response(tool_results)
            if stream:
                def error_stream():
                    yield error_response
                return error_stream()
            return error_response
    
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