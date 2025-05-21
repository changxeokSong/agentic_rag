# retrieval/vector_store.py

import os
from langchain.embeddings.huggingface import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from config import (
    LM_STUDIO_BASE_URL, 
    LM_STUDIO_API_KEY, 
    CHUNK_SIZE, 
    CHUNK_OVERLAP, 
    VECTOR_DB_PATH,
    TOP_K_RESULTS
)
from utils.logger import setup_logger

logger = setup_logger(__name__)

class VectorStore:
    """벡터 저장소 관리 클래스"""
    
    def __init__(self):
        """벡터 저장소를 초기화합니다."""
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP
        )
        self.stores = {}
        
        # 벡터 저장소 디렉토리 생성
        os.makedirs(VECTOR_DB_PATH, exist_ok=True)
        
        logger.info("벡터 저장소 초기화 완료")
    
    def add_texts(self, texts, collection_name):
        """텍스트를 벡터 저장소에 추가합니다."""
        logger.info(f"텍스트 추가 to {collection_name}, {len(texts)} 항목")
        try:
            # 텍스트 분할
            chunks = self.text_splitter.create_documents(texts)
            
            # 기존 저장소가 있는지 확인
            store_path = os.path.join(VECTOR_DB_PATH, collection_name)
            if os.path.exists(store_path) and collection_name in self.stores:
                # 기존 저장소에 추가
                self.stores[collection_name].add_documents(chunks)
            else:
                # 새 저장소 생성
                self.stores[collection_name] = FAISS.from_documents(chunks, self.embeddings)
            
            # 저장
            self.stores[collection_name].save_local(store_path)
            logger.info(f"벡터 저장소 저장 완료: {collection_name}")
            
            return True
        except Exception as e:
            logger.error(f"텍스트 추가 오류 ({collection_name}): {str(e)}")
            return False
    
    def search(self, query, collection_name, top_k=TOP_K_RESULTS):
        """벡터 저장소에서 쿼리와 관련된 문서를 검색합니다."""
        logger.info(f"검색: {query} in {collection_name}")
        
        # 저장소가 메모리에 없으면 로드
        if collection_name not in self.stores:
            store_path = os.path.join(VECTOR_DB_PATH, collection_name)
            if os.path.exists(store_path):
                try:
                    self.stores[collection_name] = FAISS.load_local(store_path, self.embeddings)
                    logger.info(f"벡터 저장소 로드: {collection_name}")
                except Exception as e:
                    logger.error(f"벡터 저장소 로드 오류 ({collection_name}): {str(e)}")
                    return []
            else:
                logger.warning(f"벡터 저장소를 찾을 수 없음: {collection_name}")
                return []
        
        # 검색 실행
        try:
            results = self.stores[collection_name].similarity_search(query, k=top_k)
            logger.info(f"검색 결과: {len(results)} 항목 찾음")
            return results
        except Exception as e:
            logger.error(f"검색 오류: {str(e)}")
            return []