# app.py - Streamlit 앱 (환경변수 활용)

import streamlit as st
import asyncio
import nest_asyncio
import time
import os
import json
from models.lm_studio import LMStudioClient
from retrieval.vector_store import VectorStore
from core.orchestrator import Orchestrator
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
            
            # 벡터 스토어 초기화 (vector_tool 도구가 활성화된 경우에만)
            vector_store = None
            if "vector_tool" in ENABLED_TOOLS:
                vector_store = VectorStore()
            
            # 오케스트레이터 초기화
            orchestrator = Orchestrator(lm_studio_client, vector_store)
            
            # 세션 상태에 저장
            st.session_state.lm_studio_client = lm_studio_client
            st.session_state.vector_store = vector_store
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
                st.success("시스템이 성공적으로 초기화되었습니다.")
            else:
                st.error("시스템 초기화에 실패했습니다.")
        
        # 시스템 상태
        if st.session_state.system_initialized:
            st.success("시스템 상태: 초기화됨")
            
            # 모델 정보 표시
            if 'model_info' in st.session_state:
                st.subheader("모델 정보")
                model_info = st.session_state.model_info
                st.write(f"모델: **{model_info['model']}**")
                st.write(f"API 상태: {'✅ 연결됨' if model_info['api_available'] else '❌ 연결 안됨'}")
        else:
            st.warning("시스템 상태: 초기화 필요")
        
        # 환경 설정 표시
        with st.expander("환경 설정"):
            if 'config_info' in st.session_state:
                config_info = st.session_state.config_info
                st.json(config_info)
        
        # 디버그 모드
        debug_mode = st.checkbox("디버그 모드", value=DEBUG_MODE)
        
        # 도구 정보 표시
        if st.session_state.system_initialized and 'tool_info' in st.session_state:
            st.subheader("활성화된 도구")
            tool_info = st.session_state.tool_info
            for name, info in tool_info.items():
                st.write(f"- **{info['name']}**: {info['description']}")
    
    # 메인 영역
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # 시스템 초기화 확인
        if not st.session_state.system_initialized:
            if initialize_system():
                st.success("시스템이 자동으로 초기화되었습니다.")
            else:
                st.error("시스템을 초기화할 수 없습니다. 사이드바에서 '시스템 초기화' 버튼을 클릭하세요.")
        
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
        upload_and_index_files()
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