# app.py - Streamlit 앱

import streamlit as st
import time
import base64
from datetime import datetime
from models.lm_studio import LMStudioClient
from core.orchestrator import Orchestrator
from utils.logger import setup_logger
from utils.helpers import clean_ai_response
from config import print_config, DEBUG_MODE, ENABLED_TOOLS
from storage.postgresql_storage import PostgreSQLStorage
from tools.water_level_monitoring_tool import water_level_monitoring_tool

# 로거 설정
logger = setup_logger(__name__)

# --- 세션 상태 초기화 ---
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
            
            # 오케스트레이터 초기화
            orchestrator = Orchestrator(lm_studio_client)
            
            # 세션 상태에 저장
            st.session_state.lm_studio_client = lm_studio_client
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
                        # 먼저 포트를 찾아본다
                        found_port = arduino_tool._find_arduino_port()
                        if found_port and found_port != "SIMULATION":
                            # 실제 하드웨어 포트가 발견된 경우에만 연결 시도
                            if arduino_tool._connect_to_arduino():
                                logger.info("아두이노 자동 연결 성공")
                                st.toast("🔌 아두이노 자동 연결 성공!", icon="✅")
                            else:
                                logger.warning("아두이노 자동 연결 실패")
                                st.warning("⚠️ 아두이노 자동 연결 실패 - USB 연결 및 드라이버를 확인하세요")
                        elif found_port == "SIMULATION":
                            logger.info("아두이노 시뮬레이션 모드")
                            arduino_tool.arduino_port = "SIMULATION"
                            st.info("🔄 아두이노 시뮬레이션 모드로 실행됩니다")
                        else:
                            logger.warning("아두이노 포트를 찾을 수 없음")
                            st.warning("⚠️ 아두이노를 찾을 수 없습니다 - USB 연결을 확인하세요")
                    except Exception as e:
                        logger.error(f"아두이노 자동 연결 중 오류: {e}")
                        st.warning(f"⚠️ 아두이노 연결 시도 중 오류: {str(e)}")
                
                # 대시보드용 아두이노 직접 통신 객체 초기화 (자동 연결 안함)
                from utils.arduino_direct import DirectArduinoComm
                if 'shared_arduino' not in st.session_state:
                    st.session_state.shared_arduino = DirectArduinoComm()
                    # 주의: 객체만 생성하고 자동 연결은 하지 않음 (사용자가 수동으로 연결 버튼 클릭 필요)
            
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
        layout="wide"
    )

    # 페이지 라우팅
    if 'page' not in st.session_state:
        st.session_state.page = "main"

    if st.session_state.page == "water_dashboard":
        try:
            from water_dashboard import main as dashboard_main
            dashboard_main()
            return
        except ImportError as e:
            st.error(f"대시보드 모듈 로드 실패: {e}")
            st.session_state.page = "main"
            
    st.session_state.page = "main"

    render_pdf_modal()
    

    # --- 카카오톡 스타일 CSS ---
    st.markdown("""
    <style>
    :root{
        --kakao-bg: #b5b2ff;
        --kakao-yellow: #fee500;
        --user-bubble: #fee500;
        --ai-bubble: #ffffff;
        --text-dark: #191919;
        --text-light: #666666;
        --bubble-shadow: rgba(0,0,0,0.1);
        --border-light: #e1e1e1;
    }
    
    .main .block-container {
        padding: 0.5rem 1rem;
        max-width: 1400px;
    }
    
    /* 채팅 컨테이너 배경 */
    .stChatMessage {
        background: none !important;
        border: none !important;
        box-shadow: none !important;
        margin: 12px 0 !important;
        padding: 0 !important;
        position: relative !important;
    }
    
    /* 사용자 메시지 - 카카오톡 노란색 말풍선 (오른쪽) */
    .stChatMessage[data-testid="chat-message-user"] {
        display: flex !important;
        justify-content: flex-end !important;
        margin-bottom: 8px !important;
    }
    
    .stChatMessage[data-testid="chat-message-user"] .stMarkdown {
        background: var(--user-bubble) !important;
        color: var(--text-dark) !important;
        padding: 12px 16px !important;
        border-radius: 18px 4px 18px 18px !important;
        max-width: 70% !important;
        box-shadow: 0 2px 8px var(--bubble-shadow) !important;
        font-size: 14px !important;
        line-height: 1.4 !important;
        margin: 0 !important;
        position: relative !important;
        word-break: break-word !important;
    }
    
    /* AI 메시지 - 흰색 말풍선 (왼쪽) */
    .stChatMessage[data-testid="chat-message-assistant"] {
        display: flex !important;
        justify-content: flex-start !important;
        margin-bottom: 8px !important;
        align-items: flex-start !important;
    }
    
    .stChatMessage[data-testid="chat-message-assistant"]::before {
        content: "🤖";
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        display: flex !important;
        align-items: center;
        justify-content: center;
        margin-right: 8px !important;
        font-size: 18px;
        flex-shrink: 0;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
    }
    
    .stChatMessage[data-testid="chat-message-assistant"] .stMarkdown {
        background: var(--ai-bubble) !important;
        color: var(--text-dark) !important;
        padding: 12px 16px !important;
        border-radius: 4px 18px 18px 18px !important;
        max-width: 70% !important;
        box-shadow: 0 2px 8px var(--bubble-shadow) !important;
        border: 1px solid var(--border-light) !important;
        font-size: 14px !important;
        line-height: 1.5 !important;
        margin: 0 !important;
        position: relative !important;
        word-break: break-word !important;
    }
    
    /* 생각 중 메시지 스타일 - 채팅창 내에서만 적용 */
    .thinking-bubble {
        background: #f5f5f5 !important;
        border: 2px dashed #667eea !important;
        animation: thinking-pulse 2s ease-in-out infinite !important;
        position: relative !important;
        z-index: 1 !important;
    }
    
    /* 전체 화면 오버레이 방지 */
    .stApp > div[data-testid="stAppViewContainer"] {
        background: transparent !important;
    }
    
    /* streamlit 기본 스피너/로더 숨기기 */
    .stSpinner {
        display: none !important;
    }
    
    /* 전체 화면 블록킹 방지 */
    body {
        overflow: visible !important;
    }
    
    @keyframes thinking-pulse {
        0%, 100% { opacity: 0.8; transform: scale(1); }
        50% { opacity: 1; transform: scale(1.05); }
    }
    
    @keyframes thinking-glow {
        0%, 100% { 
            box-shadow: 0 4px 12px rgba(44, 90, 160, 0.2);
            border-color: #667eea;
        }
        50% { 
            box-shadow: 0 6px 20px rgba(44, 90, 160, 0.4);
            border-color: #4f5bd5;
        }
    }
    
    @keyframes thinking-dots {
        0%, 20% { opacity: 0.3; transform: scale(0.8); }
        50% { opacity: 1; transform: scale(1.2); }
        80%, 100% { opacity: 0.3; transform: scale(0.8); }
    }
    
    /* 타임스탬프 스타일 */
    .timestamp {
        font-size: 11px !important;
        color: var(--text-light) !important;
        margin-top: 4px !important;
        text-align: right !important;
    }
    
    .timestamp-left {
        text-align: left !important;
        margin-left: 48px !important;
    }
    
    /* --- 🎨 채팅 입력창 스타일 (강제 라이트 모드) --- */
    /* 입력창 내부 텍스트 스타일 */
    .stChatInput > div > div > textarea {
        border: none !important; /* 이 부분이 textarea의 테두리를 제거합니다 */
        border-radius: 24px !important;
        padding: 12px 20px !important;
        font-size: 14px !important;
        background: transparent !important;
        resize: none !important;
        color: #191919 !important; 
    }

    /* 입력창 내부 텍스트 스타일 */
    .stChatInput > div > div > textarea {
        border: none !important;
        border-radius: 24px !important;
        padding: 12px 20px !important;
        font-size: 14px !important;
        background: transparent !important;
        resize: none !important;
        color: #191919 !important; /* 텍스트 색상 고정 */
    }

    /* 입력창 플레이스홀더 텍스트 색상 */
    .stChatInput > div > div > textarea::placeholder {
        color: #888888 !important;
    }

    .stChatInput > div > div > textarea:focus {
        outline: none !important;
        box-shadow: none !important;
    }

    
    /* 파일 아이템 스타일 */
    .file-item{
        border: 1px solid var(--border-light);
        border-radius: 8px;
        padding: 8px;
        margin: 6px 0;
        background: white;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    .file-item:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    /* 컨테이너 간격 최적화 */
    .stContainer > div {
        gap: 0.5rem !important;
    }

    /* 다크 모드 */
    [data-theme="dark"] {
        --ai-bubble: #2f2f2f;
        --user-bubble: #4a4a4a;
        --text-dark: #ffffff;
        --text-light: #b0b0b0;
        --border-light: #444444;
        --bubble-shadow: rgba(0,0,0,0.3);
    }
    
    /* 다크 모드 오버라이드 방지 (기존 다크모드 CSS는 삭제) */
    [data-theme="dark"] .stChatInput > div > div {
        background: #ffffff !important; /* 다크모드에서도 흰색 배경 유지 */
        border-color: #e1e1e1 !important;
    }
    [data-theme="dark"] .stChatInput > div > div > textarea {
        color: #191919 !important; /* 다크모드에서도 검은 텍스트 유지 */
    }
    [data-theme="dark"] .stChatInput > div > div > textarea::placeholder {
        color: #888888 !important; /* 다크모드에서도 플레이스홀더 색상 유지 */
    }
    
    [data-theme="dark"] .file-item {
        background: #2f2f2f;
        border-color: #444444;
        color: #ffffff;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- 헤더 (전체 화면 폭에 맞게 수정) ---
    st.markdown("""
    <div style="text-align:center; padding:24px 16px; border-radius:16px; width: 100%; margin: 16px 0; color:#fff; background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); box-shadow:0 6px 24px rgba(102,126,234,.3); position: relative; overflow: hidden;">
        <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: radial-gradient(circle at 20% 80%, rgba(255,255,255,0.1) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(255,255,255,0.1) 0%, transparent 50%);"></div>
        <div style="position: relative; z-index: 1;">
            <h1 style="margin:0; font-size:32px; color:white; font-weight:700; text-shadow: 0 2px 4px rgba(0,0,0,0.2);">⚡Synergy ChatBot</h1>
            <p style="margin:8px 0 0; opacity:.95; color:white; font-size:16px; font-weight:400;">AI-Powered Intelligent Assistant</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # --- 3단 레이아웃 정의 (비율 조정) ---
    left_col, center_col, right_col = st.columns([0.8, 2.4, 1])

    # --- 왼쪽 컬럼: 제어판 ---
    with left_col:
        is_system_initialized = st.session_state.get('system_initialized', False)

        with st.container(border=True):
            st.subheader("🎛️ 시스템 제어")
            if st.button("🔄 시스템 초기화", type="primary", use_container_width=True):
                if initialize_system():
                    st.toast("시스템 초기화 성공!", icon="🎉")
                    st.rerun()
                else:
                    st.error("시스템 초기화에 실패했습니다.")
            
            if st.button("💧 수위 대시보드", use_container_width=True, disabled=not is_system_initialized):
                st.session_state.page = "water_dashboard"
                st.rerun()

            if is_system_initialized:
                st.success("✅ 시스템 준비완료")
            else:
                st.error("❌ 초기화 필요")

        with st.container(border=True):
            st.subheader("🤖 모델 / 연결 상태")
            if is_system_initialized:
                model_info = st.session_state.get('model_info', {})
                api_ok = model_info.get('api_available', False)
                
                # 아두이노 상태 로직 개선
                arduino_status = "❌ 연결 안됨"
                arduino_color = "#dc2626"
                
                # 아두이노 도구 확인
                arduino_tool = None
                if (hasattr(st.session_state, 'orchestrator') and 
                    hasattr(st.session_state.orchestrator, 'tool_manager') and
                    st.session_state.orchestrator.tool_manager.tools):
                    arduino_tool = st.session_state.orchestrator.tool_manager.tools.get('arduino_water_sensor')
                
                if arduino_tool:
                    # 포트 정보 확인
                    port = getattr(arduino_tool, 'arduino_port', None)
                    serial_conn = getattr(arduino_tool, 'serial_connection', None)
                    
                    if port == "SIMULATION":
                        arduino_status = "🔄 시뮬레이션"
                        arduino_color = "#f59e0b"
                    elif port and serial_conn and hasattr(serial_conn, 'is_open') and serial_conn.is_open:
                        # 실제 연결 상태를 다시 한번 확인
                        try:
                            # 시리얼 연결이 실제로 작동하는지 테스트
                            serial_conn.write(b"STATUS\n")
                            serial_conn.flush()
                            # Windows COM 포트 처리
                            port_name = port.split('\\')[-1] if '\\' in port else port.split('/')[-1]
                            arduino_status = f"✅ 연결됨 ({port_name})"
                            arduino_color = "#16a34a"
                        except Exception as e:
                            # 실제로는 연결이 안된 상태
                            arduino_status = "❌ 연결 끊어짐"
                            arduino_color = "#dc2626"
                            # 연결을 닫고 포트 정보 초기화
                            try:
                                serial_conn.close()
                            except:
                                pass
                            arduino_tool.serial_connection = None
                            arduino_tool.arduino_port = None
                    elif port:
                        # 포트는 있지만 연결이 안된 상태
                        port_name = port.split('\\')[-1] if '\\' in port else port.split('/')[-1]
                        arduino_status = f"🔌 포트 발견 ({port_name})"
                        arduino_color = "#3b82f6"
                
                st.markdown(f"**모델**: `{model_info.get('model', '-')}`")
                st.markdown(f"**API**: {'<span style="color: #16a34a;">✅ 연결됨</span>' if api_ok else '<span style="color: #dc2626;">❌ 연결 안됨</span>'}", unsafe_allow_html=True)
                st.markdown(f"**아두이노**: <span style='color: {arduino_color};'>{arduino_status}</span>", unsafe_allow_html=True)

            else:
                st.info("시스템 초기화 후 표시됩니다.")

        with st.container(border=True):
            st.subheader("⚙️ 환경 설정")
            with st.expander("열기"):
                st.json(st.session_state.get('config_info', {}))
        
        with st.container(border=True):
            st.subheader("🐛 디버그")
            debug_mode = st.checkbox("디버그 모드", value=DEBUG_MODE, disabled=not is_system_initialized)
            if debug_mode and st.session_state.debug_info:
                with st.expander("최근 처리 정보", expanded=False):
                    st.json(st.session_state.debug_info)

    # --- 중앙 컬럼: 채팅 ---
    with center_col:
        # 채팅 메시지를 담을 컨테이너 (헤더 제거, 높이 최적화)
        chat_container = st.container(height=650)
        with chat_container:
            for i, message in enumerate(st.session_state.messages):
                # 카카오톡 스타일 메시지 표시
                if message["role"] == "user":
                    # 사용자 메시지 - 오른쪽 정렬 노란색 말풍선
                    st.markdown(f"""
                    <div style="display: flex; justify-content: flex-end; margin-bottom: 8px;">
                        <div style="background: #fee500; color: #191919; padding: 12px 16px; 
                                    border-radius: 18px 4px 18px 18px; max-width: 70%; 
                                    box-shadow: 0 2px 8px rgba(0,0,0,0.1); font-size: 14px; 
                                    line-height: 1.4; word-break: break-word;">
                            {message["content"]}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 타임스탬프 (오른쪽 정렬)
                    if message.get("timestamp"):
                        st.markdown(f"""
                        <div style="text-align: right; font-size: 11px; color: #666666; margin-top: -4px; margin-bottom: 12px;">
                            {message["timestamp"]}
                        </div>
                        """, unsafe_allow_html=True)
                
                else:
                    # AI 메시지 - 왼쪽 정렬 흰색 말풍선
                    is_thinking = message.get("is_thinking", False)
                    bubble_class = "thinking-bubble" if is_thinking else ""
                    
                    # 생각 중 메시지는 특별한 스타일
                    if is_thinking:
                        st.markdown(f"""
                        <div style="display: flex; align-items: flex-start; margin-bottom: 8px;">
                            <div style="width: 40px; height: 40px; border-radius: 50%; 
                                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                        display: flex; align-items: center; justify-content: center; 
                                        margin-right: 8px; font-size: 18px; flex-shrink: 0;
                                        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
                                        animation: thinking-pulse 2s ease-in-out infinite;">
                                🤖
                            </div>
                            <div class="{bubble_class}" style="background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%); 
                                        color: #2c5aa0; padding: 16px 20px; 
                                        border-radius: 4px 18px 18px 18px; max-width: 70%; 
                                        box-shadow: 0 4px 12px rgba(44, 90, 160, 0.2); 
                                        border: 2px solid #667eea;
                                        font-size: 15px; line-height: 1.5; word-break: break-word;
                                        animation: thinking-glow 2s ease-in-out infinite;
                                        position: relative; font-weight: 500;">
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <span style="font-size: 16px;">🧠</span>
                                    <span>AI가 답변을 생성하고 있습니다</span>
                                    <span style="animation: thinking-dots 1.5s infinite; font-size: 18px; color: #667eea;">⋯</span>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        # 일반 AI 메시지 - HTML과 마크다운을 분리
                        st.markdown(f"""
                        <div style="display: flex; align-items: flex-start; margin-bottom: 8px;">
                            <div style="width: 40px; height: 40px; border-radius: 50%; 
                                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                        display: flex; align-items: center; justify-content: center; 
                                        margin-right: 8px; font-size: 18px; flex-shrink: 0;
                                        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);">
                                🤖
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # AI 메시지 내용을 깔끔한 마크다운으로만 표시
                        with st.container():
                            # 가독성 향상을 위한 CSS
                            st.markdown("""
                            <style>
                            .ai-message-container {
                                margin-left: 48px;
                                position: relative;
                                max-width: 80%;
                                margin-top: -8px;
                            }
                            .ai-message-content {
                                background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
                                color: #1f2937;
                                padding: 24px 28px;
                                border-radius: 8px 20px 20px 8px;
                                box-shadow: 0 4px 16px rgba(0,0,0,0.08), 0 1px 4px rgba(0,0,0,0.04);
                                border: 1px solid #e2e8f0;
                                font-size: 15px;
                                line-height: 1.7;
                                position: relative;
                            }
                            .ai-message-content::before {
                                content: '';
                                position: absolute;
                                left: -1px;
                                top: 20%;
                                height: 60%;
                                width: 4px;
                                background: linear-gradient(135deg, #667eea, #764ba2);
                                border-radius: 0 4px 4px 0;
                            }
                            .ai-message-content h2 {
                                font-size: 20px !important;
                                margin: 0 0 20px 0 !important;
                                color: #1e40af !important;
                                border-bottom: 3px solid #e0e7ff;
                                padding-bottom: 10px;
                                font-weight: 700 !important;
                                display: flex;
                                align-items: center;
                                gap: 8px;
                            }
                            .ai-message-content h3 {
                                font-size: 17px !important;
                                margin: 24px 0 14px 0 !important;
                                color: #374151 !important;
                                font-weight: 650 !important;
                                background: linear-gradient(90deg, #f1f5f9, transparent);
                                padding: 8px 12px;
                                border-left: 4px solid #64748b;
                                border-radius: 0 8px 8px 0;
                            }
                            .ai-message-content p {
                                margin: 12px 0 !important;
                                font-size: 15px !important;
                                line-height: 1.7 !important;
                                text-align: justify;
                            }
                            .ai-message-content ul {
                                margin: 16px 0 !important;
                                padding-left: 20px !important;
                            }
                            .ai-message-content li {
                                font-size: 15px !important;
                                line-height: 1.7 !important;
                                margin: 8px 0 !important;
                                padding-left: 8px;
                            }
                            .ai-message-content table {
                                width: 100% !important;
                                border-collapse: collapse !important;
                                margin: 20px 0 !important;
                                font-size: 14px !important;
                                border-radius: 8px;
                                overflow: hidden;
                                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                            }
                            .ai-message-content th, .ai-message-content td {
                                padding: 14px 18px !important;
                                border: 1px solid #e2e8f0 !important;
                                text-align: left !important;
                                font-size: 14px !important;
                            }
                            .ai-message-content th {
                                background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%) !important;
                                font-weight: 650 !important;
                                color: #475569 !important;
                            }
                            .ai-message-content td {
                                background: #fefefe !important;
                            }
                            .ai-message-content strong {
                                font-weight: 650 !important;
                                color: #1e293b !important;
                            }
                            .ai-message-content hr {
                                margin: 24px 0 !important;
                                border: none !important;
                                height: 2px !important;
                                background: linear-gradient(90deg, #e2e8f0, transparent) !important;
                            }
                            .pdf-download-btn {
                                position: absolute;
                                bottom: 8px;
                                right: 12px;
                                z-index: 10;
                            }
                            .pdf-download-btn a {
                                background: rgba(102, 126, 234, 0.1);
                                color: #667eea;
                                padding: 6px 10px;
                                border-radius: 6px;
                                text-decoration: none;
                                font-size: 12px;
                                font-weight: 500;
                                border: 1px solid rgba(102, 126, 234, 0.2);
                                transition: all 0.2s;
                                display: inline-block;
                                cursor: pointer;
                                pointer-events: auto;
                            }
                            .pdf-download-btn a:hover {
                                background: rgba(102, 126, 234, 0.2);
                                transform: translateY(-1px);
                                box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
                            }
                            </style>
                            """, unsafe_allow_html=True)
                            
                            # 메시지 컨테이너와 PDF 버튼을 함께 배치
                            if message["role"] == "assistant" and not is_thinking:
                                from datetime import datetime
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                
                                # PDF 다운로드 버튼 파라미터 생성
                                download_button_args = None
                                try:
                                    from utils.pdf_generator import (
                                        MarkdownToPDFConverter, 
                                        is_pdf_available
                                    )
                                    
                                    if is_pdf_available():
                                        pdf_converter = MarkdownToPDFConverter()
                                        # 영문 파일명으로 변경 (한글 파일명 문제 해결)
                                        filename = f"agentic_rag_report_{timestamp}.pdf"
                                        pdf_bytes = pdf_converter.convert_markdown_to_pdf(message["content"], filename)
                                        download_button_args = {
                                            "label": "📄 PDF",
                                            "data": pdf_bytes,
                                            "file_name": filename,
                                            "mime": "application/pdf"
                                        }
                                    else:
                                        # 텍스트 파일도 영문 파일명으로 변경
                                        filename = f"agentic_rag_report_{timestamp}.txt"
                                        text_bytes = message["content"].encode('utf-8')
                                        download_button_args = {
                                            "label": "📝 저장",
                                            "data": text_bytes,
                                            "file_name": filename,
                                            "mime": "text/plain"
                                        }
                                except Exception as e:
                                    logger.error(f"다운로드 버튼 생성 오류: {str(e)}")
                                    # 오류 발생시 기본 텍스트 저장 버튼 제공
                                    filename = f"agentic_rag_report_{timestamp}.txt"
                                    text_bytes = message["content"].encode('utf-8')
                                    download_button_args = {
                                        "label": "📝 저장",
                                        "data": text_bytes,
                                        "file_name": filename,
                                        "mime": "text/plain"
                                    }
                                
                                # 메시지 마크다운을 HTML로 변환해 코드블록 누락 등으로 인한 HTML 누출 방지
                                try:
                                    import markdown as _md
                                    message_html = _md.markdown(message["content"], extensions=['tables', 'fenced_code'])
                                except Exception:
                                    # 변환 실패 시 원문 그대로 출력하되 안전을 위해 escape 처리 없이 출력 (기존 동작 유지)
                                    message_html = message["content"]

                                # 컨테이너 내부 오른쪽 아래에 표시될 다운로드 버튼(앵커) HTML 구성
                                download_anchor_html = ""
                                if download_button_args:
                                    import base64 as _b64
                                    data_bytes = download_button_args.get("data", b"")
                                    file_name = download_button_args.get("file_name", f"agentic_rag_report_{timestamp}.txt")
                                    mime_type = download_button_args.get("mime", "application/octet-stream")
                                    b64_data = _b64.b64encode(data_bytes).decode()
                                    download_anchor_html = f'''
                                    <div class="pdf-download-btn">
                                        <a href="data:{mime_type};base64,{b64_data}" download="{file_name}" title="파일 저장">
                                            {download_button_args.get("label", "⬇️ 다운로드")}
                                        </a>
                                    </div>
                                    '''

                                # 메시지 내용과 다운로드 버튼을 같은 컨테이너에 렌더링
                                # 컨테이너를 먼저 렌더링하고, 그 다음 HTML 앵커를 별도 출력하여
                                # 일부 환경에서 앵커가 코드처럼 보이는 문제를 방지
                                st.markdown(f'''
                                <div class="ai-message-container">
                                    <div class="ai-message-content">
                                        {message_html}
                                    </div>
                                </div>
                                ''', unsafe_allow_html=True)
                                if download_anchor_html:
                                    st.markdown(download_anchor_html, unsafe_allow_html=True)
                            else:
                                # thinking 상태이거나 사용자 메시지인 경우 일반 표시
                                st.markdown(f'<div class="ai-message-content">{message["content"]}</div>', unsafe_allow_html=True)
                    
                    # 타임스탬프와 처리시간 (왼쪽 정렬, 프로필 이미지 만큼 들여쓰기)
                    if not is_thinking:
                        timestamp_parts = []
                        if message.get("timestamp"):
                            timestamp_parts.append(message["timestamp"])
                        if message.get("processing_time"):
                            timestamp_parts.append(f"⚡ {message['processing_time']}")
                        
                        if timestamp_parts:
                            st.markdown(f"""
                            <div style="margin-left: 48px; font-size: 11px; color: #666666; margin-top: -4px; margin-bottom: 12px;">
                                {" | ".join(timestamp_parts)}
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # 도구 실행 결과 (생각 중이 아닌 경우에만)
                    if not is_thinking and "tool_results" in message:
                        tool_results = message.get("tool_results", {})
                        if tool_results:
                            with st.expander("🔍 도구 실행 결과", expanded=False):
                                for tool_name, result in tool_results.items():
                                    st.subheader(f"🛠️ {tool_name}")
                                    if isinstance(result, dict):
                                        # 중요 정보만 하이라이트
                                        if 'success' in result:
                                            status = "✅ 성공" if result.get('success') else "❌ 실패"
                                            st.markdown(f"**상태:** {status}")
                                        if 'message' in result:
                                            st.markdown(f"**결과:** {result['message']}")
                                        if 'temperature_c' in result:
                                            st.markdown(f"**🌡️ 기온:** {result['temperature_c']}°C")
                                        if 'humidity' in result:
                                            st.markdown(f"**💧 습도:** {result['humidity']}%")
                                        # 전체 JSON은 접을 수 있게
                                        with st.expander("전체 데이터", expanded=False):
                                            st.json(result)
                                    else:
                                        st.write(str(result))

        # 사용자 입력 (플레이스홀더 개선)
        placeholder_text = "메시지를 입력하세요..."
        # AI 응답 생성 중일 때 입력창 비활성화 - thinking 메시지가 있으면 처리 중으로 간주
        is_processing = (st.session_state.messages and 
                        st.session_state.messages[-1].get("is_thinking", False))
        if is_processing:
            placeholder_text = "AI가 응답 생성 중입니다..."
        
        if prompt := st.chat_input(placeholder_text, key="main_chat_input", disabled=is_processing):
            if not is_system_initialized:
                st.toast("⚠️ 먼저 '시스템 초기화'를 실행해주세요!", icon="🔄")
            else:
                # 사용자 메시지에 타임스탬프 추가
                current_time = datetime.now().strftime("%H:%M")
                user_message = {
                    "role": "user", 
                    "content": prompt,
                    "timestamp": current_time
                }
                st.session_state.messages.append(user_message)
                
                # AI 생각 중 메시지 추가
                thinking_message = {
                    "role": "assistant",
                    "content": "AI가 답변을 생성하고 있습니다...",
                    "timestamp": datetime.now().strftime("%H:%M"),
                    "is_thinking": True
                }
                st.session_state.messages.append(thinking_message)
                
                # 즉시 화면을 다시 그려서 thinking 메시지 표시
                st.rerun()
                
        # thinking 메시지가 있을 때 백그라운드에서 처리
        if (st.session_state.messages and 
            st.session_state.messages[-1].get("is_thinking") and 
            not st.session_state.get('processing_started', False)):
            
            # 처리 시작 플래그 설정 (중복 처리 방지)
            st.session_state.processing_started = True
            
            # 사용자 질문 가져오기
            user_prompt = st.session_state.messages[-2]["content"]
            
            try:
                # 백그라운드에서 AI 응답 생성
                start_time = time.time()
                orchestrator_result = st.session_state.orchestrator.process_query_sync(user_prompt)
                response_text = orchestrator_result.get("response", "응답 생성 실패")
                processing_time = time.time() - start_time
                
                # thinking 메시지를 실제 응답으로 교체
                # AI 응답 정리 적용
                cleaned_response = clean_ai_response(response_text)
                st.session_state.messages[-1] = {
                    "role": "assistant",
                    "content": cleaned_response,
                    "tool_results": orchestrator_result.get("tool_results", {}),
                    "timestamp": datetime.now().strftime("%H:%M"),
                    "processing_time": f"{processing_time:.2f}초"
                }
                
                # 디버그 정보 업데이트
                st.session_state.debug_info = {
                    "query": user_prompt,
                    "tool_calls": orchestrator_result.get("tool_calls", []),
                    "tool_results": orchestrator_result.get("tool_results", {}),
                    "processing_time": f"{processing_time:.2f}초"
                }
                
                # 처리 완료 플래그 제거
                if 'processing_started' in st.session_state:
                    del st.session_state.processing_started
                
                st.toast("✅ 응답 완료!", icon="🎉")
                st.rerun()
                
            except Exception as e:
                # 오류 발생 시 오류 메시지로 교체
                error_message = f"❌ 오류가 발생했습니다: {str(e)}"
                cleaned_error = clean_ai_response(error_message)
                st.session_state.messages[-1] = {
                    "role": "assistant", 
                    "content": cleaned_error,
                    "timestamp": datetime.now().strftime("%H:%M")
                }
                
                if 'processing_started' in st.session_state:
                    del st.session_state.processing_started
                    
                st.toast("❌ 오류 발생", icon="⚠️")
                st.rerun()

    # --- 오른쪽 컬럼: 파일 관리 ---
    with right_col:
        # 수위 모니터링 대시보드
        with st.container(border=True):
            st.subheader("💧 수위 모니터링")
            if is_system_initialized:
                # 배수지 선택 버튼들
                col1, col2, col3 = st.columns(3)
                with col1:
                    gagok_btn = st.button("🏔️ 가곡", use_container_width=True, key="gagok_btn")
                with col2:
                    haeryong_btn = st.button("🌊 해룡", use_container_width=True, key="haeryong_btn")
                with col3:
                    sangsa_btn = st.button("🏞️ 상사", use_container_width=True, key="sangsa_btn")
                
                # 선택된 배수지 상태 초기화
                if 'selected_reservoir' not in st.session_state:
                    st.session_state.selected_reservoir = 'gagok'
                
                # 버튼 클릭 처리
                if gagok_btn:
                    st.session_state.selected_reservoir = 'gagok'
                elif haeryong_btn:
                    st.session_state.selected_reservoir = 'haeryong'
                elif sangsa_btn:
                    st.session_state.selected_reservoir = 'sangsa'
                
                # synergy 데이터베이스의 water 테이블에서만 데이터 가져오기
                try:
                    from tools.water_level_monitoring_tool import water_level_monitoring_tool
                    
                    # 오직 실제 water 테이블의 데이터만 조회 (샘플 데이터 생성 안함)
                    current_status = water_level_monitoring_tool(action='current_status')
                    
                    if current_status.get('success'):
                        reservoirs = current_status.get('reservoirs', [])
                        selected_res = st.session_state.selected_reservoir
                        
                        # 선택된 배수지 정보 찾기
                        selected_data = None
                        for res in reservoirs:
                            if res.get('reservoir_id') == selected_res:
                                selected_data = res
                                break
                        
                        if selected_data:
                            # 수위 그래프 표시
                            level = selected_data.get('current_level', 0)
                            max_level = 120  # 최대 표시 수위
                            level_percent = min(100, (level / max_level) * 100)
                            
                            # 상태별 색상 설정
                            status = selected_data.get('status', 'UNKNOWN')
                            if status == 'CRITICAL':
                                color = '#dc2626'  # 빨간색
                            elif status == 'WARNING':
                                color = '#f59e0b'  # 주황색
                            else:
                                color = '#3b82f6'  # 파란색
                            
                            # 날짜 정보 추출 (연월일 시분초까지 전체 표시)
                            last_update = selected_data.get('last_update', '')
                            try:
                                from datetime import datetime
                                if 'T' in last_update:
                                    update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                                else:
                                    update_dt = datetime.strptime(last_update, '%Y-%m-%d %H:%M:%S')
                                date_display = update_dt.strftime('%Y-%m-%d %H:%M:%S')
                            except:
                                date_display = last_update if last_update else '날짜 불명'
                            
                            st.markdown(f"""
                            <div style="background: linear-gradient(to top, {color} {level_percent}%, #e5e7eb {level_percent}%); 
                                       height: 80px; border-radius: 8px; position: relative; margin: 8px 0;
                                       border: 2px solid {color}; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                                <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); 
                                           color: white; font-weight: bold; font-size: 14px; text-shadow: 1px 1px 2px rgba(0,0,0,0.7);">
                                    {level:.1f}cm ({level_percent:.0f}%)
                                </div>
                                <div style="position: absolute; top: 5px; left: 8px; color: white; font-size: 11px; font-weight: bold; text-shadow: 1px 1px 2px rgba(0,0,0,0.7);">
                                    {selected_data.get('reservoir', '').replace(' 배수지', '')}
                                </div>
                                <div style="position: absolute; top: 5px; right: 8px; color: white; font-size: 10px; font-weight: bold; text-shadow: 1px 1px 2px rgba(0,0,0,0.7);">
                                    {status}
                                </div>
                                <div style="position: absolute; bottom: 3px; left: 8px; color: white; font-size: 9px; font-weight: bold; text-shadow: 1px 1px 2px rgba(0,0,0,0.8); opacity: 0.95; max-width: calc(100% - 16px); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; background: rgba(0,0,0,0.2); padding: 2px 4px; border-radius: 3px;">
                                    📅 {date_display}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # 펌프 상태 표시
                            st.markdown("**💨 펌프 상태**")
                            pump_statuses = selected_data.get('pump_statuses', {})
                            active_pumps = selected_data.get('active_pumps', 0)
                            total_pumps = selected_data.get('total_pumps', 0)
                            
                            if pump_statuses:
                                pump_cols = st.columns(len(pump_statuses))
                                for i, (pump_name, is_active) in enumerate(pump_statuses.items()):
                                    with pump_cols[i]:
                                        pump_display_name = pump_name.replace('pump_', '펌프 ').upper()
                                        if is_active:
                                            st.success(f"🟢 {pump_display_name}", icon="⚡")
                                        else:
                                            st.info(f"⚪ {pump_display_name}", icon="⏸️")
                            
                            # 요약 정보
                            st.markdown(f"**📊 요약:** {active_pumps}/{total_pumps} 펌프 가동 중")
                        else:
                            st.warning("선택된 배수지 데이터를 찾을 수 없습니다.")
                    else:
                        st.error("📊 synergy 데이터베이스의 water 테이블에 데이터가 없습니다.")
                        st.info("💡 데이터베이스에 수위 데이터를 추가한 후 새로고침해주세요.")
                        
                        # 개발/테스트 편의를 위한 샘플 데이터 생성 버튼 (선택적)
                        if st.button("🔧 테스트용 샘플 데이터 생성", key="create_sample_data"):
                            try:
                                sample_result = water_level_monitoring_tool(action='add_sample_data')
                                if sample_result.get('success'):
                                    st.success("✅ 테스트용 샘플 데이터 생성 완료!")
                                    st.rerun()
                                else:
                                    st.error(f"샘플 데이터 생성 실패: {sample_result.get('error')}")
                            except Exception as e:
                                st.error(f"샘플 데이터 생성 오류: {str(e)}")
                        
                except Exception as e:
                    logger.error(f"수위 모니터링 오류: {str(e)}")
                    st.error(f"모니터링 시스템 오류: {str(e)}")
                
                # 새로고침 버튼 (실제 데이터베이스 재조회)
                if st.button("🔄 새로고침", use_container_width=True, key="refresh_water"):
                    st.rerun()
                    
                # 그래프 생성 버튼 (시간 범위 표시 포함)
                if st.button("📊 24시간 그래프", use_container_width=True, key="show_graph"):
                    try:
                        graph_result = water_level_monitoring_tool(action='generate_graph', hours=24)
                        if graph_result.get('success'):
                            time_range = graph_result.get('time_range_display', '24시간')
                            st.success(f"📊 그래프 생성 완료!\n📅 시간 범위: {time_range}")
                            if 'image_base64' in graph_result:
                                import base64
                                image_data = base64.b64decode(graph_result['image_base64'])
                                st.image(image_data, 
                                        caption=f"📊 배수지 수위 변화 ({time_range})", 
                                        use_column_width=True)
                        else:
                            st.error(f"그래프 생성 실패: {graph_result.get('error')}")
                    except Exception as e:
                        st.error(f"그래프 생성 오류: {str(e)}")
                        
            else:
                st.info("시스템 초기화 후 표시됩니다.")

        with st.container(border=True):
            st.subheader("📤 파일 업로드")
            if is_system_initialized:
                uploaded_file = st.file_uploader("DB에 저장할 파일 선택", label_visibility="collapsed", disabled=not is_system_initialized)
                if uploaded_file:
                    if st.button("업로드"):
                        with st.spinner(f"'{uploaded_file.name}' 업로드 중..."):
                            storage = st.session_state.get('storage')
                            if storage:
                                file_data = uploaded_file.getvalue()
                                file_id = storage.save_file(file_data, uploaded_file.name, metadata={"source": "streamlit_upload"})
                                if file_id:
                                    st.success(f"업로드 완료! (ID: {file_id})")
                                    # 파일 목록 즉시 갱신을 위해 세션 상태 초기화
                                    if 'postgres_files' in st.session_state:
                                        del st.session_state['postgres_files']
                                    st.rerun()
                                else:
                                    st.error("파일 업로드 실패.")
                            else:
                                st.error("스토리지 시스템이 초기화되지 않았습니다.")
            else:
                st.info("시스템 초기화 후 파일 업로드가 가능합니다.")

        with st.container(border=True):
            st.subheader("📂 파일 목록")
            if is_system_initialized:
                # 세션 상태에 파일 목록 캐싱
                if 'postgres_files' not in st.session_state:
                    storage = st.session_state.get('storage')
                    if storage:
                        st.session_state.postgres_files = storage.list_files()
                    else:
                        st.session_state.postgres_files = []
                
                file_list = st.session_state.postgres_files
                
                if not file_list:
                    st.write("업로드된 파일이 없습니다.")
                else:
                    for idx, file_info in enumerate(file_list):
                        file_id = file_info.get('_id')
                        with st.container(border=True):
                            st.markdown(f"**📄 {file_info.get('filename', 'N/A')}**")
                            size_mb = file_info.get('length', 0) / (1024*1024)
                            st.caption(f"크기: {size_mb:.2f} MB")
                            
                            storage = st.session_state.get('storage')
                            if storage and file_id:
                                file_content = storage.get_file_content_by_id(file_id)
                                if file_content:
                                    st.download_button(
                                        label="⬇️ 다운로드",
                                        data=bytes(file_content),
                                        file_name=file_info.get('filename'),
                                        key=f"download_{idx}_{file_id}",
                                        use_container_width=True
                                    )
            else:
                st.info("시스템 초기화 후 파일 목록이 표시됩니다.")


if __name__ == "__main__":
    # 초기 메시지 설정
    if len(st.session_state.messages) == 0:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "안녕하세요! 좌측의 **🔄 시스템 초기화**를 먼저 눌러주세요.",
            "timestamp": datetime.now().strftime("%H:%M")
        })
    main()