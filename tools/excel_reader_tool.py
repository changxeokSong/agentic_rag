import os
import tempfile
import pandas as pd
from tools.base_tool import BaseTool
from utils.logger import setup_logger
from storage.mongodb_storage import MongoDBStorage

logger = setup_logger(__name__)

class ExcelReaderTool(BaseTool):
    """DB(GridFS)에서 엑셀 파일을 읽어 미리보기(상위 5개 행)를 반환하는 도구"""

    def __init__(self):
        super().__init__(
            name="excel_reader_tool",
            description="DB(GridFS)에 저장된 엑셀 파일을 file_id 또는 filename으로 찾아 미리보기(상위 5개 행)를 반환합니다."
        )

    def execute(self, file_id: str = None, filename: str = None):
        logger.info(f"DB 엑셀 미리보기 실행: file_id={file_id}, filename={filename}")
        try:
            mongo_storage = MongoDBStorage.get_instance()
            # 파일 추출 (file_id 우선)
            if file_id:
                content = mongo_storage.get_file_content_by_id(file_id)
                fname = f"{file_id}.xlsx"
            elif filename:
                # 부분 일치(대소문자 무시)로 파일명 검색
                file_list = mongo_storage.list_files()
                matched = [f for f in file_list if filename.lower() in f['filename'].lower()]
                if not matched:
                    return f"'{filename}'(와)과 비슷한 파일을 DB에서 찾을 수 없습니다."
                # 첫 번째 매칭 파일 사용
                fname = matched[0]['filename']
                content = mongo_storage.get_file_content(fname)
            else:
                return "file_id 또는 filename 중 하나는 반드시 입력해야 합니다."
            if not content:
                return "DB에서 파일을 찾을 수 없습니다."
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                df = pd.read_excel(tmp_path)
                preview = df.head().to_string()
                logger.info(f"엑셀 미리보기 성공: {fname}, shape={df.shape}")
            except Exception as e:
                logger.error(f"엑셀 파일 읽기 오류: {e}")
                preview = f"엑셀 파일을 읽는 중 오류가 발생했습니다: {e}"
            finally:
                os.remove(tmp_path)
            return preview
        except Exception as e:
            logger.error(f"DB 엑셀 미리보기 도구 오류: {e}")
            return f"DB 엑셀 미리보기 도구 오류: {e}"
