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
            
            # 데이터베이스 연결 상태 확인
            if not pg_storage._connection or pg_storage._connection.closed:
                logger.warning("데이터베이스 연결이 끊어진 상태입니다. 재연결을 시도합니다.")
                pg_storage.connect()
            
            file_list = pg_storage.list_files()
            
            # 파일 목록이 없거나 빈 리스트인 경우
            if not file_list or len(file_list) == 0:
                logger.info("업로드된 파일이 없습니다.")
                return {"message": "현재 업로드된 파일이 없습니다.", "files": []}

            # 파일 목록을 JSON 리스트로 반환
            result = []
            for file_info in file_list:
                filename = file_info.get("filename", "알 수 없는 파일")
                file_size = file_info.get("length", 0)
                file_size_mb = round(file_size / (1024*1024), 2) if file_size > 0 else 0
                upload_date = file_info.get("uploadDate", "알 수 없음")
                
                result.append({
                    "filename": filename,
                    "size_mb": file_size_mb,
                    "upload_date": str(upload_date) if upload_date else "알 수 없음"
                })
            
            logger.info(f"파일 목록 조회 성공: {len(result)}개 파일")
            return {"message": f"총 {len(result)}개의 파일이 업로드되어 있습니다.", "files": result}
            
        except ImportError as e:
            logger.error(f"필요한 모듈이 설치되지 않았습니다: {str(e)}")
            return {"error": "데이터베이스 연결 모듈(psycopg2)이 설치되지 않았습니다. 'pip install psycopg2-binary'를 실행하세요."}
        except Exception as e:
            logger.error(f"데이터베이스 파일 목록 조회 오류 (PostgreSQL): {str(e)}")
            # 구체적인 오류 유형에 따라 다른 메시지 제공
            if "connection" in str(e).lower() or "connect" in str(e).lower():
                return {"error": "데이터베이스 연결에 실패했습니다. 시스템 초기화를 실행하거나 PostgreSQL 서버 상태를 확인하세요."}
            else:
                return {"error": f"파일 목록 조회 중 오류가 발생했습니다: {str(e)}"}
    
    def get_info(self) -> Dict[str, str]:
        """도구 정보 반환"""
        return {
            "name": self.name,
            "description": self.description
        } 