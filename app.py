# app.py - Streamlit 앱 (환경변수 활용)

import streamlit as st
import asyncio
import nest_asyncio
import time
import os
import json
from models.lm_studio import LMStudioClient
# from retrieval.vector_store import VectorStore # VectorStore 임포트 제거
from core.orchestrator import Orchestrator
from retrieval.document_loader import DocumentLoader # 이 로더는 save_file에서 사용되므로 유지
from utils.logger import setup_logger
from config import print_config, DEBUG_MODE, ENABLED_TOOLS

# 비동기 지원을 위한 nest_asyncio 설정
nest_asyncio.apply()

# 로거 설정
logger = setup_logger(__name__)

# 세션 상태 초기화
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'system_initialized' not in st.session_state:
    st.session_state.system_initialized = False

if 'debug_info' not in st.session_state:
    st.session_state.debug_info = {}

if 'config_info' not in st.session_state:
    st.session_state.config_info = print_config()

def initialize_system():
    """AgenticRAG 시스템 초기화"""
    with st.spinner("시스템 초기화 중..."):
        try:
            # LM Studio 클라이언트 초기화
            lm_studio_client = LMStudioClient()
            
            # 벡터 스토어 초기화 (vector_tool 도구가 활성화된 경우에만) 로직 제거
            # vector_store = None
            # if "vector_tool" in ENABLED_TOOLS:
            #     vector_store = VectorStore()
            
            # 오케스트레이터 초기화 - vector_store 인자 제거
            orchestrator = Orchestrator(lm_studio_client)
            
            # 세션 상태에 저장
            st.session_state.lm_studio_client = lm_studio_client
            # st.session_state.vector_store = vector_store # vector_store 저장 제거
            st.session_state.orchestrator = orchestrator
            st.session_state.system_initialized = True
            
            # 설정 정보 업데이트
            st.session_state.config_info = print_config()
            
            # 모델 정보 확인
            model_info = lm_studio_client.get_model_info()
            st.session_state.model_info = model_info
            
            # 활성화된 도구 정보
            if hasattr(orchestrator, 'tool_manager'):
                st.session_state.tool_info = orchestrator.tool_manager.get_tool_info()
            
            return True
        except Exception as e:
            logger.error(f"시스템 초기화 오류: {str(e)}")
            st.error(f"시스템 초기화 중 오류가 발생했습니다: {str(e)}")
            return False

async def process_query_async(query):
    """질의를 비동기적으로 처리"""
    orchestrator = st.session_state.orchestrator
    start_time = time.time()
    
    try:
        result = await orchestrator.process_query(query)
        
        # 디버그 정보 업데이트
        st.session_state.debug_info = {
            "query": query,
            "tool_calls": result["tool_calls"],
            "tool_results": result["tool_results"],
            "processing_time": f"{time.time() - start_time:.2f} 초"
        }
        
        return result["response"]
    except Exception as e:
        logger.error(f"질의 처리 오류: {str(e)}")
        return f"질의 처리 중 오류가 발생했습니다: {str(e)}"

def upload_and_index_files():
    st.subheader("문서 업로드 및 색인")
    uploaded_files = st.file_uploader("문서를 업로드하세요 (txt, pdf)", type=["txt", "pdf"], accept_multiple_files=True)
    if uploaded_files and st.session_state.system_initialized:
        docs = []
        for file in uploaded_files:
            file_path = f"/tmp/{file.name}"
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
            if file.name.lower().endswith(".txt"):
                loaded = DocumentLoader.load_text(file_path)
            elif file.name.lower().endswith(".pdf"):
                loaded = DocumentLoader.load_pdf(file_path)
            else:
                loaded = []
            docs.extend(loaded)
        # 벡터 스토어에 추가
        vector_store = st.session_state.vector_store
        if vector_store:
            vector_store.add_texts([doc.page_content for doc in docs], "user_uploads")
            st.success(f"{len(docs)}개 문서가 색인되었습니다.")
        else:
            st.error("벡터 스토어가 초기화되지 않았습니다.")

def main():
    """Streamlit 앱 메인 함수"""
    st.set_page_config(
        page_title="AgenticRAG + LM Studio",
        page_icon="🤖",
        layout="wide"
    )
    
    # 제목
    st.title("AgenticRAG + LM Studio + LangChain + Function Calling")
    
    # 사이드바
    with st.sidebar:
        st.header("시스템 설정")
        
        # 초기화 버튼
        if st.button("시스템 초기화"):
            if initialize_system():
                pass # 초기화 성공 메시지 제거
            else:
                st.error("시스템 초기화에 실패했습니다.")
        
        # 시스템 상태
        # 초기화 상태에 따라 다른 메시지 표시
        if 'system_initialized' not in st.session_state or not st.session_state.system_initialized:
            st.error("시스템 상태: 초기화 필요")
        else:
            st.success("시스템 상태: 초기화됨")
            
            # 모델 정보 표시
            if 'model_info' in st.session_state:
                st.subheader("모델 정보")
                model_info = st.session_state.model_info
                st.write(f"모델: **{model_info['model']}**")
                st.write(f"API 상태: {'✅ 연결됨' if model_info['api_available'] else '❌ 연결 안됨'}")
        
        # 환경 설정 표시
        with st.expander("환경 설정"):
            if 'config_info' in st.session_state:
                config_info = st.session_state.config_info
                st.json(config_info)
        
        # 디버그 모드
        # 시스템 초기화 상태에 따라 디버그 모드 활성화/비활성화
        is_system_initialized = st.session_state.get('system_initialized', False)
        debug_mode = st.checkbox("디버그 모드", value=DEBUG_MODE, disabled=not is_system_initialized)

        # 디버그 모드 활성화/비활성화 상태 메시지 표시
        if debug_mode:
            st.info("디버그 모드가 활성화되었습니다.")
        else:
            st.info("디버그 모드가 비활성화되었습니다.")
        
        # 도구 정보 표시
        if st.session_state.system_initialized and 'tool_info' in st.session_state:
            st.subheader("활성화된 도구")
            tool_info = st.session_state.tool_info
            for name, info in tool_info.items():
                st.write(f"- **{info['name']}**: {info['description']}")
    
    # 메인 영역
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # 시스템 초기화 확인 (페이지 로드 시 자동 초기화 로직 제거)
        # 초기화는 이제 사이드바의 버튼 클릭 시에만 수행됩니다.
        # if not st.session_state.system_initialized:
        #     if initialize_system():
        #         pass
        #     else:
        #         st.error("시스템을 초기화할 수 없습니다. 사이드바에서 '시스템 초기화' 버튼을 클릭하세요.")
        
        # 이전 메시지 표시
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # 사용자 입력 처리
        if prompt := st.chat_input("질문을 입력하세요"):
            # 사용자 메시지 추가
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # 응답 생성
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                with st.spinner("처리 중..."):
                    if st.session_state.system_initialized:
                        # 비동기 처리 실행
                        response = asyncio.run(process_query_async(prompt))
                        message_placeholder.markdown(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                    else:
                        error_msg = "시스템이 초기화되지 않았습니다. 사이드바에서 '시스템 초기화' 버튼을 클릭하세요."
                        message_placeholder.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
    
    with col2:
        # 문서 업로드 및 색인 UI
        # upload_and_index_files() # 기존 벡터 스토어 색인 기능 주석 처리 또는 제거

        # --- 파일 업로드 (MongoDB GridFS) ---
        # 시스템이 초기화된 경우에만 파일 업로드 섹션 표시
        if st.session_state.get('system_initialized', False):
            st.subheader("파일 업로드")
            # 파일 업로더 위젯에 고유한 키 부여
            uploaded_file_mongo = st.file_uploader("MongoDB에 저장할 파일을 업로드하세요", type=None, accept_multiple_files=False, key="file_uploader_key")

            # 세션 상태에 처리된 파일 목록 저장을 위한 초기화
            if 'processed_files' not in st.session_state:
                st.session_state.processed_files = []

            # 업로드 버튼 추가 - 파일이 선택된 경우에만 보이도록 합니다.
            if uploaded_file_mongo is not None:
                if st.button("업로드", key="upload_button"):
                    filename = uploaded_file_mongo.name

                    # MongoDBStorage 싱글톤 인스턴스 가져오기
                    from storage.mongodb_storage import MongoDBStorage
                    mongo_storage = MongoDBStorage.get_instance()

                    # 0. GridFS에 이미 파일이 존재하는지 먼저 확인
                    if mongo_storage.is_file_exist(filename):
                        st.info(f"'{filename}' 파일은 이미 업로드되었습니다.")
                        # 파일 목록 캐시 초기화 (새로고침 없으므로 목록 수동 갱신 필요)
                        st.session_state.mongo_files = None # 목록 캐시 초기화는 유지
                        # st.rerun() # 새로고침 제거
                    else:
                        # 파일 데이터를 읽어서 MongoDB에 저장
                        file_data = uploaded_file_mongo.getvalue()
                        # content_type = uploaded_file_mongo.type # GridFS에 저장 시 필요할 수 있음

                        # MongoDBStorage 싱글톤 인스턴스 가져오기
                        from storage.mongodb_storage import MongoDBStorage
                        mongo_storage = MongoDBStorage.get_instance()

                        with st.spinner(f"{filename} 업로드 중..."):
                            try:
                                # save_file 메소드 호출 (metadata는 필요에 따라 추가)
                                # save_file 메소드는 GridFS 저장 후 벡터 컬렉션 저장까지 처리
                                # save_file 메소드가 file_id를 반환하도록 수정했다면 여기서 사용 가능
                                mongo_storage.save_file(file_data, filename, metadata={"tags": ["업로드"]}) # 예시 메타데이터

                                st.success(f"{filename} 업로드 성공!")
                                # 성공적으로 처리된 파일 정보를 세션 상태에 추가
                                st.session_state.processed_files.append((filename, uploaded_file_mongo.size))
                                # 파일 목록을 새로고침하기 위해 세션 상태의 mongo_files를 None으로 설정
                                st.session_state.mongo_files = None
                                # 파일 업로더 위젯 초기화
                                # st.session_state["file_uploader_key"] = None # 이 줄을 제거합니다.
                                st.rerun() # 위젯 상태를 반영하기 위해 앱 다시 실행

                            except Exception as e:
                                logger.error(f"업로드 중 오류 발생: {e}")
                                st.error(f"업로드 중 오류가 발생했습니다: {str(e)}")
                                # 오류 발생 시 파일 목록 세션 상태를 초기화하여 다시 로드하도록 강제
                                st.session_state.mongo_files = None
                                st.rerun() # 변경사항 반영을 위해 다시 실행
        else:
            # 시스템이 초기화되지 않은 경우 메시지 표시
            st.info("시스템을 초기화 해주세요")

        # GridFS에 저장된 파일 목록 표시 (기존 도구 사용)
        # 'list_mongodb_files_tool'이 활성화되어 있어야 합니다.
        # 이 부분은 기존 MongoDB 도구를 사용하므로 수정하지 않습니다.
        # 파일 목록을 세션 상태에 저장하여 중복 호출 방지

        # 파일 목록 섹션 제목 표시
        st.subheader("파일 목록")

        # 시스템이 초기화된 경우에만 파일 목록을 불러오고 표시
        if st.session_state.get('system_initialized', False):
            if 'mongo_files' not in st.session_state or st.session_state.mongo_files is None:
                 # MongoDBStorage 인스턴스 가져와서 list_files 호출
                from storage.mongodb_storage import MongoDBStorage
                mongo_storage = MongoDBStorage.get_instance()
                try:
                     st.session_state.mongo_files = mongo_storage.list_files()
                     logger.info(f"GridFS 파일 목록 세션 상태에 저장: {len(st.session_state.mongo_files)}개")
                except Exception as e:
                     logger.error(f"GridFS 파일 목록 조회 오류: {e}")
                     st.session_state.mongo_files = [] # 오류 발생 시 빈 리스트
                     st.warning("파일 목록을 가져오는 중 오류가 발생했습니다. MongoDB 연결 상태를 확인하세요.")

            if st.session_state.mongo_files:
                # 각 파일 정보와 다운로드 버튼을 표시
                for file_info in st.session_state.mongo_files:
                     filename = file_info.get('filename', '이름 없음')
                     # 파일 크기 (바이트)를 MB 단위로 변환하여 표시
                     file_size_bytes = file_info.get('length', 0)
                     file_size_mb = round(file_size_bytes / (1024 * 1024), 2)
                     file_id = file_info.get('_id', 'ID 없음')

                     # 각 파일 항목을 시각적으로 그룹화하여 간격 조정 및 구분
                     with st.container(border=True):
                         # 파일 이름과 크기 표시
                         st.write(f"**{filename}** ({file_size_mb} MB)")

                         # 다운로드 버튼 추가 (파일 정보 바로 아래에 배치)
                         # MongoDBStorage 싱글톤 인스턴스 가져오기
                         from storage.mongodb_storage import MongoDBStorage
                         mongo_storage = MongoDBStorage.get_instance()

                         # 파일 내용 가져오기 (다운로드 버튼 클릭 시 실행)
                         file_content = mongo_storage.get_file_content_by_id(file_id)

                         if file_content is not None:
                             st.download_button(
                                 label="다운로드",
                                 data=file_content,
                                 file_name=filename,
                                 mime='application/octet-stream',
                                 key=f"download_{file_id}"
                             )
                         else:
                              st.text("내용 가져오기 실패")

            else:
                # 시스템 초기화는 되었지만 파일이 없는 경우
                st.info("업로드된 파일이 없습니다.")
        else:
            # 시스템이 초기화되지 않은 경우 메시지 표시
            st.info("시스템을 초기화 해주세요")

        # 디버그 정보 표시 (디버그 모드가 활성화된 경우에만)
        if debug_mode and st.session_state.debug_info:
            st.header("처리 정보")
            debug_info = st.session_state.debug_info
            
            st.subheader("사용자 질의")
            st.write(debug_info.get("query", "N/A"))
            
            st.subheader("선택된 도구")
            tool_call = debug_info.get("tool_calls", {})
            if tool_call:
                if isinstance(tool_call, list):
                    for i, call in enumerate(tool_call, 1):
                        st.write(f"도구 {i}: `{call.get('name', 'N/A')}`")
                        st.write("인자:")
                        st.json(call.get("arguments", {}))
                elif isinstance(tool_call, dict):
                    st.write(f"도구: `{tool_call.get('name', 'N/A')}`")
                    st.write("인자:")
                    st.json(tool_call.get("arguments", {}))
            else:
                st.write("선택된 도구 없음")
            
            st.subheader("도구 실행 결과")
            tool_results = debug_info.get("tool_results", {})
            for tool_name, result in tool_results.items():
                st.write(f"도구: `{tool_name}`")
                with st.expander("결과 보기"):
                    st.write(result)
            
            st.subheader("처리 시간")
            st.write(debug_info.get("processing_time", "N/A"))

if __name__ == "__main__":
    main()