# tools/internal_vector_search.py

from typing import Dict, Any
from utils.logger import setup_logger
# PostgreSQLStorage 클래스 임포트 (싱글톤 인스턴스 사용)
from storage.postgresql_storage import PostgreSQLStorage
from config import TOP_K_RESULTS # 설정 값 임포트

logger = setup_logger(__name__)

class VectorSearchTool:
    """PostgreSQL pgvector를 사용하여 문서를 검색하는 도구"""

    def __init__(self):
        self.name = "vector_search_tool"
        self.description = (
            "사용자의 질문과 관련된 내부 문서 저장소의 내용을 검색합니다. "
            "벡터(의미) 검색과 키워드(컨텍스트) 검색을 지원하며, 필요시 특정 파일 이름(file_filter)이나 태그(tags_filter)로 필터링할 수 있습니다."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "문서 저장소에서 검색할 키워드 또는 질문"
                },
                "file_filter": {
                    "type": "string",
                    "description": "검색 결과를 필터링할 특정 파일 이름 (선택 사항)"
                },
                 "tags_filter": {
                    "type": "array",
                    "items": { "type": "string" },
                    "description": "검색 결과를 필터링할 태그 목록 (선택 사항)"
                },
                "mode": {
                    "type": "string",
                    "enum": ["auto", "vector", "context"],
                    "description": "검색 모드: auto(기본), vector(임베딩 유사도), context(키워드)",
                    "default": "auto"
                }
            },
            "required": ["query"]
        }

    def execute(self, query: str, file_filter: str | None = None, tags_filter: list[str] | None = None, top_k: int | None = None, mode: str | None = None, **kwargs):
        """내부 문서 저장소에서 벡터 검색을 수행하고 결과를 반환합니다.

        호환성:
        - fileFilter(list[str]|str) → file_filter(str)
        - tagsFilter(str|list[str]) → tags_filter(list[str])
        - topK(str|int) → top_k(int)
        """
        logger.info(f"VectorSearchTool 실행: 쿼리='{query}', 파일 필터='{file_filter}', 태그 필터='{tags_filter}'")
        try:
            # 인자 정규화 (호환 처리)
            if file_filter is None:
                camel_ff = kwargs.get('fileFilter')
                if isinstance(camel_ff, list):
                    file_filter = camel_ff[0] if len(camel_ff) > 0 else None
                elif isinstance(camel_ff, str):
                    file_filter = camel_ff

            if tags_filter is None:
                camel_tf = kwargs.get('tagsFilter')
                if isinstance(camel_tf, str):
                    tags_filter = [camel_tf]
                elif isinstance(camel_tf, list):
                    tags_filter = camel_tf

            if top_k is None:
                camel_tk = kwargs.get('topK')
                if isinstance(camel_tk, str) and camel_tk.isdigit():
                    top_k = int(camel_tk)
                elif isinstance(camel_tk, int):
                    top_k = camel_tk

            if mode is None:
                camel_mode = kwargs.get('mode')
                if isinstance(camel_mode, str):
                    mode = camel_mode

            if isinstance(tags_filter, str):
                tags_filter = [tags_filter]
            if isinstance(file_filter, list):
                file_filter = file_filter[0] if len(file_filter) > 0 else None

            # PostgreSQLStorage 싱글톤 인스턴스 사용
            pg_storage = PostgreSQLStorage.get_instance()
            if pg_storage is None:
                logger.error("PostgreSQLStorage 인스턴스가 초기화되지 않았습니다.")
                return []

            # 파일 필터 처리: 제공된 필터가 있을 경우 실제 파일 이름을 찾아 사용
            actual_file_filter = file_filter
            if file_filter:
                logger.info(f"파일 필터 인자 제공됨: '{file_filter}'. 실제 파일 이름을 찾습니다.")
                try:
                    # PostgreSQLStorage의 vector_search 메소드 호출
                    # PostgreSQL의 vector_search는 file_filter 인자를 문자열(파일 이름)로 직접 받을 수 있음
                    # tags_filter는 list[str] 형태로 전달
                    # mypy/pylance 회피: None일 수 있는 파라미터 보정
                    safe_file_filter = actual_file_filter if isinstance(actual_file_filter, str) else None
                    safe_tags_filter = tags_filter if isinstance(tags_filter, list) else None
                    safe_top_k = (top_k if isinstance(top_k, int) and top_k > 0 else TOP_K_RESULTS)

                    # 모드 결정: auto → vector 우선, 실패 시 context 백업
                    run_mode = (mode or 'auto').lower()
                    if run_mode == 'context':
                        search_results = pg_storage.context_search(
                            query=query,
                            file_filter=safe_file_filter or "",
                            tags_filter=safe_tags_filter or [],
                            top_k=int(safe_top_k)
                        )
                    else:
                        try:
                            search_results = pg_storage.vector_search(
                                query=query,
                                file_filter=safe_file_filter or "",
                                tags_filter=safe_tags_filter or [],
                                top_k=int(safe_top_k)
                            )
                            # vector 결과가 비었고 auto이면 context로 폴백
                            if (not search_results) and run_mode == 'auto':
                                search_results = pg_storage.context_search(
                                    query=query,
                                    file_filter=safe_file_filter or "",
                                    tags_filter=safe_tags_filter or [],
                                    top_k=int(safe_top_k)
                                )
                        except Exception as e:
                            logger.warning(f"vector 검색 실패, context로 폴백: {e}")
                            search_results = pg_storage.context_search(
                                query=query,
                                file_filter=safe_file_filter or "",
                                tags_filter=safe_tags_filter or [],
                                top_k=int(safe_top_k)
                            )

                    if not search_results:
                        return []

                    # 검색 결과를 JSON 리스트로 반환 (출처 식별을 위해 file_id 포함)
                    result = []
                    for doc in search_results:
                        metadata = doc.get('metadata', {}) or {}
                        content = doc.get('content', '내용 없음')
                        filename = metadata.get('filename', '파일 이름 알 수 없음')
                        file_id = metadata.get('original_file_id')  # files.id
                        chunk_index = metadata.get('chunk_index', 'N/A')
                        score = doc.get('score', 'N/A')
                        # 검색 기반 답변의 근거로 사용하기 위해 전체 내용을 반환
                        display_content = content
                        result.append({
                            "filename": filename,
                            "file_id": str(file_id) if file_id is not None else None,
                            "chunk_index": chunk_index,
                            "score": score,
                            "content": display_content
                        })
                    return result

                except Exception as file_filter_error:
                    logger.error(f"파일 필터 처리 중 오류 발생: {file_filter_error}")
                    actual_file_filter = file_filter # 오류 발생 시 제공된 필터를 그대로 사용 (또는 None)

            # PostgreSQLStorage의 vector_search 메소드 호출 (실제 파일 필터 사용)
            # mypy/pylance 회피: None일 수 있는 파라미터 보정
            safe_file_filter = actual_file_filter if isinstance(actual_file_filter, str) else None
            safe_tags_filter = tags_filter if isinstance(tags_filter, list) else None
            safe_top_k = (top_k if isinstance(top_k, int) and top_k > 0 else TOP_K_RESULTS)
            run_mode = (mode or 'auto').lower()
            if run_mode == 'context':
                search_results = pg_storage.context_search(
                    query=query,
                    file_filter=safe_file_filter or "",
                    tags_filter=safe_tags_filter or [],
                    top_k=int(safe_top_k)
                )
            else:
                try:
                    search_results = pg_storage.vector_search(
                        query=query,
                        file_filter=safe_file_filter or "",
                        tags_filter=safe_tags_filter or [],
                        top_k=int(safe_top_k)
                    )
                    if (not search_results) and run_mode == 'auto':
                        search_results = pg_storage.context_search(
                            query=query,
                            file_filter=safe_file_filter or "",
                            tags_filter=safe_tags_filter or [],
                            top_k=int(safe_top_k)
                        )
                except Exception as e:
                    logger.warning(f"vector 검색 실패, context로 폴백: {e}")
                    search_results = pg_storage.context_search(
                        query=query,
                        file_filter=safe_file_filter or "",
                        tags_filter=safe_tags_filter or [],
                        top_k=int(safe_top_k)
                    )

            if not search_results:
                return []

            # 검색 결과를 JSON 리스트로 반환 (출처 식별을 위해 file_id 포함)
            result = []
            for doc in search_results:
                metadata = doc.get('metadata', {}) or {}
                content = doc.get('content', '내용 없음')
                filename = metadata.get('filename', '파일 이름 알 수 없음')
                file_id = metadata.get('original_file_id')  # files.id
                chunk_index = metadata.get('chunk_index', 'N/A')
                score = doc.get('score', 'N/A')
                # 검색 기반 답변의 근거로 사용하기 위해 전체 내용을 반환
                display_content = content
                result.append({
                    "filename": filename,
                    "file_id": str(file_id) if file_id is not None else None,
                    "chunk_index": chunk_index,
                    "score": score,
                    "content": display_content
                })
            return result

        except Exception as e:
            logger.error(f"InternalVectorSearchTool 실행 중 오류 발생: {str(e)}")
            return f"문서 검색 중 오류가 발생했습니다: {str(e)}"
    
    def get_info(self) -> Dict[str, str]:
        """도구 정보 반환"""
        return {
            "name": self.name,
            "description": self.description
        } 