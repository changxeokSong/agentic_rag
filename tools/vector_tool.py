# tools/vector_tool.py

from tools.base_tool import BaseTool
from utils.logger import setup_logger

logger = setup_logger(__name__)

class VectorSearchTool(BaseTool):
    """벡터 검색 도구"""
    
    def __init__(self, vector_store):
        """벡터 검색 도구 초기화"""
        super().__init__(
            name="vector_tool",
            description="내부 문서 저장소(사내 위키, 정책, 기술 문서 등)에서 정보를 검색합니다. 회사 내부 자료, 정책, 기술 가이드, 업무 매뉴얼 등 조직 내에서만 접근 가능한 정보가 필요할 때 사용하세요."
        )
        self.vector_store = vector_store
    
    def execute(self, query, collection="user_uploads"):
        """벡터 검색 실행"""
        logger.info(f"벡터 검색 실행: {query}, 컬렉션: {collection}")
        try:
            results = self.vector_store.search(query, collection)
            
            if not results:
                return "검색 결과가 없습니다."
            
            # 결과 포맷팅
            formatted_results = []
            for i, doc in enumerate(results):
                formatted_results.append(f"결과 {i+1}:")
                formatted_results.append(doc.page_content)
                formatted_results.append("")
            
            return "\n".join(formatted_results)
        except Exception as e:
            logger.error(f"벡터 검색 오류: {str(e)}")
            return f"검색 중 오류가 발생했습니다: {str(e)}"