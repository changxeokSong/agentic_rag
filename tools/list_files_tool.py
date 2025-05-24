from tools.base_tool import BaseTool
from utils.logger import setup_logger
from storage.mongodb_storage import MongoDBStorage # MongoDBStorage 클래스 임포트
# 필요한 함수 임포트 (더 이상 개별 함수를 임포트하지 않음)

logger = setup_logger(__name__)

class ListFilesTool(BaseTool):
    """MongoDB GridFS에 저장된 파일 목록을 조회하는 도구"""

    def __init__(self):
        super().__init__(
            name="list_files_tool",
            description="MongoDB GridFS에 저장된 파일 목록을 조회합니다. 사용자가 업로드한 파일의 이름이나 목록 정보가 필요할 때 사용하세요."
        )

    def execute(self, **kwargs):
        """파일 목록을 조회하고 결과를 반환합니다."""
        logger.info("MongoDB 파일 목록 조회 실행")
        try:
            # MongoDBStorage 싱글톤 인스턴스 사용
            mongo_storage = MongoDBStorage.get_instance()
            file_list = mongo_storage.list_files()
            if not file_list:
                return "저장된 파일이 없습니다."

            # 파일 목록 정보를 보기 좋게 포맷팅
            formatted_list = ["저장된 파일 목록:"]
            for file_info in file_list:
                filename = file_info.get("filename", "알 수 없는 파일")
                file_size_mb = round(file_info.get("length", 0) / (1024*1024), 2)
                formatted_list.append(f"- 파일 이름: {filename}, 크기: {file_size_mb} MB")

            return "\n".join(formatted_list)
        except Exception as e:
            logger.error(f"MongoDB 파일 목록 조회 오류: {str(e)}")
            return f"파일 목록 조회 중 오류가 발생했습니다: {str(e)}" 