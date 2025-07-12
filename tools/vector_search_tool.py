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
            "주로 업로드된 문서에 대한 질문이나 내용 요약/응답에 사용하세요. "
            "검색 쿼리를 입력받으며, 필요시 특정 파일 이름(file_filter)이나 태그 목록(tags_filter)으로 검색을 필터링할 수 있습니다."
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
                }
            },
            "required": ["query"]
        }

    def execute(self, query: str, file_filter: str = None, tags_filter: list[str] = None):
        """내부 문서 저장소에서 벡터 검색을 수행하고 결과를 반환합니다."""
        logger.info(f"VectorSearchTool 실행: 쿼리='{query}', 파일 필터='{file_filter}', 태그 필터='{tags_filter}'")
        try:
            # PostgreSQLStorage 싱글톤 인스턴스 사용
            pg_storage = PostgreSQLStorage.get_instance()

            # 파일 필터 처리: 제공된 필터가 있을 경우 실제 파일 이름을 찾아 사용
            actual_file_filter = file_filter
            if file_filter:
                logger.info(f"파일 필터 인자 제공됨: '{file_filter}'. 실제 파일 이름을 찾습니다.")
                try:
                    # PostgreSQLStorage의 vector_search 메소드 호출
                    # PostgreSQL의 vector_search는 file_filter 인자를 문자열(파일 이름)로 직접 받을 수 있음
                    # tags_filter는 list[str] 형태로 전달
                    search_results = pg_storage.vector_search(
                        query=query,
                        file_filter=actual_file_filter, # <- 처리된 파일 필터 사용
                        tags_filter=tags_filter,
                        top_k=TOP_K_RESULTS # config에서 가져온 TOP_K_RESULTS 사용
                    )

                    if not search_results:
                        return []

                    # 검색 결과를 JSON 리스트로 반환
                    result = []
                    for doc in search_results:
                        content = doc.get('content', '내용 없음')
                        filename = doc.get('metadata', {}).get('filename', '파일 이름 알 수 없음')
                        chunk_index = doc.get('metadata', {}).get('chunk_index', 'N/A')
                        score = doc.get('score', 'N/A')
                        # 내용이 길 경우 일부만 표시
                        display_content = content[:200] + '...' if len(content) > 200 else content
                        result.append({
                            "filename": filename,
                            "chunk_index": chunk_index,
                            "score": score,
                            "content": display_content
                        })
                    return result

                except Exception as file_filter_error:
                    logger.error(f"파일 필터 처리 중 오류 발생: {file_filter_error}")
                    actual_file_filter = file_filter # 오류 발생 시 제공된 필터를 그대로 사용 (또는 None)

            # PostgreSQLStorage의 vector_search 메소드 호출 (실제 파일 필터 사용)
            search_results = pg_storage.vector_search(
                query=query,
                file_filter=actual_file_filter, # <- 처리된 파일 필터 사용
                tags_filter=tags_filter,
                top_k=TOP_K_RESULTS # config에서 가져온 TOP_K_RESULTS 사용
            )

            if not search_results:
                return []

            # 검색 결과를 JSON 리스트로 반환
            result = []
            for doc in search_results:
                content = doc.get('content', '내용 없음')
                filename = doc.get('metadata', {}).get('filename', '파일 이름 알 수 없음')
                chunk_index = doc.get('metadata', {}).get('chunk_index', 'N/A')
                score = doc.get('score', 'N/A')
                # 내용이 길 경우 일부만 표시
                display_content = content[:200] + '...' if len(content) > 200 else content
                result.append({
                    "filename": filename,
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