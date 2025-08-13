# storage/postgresql_storage.py

import os
import psycopg2
import psycopg2.extras # JSONB 처리를 위해 필요
from utils.logger import setup_logger
from config import (
    PG_DB_HOST, PG_DB_NAME, PG_DB_USER, PG_DB_PASSWORD, PG_DB_PORT,
    EMBEDDING_MODEL_NAME, OPENAI_API_KEY_ENV_VAR, TOP_K_RESULTS,
    CHUNK_SIZE, CHUNK_OVERLAP
)
# 필요한 Langchain 컴포넌트 및 임베딩 모델 임포트
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings # OpenAIEmbeddings 임포트
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader # 파일 내용 로딩용
import tempfile
from bson.objectid import ObjectId # ObjectId 처리가 더 이상 필요 없을 수 있으나, 마이그레이션 과정에서 필요할 수도 있으므로 남겨둡니다.

logger = setup_logger(__name__)

class PostgreSQLStorage:
    """PostgreSQL 데이터베이스와 상호작용하는 클래스 (pgvector 포함) - 싱글톤 적용"""
    _instance = None # 싱글톤 인스턴스
    _initialized = False # 초기화 상태 플래그
    _connection = None # 데이터베이스 연결 객체
    _cursor = None # 커서 객체
    _pgvector_available = False

    def __new__(cls, *args, **kwargs):
        """인스턴스가 없을 때만 새로 생성하여 반환"""
        if not cls._instance:
            cls._instance = super(PostgreSQLStorage, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """
        PostgreSQL 연결을 초기화하고 임베딩 모델을 로드합니다.
        싱글톤이므로 한 번만 초기화되도록 합니다.
        """
        if self._initialized:
            return # 이미 초기화되었으면 바로 반환

        # 환경 변수에서 PostgreSQL 연결 정보 가져오기
        self.db_host = PG_DB_HOST
        self.db_name = PG_DB_NAME
        self.db_user = PG_DB_USER
        self.db_password = PG_DB_PASSWORD
        self.db_port = int(PG_DB_PORT) # config에서 int로 변환했으니 그대로 사용
        
        # 환경 변수에서 OpenAI API 키 가져오기 (임베딩용)
        openai_api_key = os.getenv(OPENAI_API_KEY_ENV_VAR)

        # Check if required environment variables are set and are not empty strings
        if not all([PG_DB_NAME, PG_DB_USER, PG_DB_PASSWORD]) or any([not PG_DB_NAME, not PG_DB_USER, not PG_DB_PASSWORD]):
            logger.error("PostgreSQL 연결 환경 변수(PG_DB_NAME, PG_DB_USER, PG_DB_PASSWORD)가 설정되지 않았습니다.")
            return # Initialize fails if required vars are not set

        try:
            # libpq 환경 변수에 비UTF-8 값이 설정되어 있으면 내부 디코딩에서 실패할 수 있음
            # 연결 인자로 모두 전달할 것이므로 libpq 관련 환경 변수는 임시로 제거
            self._libpq_env_backup = {}
            try:
                _libpq_keys = [
                    "PGPASSWORD", "PGSERVICE", "PGSERVICEFILE", "PGPASSFILE",
                    "PGHOST", "PGHOSTADDR", "PGPORT", "PGUSER", "PGDATABASE"
                ]
                for k in _libpq_keys:
                    if k in os.environ:
                        self._libpq_env_backup[k] = os.environ[k]
                        del os.environ[k]
            except Exception as e:
                logger.debug(f"libpq 환경 변수 초기화 경고: {e}")

            # libpq가 사용자 홈/시스템 서비스 파일을 읽으며 인코딩 문제가 발생할 수 있어
            # 안전한 임시 빈 파일로 우회 (비밀번호는 직접 전달하므로 .pgpass 불필요)
            self._temp_pgservice = None
            self._temp_pgpass = None
            self._temp_pgsysconfdir = None
            try:
                if not os.environ.get("PGSERVICEFILE"):
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".conf")
                    tmp.close()
                    os.environ["PGSERVICEFILE"] = tmp.name
                    self._temp_pgservice = tmp.name
                if not os.environ.get("PGPASSFILE"):
                    tmp2 = tempfile.NamedTemporaryFile(delete=False)
                    tmp2.close()
                    os.environ["PGPASSFILE"] = tmp2.name
                    self._temp_pgpass = tmp2.name
                if not os.environ.get("PGSYSCONFDIR"):
                    # 시스템 서비스 디렉토리 우회를 위한 임시 폴더
                    tmpdir = tempfile.mkdtemp(prefix="pgsysconf_")
                    os.environ["PGSYSCONFDIR"] = tmpdir
                    self._temp_pgsysconfdir = tmpdir
                logger.debug(
                    f"libpq files pinned: PGSERVICEFILE={os.environ.get('PGSERVICEFILE')}, "
                    f"PGPASSFILE={os.environ.get('PGPASSFILE')}, PGSYSCONFDIR={os.environ.get('PGSYSCONFDIR')}"
                )
            except Exception as e:
                logger.debug(f"libpq 파일 경로 설정 중 경고: {e}")

            # 윈도우/로케일 이슈 방지를 위해 클라이언트 인코딩을 강제 지정
            try:
                os.environ.setdefault("PGCLIENTENCODING", "UTF8")
            except Exception:
                pass

            connection_kwargs = {
                "host": str(self.db_host) if self.db_host is not None else None,
                "database": str(self.db_name) if self.db_name is not None else None,
                "user": str(self.db_user) if self.db_user is not None else None,
                "password": str(self.db_password) if self.db_password is not None else None,
                "port": int(self.db_port) if self.db_port is not None else None,
                # libpq에 클라이언트 인코딩 옵션 전달
                "options": "-c client_encoding=UTF8",
            }

            # 데이터베이스 연결
            self._connection = psycopg2.connect(**connection_kwargs)
            try:
                # 연결 직후에도 안전하게 클라이언트 인코딩을 강제
                self._connection.set_client_encoding('UTF8')
            except Exception:
                pass
            # 커서 생성 (딕셔너리 형태로 결과를 받기 위해 cursor_factory 사용)
            self._cursor = self._connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            logger.info("PostgreSQL 연결 성공!")
            
            # Embedding 모델 로드 (config에서 모델 이름 가져오기)
            try:
                # config에서 임베딩 모델 이름과 API 키 환경 변수 이름 가져와 사용
                self.embedding_model = OpenAIEmbeddings(model=EMBEDDING_MODEL_NAME, openai_api_key=openai_api_key)
                logger.info(f"Embedding 모델 로드 성공: {EMBEDDING_MODEL_NAME}.")
            except Exception as e:
                logger.error(f"Embedding 모델 로드 오류 ({EMBEDDING_MODEL_NAME}): {e}")
                self.embedding_model = None # 모델 로드 실패 시 None으로 설정

            self._pgvector_available = True
            try:
                from pgvector.psycopg2 import register_vector # register_vector 임포트
                from pgvector import Vector # Vector 타입은 pgvector에서 임포트
                register_vector(self._connection)
            except ImportError:
                logger.warning("pgvector 라이브러리가 설치되지 않았습니다. 벡터 기능을 사용할 수 없습니다.")

            # 연결 성공 메시지 로깅
            logger.info("PostgreSQL 데이터베이스 연결 성공")

            self._initialized = True # 초기화 완료 플래그 설정

        except UnicodeDecodeError as e:
            logger.error(
                "PostgreSQL DSN 인코딩 오류(UnicodeDecodeError). 환경 변수/서비스 인코딩 확인 필요. "
                f"host={self.db_host}, db={self.db_name}, user={self.db_user}, port={self.db_port}"
            )
            logger.error(f"원본 오류: {e}")
            self._initialized = False
            self._connection = None
            self._cursor = None
            raise
        except (psycopg2.OperationalError, psycopg2.Error) as e:
            logger.error(f"PostgreSQL 데이터베이스 연결 오류: {e}", exc_info=True)
            self._initialized = False
            self._connection = None
            self._cursor = None
        except Exception as e:
            logger.error(f"PostgreSQLStorage 초기화 중 알 수 없는 오류 발생: {e}", exc_info=True)
            self._initialized = False
            self._connection = None
            self._cursor = None

    # 싱글톤 인스턴스를 얻는 스태틱 메소드
    @staticmethod
    def get_instance():
        if PostgreSQLStorage._instance is None or not PostgreSQLStorage._initialized:
             PostgreSQLStorage()
        return PostgreSQLStorage._instance

    def close(self):
        """PostgreSQL 연결을 닫습니다."""
        if self._cursor:
            self._cursor.close()
            self._cursor = None
        if self._connection:
            self._connection.close()
            self._connection = None
        self._initialized = False # 연결 종료 시 초기화 상태 해제
        logger.info("PostgreSQL 연결 종료.")
        # 생성한 임시 libpq 파일 제거
        try:
            if getattr(self, "_temp_pgservice", None) and os.path.exists(self._temp_pgservice):
                os.remove(self._temp_pgservice)
                self._temp_pgservice = None
            if getattr(self, "_temp_pgpass", None) and os.path.exists(self._temp_pgpass):
                os.remove(self._temp_pgpass)
                self._temp_pgpass = None
            if getattr(self, "_temp_pgsysconfdir", None) and os.path.isdir(self._temp_pgsysconfdir):
                # 디렉토리 내부 비우고 제거
                try:
                    for name in os.listdir(self._temp_pgsysconfdir):
                        try:
                            path = os.path.join(self._temp_pgsysconfdir, name)
                            if os.path.isfile(path):
                                os.remove(path)
                        except Exception:
                            pass
                    os.rmdir(self._temp_pgsysconfdir)
                except Exception:
                    pass
                self._temp_pgsysconfdir = None
        except Exception as e:
            logger.debug(f"임시 파일 정리 중 경고: {e}")

    def execute_query(self, query, params=None, fetchone=False, fetchall=False, commit=False):
        """SQL 쿼리 실행을 위한 헬퍼 메소드"""
        if not self._initialized or not self._cursor:
            logger.error("데이터베이스 연결이 초기화되지 않았습니다.")
            # 연결이 안된 경우 적절한 오류 처리 또는 None 반환
            if commit: # 쓰기 작업 시
                 # 오류를 발생시키거나 False 반환
                 raise ConnectionError("데이터베이스 연결이 초기화되지 않았습니다.")
            else: # 읽기 작업 시
                 return None # 또는 빈 리스트/딕셔너리

        try:
            self._cursor.execute(query, params)
            if commit:
                self._connection.commit()
                return True
            elif fetchone:
                return self._cursor.fetchone()
            elif fetchall:
                return self._cursor.fetchall()
            else:
                return None # SELECT 문이 아니거나 결과를 원하지 않는 경우
        except Exception as e:
            self._connection.rollback() # 오류 발생 시 롤백
            logger.error(f"SQL 쿼리 실행 오류: {e}\n쿼리: {query}\n파라미터: {params}")
            raise # 오류를 상위 호출자로 전파

    def save_file(self, file_content: bytes, filename: str, metadata: dict = None):
        """
        파일을 files 테이블에 저장하고 내용을 처리하여 chunks 테이블에 저장합니다.
        PostgreSQL용으로 재구현.
        
        Args:
            file_content (bytes): 저장할 파일 내용 (바이트).
            filename (str): 파일 이름.
            metadata (dict, optional): 파일과 관련된 추가 메타데이터. Defaults to None.
            
        Returns:
            str or None: 저장된 파일의 ID (문자열) 또는 중복/오류 시 None (또는 예외 발생)
        """
        logger.info(f"PostgreSQL 파일 저장 시도: {filename}")
        # 1. 파일 이름 중복 확인
        existing_file_query = "SELECT id FROM files WHERE filename = %s"
        existing_file = self.execute_query(existing_file_query, params=(filename,), fetchone=True)

        if existing_file:
           file_id = existing_file['id']
           logger.warning(f"파일 '{filename}' 이미 존재. ID: {file_id}")
           return str(file_id)

        file_id = None
        try:
            # 2. files 테이블에 파일 저장
            # psycopg2는 bytea 타입에 bytes 객체를 직접 바인딩할 수 있습니다.
            # JSONB 타입에는 psycopg2.extras.Json()을 사용하여 파이썬 dict/list를 변환해야 합니다.
            file_insert_query = "INSERT INTO files (filename, length, metadata, content) VALUES (%s, %s, %s, %s) RETURNING id"
            self.execute_query(
                file_insert_query,
                params=(filename, len(file_content), psycopg2.extras.Json(metadata), file_content),
                commit=False # 청크 저장까지 하나의 트랜잭션으로 묶기 위해 commit은 나중에
            )
            # 방금 삽입된 파일의 ID를 가져옵니다.
            self._cursor.execute("SELECT currval(pg_get_serial_sequence('files','id')) AS new_file_id")
            result_row = self._cursor.fetchone()
            file_id = result_row['new_file_id'] if result_row else None # 결과가 있을 경우 'new_file_id' 키로 접근
            logger.info(f"파일 '{filename}' files 테이블에 저장 완료. ID: {file_id}")

            # 3. 파일 내용 처리 및 chunks 테이블에 저장 (MongoDBStorage의 로직 참고하여 재구현)
            # .xlsx 또는 .png 파일은 청크 및 임베딩 처리 건너뛰기
            file_extension = os.path.splitext(filename)[1].lower()
            if file_extension in ['.xlsx', '.png']:
                logger.info(f"{file_extension.upper()} 파일 '{filename}'은 청크 및 임베딩 처리를 건너킵니다.")
                # GridFS에만 저장했던 것처럼, files 테이블에만 저장하고 바로 파일 ID 반환
                self._connection.commit() # files 테이블 삽입 트랜잭션 커밋
                return str(file_id) # 파일 ID 반환
            
            # 지원되는 다른 파일 형식 (txt, pdf, docx)은 내용 로드 및 청크 분할, 임베딩 생성 후 chunks 테이블에 저장
            # MongoDBStorage의 해당 로직을 PostgreSQL에 맞게 수정
            # 임시 파일 사용 로직 등 재활용 가능
            temp_file_path = None
            docs = []
            try:
                 # Langchain 로더는 파일 경로를 받는 경우가 많으므로 임시 파일로 저장
                 with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp:
                     tmp.write(file_content)
                     temp_file_path = tmp.name
 
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
                      # 여기에 도달하는 경우는 지원되는 확장자 목록에 없는 경우로 이미 위에서 처리되었어야 하지만, 방어적으로 추가
                      logger.warning(f"청크 처리가 지원되지 않는 파일 형식: {filename}")
                      self._connection.rollback() # 파일 저장 롤백
                      # GridFS에서 삭제하는 로직 대신 files 테이블에서 삭제
                      delete_query = "DELETE FROM files WHERE id = %s"
                      self.execute_query(delete_query, params=(file_id,), commit=True)
                      return None # 처리 실패

            finally:
                 # 임시 파일 삭제
                 if temp_file_path and os.path.exists(temp_file_path):
                     os.remove(temp_file_path)

            if not docs:
                 logger.warning(f"파일 내용 로드 실패 또는 내용 없음: {filename}")
                 self._connection.rollback() # 파일 저장 롤백
                 delete_query = "DELETE FROM files WHERE id = %s"
                 self.execute_query(delete_query, params=(file_id,), commit=True)
                 return None # 문서 로드 실패 시 처리 중단

            # 3. 로드된 문서를 청크로 분할
            text_splitter = RecursiveCharacterTextSplitter(
                 chunk_size=CHUNK_SIZE,
                 chunk_overlap=CHUNK_OVERLAP,
                 length_function=len,
                 is_separator_regex=False,
            )
            chunks = text_splitter.split_documents(docs)
 
            # 각 청크(Document 객체)에 대한 벡터 임베딩 생성
            if not self.embedding_model:
                logger.error("Embedding 모델이 로드되지 않았습니다. 청크 임베딩 생성이 불가능합니다.")
                self._connection.rollback() # 파일 저장 롤백
                delete_query = "DELETE FROM files WHERE id = %s"
                self.execute_query(delete_query, params=(file_id,), commit=True)
                raise RuntimeError("Embedding model not loaded") # 임베딩 모델 없으면 오류 발생

            chunk_texts = [chunk.page_content for chunk in chunks]
            embeddings = self.embedding_model.embed_documents(chunk_texts)
            logger.info(f"{len(embeddings)}개의 청크 임베딩 생성 완료.")

            # KeyBERT로 태그 추출기 준비 (최초 1회만 로드)
            # KeyBERT 임포트 및 사용 로직 추가
            # try:
            #     from keybert import KeyBERT # KeyBERT 임포트
            #     if not hasattr(self, '_keybert_model'):
            #        self._keybert_model = KeyBERT()
            #     kw_model = self._keybert_model
            #     use_keybert = True
            # except ImportError:
            #      logger.warning("KeyBERT 라이브러리가 설치되지 않았습니다. 태그 자동 추출 기능을 사용할 수 없습니다.")
            #      use_keybert = False

            # 4. chunks 테이블에 청크 및 임베딩 저장
            # pgvector의 Vector 타입을 사용해야 합니다.
            # from pgvector.psycopg2 import register_vector
            # register_vector(self._connection)

            # pgvector의 Vector 타입을 사용하기 위해 Vector 임포트
            from pgvector import Vector # Vector 타입 임포트

            chunk_insert_query = "INSERT INTO chunks (file_id, chunk_index, content, embedding, metadata) VALUES (%s, %s, %s, %s, %s)"
            chunk_data_to_insert = []
            # KeyBERT 태그 추출 로직 추가 필요
            # if use_keybert:
            #    # KeyBERT로 주요 키워드 추출 (상위 5개, 단어만)
            #    keywords = [kw for kw, _ in kw_model.extract_keywords(chunk.page_content, top_n=5)]
            # else:
            #     keywords = []

            for i, chunk in enumerate(chunks):
                 chunk_metadata = {
                     "filename": filename,
                     "chunk_index": i,
                     "original_file_id": file_id, # PostgreSQL 파일 ID 참조
                     # "tags": keywords, # 태그 추가 (KeyBERT 사용 시)
                     **chunk.metadata
                 }
                 # 임베딩 벡터를 pgvector의 Vector 타입으로 변환 (register_vector 후 가능)
                 # embedding_vector = Vector(embeddings[i])
                 chunk_data_to_insert.append((
                     file_id,
                     i,
                     chunk.page_content,
                     Vector(embeddings[i]), # pgvector의 Vector 객체 사용
                     psycopg2.extras.Json(chunk_metadata)
                 ))

            # psycopg2.extras.execute_batch를 사용하여 일괄 삽입
            from psycopg2.extras import execute_batch # execute_batch 임포트 활성화
            execute_batch(self._cursor, chunk_insert_query, chunk_data_to_insert)
            self._connection.commit() # files 및 chunks 테이블 삽입 트랜잭션 커밋
            logger.info(f"{len(chunk_data_to_insert)}개의 청크 files ID {file_id}에 대해 chunks 테이블에 저장 완료.")

            # 모든 처리가 성공적으로 완료되면 파일 ID 반환 (일반 문서의 경우)
            return str(file_id)

        except Exception as e:
             logger.error(f"PostgreSQL 파일 저장 및 처리 중 오류 발생: {e}")
             if self._connection: # 연결이 있는 경우 롤백 시도
                 self._connection.rollback()
             # 오류 발생 시 예외 다시 발생
             raise

    def list_files(self):
        """files 테이블에 저장된 파일 목록을 조회합니다."""
        logger.info("PostgreSQL 파일 목록 조회 시도")
        # SQL: SELECT id, filename, upload_date, length, metadata FROM files
        list_files_query = "SELECT id, filename, upload_date, length, metadata FROM files ORDER BY upload_date DESC"
        files = self.execute_query(list_files_query, fetchall=True)

        # MongoDBStorage의 반환 형태와 유사하게 변환
        # ObjectId 대신 PostgreSQL의 INTEGER ID를 문자열로 반환
        if files:
             return [{
                 '_id': str(f['id']),
                 'filename': f['filename'],
                 'length': f['length'],
                 'uploadDate': f['upload_date']
                 # metadata는 필요한 경우 get_file_content_by_id 등에서 가져오거나 여기에 추가
             } for f in files]
        else:
             return []

    def get_file_content_by_id(self, file_id: str):
        """files 테이블에서 특정 ID의 파일 내용을 가져옵니다."""
        logger.info(f"PostgreSQL 파일 내용 ID {file_id}로 조회 시도")
        # SQL: SELECT content FROM files WHERE id = %s
        # 파일 ID는 INTEGER 타입으로 변환하여 쿼리에 사용
        try:
            file_id_int = int(file_id)
        except ValueError:
            logger.error(f"유효하지 않은 파일 ID 형식: {file_id}")
            return None

        content_query = "SELECT content FROM files WHERE id = %s"
        content_row = self.execute_query(content_query, params=(file_id_int,), fetchone=True)

        # content는 bytea 타입으로 저장되므로 bytes 객체 그대로 반환
        return content_row['content'] if content_row and content_row.get('content') else None

    def delete_file(self, file_id: str):
        """files 테이블에서 파일 및 연결된 chunks 삭제합니다.

        # files 테이블의 ON DELETE CASCADE 제약 조건 덕분에 chunks 테이블의 데이터는 자동으로 삭제됩니다.
        """
        logger.info(f"PostgreSQL 파일 ID {file_id} 삭제 시도")
        # SQL: DELETE FROM files WHERE id = %s
        try:
            file_id_int = int(file_id)
        except ValueError:
            logger.error(f"유효하지 않은 파일 ID 형식: {file_id}")
            return False # 삭제 실패

        delete_query = "DELETE FROM files WHERE id = %s"
        # execute_query 내부에서 commit 처리가 됩니다.
        success = self.execute_query(delete_query, params=(file_id_int,), commit=True)

        if success:
             logger.info(f"파일 ID {file_id} 삭제 완료")
             return True # 삭제 성공
        else:
             logger.error(f"파일 ID {file_id} 삭제 실패")
             return False # 삭제 실패

    def vector_search(self, query: str, file_filter: str = None, tags_filter: list[str] = None, top_k: int = TOP_K_RESULTS):
        """PostgreSQL pgvector를 사용하여 문서를 검색합니다."""
        logger.info(f"PostgreSQL 벡터 검색 시도: {query}")
        if not self.embedding_model:
             logger.error("Embedding 모델이 로드되지 않았습니다. 벡터 검색을 수행할 수 없습니다.")
             return []

        try:
            # 쿼리 임베딩 생성
            query_embedding = self.embedding_model.embed_query(query)

            # pgvector의 Vector 타입을 사용하기 위한 등록 (connection 당 한 번만 필요)
            # __init__ 에서 이미 수행되었다고 가정하거나, 여기서 확인/수행
            try:
                from pgvector import Vector # Vector 타입은 pgvector에서 임포트
                # register_vector(self._connection) # __init__에서 수행
                query_embedding_vector = Vector(query_embedding)
            except ImportError:
                 logger.error("pgvector 라이브러리가 설치되지 않았습니다. 벡터 검색이 불가능합니다.")
                 raise RuntimeError("pgvector library not installed")

            # SQL 쿼리 작성 (pgvector 연산자 사용)
            # 필터 조건 추가 (file_id, tags 등)
            # L2 거리 연산자 (<->)를 사용하여 유사도 검색
            # SELECT c.content, c.metadata, c.embedding <-> %s AS score
            # FROM chunks c
            # WHERE ... -- 필터 조건
            # ORDER BY c.embedding <-> %s
            # LIMIT %s

            search_query = "SELECT c.content, c.metadata, c.embedding <-> %s AS score FROM chunks c"
            params = [query_embedding_vector]
            where_clauses = []

            # 파일 필터 추가 (파일 이름을 ID로 변환해야 함)
            if file_filter:
                # 파일 이름으로 file_id 조회
                file_id_query = "SELECT id FROM files WHERE filename = %s"
                file_row = self.execute_query(file_id_query, params=(file_filter,), fetchone=True)
                if file_row:
                    file_id_int = file_row['id']
                    where_clauses.append("c.file_id = %s")
                    params.append(file_id_int)
                else:
                    logger.warning(f"벡터 검색: 파일 필터 '{file_filter}'에 해당하는 파일을 찾을 수 없습니다.")
                    return [] # 해당 파일이 없으면 결과 없음

            # 태그 필터 추가
            if tags_filter:
                # tags 컬럼(JSONB)에서 배열에 특정 태그가 포함되어 있는지 확인
                # 예: metadata->'tags' ?| ARRAY['tag1', 'tag2']
                where_clauses.append("c.metadata->'tags' ?| ARRAY[%s]")
                params.append(tags_filter) # psycopg2가 리스트를 PostgreSQL ARRAY로 자동 변환

            # WHERE 절 추가
            if where_clauses:
                search_query += " WHERE " + " AND ".join(where_clauses)

            # ORDER BY (유사도 점수 오름차순) 및 LIMIT 추가
            search_query += " ORDER BY c.embedding <-> %s LIMIT %s"
            params.append(query_embedding_vector) # ORDER BY 절에도 임베딩 벡터 사용
            params.append(top_k)

            search_results = self.execute_query(search_query, params=params, fetchall=True)

            # 결과 변환 (MongoDBStorage의 검색 결과 형태와 유사하게)
            # PostgreSQL 결과는 RealDictRow 객체의 리스트입니다.
            # 필요한 정보 (content, metadata, score)를 추출하여 반환
            formatted_results = []
            if search_results:
                 for row in search_results:
                      formatted_results.append({
                          'content': row['content'],
                          'metadata': row['metadata'],
                          'score': row['score']
                      })

            return formatted_results

        except Exception as e:
            logger.error(f"PostgreSQL 벡터 검색 중 오류 발생: {e}")
            raise

    def context_search(self, query: str, file_filter: str = None, tags_filter: list[str] = None, top_k: int = TOP_K_RESULTS):
        """단순 키워드 기반 컨텍스트 검색 (ILIKE)을 수행합니다."""
        logger.info(f"PostgreSQL 컨텍스트(키워드) 검색 시도: {query}")
        try:
            search_query = "SELECT c.content, c.metadata, 0.0 AS score FROM chunks c"
            where_clauses = ["c.content ILIKE %s"]
            params = [f"%{query}%"]

            # 파일 필터 처리 (파일명 → id)
            if file_filter:
                file_row = self.execute_query(
                    "SELECT id FROM files WHERE filename = %s",
                    params=(file_filter,),
                    fetchone=True
                )
                if file_row:
                    file_id_int = file_row['id']
                    where_clauses.append("c.file_id = %s")
                    params.append(file_id_int)
                else:
                    logger.warning(f"컨텍스트 검색: 파일 필터 '{file_filter}'에 해당하는 파일 없음")
                    return []

            # 태그 필터 처리 (metadata->'tags')
            if tags_filter:
                where_clauses.append("c.metadata->'tags' ?| ARRAY[%s]")
                params.append(tags_filter)

            if where_clauses:
                search_query += " WHERE " + " AND ".join(where_clauses)

            search_query += " LIMIT %s"
            params.append(top_k)

            rows = self.execute_query(search_query, params=tuple(params), fetchall=True)
            formatted_results = []
            if rows:
                for row in rows:
                    formatted_results.append({
                        'content': row['content'],
                        'metadata': row['metadata'],
                        'score': row.get('score', 0.0)
                    })

            return formatted_results
        except Exception as e:
            logger.error(f"PostgreSQL 컨텍스트 검색 중 오류 발생: {e}")
            raise

    def is_file_exist(self, filename: str) -> bool:
        """files 테이블에 특정 이름의 파일이 존재하는지 확인합니다."""
        logger.info(f"PostgreSQL 파일 '{filename}' 존재 확인 시도")
        # SQL: SELECT COUNT(*) FROM files WHERE filename = %s
        count_query = "SELECT COUNT(*) FROM files WHERE filename = %s"
        result = self.execute_query(count_query, params=(filename,), fetchone=True)

        # 결과는 딕셔너리 형태이므로 첫 번째 값 (COUNT(*))을 가져옵니다.
        count = result[list(result.keys())[0]] if result else 0

        return count > 0

# TODO: config.py에 PostgreSQL 연결 정보 추가 (PG_DB_HOST, PG_DB_NAME, PG_DB_USER, PG_DB_PASSWORD, PG_DB_PORT)
# TODO: app.py 등에서 MongoDBStorage 대신 PostgreSQLStorage 사용하도록 수정 