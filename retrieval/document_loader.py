# retrieval/document_loader.py

from langchain_community.document_loaders import TextLoader, DirectoryLoader, PyPDFLoader
from utils.logger import setup_logger

logger = setup_logger(__name__)

class DocumentLoader:
    """문서 로더 클래스"""
    
    @staticmethod
    def load_text(file_path):
        """텍스트 파일을 로드합니다."""
        logger.info(f"텍스트 파일 로드: {file_path}")
        try:
            loader = TextLoader(file_path)
            documents = loader.load()
            return documents
        except Exception as e:
            logger.error(f"텍스트 로드 오류 ({file_path}): {str(e)}")
            return []
    
    @staticmethod
    def load_pdf(file_path):
        """PDF 파일을 로드합니다."""
        logger.info(f"PDF 파일 로드: {file_path}")
        try:
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            return documents
        except Exception as e:
            logger.error(f"PDF 로드 오류 ({file_path}): {str(e)}")
            return []
    
    @staticmethod
    def load_directory(dir_path, glob_pattern="**/*.txt"):
        """디렉토리에서 파일을 로드합니다."""
        logger.info(f"디렉토리 로드: {dir_path}, 패턴: {glob_pattern}")
        try:
            loader = DirectoryLoader(dir_path, glob=glob_pattern)
            documents = loader.load()
            logger.info(f"{len(documents)} 문서 로드됨")
            return documents
        except Exception as e:
            logger.error(f"디렉토리 로드 오류 ({dir_path}): {str(e)}")
            return []
    
    @staticmethod
    def get_raw_texts(documents):
        """문서에서 원시 텍스트를 추출합니다."""
        return [doc.page_content for doc in documents]