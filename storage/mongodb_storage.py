# storage/mongodb_storage.py

import os
import tempfile # 임시 파일 사용을 위해 임포트
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from gridfs import GridFS
from utils.logger import setup_logger
from config import (
    VECTOR_COLLECTION_NAME, CHUNK_SIZE, CHUNK_OVERLAP,
    EMBEDDING_MODEL_NAME, OPENAI_API_KEY_ENV_VAR, TOP_K_RESULTS # 임베딩 설정 가져오기
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings # OpenAIEmbeddings 임포트
# Document Loaders 임포트
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader

logger = setup_logger(__name__)

# MongoDB Atlas 설정
# MongoDB Atlas 연결 문자열을 환경 변수 MONGO_URI에 설정해야 합니다.
# 예: MONGO_URI="mongodb+srv://<username>:<password>@<cluster-url>/<database-name>?retryWrites=true&w=majority"
# <username>, <password>, <cluster-url> 부분을 실제 정보로 대체하세요.
# 데이터베이스 이름은 연결 문자열이나 코드에서 지정할 수 있으며, 여기서는 코드로 지정합니다.
MONGO_URI = os.environ.get("MONGO_URI")
DATABASE_NAME = "document" # 요청하신 데이터베이스 이름

# MONGO_URI가 설정되지 않은 경우 오류 발생 또는 기본값 설정 (배포 시에는 환경 변수 필수)
if not MONGO_URI:
    logger.error("MONGO_URI 환경 변수가 설정되지 않았습니다. MongoDB 연결에 실패할 수 있습니다.")
    # 개발 환경을 위해 로컬 MongoDB 기본값을 사용할 수도 있지만, Atlas 사용 시에는 환경 변수를 사용해야 합니다.
    # MONGO_URI = "mongodb://localhost:27017/"

# 전역 클라이언트 객체 (싱글톤 패턴을 위해 클래스 내부로 이동 고려)
# client = None
# db = None
# fs = None

# connect_db, get_database, get_gridfs 함수는 MongoDBStorage 클래스로 통합 고려
# def connect_db():
# ...
# def get_database():
# ...
# def get_gridfs():
# ...
# def save_file(file_data, filename, content_type=None, metadata=None):
# ...
# def find_file(filename):
# ...
# def get_file_data(file_id):
# ...
# def list_files():
# ...

# 초기 연결 시도 (선택 사항)
# connect_db()

class MongoDBStorage:
    """MongoDB와 상호작용하는 클래스 (GridFS 및 일반 컬렉션) - 싱글톤 적용"""
    _instance = None # 싱글톤 인스턴스를 저장할 클래스 변수
    _initialized = False # 초기화 상태 플래그

    def __new__(cls, *args, **kwargs):
        """인스턴스가 없을 때만 새로 생성하여 반환"""
        if not cls._instance:
            cls._instance = super(MongoDBStorage, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """
        MongoDB 연결을 초기화하고 임베딩 모델을 로드합니다.
        환경 변수 MONGO_URI에서 연결 문자열을 가져옵니다.
        환경 변수 OPENAI_API_KEY 환경 변수 이름을 가져옵니다.
        싱글톤이므로 한 번만 초기화되도록 합니다.
        """
        if self._initialized:
            return # 이미 초기화되었으면 바로 반환
            
        mongo_uri = os.getenv("MONGO_URI")
        # config에서 정의한 환경 변수 이름 사용
        openai_api_key = os.getenv(OPENAI_API_KEY_ENV_VAR)
        
        if not mongo_uri:
            raise ValueError("MONGO_URI 환경 변수가 설정되지 않았습니다.")
        if not openai_api_key:
             logger.warning(f"{OPENAI_API_KEY_ENV_VAR} 환경 변수가 설정되지 않았습니다. 임베딩 기능이 작동하지 않을 수 있습니다.")
             # raise ValueError(f"{OPENAI_API_KEY_ENV_VAR} 환경 변수가 설정되지 않았습니다.")

        try:
            self.client = MongoClient(mongo_uri, server_api=ServerApi('1'))
            # DATABASE_NAME 변수를 사용하여 명시적으로 데이터베이스 지정
            self.db = self.client.get_database(DATABASE_NAME)
            self.fs = GridFS(self.db)
            self.vector_collection = self.db[VECTOR_COLLECTION_NAME] # 벡터 임베딩 및 메타데이터 저장 컬렉션
            
            # Embedding 모델 로드 (config에서 모델 이름 가져오기)
            try:
                 self.embedding_model = OpenAIEmbeddings(model=EMBEDDING_MODEL_NAME, openai_api_key=openai_api_key)
                 logger.info(f"Embedding 모델 로드 성공: {EMBEDDING_MODEL_NAME}.")
            except Exception as e:
                 logger.error(f"Embedding 모델 로드 오류 ({EMBEDDING_MODEL_NAME}): {e}")
                 self.embedding_model = None # 모델 로드 실패 시 None으로 설정

            # 연결 확인을 위해 admin 데이터베이스의 command_with_namespace 사용
            self.client.admin.command('ping')
            logger.info("MongoDB 연결 성공!")
            
            self._initialized = True # 초기화 완료 플래그 설정

        except Exception as e:
            logger.error(f"MongoDB 연결 오류: {e}")
            raise

    # 싱글톤 인스턴스를 얻는 스태틱 메소드 추가 (선택 사항, __new__만 사용해도 됨)
    @staticmethod
    def get_instance():
        if MongoDBStorage._instance is None or not MongoDBStorage._initialized:
            # 필요하다면 여기서 __init__ 호출
             MongoDBStorage()
        return MongoDBStorage._instance

    def close(self):
        """MongoDB 연결을 닫습니다."""
        # 싱글톤에서는 연결을 닫을 때 주의 필요. 애플리케이션 종료 시점에 한 번만 호출되도록 관리해야 함.
        if hasattr(self, 'client') and self.client and self._initialized:
            self.client.close()
            logger.info("MongoDB 연결 종료.")
            self._initialized = False # 연결 종료 시 초기화 상태 해제
            
    # 기존 save_file, list_files, get_file_content, delete_file, vector_search 메소드는 그대로 유지 또는 필요에 따라 수정
    def save_file(self, file_content: bytes, filename: str, metadata: dict = None):
        """
        파일을 GridFS에 저장하고 내용을 처리하여 벡터 컬렉션에 저장합니다.
        다양한 파일 형식(txt, pdf, docx 등)을 지원합니다.
        
        Args:
            file_content (bytes): 저장할 파일 내용 (바이트).
            filename (str): 파일 이름.
            metadata (dict, optional): 파일과 관련된 추가 메타데이터. Defaults to None.
        """
        if not self.embedding_model:
             logger.error("Embedding 모델이 로드되지 않았습니다. 파일 내용을 저장할 수 없습니다.")
             raise RuntimeError("Embedding model not loaded")
             
        try:
            # 1. 원본 파일 GridFS에 저장
            file_id = self.fs.put(file_content, filename=filename, metadata=metadata)
            logger.info(f"원본 파일 '{filename}' GridFS에 저장 완료. file_id: {file_id}")

            # 2. 파일 내용 추출 (파일 형식에 따라 다른 로더 사용)
            temp_file_path = None
            try:
                # Langchain 로더는 파일 경로를 받는 경우가 많으므로 임시 파일로 저장
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
                    tmp.write(file_content)
                    temp_file_path = tmp.name
                    
                file_extension = os.path.splitext(filename)[1].lower()
                docs = []
                
                if file_extension == '.txt':
                    loader = TextLoader(temp_file_path)
                    docs = loader.load()
                elif file_extension == '.pdf':
                    loader = PyPDFLoader(temp_file_path)
                    docs = loader.load()
                elif file_extension == '.docx':
                    loader = Docx2txtLoader(temp_file_path)
                    docs = loader.load()
                else:
                    logger.warning(f"지원되지 않는 파일 형식: {filename}")
                    # 지원되지 않는 형식은 처리하지 않고 넘어갑니다.
                    return # 파일은 GridFS에 저장되었지만 벡터 컬렉션에는 추가되지 않음

            finally:
                # 임시 파일 삭제
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

            if not docs:
                 logger.warning(f"파일 내용 로드 실패 또는 내용 없음: {filename}")
                 return # 문서 로드 실패 시 처리 중단

            # 3. 로드된 문서를 청크로 분할
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
                length_function=len,
                is_separator_regex=False,
            )
            chunks = text_splitter.split_documents(docs) # Document 객체 리스트를 받도록 변경
            
            # 각 청크(Document 객체)에 대한 벡터 임베딩 생성
            chunk_texts = [chunk.page_content for chunk in chunks]
            embeddings = self.embedding_model.embed_documents(chunk_texts)
            logger.info(f"{len(embeddings)}개의 청크 임베딩 생성 완료.")
            
            # 4. 각 청크의 벡터 임베딩 및 메타데이터를 별도 컬렉션에 저장
            chunks_to_insert = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = {
                    "filename": filename,
                    "chunk_index": i, # 청크 순서
                    "original_file_id": file_id, # GridFS 파일 ID 참조
                    "tags": metadata.get("tags", []) if metadata else [], # 원본 파일의 태그 상속
                    # 기존 chunk.metadata에 source 정보 등이 있다면 병합
                    **chunk.metadata
                }
                chunk_document = {
                    "content": chunk.page_content,
                    "metadata": chunk_metadata,
                    "embedding": embeddings[i] # 실제 임베딩 값 추가
                }
                chunks_to_insert.append(chunk_document)

            if chunks_to_insert:
                self.vector_collection.insert_many(chunks_to_insert)
                logger.info(f"{len(chunks_to_insert)}개의 청크 문서 벡터 컬렉션에 저장 완료.")

        except Exception as e:
            logger.error(f"파일 저장 및 처리 중 오류 발생: {e}")
            # 오류 발생 시 GridFS에 저장된 파일 삭제 고려 (필요에 따라 구현)
            # self.delete_file(filename) # 또는 file_id로 삭제
            raise # 오류를 상위 호출자로 전파
            
    def list_files(self):
        """GridFS에 저장된 원본 파일 목록을 조회합니다. 파일 ID, 이름, 크기를 포함합니다."""
        try:
            # self.fs.list() 대신 self.fs.find()를 사용하여 파일 문서를 가져옵니다.
            # 파일 문서에서 필요한 정보만 추출하여 목록으로 반환합니다.
            file_infos = []
            for file in self.fs.find():
                file_infos.append({
                    '_id': str(file._id), # ObjectId를 문자열로 변환
                    'filename': file.filename,
                    'length': file.length,
                    'uploadDate': file.upload_date # 업로드 날짜 추가
                })
            logger.info(f"GridFS 파일 목록 조회 성공. {len(file_infos)}개 파일.")
            return file_infos
        except Exception as e:
            logger.error(f"GridFS 파일 목록 조회 오류: {e}")
            raise

    def get_file_content(self, filename: str):
        """GridFS에 저장된 특정 원본 파일의 내용을 가져옵니다."""
        try:
            file = self.fs.find_one({"filename": filename})
            if file:
                content = file.read()
                logger.info(f"파일 '{filename}' 내용 조회 성공.")
                return content
            else:
                logger.warning(f"파일 '{filename}' GridFS에서 찾을 수 없음.")
                return None
        except Exception as e:
            logger.error(f"파일 '{filename}' 내용 조회 오류: {e}")
            raise

    def get_file_content_by_id(self, file_id: str):
        """GridFS에 저장된 특정 원본 파일의 내용을 ID로 가져옵니다."""
        try:
            from bson.objectid import ObjectId # ObjectId 임포트
            # 문자열 file_id를 ObjectId로 변환
            object_id = ObjectId(file_id)
            file = self.fs.find_one({"_id": object_id})
            if file:
                content = file.read()
                logger.info(f"파일 ID '{file_id}' 내용 조회 성공.")
                return content
            else:
                logger.warning(f"파일 ID '{file_id}' GridFS에서 찾을 수 없음.")
                return None
        except Exception as e:
            logger.error(f"파일 ID '{file_id}' 내용 조회 오류: {e}")
            raise

    def delete_file(self, filename: str):
        """GridFS에 저장된 원본 파일과 연결된 벡터 컬렉션 문서를 삭제합니다."""
        try:
            # GridFS 파일 조회 및 삭제
            file = self.fs.find_one({"filename": filename})
            if file:
                file_id = file._id
                self.fs.delete(file_id)
                logger.info(f"원본 파일 '{filename}' GridFS에서 삭제 완료.")

                # 연결된 벡터 컬렉션 문서 삭제
                delete_result = self.vector_collection.delete_many({"metadata.original_file_id": file_id})
                logger.info(f"벡터 컬렉션에서 연결된 문서 {delete_result.deleted_count}개 삭제 완료.")

            else:
                logger.warning(f"파일 '{filename}' 삭제 - GridFS에서 찾을 수 없음.")

        except Exception as e:
            logger.error(f"파일 '{filename}' 삭제 중 오류 발생: {e}")
            raise
            
    def vector_search(self, query: str, file_filter: str = None, tags_filter: list[str] = None, top_k: int = TOP_K_RESULTS):
        """
        MongoDB Atlas Vector Search를 사용하여 문서를 검색합니다.
        
        Args:
            query (str): 검색할 쿼리.
            file_filter (str, optional): 검색 결과를 필터링할 특정 파일 이름. Defaults to None.
            tags_filter (list[str], optional): 검색 결과를 필터링할 태그 목록. Defaults to None.
            top_k (int, optional): 반환할 검색 결과의 최대 개수. Defaults to TOP_K_RESULTS.
            
        Returns:
            list: 검색 결과 문서 목록 (dict).
        """
        if not self.embedding_model:
             logger.error("Embedding 모델이 로드되지 않았습니다. 벡터 검색을 수행할 수 없습니다.")
             return [] # 모델 없으면 빈 결과 반환

        try:
            # 쿼리 문자열을 벡터 임베딩으로 변환
            query_embedding = self.embedding_model.embed_query(query)

            # 필터 조건 설정
            filter_conditions = {}
            if file_filter:
                filter_conditions['metadata.filename'] = file_filter
            if tags_filter:
                filter_conditions['metadata.tags'] = { '$in': tags_filter }

            pipeline = [
                {
                    '$vectorSearch': {
                        'queryVector': query_embedding,
                        'path': 'embedding', # 벡터 필드 이름
                        'numCandidates': top_k * 10, # 검색 효율을 위해 top_k보다 크게 설정
                        'limit': top_k,
                        'index': 'vector_index', # MongoDB Atlas에서 생성한 벡터 인덱스 이름
                        # 필터 조건 추가
                        'filter': filter_conditions
                    }
                },
                 { '$addFields': { 'score': { '$meta': 'vectorSearchScore' } } }, # 유사도 점수 추가
                 { '$project': { '_id': 0, 'content': 1, 'metadata': 1, 'score': 1 } } # 필요한 필드만 선택
            ]
            
            # $vectorSearch 내 filter 필드 사용 시 $match 스테이지는 필요 없습니다.
            # if match_conditions:
            #     pipeline.append({'$match': match_conditions})

            # 검색 실행
            search_results = list(self.vector_collection.aggregate(pipeline))
            
            # 검색 결과에 score를 포함시키려면 $addFields 스테이지를 추가해야 합니다.
            # 예: { '$addFields': { 'score': { '$meta': 'vectorSearchScore' } } }
            # $vectorSearch 스테이지 바로 뒤 또는 $match 스테이지 뒤에 추가할 수 있습니다.
            # 현재는 score를 반환한다고 가정하고 internal_vector_search.py에서 사용하고 있습니다.
            # 실제 구현 시 필요에 따라 추가하십시오.

            logger.info(f"MongoDB 벡터 검색 완료. {len(search_results)}개 결과 반환.")
            # 검색 결과 형태에 따라 가공 필요
            # 예: search_results = [doc['content'] for doc in search_results]

            return search_results # 필요한 필드만 포함하도록 $project 사용 고려
            
        except Exception as e:
            logger.error(f"MongoDB 벡터 검색 중 오류 발생: {e}")
            raise

# 예시 사용 (실제 애플리케이션에서는 직접 호출하지 않음)
# if __name__ == "__main__":
#     # 환경변수 설정 필요: export MONGO_URI="your_mongodb_connection_string" AND export OPENAI_API_KEY="your_openai_api_key"
#     # Atlas Cluster에 vector_index 라는 이름의 벡터 인덱스가 생성되어 있어야 함
#     try:
#         mongo_storage = MongoDBStorage.get_instance() # 싱글톤 인스턴스 사용
#         # 파일 저장 예시 (테스트 파일 필요)
#         # try:
#         #     # 테스트 파일 생성 (예: test.txt, test.pdf, test.docx)
#         #     with open("test.txt", "w", encoding='utf-8') as f:
#         #         f.write("이것은 테스트 텍스트 문서입니다. RAG 테스트를 위해 작성되었습니다.")
#         #     # pdf 또는 docx 파일은 직접 생성하거나 예제 파일 사용
#         #
#         #     # 파일 저장 테스트
#         #     with open("test.txt", "rb") as f:
#         #          content = f.read()
#         #          mongo_storage.save_file(content, "test.txt", metadata={"tags": ["테스트", "텍스트"]})
#         #
#         #     # with open("test.pdf", "rb") as f:
#         #     #      content = f.read()
#         #     #      mongo_storage.save_file(content, "test.pdf", metadata={"tags": ["테스트", "PDF"]})
#         #
#         #     # with open("test.docx", "rb") as f:
#         #     #      content = f.read()
#         #     #      mongo_storage.save_file(content, "test.docx", metadata={"tags": ["테스트", "DOCX"]})
#         #
#         # except FileNotFoundError:
#         #     print("테스트 파일을 찾을 수 없습니다. 테스트 파일을 생성하거나 경로를 확인해주세요.")
#         # except Exception as e:
#         #      print(f"파일 저장 테스트 중 오류 발생: {e}")
#
#         # 파일 목록 조회 예시
#         # print("\nGridFS 파일 목록:")
#         # try:
#         #     for file_info in mongo_storage.list_files():
#         #         print(f"- {file_info['filename']} (ID: {file_info['_id']})")
#         # except Exception as e:
#         #     print(f"파일 목록 조회 중 오류 발생: {e}")
#
#         # 파일 내용 조회 예시
#         # print("\n'test.txt' 파일 내용:")
#         # try:
#         #     file_data = mongo_storage.get_file_content("test.txt")
#         #     if file_data:
#         #         print(file_data.decode('utf-8'))
#         # except Exception as e:
#         #      print(f"파일 내용 조회 중 오류 발생: {e}")
#
#         # 벡터 검색 예시
#         print("\n벡터 검색 결과:")
#         # 검색 쿼리를 실제 데이터에 맞게 수정 필요
#         try:
#             results = mongo_storage.vector_search("문서 내용에 대한 질문", tags_filter=["테스트"], top_k=3)
#             if results:
#                  for doc in results:
#                     # 검색 결과 형태에 따라 접근 방식이 다를 수 있습니다.
#                     # 예: print(f"- 내용: {doc.get('content', 'N/A')[:100]}... (파일: {doc.get('metadata', {}).get('filename', 'N/A')}, 청크: {doc.get('metadata', {}).get('chunk_index', 'N/A')})")
#                     # internal_vector_search 도구에서 가공하므로 여기서는 원본 결과 형태를 확인합니다.
#                      print(f"- 문서: {doc}") # 임시 전체 출력
#             else:
#                  print("검색 결과가 없습니다.")
#         except Exception as e:
#             print(f"벡터 검색 중 오류 발생: {e}")
#
#         # 파일 삭제 예시 (주의: 실제 삭제)
#         # try:
#         #      mongo_storage.delete_file("test.txt")
#         #      # mongo_storage.delete_file("test.pdf")
#         #      # mongo_storage.delete_file("test.docx")
#         # except Exception as e:
#         #      print(f"파일 삭제 중 오류 발생: {e}")
#
#     except ValueError as e:
#         print(f"환경 변수 오류: {e}")
#     except Exception as e:
#         print(f"오류 발생: {e}")
#     finally:
#         # 스크립트 종료 시 연결 닫기
#         # if 'mongo_storage' in locals() and mongo_storage:
#         #     mongo_storage.close() # 싱글톤이므로 실제 애플리케이션 종료 시에만 닫아야 합니다.
#          pass