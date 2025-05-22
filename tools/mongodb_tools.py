from tools.base_tool import BaseTool
from utils.logger import setup_logger
from storage.mongodb_storage import MongoDBStorage # MongoDBStorage 클래스 임포트
# 필요한 함수 임포트 (더 이상 개별 함수를 임포트하지 않음)

logger = setup_logger(__name__)

class ListMongoDBFilesTool(BaseTool):
    """MongoDB GridFS에 저장된 파일 목록을 조회하는 도구"""

    def __init__(self):
        super().__init__(
            name="list_mongodb_files_tool",
            description="MongoDB GridFS에 저장된 파일 목록을 조회합니다. 사용자가 업로드한 파일의 이름이나 목록 정보가 필요할 때 사용하세요."
        )

    def execute(self):
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
                file_size_kb = round(file_info.get("length", 0) / 1024, 2)
                formatted_list.append(f"- 파일 이름: {filename}, 크기: {file_size_kb} KB")

            return "\\n".join(formatted_list)
        except Exception as e:
            logger.error(f"MongoDB 파일 목록 조회 오류: {str(e)}")
            return f"파일 목록 조회 중 오류가 발생했습니다: {str(e)}"

class GetMongoDBFileContentTool(BaseTool):
    """MongoDB GridFS에 저장된 특정 파일의 내용을 가져오는 도구"""

    def __init__(self):
        super().__init__(
            name="get_mongodb_file_content_tool",
            description="MongoDB GridFS에 저장된 특정 파일의 내용을 가져옵니다. 사용자가 업로드한 파일의 내용을 확인하거나 응답에 활용해야 할 때 사용하세요. 파일 이름을 입력받습니다."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "내용을 가져올 파일의 이름"
                }
            },
            "required": ["filename"]
        }

    def execute(self, filename: str):
        """파일 이름으로 파일을 검색하고 내용을 가져와 반환합니다."""
        logger.info(f"MongoDB 파일 내용 가져오기 실행: 파일 이름 {filename}")
        try:
            # MongoDBStorage 싱글톤 인스턴스 사용
            mongo_storage = MongoDBStorage.get_instance()

            # get_file_content 메소드 사용
            file_content_bytes = mongo_storage.get_file_content(filename)

            if file_content_bytes is None:
                return f"'{filename}' 파일을 찾을 수 없거나 내용을 가져올 수 없습니다."

            # 파일 내용을 읽어서 반환 (텍스트 파일로 가정)
            content = file_content_bytes.decode('utf-8')

            logger.info(f"'{filename}' 파일 내용 가져오기 성공 (길이: {len(content)} bytes)")
            return f"'{filename}' 파일 내용:\\n---\\n{content}\\n---"

        except Exception as e:
            logger.error(f"MongoDB 파일 내용 가져오기 오류 (파일 이름: {filename}): {str(e)}")
            return f"파일 내용 가져오기 중 오류가 발생했습니다: {str(e)}" 