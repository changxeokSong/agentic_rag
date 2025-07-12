from typing import Dict, Any
from utils.logger import setup_logger
# 필요한 함수 임포트 (더 이상 개별 함수를 임포트하지 않음)
from storage.postgresql_storage import PostgreSQLStorage

logger = setup_logger(__name__)

class ListFilesTool:
    """MongoDB GridFS에 저장된 파일 목록을 조회하는 도구"""

    def __init__(self):
        self.name = "list_files_tool"
        self.description = "데이터베이스에 저장된 파일 목록을 조회합니다. 사용자가 업로드한 파일의 이름이나 목록 정보가 필요할 때 사용하세요."

    def execute(self, **kwargs):
        """파일 목록을 조회하고 결과를 반환합니다."""
        logger.info("데이터베이스 파일 목록 조회 실행 (PostgreSQL)")
        try:
            # PostgreSQLStorage 싱글톤 인스턴스 사용
            pg_storage = PostgreSQLStorage.get_instance()
            file_list = pg_storage.list_files()
            if not file_list:
                return []

            # 파일 목록을 JSON 리스트로 반환
            result = []
            for file_info in file_list:
                filename = file_info.get("filename", "알 수 없는 파일")
                file_size_mb = round(file_info.get("length", 0) / (1024*1024), 2)
                result.append({
                    "filename": filename,
                    "size_mb": file_size_mb
                })
            return result
        except Exception as e:
            logger.error(f"데이터베이스 파일 목록 조회 오류 (PostgreSQL): {str(e)}")
            return {"error": f"파일 목록 조회 중 오류가 발생했습니다: {str(e)}"}
    
    def get_info(self) -> Dict[str, str]:
        """도구 정보 반환"""
        return {
            "name": self.name,
            "description": self.description
        } 