# tools/internal_vector_search.py

from utils.logger import setup_logger
# MongoDBStorage 클래스 임포트 (싱글톤 인스턴스 사용)
from storage.mongodb_storage import MongoDBStorage
from config import TOP_K_RESULTS # 설정 값 임포트
from tools.base_tool import BaseTool

logger = setup_logger(__name__)

# 기존 internal_vector_search 함수 로직을 클래스 메소드로 이동
# def internal_vector_search(query: str, file_filter: str = None, tags_filter: list[str] = None):
#     ...

class VectorSearchTool(BaseTool):
    """MongoDB Atlas Vector Search를 사용하여 문서를 검색하는 도구"""

    def __init__(self):
        super().__init__(
            name="vector_search_tool",
            description=(
                "사용자의 질문과 관련된 내부 문서 저장소의 내용을 검색합니다. "
                "주로 업로드된 문서에 대한 질문이나 내용 요약/응답에 사용하세요. "
                "검색 쿼리를 입력받으며, 필요시 특정 파일 이름(file_filter)이나 태그 목록(tags_filter)으로 검색을 필터링할 수 있습니다." # 설명 업데이트
            )
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
            # MongoDBStorage 싱글톤 인스턴스 사용
            mongo_storage = MongoDBStorage.get_instance()

            # 파일 필터 처리: 제공된 필터가 있을 경우 실제 파일 이름을 찾아 사용
            actual_file_filter = file_filter
            if file_filter:
                logger.info(f"파일 필터 인자 제공됨: '{file_filter}'. 실제 파일 이름을 찾습니다.")
                try:
                    # GridFS에 저장된 파일 목록 조회
                    available_files = mongo_storage.list_files()
                    logger.info(f"GridFS에서 조회된 파일 목록: {[f['filename'] for f in available_files]}")

                    # 제공된 file_filter 문자열을 포함하는 파일 이름 찾기 (대소문자 구분 없이)
                    matching_files = [
                        f['filename'] for f in available_files
                        if file_filter.lower() in f['filename'].lower()
                    ]

                    if len(matching_files) == 1:
                        actual_file_filter = matching_files[0]
                        logger.info(f"매칭되는 파일 이름 하나 발견: '{actual_file_filter}'으로 필터링합니다.")
                    elif len(matching_files) > 1:
                        logger.warning(f"매칭되는 파일 이름이 여러 개 발견되었습니다 ({matching_files}). 제공된 필터 '{file_filter}'을 그대로 사용합니다.")
                        # 이 경우 사용자가 더 명확한 파일 이름을 제공하도록 유도하거나,
                        # 사용자에게 선택지를 주거나, 모든 매칭 파일에서 검색하는 등의 로직을 추가할 수 있지만,
                        # 현재는 제공된 필터를 그대로 사용하여 검색 결과가 부정확할 수 있음을 알립니다.
                        actual_file_filter = file_filter # 제공된 필터를 그대로 사용
                    else:
                        logger.warning(f"제공된 파일 필터 '{file_filter}'에 매칭되는 파일이 GridFS에 없습니다. 파일 필터 없이 검색합니다.")
                        actual_file_filter = None # 매칭되는 파일이 없으면 필터링하지 않음

                except Exception as file_filter_error:
                    logger.error(f"파일 필터 처리 중 오류 발생: {file_filter_error}")
                    actual_file_filter = file_filter # 오류 발생 시 제공된 필터를 그대로 사용 (또는 None)


            # MongoDBStorage의 vector_search 메소드 호출 (실제 파일 필터 사용)
            search_results = mongo_storage.vector_search(
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

# 이전 함수는 이제 사용되지 않으므로 제거하거나 주석 처리합니다.
# def internal_vector_search(query: str, file_filter: str = None, tags_filter: list[str] = None):
#     # 이 함수는 이제 InternalVectorSearchTool 클래스의 execute 메소드로 대체됩니다.
#     pass

# core/agent.py에서 이 클래스를 직접 임포트하여 사용하도록 수정해야 할 수 있습니다.
# 또는 ToolManager를 통해 간접적으로 사용.
# 현재 구조에서는 ToolManager를 통해 사용됩니다.

# 이 함수는 config.py의 AVAILABLE_FUNCTIONS에 정의되어야 합니다.
# 예: {'name': 'internal_vector_search', 'description': '...', 'parameters': {...}, 'function': internal_vector_search}
# 실제 호출은 core/agent.py에서 도구 매핑을 통해 이루어집니다. 