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
import pandas as pd
import tempfile
from storage.postgresql_storage import PostgreSQLStorage
# from bson.objectid import ObjectId
import base64

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
if 'last_vector_items' not in st.session_state:
    st.session_state.last_vector_items = []
if 'pdf_preview' not in st.session_state:
    st.session_state.pdf_preview = None
if 'show_pdf_modal' not in st.session_state:
    st.session_state.show_pdf_modal = False

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
                
                # 아두이노 도구가 활성화되어 있으면 자동 연결 시도
                if 'arduino_water_sensor' in orchestrator.tool_manager.tools:
                    try:
                        arduino_tool = orchestrator.tool_manager.tools['arduino_water_sensor']
                        if arduino_tool._connect_to_arduino():
                            logger.info("아두이노 자동 연결 성공")
                            st.success("🔌 아두이노 자동 연결 성공!")
                        else:
                            logger.warning("아두이노 자동 연결 실패")
                            st.warning("⚠️ 아두이노 자동 연결 실패 - USB 연결을 확인하세요")
                    except Exception as e:
                        logger.error(f"아두이노 자동 연결 중 오류: {e}")
                        st.warning(f"⚠️ 아두이노 연결 시도 중 오류: {str(e)}")
                
                # 대시보드용 아두이노 직접 통신 객체 초기화 및 연결
                from utils.arduino_direct import DirectArduinoComm
                if 'shared_arduino' not in st.session_state:
                    st.session_state.shared_arduino = DirectArduinoComm()
                    # 시스템 초기화 시 아두이노 연결 시도
                    if st.session_state.shared_arduino.connect():
                        logger.info("대시보드용 아두이노 연결 성공")
                    else:
                        logger.warning("대시보드용 아두이노 연결 실패")
            
            # PostgreSQLStorage 초기화
            try:
                st.session_state.storage = PostgreSQLStorage.get_instance()
                logger.info("PostgreSQLStorage 초기화 성공")
            except Exception as e:
                logger.error(f"PostgreSQLStorage 초기화 오류: {e}")
                st.error(f"PostgreSQL 스토리지 초기화 중 오류가 발생했습니다: {e}")
                st.session_state.system_initialized = False # 스토리지 초기화 실패 시 시스템 초기화 실패로 간주
                return False
            
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
            "tool_calls": result.get("tool_calls", "N/A"),
            "tool_results": result.get("tool_results", "N/A"),
            "processing_time": f"{time.time() - start_time:.2f} 초"
        }
        
        return result
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

def display_graph_image(graph_file_id):
    """PostgreSQL에서 그래프 이미지를 가져와 표시"""
    storage = st.session_state.get('storage')
    if not storage:
        st.error("스토리지 시스템이 초기화되지 않았습니다.")
        return

    try:
        # 파일 내용을 바이트로 가져옴
        image_content = storage.get_file_content_by_id(graph_file_id)

        if image_content:
            # 파일 확장자를 확인하여 이미지 타입 결정 (예: png)
            # 실제 파일 이름이나 메타데이터에서 확장자를 가져오는 것이 더 정확할 수 있습니다.
            # 여기서는 임시로 png로 가정하거나, get_file_content_by_id가 파일 정보를 더 반환하도록 수정
            # (현재는 content만 반환하므로, 파일 정보를 조회하는 추가 호출이 필요할 수 있음) -> save_file에서 metadata에 확장자 저장 고려
            # get_file_content_by_id를 확장하여 파일 이름/메타데이터도 함께 가져오도록 수정하는 것이 좋음.

            # 만약 get_file_content_by_id가 content만 반환한다면,
            # 파일 ID로 파일 정보를 별도 조회하여 filename이나 확장자를 얻어야 함.
            # 현재는 content만 가져오므로, Streamlit에서 이미지 타입 추론이 필요.
            # Streamlit의 st.image는 bytes를 받을 때 type을 지정할 수 있습니다.
            # 가장 흔한 그래프 이미지 형식인 png로 가정하고 시도.

            # 파일 내용을 Base64로 인코딩 (Streamlit st.image는 bytes도 직접 받음)
            # base64_image = base64.b64encode(image_content).decode()
            # image_tag = f'<img src="data:image/png;base64,{base64_image}" alt="Graph Image" style="max-width:100%;">'
            # st.markdown(image_tag, unsafe_allow_html=True)

            # 또는 Streamlit의 st.image 사용
            st.image(bytes(image_content), caption='생성된 그래프', use_container_width=True, output_format='auto')

        else:
            st.warning(f"그래프 이미지 ID {graph_file_id}에 해당하는 파일 내용을 가져올 수 없습니다.")

    except Exception as e:
        logger.error(f"그래프 이미지 표시 오류: {graph_file_id} - {e}")
        st.error(f"그래프 이미지를 가져오는 중 오류가 발생했습니다: {e}")

def display_pdf_inline(file_bytes: bytes, filename: str):
    """PDF 바이트를 인라인으로 렌더링"""
    try:
        b64_pdf = base64.b64encode(file_bytes).decode('utf-8')
        pdf_iframe = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="700" type="application/pdf"></iframe>'
        st.markdown(pdf_iframe, unsafe_allow_html=True)
    except Exception as e:
        logger.error(f"PDF 인라인 표시 오류: {filename} - {e}")
        st.error(f"PDF를 표시하는 중 오류가 발생했습니다: {e}")

def open_pdf_modal(file_id: str, filename: str):
    st.session_state.pdf_preview = {"file_id": file_id, "filename": filename}
    st.session_state.show_pdf_modal = True

def close_pdf_modal():
    st.session_state.pdf_preview = None
    st.session_state.show_pdf_modal = False

def render_pdf_modal():
    if not st.session_state.get('show_pdf_modal'):
        return
    preview = st.session_state.get('pdf_preview') or {}
    file_id = preview.get('file_id')
    filename = preview.get('filename') or '미리보기'
    storage = st.session_state.get('storage')
    if not storage or not file_id:
        st.session_state.show_pdf_modal = False
        return
    file_bytes = storage.get_file_content_by_id(file_id)
    # Modal API가 없을 수 있으므로 공통 fallback(expander) 사용
    with st.expander(f"📄 {filename} (미리보기)", expanded=True):
        if file_bytes:
            display_pdf_inline(bytes(file_bytes), filename)
        else:
            st.warning("PDF 데이터를 불러오지 못했습니다.")
        if st.button("닫기", key="close_pdf_expander_btn"):
            close_pdf_modal()
            st.rerun()

def main():
    """Streamlit 앱 메인 함수"""
    st.set_page_config(
        page_title="Synergy ChatBot",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 페이지 라우팅
    if 'page' not in st.session_state:
        st.session_state.page = "main"
    
    # 대시보드 페이지로 이동
    if st.session_state.page == "water_dashboard":
        try:
            from water_dashboard import main as dashboard_main
            dashboard_main()
            return
        except ImportError as e:
            st.error(f"대시보드 모듈 로드 실패: {e}")
            st.error("필요한 패키지를 설치하세요: pip install plotly")
            st.session_state.page = "main"  # 메인 페이지로 돌아가기
    
    # 메인 페이지 계속 실행
    st.session_state.page = "main"

    # 전역 모달 렌더링 훅 (세션 state에 따라 표시)
    render_pdf_modal()
    
    # 다크 모드 호환 CSS 추가
    st.markdown("""
    <style>
    :root {
        --text-color: #1f2937;
        --text-color-secondary: #6b7280;
        --bg-color: #ffffff;
        --border-color: #e5e7eb;
    }
    
    [data-theme="dark"] {
        --text-color: #f9fafb;
        --text-color-secondary: #d1d5db;
        --bg-color: #111827;
        --border-color: #374151;
    }
    
    .stApp[data-theme="dark"] {
        --text-color: #f9fafb !important;
        --text-color-secondary: #d1d5db !important;
    }
    
    /* 다크 모드에서 텍스트 색상 강제 적용 */
    .stApp[data-theme="dark"] .markdown-text-container {
        color: #f9fafb !important;
    }
    
    .stApp[data-theme="dark"] p, 
    .stApp[data-theme="dark"] span,
    .stApp[data-theme="dark"] div {
        color: #f9fafb !important;
    }
    
    /* 사이드바 다크 모드 개선 */
    .stApp[data-theme="dark"] .css-1d391kg {
        background-color: #1f2937 !important;
    }
    
    /* 버튼 스타일 개선 */
    .stButton > button {
        border-radius: 8px;
        border: none;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 메인 헤더 (다크 모드 호환)
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; margin-bottom: 2rem; color: white; box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);">
        <h1 style="margin: 0; font-size: 2.5em; font-weight: 700; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); color: white !important;">⚡ Synergy ChatBot</h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.2em; opacity: 0.9; color: white !important;">AI-Powered Intelligent Assistant</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 사이드바
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; margin-bottom: 1rem; color: white;">
            <h3 style="margin: 0; font-weight: 600; color: white !important;">🎛️ 시스템 제어</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # 초기화 버튼
        if st.button("🔄 시스템 초기화", type="primary", use_container_width=True):
            if initialize_system():
                pass # 초기화 성공 메시지 제거
            else:
                st.error("시스템 초기화에 실패했습니다.")
        
        # 대시보드 버튼 및 아두이노 상태
        if st.session_state.get('system_initialized', False):
            
            if st.button("💧 수위 대시보드", type="secondary", use_container_width=True):
                # Streamlit multipage navigation using session state
                st.session_state.page = "water_dashboard"
                st.rerun()
        
        # 시스템 상태
        st.markdown("#### 📊 시스템 상태")
        if 'system_initialized' not in st.session_state or not st.session_state.system_initialized:
            st.markdown("""
            <div style='padding: 12px; background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); 
                        border-left: 4px solid #f44336; border-radius: 8px; margin: 10px 0; 
                        box-shadow: 0 2px 8px rgba(244, 67, 54, 0.2);'>
                <strong style='color: #d32f2f;'>❌ 초기화 필요</strong>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style='padding: 12px; background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c8 100%); 
                        border-left: 4px solid #4caf50; border-radius: 8px; margin: 10px 0;
                        box-shadow: 0 2px 8px rgba(76, 175, 80, 0.2);'>
                <strong style='color: #2e7d32;'>✅ 시스템 준비완료</strong>
            </div>
            """, unsafe_allow_html=True)
            
            # 모델 정보 표시
            if 'model_info' in st.session_state:
                st.markdown("#### 🤖 모델 정보")
                model_info = st.session_state.model_info
                
                # 아두이노 연결 상태 확인
                arduino_status = "❌ 연결 안됨"
                arduino_color = "#dc2626"
                
                if st.session_state.system_initialized and 'tool_info' in st.session_state:
                    if 'arduino_water_sensor' in st.session_state.tool_info:
                        try:
                            # 아두이노 도구에서 상태 확인
                            arduino_tool = st.session_state.orchestrator.tool_manager.tools.get('arduino_water_sensor')
                            if arduino_tool and hasattr(arduino_tool, 'arduino_port'):
                                if arduino_tool.arduino_port == "SIMULATION":
                                    arduino_status = "🔄 시뮬레이션 모드"
                                    arduino_color = "#f59e0b"
                                elif arduino_tool.arduino_port and arduino_tool.arduino_port.startswith('/dev/tty'):
                                    # usbipd-win으로 포워딩된 실제 포트
                                    if (hasattr(arduino_tool, 'serial_connection') and 
                                        arduino_tool.serial_connection and 
                                        arduino_tool.serial_connection.is_open):
                                        arduino_status = f"✅ 실제 연결됨 ({arduino_tool.arduino_port})"
                                        arduino_color = "#16a34a"
                                    else:
                                        arduino_status = f"🔌 포트 발견 ({arduino_tool.arduino_port})"
                                        arduino_color = "#3b82f6"
                                elif arduino_tool.arduino_port:
                                    # 기타 포트
                                    arduino_status = f"✅ 연결됨 ({arduino_tool.arduino_port})"
                                    arduino_color = "#16a34a"
                        except Exception as e:
                            logger.debug(f"아두이노 상태 확인 중 오류: {e}")
                
                st.markdown(f"""
                <div style='padding: 15px; background: linear-gradient(135deg, #f8f9ff 0%, #e8f4ff 100%); 
                            border-radius: 10px; margin: 10px 0; border: 1px solid #e1e8ff;
                            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);'>
                    <p style='margin: 5px 0; color: var(--text-color, #1f2937);'><strong>📝 모델:</strong> {model_info['model']}</p>
                    <p style='margin: 5px 0; color: var(--text-color, #1f2937);'><strong>🔗 API 상태:</strong> {'<span style="color: #16a34a; font-weight: 600;">✅ 연결됨</span>' if model_info['api_available'] else '<span style="color: #dc2626; font-weight: 600;">❌ 연결 안됨</span>'}</p>
                    <p style='margin: 5px 0; color: var(--text-color, #1f2937);'><strong>🔌 아두이노:</strong> <span style="color: {arduino_color}; font-weight: 600;">{arduino_status}</span></p>
                </div>
                """, unsafe_allow_html=True)
        
        # 환경 설정 표시
        with st.expander("⚙️ 환경 설정", expanded=False):
            if 'config_info' in st.session_state:
                config_info = st.session_state.config_info
                st.json(config_info)
        
        # 디버그 모드
        st.markdown("---")
        is_system_initialized = st.session_state.get('system_initialized', False)
        debug_mode = st.checkbox("🐛 디버그 모드", value=DEBUG_MODE, disabled=not is_system_initialized)

        if debug_mode:
            st.markdown("""
            <div style='padding: 10px; background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%); 
                        border-radius: 6px; margin: 8px 0; font-size: 0.9em;
                        border: 1px solid #f1c40f; box-shadow: 0 2px 4px rgba(241, 196, 15, 0.2);'>
                <span style='color: #856404; font-weight: 500;'>🔍 디버그 모드 활성화</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style='padding: 10px; background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); 
                        border-radius: 6px; margin: 8px 0; font-size: 0.9em;
                        border: 1px solid #dee2e6; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);'>
                <span style='color: var(--text-color-secondary, #6c757d); font-weight: 500;'>😴 디버그 모드 비활성화</span>
            </div>
            """, unsafe_allow_html=True)
        
        # 도구 정보 표시
        if st.session_state.system_initialized and 'tool_info' in st.session_state:
            st.markdown("#### 🛠️ 활성화된 도구")
            tool_info = st.session_state.tool_info
            
            for info in tool_info.values():
                tool_icon = {
                    'calculator_tool': '🧮',
                    'weather_tool': '🌤️',
                    'list_files_tool': '📁',
                    'vector_search_tool': '🔎',
                    'arduino_water_sensor': '🔌',
                    'water_level_prediction_tool': '📊'
                }.get(info['name'], '🔧')

                st.markdown(f"""
                <div style='padding: 12px; background: linear-gradient(135deg, #f8f9ff 0%, #e8f4ff 100%); 
                            border-radius: 8px; margin: 5px 0; border-left: 3px solid #667eea;
                            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);'>
                    <strong style='color: var(--text-color, #1f2937);'>{tool_icon} {info['name'].replace('_tool', '').title()}</strong><br>
                    <small style='color: var(--text-color-secondary, #6b7280); opacity: 0.8;'>{info['description'][:80]}{'...' if len(info['description']) > 80 else ''}</small>
                </div>
                """, unsafe_allow_html=True)
    
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
        if prompt := st.chat_input("💬 질문을 입력하세요... (예: '펌프 켜줘', '서울 날씨 알려줘')", key="main_chat_input"):
            # 사용자 메시지 추가
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # 응답 생성
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                with st.spinner("처리 중..."):
                    if st.session_state.system_initialized:
                        # 비동기 처리 실행 -> 동기 래퍼 사용
                        # 오케스트레이터 호출 및 전체 결과 받기
                        orchestrator_result = st.session_state.orchestrator.process_query_sync(prompt) # 동기 래퍼 호출

                        response_text = orchestrator_result.get("response", "응답 생성 실패")
                        tool_results = orchestrator_result.get("tool_results", {})
                        tool_calls = orchestrator_result.get("tool_calls", [])

                        # 메인 응답 표시
                        message_placeholder.markdown(response_text)
                        
                        # 벡터 검색 출처 및 PDF 미리보기/다운로드 (메인 응답 바로 아래에 요약 표시)
                        try:
                            vector_items = []
                            for k, v in tool_results.items():
                                base_tool_name = k.split('_')[0] + '_' + k.split('_')[1] + '_tool' if '_' in k else k
                                if base_tool_name == 'vector_search_tool' and isinstance(v, list):
                                    vector_items.extend(v)

                            if vector_items:
                                # 파일 기준으로 모아 상위 5개 출처만 노출
                                seen = set()
                                unique_sources = []
                                for item in vector_items:
                                    fname = item.get('filename')
                                    fid = item.get('file_id')
                                    key = (fname, fid)
                                    if key not in seen:
                                        seen.add(key)
                                        unique_sources.append(item)

                                st.markdown("---")
                                # 사용자 요청에 따라 상단 텍스트 출처 표시는 제거

                                # 첫 번째 PDF 출처에 한해 빠른 미리보기/다운로드 제공
                                storage = st.session_state.get('storage')
                                for item in unique_sources:
                                    fname = item.get('filename') or ''
                                    fid = item.get('file_id')
                                    if fname.lower().endswith('.pdf') and fid and storage:
                                        btn_cols = st.columns(2)
                                        with btn_cols[0]:
                                            if st.button("👁️ 미리보기", key=f"src_quick_preview_{fid}", use_container_width=True):
                                                open_pdf_modal(fid, fname)
                                                st.rerun()
                                        with btn_cols[1]:
                                            try:
                                                fb = storage.get_file_content_by_id(fid)
                                                if fb:
                                                    st.download_button(
                                                        label="⬇️ 첫 번째 PDF 다운로드",
                                                        data=bytes(fb),
                                                        file_name=fname,
                                                        mime='application/pdf',
                                                        key=f"src_quick_download_{fid}",
                                                        use_container_width=True,
                                                        type="secondary"
                                                    )
                                                else:
                                                    st.info("다운로드할 PDF 데이터를 찾을 수 없습니다.")
                                            except Exception as e:
                                                logger.error(f"PDF 다운로드 준비 오류: {fid} - {e}")
                                                st.error("PDF 다운로드 준비 중 오류가 발생했습니다.")
                                        break
                        except Exception as e:
                            logger.error(f"출처 요약 섹션 렌더링 오류: {e}")
                        
                        # 상세 정보가 있는 경우 접을 수 있는 형태로 표시 (중복 출처 표시 제거)
                        if tool_results and len(tool_results) > 0:
                            with st.expander("🔍 상세 실행 정보", expanded=False):
                                for i, (tool_name, result) in enumerate(tool_results.items()):
                                    # 도구 아이콘 매핑
                                    tool_icon = {
                                        'calculator_tool': '🧮', 
                                        'weather_tool': '🌤️',
                                        'list_files_tool': '📁',
                                        'vector_search_tool': '🔎',
                                        'arduino_water_sensor': '🔌',
                                        'water_level_prediction_tool': '📊'
                                    }
                                    
                                    # 도구 이름에서 숫자 제거하여 아이콘 찾기
                                    base_tool_name = tool_name.split('_')[0] + '_' + tool_name.split('_')[1] + '_tool' if '_' in tool_name else tool_name
                                    icon = tool_icon.get(base_tool_name, '🔧')
                                    
                                    st.markdown(f"### {icon} {tool_name.replace('_', ' ').title()}")
                                    
                                    # 결과를 예쁘게 포맷팅
                                    if isinstance(result, dict):
                                        # 중요한 정보만 하이라이트해서 표시
                                        if 'success' in result:
                                            status_color = "green" if result.get('success') else "red"
                                            status_text = "✅ 성공" if result.get('success') else "❌ 실패"
                                            st.markdown(f"**상태:** <span style='color: {status_color}'>{status_text}</span>", unsafe_allow_html=True)
                                        
                                        if 'message' in result:
                                            st.markdown(f"**결과:** {result['message']}")
                                            
                                        if 'result' in result:
                                            st.markdown(f"**값:** `{result['result']}`")
                                            
                                        if 'expression' in result:
                                            st.markdown(f"**계산식:** `{result['expression']}`")
                                            
                                        # 날씨 정보 특별 표시
                                        if 'temperature_c' in result:
                                            st.markdown(f"**🌡️ 기온:** {result['temperature_c']}°C ({result.get('temperature_f', 'N/A')}°F)")
                                            if 'weather_desc' in result:
                                                st.markdown(f"**☁️ 날씨:** {result['weather_desc']}")
                                            if 'humidity' in result:
                                                st.markdown(f"**💧 습도:** {result['humidity']}%")
                                            if 'wind_speed' in result:
                                                st.markdown(f"**💨 풍속:** {result['wind_speed']} km/h")
                                        
                                        # 펌프 제어 결과 특별 표시
                                        if 'pump_id' in result:
                                            st.markdown(f"**🏷️ 펌프:** {result['pump_id']}")
                                            if 'status' in result:
                                                status_emoji = "🟢" if result['status'] == "ON" else "🔴"
                                                st.markdown(f"**⚡ 상태:** {status_emoji} {result['status']}")
                                        
                                        # 검색 결과는 상단 출처 섹션에서 이미 요약 표시하므로 중복 표시 생략
                                        
                                        # 전체 JSON은 HTML details로 표시
                                        import json as json_lib
                                        json_str = json_lib.dumps(result, indent=2, ensure_ascii=False)
                                        st.markdown(f"""
                                        <details>
                                        <summary>📋 전체 JSON 데이터</summary>
                                        <pre style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; overflow-x: auto;">
{json_str}
                                        </pre>
                                        </details>
                                        """, unsafe_allow_html=True)
                                    else:
                                            # 리스트 기반 결과 (예: 벡터 검색 결과) 전용 표시
                                            if isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
                                                st.markdown(f"**📊 검색 결과:** {len(result)}개 항목")
                                                storage = st.session_state.get('storage')
                                                for idx, item in enumerate(result):
                                                    filename = item.get('filename') or '파일 이름 알 수 없음'
                                                    file_id = item.get('file_id')
                                                    chunk_index = item.get('chunk_index', 'N/A')
                                                    score = item.get('score', 'N/A')
                                                    content_preview = item.get('content', '')
                                                    with st.container(border=True):
                                                        st.markdown(f"**출처:** `{filename}`  |  **청크:** {chunk_index}  |  **점수:** {score}")
                                                        st.markdown(content_preview)
                                                        # PDF 미리보기/다운로드 버튼 (PDF 파일에 한함)
                                                        if filename and filename.lower().endswith('.pdf') and file_id and storage:
                                                            btn_cols = st.columns(2)
                                                            with btn_cols[0]:
                                                                if st.button("👁️ PDF 미리보기", key=f"preview_pdf_{tool_name}_{idx}_{file_id}", use_container_width=True):
                                                                    try:
                                                                        file_bytes = storage.get_file_content_by_id(file_id)
                                                                        if file_bytes:
                                                                            display_pdf_inline(bytes(file_bytes), filename)
                                                                        else:
                                                                            st.warning("PDF 데이터를 불러오지 못했습니다.")
                                                                    except Exception as e:
                                                                        logger.error(f"PDF 미리보기 오류: {file_id} - {e}")
                                                                        st.error("PDF 미리보기에 실패했습니다.")
                                                            with btn_cols[1]:
                                                                try:
                                                                    file_bytes = None
                                                                    if storage:
                                                                        file_bytes = storage.get_file_content_by_id(file_id)
                                                                    if file_bytes:
                                                                        st.download_button(
                                                                            label="⬇️ PDF 다운로드",
                                                                            data=bytes(file_bytes),
                                                                            file_name=filename,
                                                                            mime='application/pdf',
                                                                            key=f"download_pdf_{tool_name}_{idx}_{file_id}",
                                                                            use_container_width=True,
                                                                            type="secondary"
                                                                        )
                                                                    else:
                                                                        st.info("다운로드할 PDF 데이터를 찾을 수 없습니다.")
                                                                except Exception as e:
                                                                    logger.error(f"PDF 다운로드 준비 오류: {file_id} - {e}")
                                                                    st.error("PDF 다운로드 준비 중 오류가 발생했습니다.")
                                            else:
                                                st.markdown(f"**결과:** {str(result)}")
                                    
                                    # 마지막 항목이 아니면 구분선 추가
                                    if i < len(tool_results) - 1:
                                        st.markdown("---")
                        
                        st.session_state.messages.append({"role": "assistant", "content": response_text})


                    else:
                        error_msg = "시스템이 초기화되지 않았습니다. 사이드바에서 '시스템 초기화' 버튼을 클릭하세요."
                        message_placeholder.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
    
    with col2:
        # 문서 업로드 및 색인 UI
        # upload_and_index_files() # 기존 벡터 스토어 색인 기능 주석 처리 또는 제거

        # --- 파일 업로드 (PostgreSQL GridFS) ---
        # 시스템이 초기화된 경우에만 파일 업로드 섹션 표시
        if st.session_state.get('system_initialized', False):
            st.markdown("""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 12px; border-radius: 10px; margin-bottom: 15px; text-align: center; color: white; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);">
                <h4 style="margin: 0; font-weight: 600; color: white !important;">📤 파일 업로드</h4>
            </div>
            """, unsafe_allow_html=True)
            # 세션 상태에 처리된 파일 목록 저장을 위한 초기화
            if 'processed_files' not in st.session_state:
                st.session_state.processed_files = []

            # 업로드 상태를 나타내는 세션 상태 변수 초기화
            if 'is_uploading' not in st.session_state:
                st.session_state.is_uploading = False

            # 파일 업로더와 업로드 버튼의 disabled 상태를 제어
            upload_disabled = not st.session_state.get('system_initialized', False) or st.session_state.is_uploading

            # 파일 업로더 위젯에 고유한 키 부여 및 disabled 상태 설정
            uploaded_file_postgres = st.file_uploader(
                "PostgreSQL에 저장할 파일을 업로드하세요", 
                type=None, 
                accept_multiple_files=False, 
                key="file_uploader_key",
                disabled=upload_disabled # disabled 상태 적용
            )

            # 업로드 버튼 추가 - 파일이 선택되고 업로드 중이 아닐 때만 보이도록 합니다.
            # 업로드 중에는 버튼을 비활성화합니다.
            if uploaded_file_postgres is not None:
                if st.button(
                    "업로드", 
                    key="upload_button",
                    disabled=upload_disabled # disabled 상태 적용
                ):
                    # 업로드 시작 시 상태 변경
                    st.session_state.is_uploading = True

            # is_uploading 상태가 True이면 실제 업로드 로직 실행
            if st.session_state.is_uploading and uploaded_file_postgres is not None:
                filename = uploaded_file_postgres.name

                # PostgreSQLStorage 싱글톤 인스턴스 가져오기
                pg_storage = PostgreSQLStorage.get_instance()
                if pg_storage is None:
                    st.error("스토리지 시스템이 초기화되지 않았습니다.")
                    st.session_state.is_uploading = False
                    return

                # 파일 데이터를 읽어서 PostgreSQL에 저장
                file_data = uploaded_file_postgres.getvalue()
                # content_type = uploaded_file_postgres.type # GridFS에 저장 시 필요할 수 있음

                with st.spinner(f"{filename} 업로드 중..."):
                    try:
                        # save_file 메소드를 호출하고 결과를 확인
                        # save_file 메소드는 GridFS 저장 후 벡터 컬렉션 저장까지 처리
                        # save_file 메소드가 file_id를 반환하도록 수정했다면 여기서 사용 가능
                        # mongo_storage.save_file(file_data, filename, metadata={"tags": ["업로드"]}) # 예시 메타데이터
                        # save_file은 성공 시 file_id(str) 또는 None 반환
                        save_result_id = pg_storage.save_file(file_data, filename, metadata={"tags": ["업로드"]}) # 결과

                        if save_result_id:
                            st.success(f"파일 '{filename}' 업로드 및 저장 완료. ID: {save_result_id}")
                        else:
                            st.error(f"파일 '{filename}' 업로드 및 저장 실패.")

                        # 성공적으로 처리된 파일 정보를 세션 상태에 추가
                        # save_file이 성공한 경우에만 추가하도록 변경
                        # 파일이 이미 존재하는 경우 (save_result is None)에도 목록 갱신을 위해 추가하도록 변경
                        if save_result_id:
                            st.session_state.processed_files.append((filename, uploaded_file_postgres.size))
                        
                        # 업로드 완료 후 상태 변경
                        st.session_state.is_uploading = False

                    except Exception as e:
                        logger.error(f"파일 업로드 중 오류 발생: {e}")
                        st.error(f"파일 업로드 중 오류가 발생했습니다: {e}")
                        
                        # 오류 발생 시 상태 변경
                        st.session_state.is_uploading = False

        else:
            # 시스템이 초기화되지 않은 경우 메시지 표시
            st.info("시스템을 초기화 해주세요")

        # PostgreSQL에 저장된 파일 목록 표시 (기존 도구 사용)
        # 'list_postgresql_files_tool'이 활성화되어 있어야 합니다.
        # 이 부분은 기존 PostgreSQL 도구를 사용하므로 수정하지 않습니다.
        # 파일 목록을 세션 상태에 저장하여 중복 호출 방지

        # 파일 목록 섹션 제목 표시
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 12px; border-radius: 10px; margin: 15px 0; text-align: center; color: white; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);">
            <h4 style="margin: 0; font-weight: 600; color: white !important;">📂 파일 목록</h4>
        </div>
        """, unsafe_allow_html=True)

        # 시스템이 초기화된 경우에만 파일 목록을 불러오고 표시
        if st.session_state.get('system_initialized', False):
            if 'postgres_files' not in st.session_state or st.session_state.postgres_files is None:
                 # PostgreSQLStorage 인스턴스 가져와서 list_files 호출
                mongo_storage = PostgreSQLStorage.get_instance()
                if mongo_storage is None:
                    st.session_state.postgres_files = []
                    st.warning("스토리지 시스템이 초기화되지 않았습니다.")
                else:
                    try:
                         st.session_state.postgres_files = mongo_storage.list_files()
                         logger.info(f"PostgreSQL 파일 목록 세션 상태에 저장: {len(st.session_state.postgres_files)}개")
                    except Exception as e:
                         logger.error(f"PostgreSQL 파일 목록 조회 오류: {e}")
                         st.session_state.postgres_files = [] # 오류 발생 시 빈 리스트
                         st.warning("파일 목록을 가져오는 중 오류가 발생했습니다. PostgreSQL 연결 상태를 확인하세요.")

            if st.session_state.postgres_files:
                # 각 파일 정보와 다운로드 버튼을 표시
                for file_info in st.session_state.postgres_files:
                     filename = file_info.get('filename', '이름 없음')
                     # 파일 크기 (바이트)를 MB 단위로 변환하여 표시
                     file_size_bytes = file_info.get('length', 0)
                     file_size_mb = round(file_size_bytes / (1024 * 1024), 2)
                     file_id = file_info.get('_id', 'ID 없음')

                     # 각 파일 항목을 시각적으로 그룹화하여 간격 조정 및 구분
                     with st.container(border=True):
                         # 파일 이름과 크기 표시
                         st.markdown(f"""
                         <div style='padding: 12px; background: linear-gradient(135deg, #f8f9ff 0%, #e8f4ff 100%); 
                                     border-radius: 8px; margin: 8px 0; border: 1px solid #e1e8ff;
                                     box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);'>
                             <div style='display: flex; align-items: center; justify-content: space-between;'>
                                 <div>
                                     <strong style='color: var(--text-color, #1f2937); font-size: 1.1em;'>📄 {filename}</strong><br>
                                     <small style='color: var(--text-color-secondary, #6b7280); font-weight: 500;'>크기: {file_size_mb} MB</small>
                                 </div>
                             </div>
                         </div>
                         """, unsafe_allow_html=True)

                         # 다운로드 버튼 추가 (파일 정보 바로 아래에 배치)
                         # file_id가 유효한 문자열 ID인지 확인
                         if file_id != 'ID 없음':
                              # PostgreSQLStorage 싱글톤 인스턴스 가져오기
                              mongo_storage = PostgreSQLStorage.get_instance()
                              if mongo_storage is None:
                                  st.warning("스토리지 시스템이 초기화되지 않았습니다.")
                                  continue
 
                              # 파일 내용 가져오기 (다운로드 버튼 클릭 시 실행)
                              # 파일을 다운로드 버튼의 data 인자로 직접 전달하면 Streamlit이 처리
                              # get_file_content_by_id 호출은 download_button이 실제로 렌더링될 때가 아닌,
                              # 페이지가 로드될 때마다 발생하므로 주의해야 함.
                              # 여기서는 단순화를 위해 get_file_content_by_id를 호출하는 로직 유지
                              # 실제 앱에서는 다운로드 버튼 클릭 시 콜백 함수 등에서 파일 내용을 가져오는 것이 효율적
                              file_content = mongo_storage.get_file_content_by_id(file_id)

                              if file_content is not None:
                                  # memoryview를 bytes로 변환하여 download_button에 전달
                                  file_content_bytes = bytes(file_content)

                                  st.download_button(
                                      label="⬇️ 다운로드",
                                      data=file_content_bytes,
                                      file_name=filename,
                                      mime='application/octet-stream',
                                      key=f"download_{file_id}",
                                      use_container_width=True,
                                      type="secondary"
                                  )
                              else:
                                  st.warning(f"'{filename}' 파일 내용을 가져오지 못했습니다 (ID: {file_id}).")
                                  # 디버깅을 위해 로그에 기록하거나 터미널에 출력할 수 있습니다.
                                  # print(f"DEBUG: Failed to get content for file ID: {file_id}") # 터미널 출력
                         else:
                             st.warning(f"'{filename}' 파일 ID가 유효하지 않습니다: {file_id}")

            else:
                # 시스템 초기화는 되었지만 파일이 없는 경우
                st.info("업로드된 파일이 없습니다.")
        else:
            # 시스템이 초기화되지 않은 경우 메시지 표시
            st.info("시스템을 초기화 해주세요")

        # 디버그 정보 표시 (디버그 모드가 활성화된 경우에만)
        if debug_mode and st.session_state.debug_info:
            st.markdown("""
            <div style="background: linear-gradient(135deg, #ffeaa7 0%, #fab1a0 100%); padding: 15px; border-radius: 10px; margin: 20px 0; color: #2d3436; box-shadow: 0 4px 12px rgba(255, 234, 167, 0.4);">
                <h3 style="margin: 0 0 10px 0; font-weight: 600; color: #2d3436 !important;">🔍 처리 정보</h3>
            </div>
            """, unsafe_allow_html=True)
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