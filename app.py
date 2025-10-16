# app.py - Streamlit 앱

import streamlit as st
import os
import time
import base64
import threading
import asyncio
from datetime import datetime
from models.lm_studio import LMStudioClient
from core.orchestrator import Orchestrator
from utils.logger import setup_logger
from utils.helpers import clean_ai_response
from config import print_config, DEBUG_MODE, ENABLED_TOOLS
from storage.postgresql_storage import PostgreSQLStorage
from tools.water_level_monitoring_tool import water_level_monitoring_tool
from utils.state_manager import get_state_manager, sync_automation_status

# 로거 설정
logger = setup_logger(__name__)

# 대시보드 세션 초기화 함수
def init_dashboard_session():
    """대시보드 세션 상태 초기화 (상태 유지 포함)"""
    pass

# --- 세션 상태 초기화 및 글로벌 상태 동기화 ---
# 글로벌 상태 관리자 인스턴스
state_manager = get_state_manager()

# 글로벌 상태를 먼저 로드하고 세션에 동기화 (최초 1회만)
if 'initial_sync_done' not in st.session_state:
    state_manager.sync_to_streamlit()
    st.session_state.initial_sync_done = True

# 세션 상태 기본값 설정 (없는 것들만)
if 'messages' not in st.session_state:
    st.session_state.messages = []
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
if 'page' not in st.session_state:
    st.session_state.page = "main"
if 'autonomous_notifications' not in st.session_state:
    st.session_state.autonomous_notifications = []
if 'pending_approvals' not in st.session_state:
    st.session_state.pending_approvals = []
if 'monitoring_thread' not in st.session_state:
    st.session_state.monitoring_thread = None
if 'autonomous_agent' not in st.session_state:
    st.session_state.autonomous_agent = None

# 중요한 상태들은 글로벌 상태 우선, 없으면 기본값
if 'automation_status' not in st.session_state:
    st.session_state.automation_status = False
if 'autonomous_monitoring' not in st.session_state:
    st.session_state.autonomous_monitoring = False
if 'system_initialized' not in st.session_state:
    st.session_state.system_initialized = False
if 'simulation_mode' not in st.session_state:
    st.session_state.simulation_mode = True

def start_autonomous_monitoring():
    """백그라운드 자율 모니터링 시작"""
    if not st.session_state.get('autonomous_agent'):
        return False
    
    if st.session_state.get('monitoring_thread') and st.session_state.monitoring_thread.is_alive():
        st.session_state.autonomous_monitoring = True  # 상태 동기화
        return True  # 이미 실행 중
    
    def monitoring_loop():
        """백그라운드 모니터링 루프"""
        try:
            # 세션 상태에서 autonomous_agent 안전하게 가져오기
            autonomous_agent = st.session_state.get('autonomous_agent')
            if not autonomous_agent:
                logger.error("autonomous_agent가 세션 상태에 없습니다")
                return
            
            # 새 이벤트 루프 생성 (스레드용)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(autonomous_agent.start_monitoring())
            except Exception as e:
                logger.error(f"자율 모니터링 오류: {e}")
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"모니터링 루프 초기화 오류: {e}")
    
    # 백그라운드 스레드에서 모니터링 시작
    thread = threading.Thread(target=monitoring_loop, daemon=True)
    thread.start()
    
    st.session_state.monitoring_thread = thread
    st.session_state.autonomous_monitoring = True
    
    # 자율 에이전트의 내부 상태도 업데이트
    autonomous_agent = st.session_state.autonomous_agent
    if hasattr(autonomous_agent, 'is_monitoring'):
        autonomous_agent.is_monitoring = True
    
    return True

def stop_autonomous_monitoring():
    """백그라운드 자율 모니터링 중지"""
    if st.session_state.get('autonomous_agent'):
        autonomous_agent = st.session_state.autonomous_agent
        autonomous_agent.stop_monitoring()
        
        # 자율 에이전트의 내부 상태도 업데이트
        if hasattr(autonomous_agent, 'is_monitoring'):
            autonomous_agent.is_monitoring = False
    
    st.session_state.autonomous_monitoring = False
    
    # 스레드는 daemon이므로 자동으로 종료됨
    if st.session_state.get('monitoring_thread'):
        st.session_state.monitoring_thread = None

def restore_automation_state():
    """새로고침 후 자동화 상태 복구"""
    try:
        from tools.automation_control_tool import automation_control_tool
        status_result = automation_control_tool(action='status')
        
        if status_result.get('success'):
            # 실제 자동화가 실행 중인지 확인
            is_running = status_result.get('is_running', False)
            if is_running:
                st.session_state.automation_status = True
                logger.info("새로고침 후 자동화 상태 복구: 활성")
                
                # 자율 모니터링도 재시작 시도 (이미 실행 중이면 그대로 유지)
                autonomous_success = False
                if st.session_state.get('autonomous_agent'):
                    if not st.session_state.get('autonomous_monitoring', False):
                        if start_autonomous_monitoring():
                            autonomous_success = True
                            st.session_state.autonomous_monitoring = True
                            logger.info("새로고침 후 자율 모니터링 재시작 성공")
                        else:
                            logger.warning("새로고침 후 자율 모니터링 재시작 실패")
                    else:
                        autonomous_success = True  # 이미 실행 중
                        
                # 글로벌 상태에 동기화
                sync_automation_status(True, autonomous_success)
                return True
            else:
                st.session_state.automation_status = False
                st.session_state.autonomous_monitoring = False
                
                # 글로벌 상태에 동기화
                sync_automation_status(False, False)
                st.session_state.autonomous_monitoring = False
                logger.info("새로고침 후 자동화 상태 복구: 비활성")
                return True
    except Exception as e:
        logger.warning(f"자동화 상태 복구 실패: {e}")
        return False

def initialize_system():
    """AgenticRAG 시스템 초기화"""
    with st.spinner("시스템 초기화 중..."):
        try:
            # LM Studio 클라이언트 초기화
            lm_studio_client = LMStudioClient()
            
            # 오케스트레이터 초기화
            orchestrator = Orchestrator(lm_studio_client)
            
            # 자율 에이전트 초기화
            from services.autonomous_agent import AutonomousAgent
            autonomous_agent = AutonomousAgent(lm_studio_client)
            
            # 세션 상태에 저장
            st.session_state.lm_studio_client = lm_studio_client
            st.session_state.orchestrator = orchestrator
            st.session_state.autonomous_agent = autonomous_agent
            st.session_state.system_initialized = True
            
            # 글로벌 상태에도 시스템 초기화 상태 업데이트
            state_manager.update_system_status(True, True)
            
            # 상태를 Streamlit에서 글로벌로 동기화
            state_manager.sync_from_streamlit()
            
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
                            else:
                                logger.warning("아두이노 자동 연결 실패")
                        elif found_port == "SIMULATION":
                            logger.info("아두이노 시뮬레이션 모드")
                            arduino_tool.arduino_port = "SIMULATION"
                        else:
                            logger.warning("아두이노 포트를 찾을 수 없음")
                    except Exception as e:
                        logger.error(f"아두이노 자동 연결 중 오류: {e}")
                
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
            
            # 자동화 상태 복구 (새로고침 후)
            try:
                restore_automation_state()
                logger.info(f"자동화 상태 복구 완료: automation_status={st.session_state.get('automation_status')}, autonomous_monitoring={st.session_state.get('autonomous_monitoring')}")
            except Exception as e:
                logger.warning(f"자동화 상태 복구 중 오류 (무시됨): {e}")
            
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

def render_pdf_download_button(content: str, key_prefix: str = "pdf"):
    """PDF 다운로드 버튼 렌더링 (재사용 가능)"""
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        from utils.pdf_generator import MarkdownToPDFConverter, is_pdf_available

        if is_pdf_available():
            pdf_converter = MarkdownToPDFConverter()
            filename = f"agentic_rag_report_{timestamp_str}.pdf"
            pdf_bytes = pdf_converter.convert_markdown_to_pdf(content, filename)
            st.download_button(
                label="📄 PDF 다운로드",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf",
                key=f"{key_prefix}_{timestamp_str}"
            )
        else:
            filename = f"agentic_rag_report_{timestamp_str}.txt"
            text_bytes = content.encode('utf-8')
            st.download_button(
                label="📝 텍스트 저장",
                data=text_bytes,
                file_name=filename,
                mime="text/plain",
                key=f"{key_prefix}_txt_{timestamp_str}"
            )
    except Exception as e:
        logger.error(f"다운로드 버튼 생성 오류: {str(e)}")

def render_tool_results(tool_results: dict):
    """도구 실행 결과 표시 (재사용 가능)"""
    if not tool_results:
        return

    with st.expander("🔍 도구 실행 결과", expanded=False):
        for tool_name, result in tool_results.items():
            st.subheader(f"🛠️ {tool_name}")
            if isinstance(result, dict):
                if 'success' in result:
                    status = "✅ 성공" if result.get('success') else "❌ 실패"
                    st.markdown(f"**상태:** {status}")
                if 'message' in result:
                    st.markdown(f"**결과:** {result['message']}")
                if 'temperature_c' in result:
                    st.markdown(f"**🌡️ 기온:** {result['temperature_c']}°C")
                if 'humidity' in result:
                    st.markdown(f"**💧 습도:** {result['humidity']}%")
                with st.expander("전체 데이터", expanded=False):
                    st.json(result)
            else:
                st.write(str(result))

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

def render_autonomous_agent_page():
    """자율 에이전트 페이지 렌더링"""
    st.set_page_config(
        page_title="🔔 자율 에이전트 - Synergy ChatBot",
        page_icon="🤖",
        layout="wide"
    )
    
    # 메인으로 돌아가기 버튼
    if st.button("🏠 메인 대시보드로 돌아가기"):
        st.session_state.page = "main"
        st.rerun()
    
    st.title("🤖 자율 에이전트 시스템")
    st.markdown("---")
    
    # 자율 에이전트가 초기화되어 있는지 확인
    if 'autonomous_agent' not in st.session_state or st.session_state.autonomous_agent is None:
        st.error("자율 에이전트가 초기화되지 않았습니다.")
        st.info("메인 페이지에서 '🔄 시스템 초기화'를 먼저 실행해주세요.")
        return
    
    # 자율 에이전트 대시보드 렌더링
    autonomous_agent = st.session_state.autonomous_agent
    
    try:
        from ui.notification_system import render_autonomous_dashboard
        render_autonomous_dashboard(autonomous_agent)
    except ImportError as e:
        st.error(f"자율 에이전트 UI 모듈 로드 실패: {e}")
        st.info("기본 자율 에이전트 제어 패널을 표시합니다.")
        
        # 기본 제어 패널
        render_basic_autonomous_controls(autonomous_agent)

def render_basic_autonomous_controls(autonomous_agent):
    """기본 자율 에이전트 제어 패널"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🤖 시스템 상태")
        status = autonomous_agent.get_system_status()
        
        st.metric("모니터링 상태", "🟢 실행 중" if status["is_monitoring"] else "🔴 중지됨")
        st.metric("모니터링 주기", f"{status['monitoring_interval']}초")
        st.metric("대기 중인 승인", status["pending_approvals_count"])
        st.metric("총 실행된 조치", status["total_actions_executed"])
        
        # 모니터링 제어
        if not status["is_monitoring"]:
            if st.button("▶️ 자율 모니터링 시작"):
                try:
                    import asyncio
                    asyncio.create_task(autonomous_agent.start_monitoring())
                    st.success("자율 모니터링을 시작했습니다!")
                    st.session_state.autonomous_monitoring = True
                    st.rerun()
                except Exception as e:
                    st.error(f"모니터링 시작 실패: {e}")
        else:
            if st.button("⏸️ 자율 모니터링 중지"):
                autonomous_agent.stop_monitoring()
                st.info("자율 모니터링을 중지했습니다.")
                st.session_state.autonomous_monitoring = False
                st.rerun()
    
    with col2:
        st.subheader("🔔 실시간 알림")
        
        # 최근 알림 표시
        notifications = autonomous_agent.get_notifications(limit=5)
        
        if notifications:
            for notification in notifications:
                with st.container():
                    level_icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨", "emergency": "🆘"}
                    icon = level_icon.get(notification.level.value, "📢")
                    
                    st.markdown(f"**{icon} {notification.title}**")
                    st.caption(f"{notification.timestamp.strftime('%H:%M:%S')} - {notification.level.value.upper()}")
                    st.text(notification.message)
                    
                    # 액션이 필요한 경우 승인 버튼
                    if notification.action_required and notification.action_id:
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ 승인", key=f"approve_{notification.action_id}"):
                                if autonomous_agent.approve_action(notification.action_id):
                                    st.success("조치가 승인되어 실행되었습니다!")
                                    st.rerun()
                        with col2:
                            if st.button("❌ 거부", key=f"reject_{notification.action_id}"):
                                if autonomous_agent.reject_action(notification.action_id):
                                    st.info("조치가 거부되었습니다.")
                                    st.rerun()
                    
                    st.divider()
        else:
            st.info("현재 알림이 없습니다.")
        
        # 대기 중인 승인
        st.subheader("⏳ 승인 대기")
        pending = autonomous_agent.get_pending_approvals()
        
        if pending:
            for approval in pending:
                with st.expander(f"🔄 {approval['description']}", expanded=True):
                    st.write(f"**상황:** {approval['situation']}")
                    st.write(f"**예상 효과:** {approval['estimated_impact']}")
                    st.write(f"**요청 시간:** {approval['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ 승인", key=f"pending_approve_{approval['action_id']}"):
                            if autonomous_agent.approve_action(approval['action_id']):
                                st.success("승인 완료!")
                                st.rerun()
                    with col2:
                        if st.button("❌ 거부", key=f"pending_reject_{approval['action_id']}"):
                            if autonomous_agent.reject_action(approval['action_id']):
                                st.info("거부 완료")
                                st.rerun()
        else:
            st.info("승인 대기 중인 조치가 없습니다.")

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
    
    if st.session_state.page == "automation_dashboard":
        try:
            from automation_dashboard import SimpleAutomationDashboard
            automation_dashboard = SimpleAutomationDashboard()
            automation_dashboard.run()
            return
        except ImportError as e:
            st.error(f"자동화 대시보드 모듈 로드 실패: {e}")
            st.session_state.page = "main"
    
    if st.session_state.page == "autonomous_agent":
        render_autonomous_agent_page()
        return
            
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
    
    /* === 채팅 메시지 기본 스타일 (명확한 구분) === */
    .stChatMessage {
        border-radius: 12px !important;
        padding: 16px 20px !important;
        margin: 12px 0 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06) !important;
        transition: all 0.2s ease !important;
        position: relative !important;
    }

    .stChatMessage:hover {
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1) !important;
    }

    /* 사용자 메시지 - 주황색 강조 */
    .stChatMessage[data-testid="chat-message-user"],
    .stChatMessage[data-testid*="user"] {
        background: #fffbf0 !important;
        border: 1px solid #fed7aa !important;
        border-left: 4px solid #f59e0b !important;
    }

    .stChatMessage[data-testid="chat-message-user"]:hover,
    .stChatMessage[data-testid*="user"]:hover {
        background: #fff7e6 !important;
        border-left-color: #d97706 !important;
    }

    /* AI 메시지 - 파란색 강조 */
    .stChatMessage[data-testid="chat-message-assistant"],
    .stChatMessage[data-testid*="assistant"] {
        background: #f0f4ff !important;
        border: 1px solid #c7d2fe !important;
        border-left: 4px solid #667eea !important;
    }

    .stChatMessage[data-testid="chat-message-assistant"]:hover,
    .stChatMessage[data-testid*="assistant"]:hover {
        background: #e0e7ff !important;
        border-left-color: #5568d3 !important;
    }

    /* 아바타 아이콘 스타일 */
    .stChatMessage [data-testid="chatAvatarIcon-assistant"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4) !important;
    }

    .stChatMessage [data-testid="chatAvatarIcon-user"] {
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%) !important;
        box-shadow: 0 4px 12px rgba(251, 191, 36, 0.4) !important;
    }

    /* 테이블 스타일 */
    .stChatMessage .stMarkdown table {
        width: 100% !important;
        border-collapse: collapse !important;
        margin: 20px 0 !important;
        border: 1px solid #e5e7eb !important;
        border-radius: 8px !important;
        overflow: hidden !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
    }

    .stChatMessage .stMarkdown th {
        background: #f9fafb !important;
        color: #111827 !important;
        padding: 14px 18px !important;
        text-align: left !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        border-bottom: 2px solid #e5e7eb !important;
    }

    .stChatMessage .stMarkdown td {
        padding: 14px 18px !important;
        border-bottom: 1px solid #f3f4f6 !important;
        font-size: 14px !important;
        color: #374151 !important;
        background: white !important;
    }

    .stChatMessage .stMarkdown tr:last-child td {
        border-bottom: none !important;
    }

    .stChatMessage .stMarkdown tr:hover td {
        background: #f9fafb !important;
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

    /* 3단 레이아웃 컬럼 정렬 - 강력한 상단 정렬 */
    [data-testid="column"] {
        vertical-align: top !important;
        align-items: flex-start !important;
        display: flex !important;
        flex-direction: column !important;
    }

    /* 컬럼 간격 조정 */
    .main .block-container [data-testid="stHorizontalBlock"] {
        gap: 1rem !important;
        align-items: flex-start !important;
    }

    /* 컬럼 내부 요소들 상단 정렬 */
    [data-testid="column"] > div {
        display: flex !important;
        flex-direction: column !important;
        align-items: stretch !important;
        padding-top: 0 !important;
        margin-top: 0 !important;
    }

    /* 모든 컬럼의 첫 번째 element-container 상단 여백 제거 */
    [data-testid="column"] > div > div[data-testid="element-container"]:first-child {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    /* 모든 컨테이너 통일 스타일 및 간격 */
    [data-testid="stVerticalBlock"] > div > div[data-testid="stVerticalBlock"] {
        gap: 0.5rem !important;
    }

    /* border=True 컨테이너들의 상단 정렬 강제 */
    [data-testid="column"] [data-testid="stVerticalBlock"]:has(> div[style*="border"]) {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    /* 컨테이너 border 통일 및 정렬 */
    div[data-testid="stVerticalBlock"] > div > div[data-testid="element-container"] > div > div {
        border-radius: 8px !important;
    }

    /* 모든 컬럼 내부의 컨테이너를 같은 위치에서 시작 */
    [data-testid="column"] > div[data-testid="stVerticalBlock"] > div:first-child {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    /* 모든 border=True 컨테이너를 같은 높이에서 시작 */
    [data-testid="column"] > div > div:first-child [data-testid="stVerticalBlock"] {
        margin-top: 0 !important;
    }

    /* element-container 내부 여백 제거 */
    [data-testid="column"] > div > div[data-testid="element-container"]:first-of-type {
        padding-top: 0 !important;
    }

    /* === 컬럼 정렬 개선 === */
    /* 모든 컬럼을 상단 정렬 */
    section[data-testid="stHorizontalBlock"] {
        align-items: flex-start !important;
    }

    /* 모든 컬럼의 직접 자식 요소 상단 여백 제거 */
    [data-testid="column"] > div[data-testid="stVerticalBlock"] {
        display: flex !important;
        flex-direction: column !important;
        align-items: stretch !important;
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    /* 컬럼 내부의 모든 첫 번째 요소 정렬 */
    [data-testid="column"] > div[data-testid="stVerticalBlock"] > div:first-child,
    [data-testid="column"] > div > div:first-child,
    section[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div > div:first-child {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    /* === 채팅 입력창 스타일 통합 개선 === */
    /* 중앙 컬럼 전체를 하나의 통합된 채팅 영역으로 표시 */
    [data-testid="column"]:nth-child(2) > div[data-testid="stVerticalBlock"] {
        background: white !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
        padding: 0 !important;
    }

    /* 중앙 컬럼의 채팅 컨테이너 - 상단 모서리만 둥글게 */
    [data-testid="column"]:nth-child(2) [data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 8px 8px 0 0 !important;
        border-bottom: none !important;
        margin-bottom: 0 !important;
        max-height: calc(100vh - 280px) !important;
        overflow-y: auto !important;
        padding: 1rem !important;
        border: 1px solid #e5e7eb !important;
    }

    /* 채팅 입력창 - 컨테이너와 완벽하게 통합 */
    .stChatInput {
        margin: 0 !important;
        padding: 0 !important;
        background: white !important;
    }

    /* 중앙 컬럼의 채팅 입력창 - 하단 모서리만 둥글게 */
    [data-testid="column"]:nth-child(2) .stChatInput {
        border-radius: 0 0 8px 8px !important;
        margin: 0 !important;
        padding: 12px 16px !important;
        border: 1px solid #e5e7eb !important;
        border-top: none !important;
    }

    /* 입력창 내부 요소 스타일 개선 */
    [data-testid="column"]:nth-child(2) .stChatInput input {
        border: none !important;
        box-shadow: none !important;
    }

    /* 입력창 전송 버튼 스타일 */
    [data-testid="column"]:nth-child(2) .stChatInput button {
        background: #667eea !important;
        border-radius: 6px !important;
    }

    [data-testid="column"]:nth-child(2) .stChatInput button:hover {
        background: #5568d3 !important;
    }

    /* 채팅 컨테이너 스크롤 부드럽게 */
    [data-testid="stVerticalBlock"]:has(.stChatMessage) {
        scroll-behavior: smooth !important;
        overflow-y: auto !important;
    }

    /* 메시지 추가 시 애니메이션 */
    .stChatMessage {
        animation: fadeInUp 0.3s ease-in-out !important;
    }

    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* 채팅 컨테이너 최대 높이 설정 */
    [data-testid="stVerticalBlock"] > div[style*="border"] {
        max-height: calc(100vh - 250px) !important;
        overflow-y: auto !important;
    }
    </style>
    <script>
    // 컬럼 정렬 강제 적용 (개선된 버전)
    function alignColumns() {
        // 모든 컬럼을 상단 정렬
        const horizontalBlock = document.querySelector('[data-testid="stHorizontalBlock"]');
        if (horizontalBlock) {
            horizontalBlock.style.alignItems = 'flex-start';
        }

        // 각 컬럼의 첫 번째 요소들 정렬
        const columns = document.querySelectorAll('[data-testid="column"]');
        columns.forEach(col => {
            // 컬럼의 직접 자식들 정렬
            const verticalBlock = col.querySelector('[data-testid="stVerticalBlock"]');
            if (verticalBlock) {
                verticalBlock.style.marginTop = '0';
                verticalBlock.style.paddingTop = '0';

                // 첫 번째 자식 요소들 정렬
                const firstChild = verticalBlock.querySelector('> div:first-child');
                if (firstChild) {
                    firstChild.style.marginTop = '0';
                    firstChild.style.paddingTop = '0';
                }
            }
        });
    }

    // 페이지 로드 시 실행
    setTimeout(alignColumns, 100);

    // Streamlit 리렌더링 감지 및 재정렬
    const observer = new MutationObserver(alignColumns);
    observer.observe(document.body, { childList: true, subtree: true });
    </script>
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

    # ===== 메시지 렌더링 헬퍼 함수들 (전역으로 정의) =====
    def render_message_styles():
        """스트리밍 포맷 기준 통일 스타일 - 깔끔한 하얀 배경"""
        st.markdown("""
        <style>
        /* 채팅 컨테이너 배경 - 하얀색 */
        [data-testid="stVerticalBlock"] > div:has(.stChatMessage) {
            background: white !important;
        }

        .stChatMessage [data-testid="chatAvatarIcon-assistant"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4) !important;
        }

        .stChatMessage [data-testid="chatAvatarIcon-user"] {
            background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%) !important;
            box-shadow: 0 4px 12px rgba(251, 191, 36, 0.4) !important;
        }

        /* 메시지 내용 스타일 향상 */
        .stChatMessage .stMarkdown {
            font-size: 15px !important;
            line-height: 1.7 !important;
            color: #1f2937 !important;
        }

        .stChatMessage .stMarkdown p {
            margin: 14px 0 !important;
            font-size: 15px !important;
            line-height: 1.7 !important;
            color: #374151 !important;
        }

        .stChatMessage .stMarkdown h1,
        .stChatMessage .stMarkdown h2 {
            font-size: 22px !important;
            margin: 24px 0 16px 0 !important;
            color: #111827 !important;
            border-bottom: 2px solid #e5e7eb !important;
            padding-bottom: 10px !important;
            font-weight: 700 !important;
        }

        .stChatMessage .stMarkdown h3 {
            font-size: 18px !important;
            margin: 20px 0 12px 0 !important;
            color: #1f2937 !important;
            font-weight: 600 !important;
        }

        .stChatMessage .stMarkdown h4,
        .stChatMessage .stMarkdown h5,
        .stChatMessage .stMarkdown h6 {
            font-size: 16px !important;
            margin: 16px 0 10px 0 !important;
            color: #374151 !important;
            font-weight: 600 !important;
        }

        .stChatMessage .stMarkdown ul,
        .stChatMessage .stMarkdown ol {
            margin: 14px 0 !important;
            padding-left: 28px !important;
        }

        .stChatMessage .stMarkdown li {
            font-size: 15px !important;
            line-height: 1.7 !important;
            margin: 8px 0 !important;
            color: #374151 !important;
        }

        .stChatMessage .stMarkdown li::marker {
            color: #9ca3af !important;
        }

        /* 테이블 스타일 */
        .stChatMessage .stMarkdown table {
            width: 100% !important;
            border-collapse: collapse !important;
            margin: 20px 0 !important;
            border: 1px solid #e5e7eb !important;
            border-radius: 8px !important;
            overflow: hidden !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
        }

        .stChatMessage .stMarkdown th {
            background: #f9fafb !important;
            color: #111827 !important;
            padding: 14px 18px !important;
            text-align: left !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            border-bottom: 2px solid #e5e7eb !important;
        }

        .stChatMessage .stMarkdown td {
            padding: 14px 18px !important;
            border-bottom: 1px solid #f3f4f6 !important;
            font-size: 14px !important;
            color: #374151 !important;
            background: white !important;
        }

        .stChatMessage .stMarkdown tr:last-child td {
            border-bottom: none !important;
        }

        .stChatMessage .stMarkdown tr:hover td {
            background: #f9fafb !important;
        }

        /* 인라인 코드 스타일 */
        .stChatMessage .stMarkdown code {
            background: #f3f4f6 !important;
            padding: 3px 7px !important;
            border-radius: 6px !important;
            font-size: 14px !important;
            color: #dc2626 !important;
            font-family: 'SF Mono', 'Monaco', 'Menlo', monospace !important;
            font-weight: 500 !important;
        }

        /* 코드 블록 스타일 */
        .stChatMessage .stMarkdown pre {
            background: #1f2937 !important;
            padding: 18px !important;
            border-radius: 10px !important;
            overflow-x: auto !important;
            margin: 18px 0 !important;
            border: 1px solid #374151 !important;
        }

        .stChatMessage .stMarkdown pre code {
            background: transparent !important;
            color: #f3f4f6 !important;
            padding: 0 !important;
            font-size: 14px !important;
        }

        /* 텍스트 강조 스타일 */
        .stChatMessage .stMarkdown strong {
            font-weight: 700 !important;
            color: #111827 !important;
        }

        .stChatMessage .stMarkdown em {
            font-style: italic !important;
            color: #6b7280 !important;
        }

        /* 구분선 스타일 */
        .stChatMessage .stMarkdown hr {
            margin: 28px 0 !important;
            border: none !important;
            height: 1px !important;
            background: #e5e7eb !important;
        }

        /* 인용구 스타일 */
        .stChatMessage .stMarkdown blockquote {
            border-left: 4px solid #667eea !important;
            padding: 12px 20px !important;
            margin: 18px 0 !important;
            background: #f9fafb !important;
            color: #4b5563 !important;
            border-radius: 0 8px 8px 0 !important;
        }

        /* 다운로드 버튼 스타일 */
        .stChatMessage .stDownloadButton button {
            background: #667eea !important;
            color: white !important;
            border: none !important;
            padding: 10px 20px !important;
            border-radius: 8px !important;
            font-size: 14px !important;
            font-weight: 600 !important;
            transition: all 0.2s ease !important;
        }

        .stChatMessage .stDownloadButton button:hover {
            background: #5568d3 !important;
            transform: translateY(-1px) !important;
        }

        /* 상태 표시기 (st.status) 스타일 */
        .stChatMessage .stStatus {
            background: #f9fafb !important;
            border: 1px solid #e5e7eb !important;
            border-radius: 8px !important;
            margin-bottom: 14px !important;
        }

        .stChatMessage .stStatus > details > summary {
            font-size: 14px !important;
            color: #667eea !important;
            font-weight: 600 !important;
            padding: 10px !important;
        }

        /* expander 스타일 개선 */
        .stChatMessage .stExpander {
            border: 1px solid #e5e7eb !important;
            border-radius: 8px !important;
            background: #f9fafb !important;
            margin: 12px 0 !important;
        }

        .stChatMessage .stExpander > details > summary {
            font-size: 14px !important;
            font-weight: 600 !important;
            color: #4b5563 !important;
            padding: 12px !important;
        }

        /* caption (타임스탬프) 스타일 */
        .stChatMessage [data-testid="stCaptionContainer"] {
            color: #9ca3af !important;
            font-size: 13px !important;
            margin-top: 12px !important;
            font-weight: 500 !important;
        }
        </style>
        """, unsafe_allow_html=True)

    def render_user_message(message):
        """사용자 메시지 렌더링 - st.chat_message 사용 (대화창 스타일)"""
        with st.chat_message("user", avatar="👤"):
            st.markdown(message["content"])

            if message.get("timestamp"):
                st.caption(f"🕐 {message['timestamp']}")

    def render_assistant_message(message):
        """어시스턴트 메시지 렌더링 - st.chat_message 사용 (스트리밍과 동일)"""
        with st.chat_message("assistant", avatar="🤖"):
            # 메시지 내용 표시 (마크다운 형식, 일관된 렌더링)
            content = message["content"]

            # 메시지 내용을 그대로 표시 - write_stream()과 동일한 방식으로 렌더링
            # st.write()는 마크다운을 자동으로 렌더링하며 write_stream()과 호환됩니다
            st.write(content)

            # 타임스탬프와 처리시간
            timestamp_parts = []
            if message.get("timestamp"):
                timestamp_parts.append(f"🕐 {message['timestamp']}")
            if message.get("processing_time"):
                timestamp_parts.append(f"⚡ {message['processing_time']}")

            if timestamp_parts:
                st.caption(" | ".join(timestamp_parts))

            # PDF 다운로드 버튼 (헬퍼 함수 사용)
            render_pdf_download_button(message["content"], key_prefix=f"pdf_btn_{id(message)}")

            # 도구 실행 결과 (헬퍼 함수 사용)
            if "tool_results" in message:
                render_tool_results(message.get("tool_results", {}))

    # --- 3단 레이아웃 정의 전 초기화 처리 ---
    # 글로벌 상태와 세션 상태 동기화 (UI 없이 백그라운드에서 실행)
    state_manager = get_state_manager()
    state = state_manager.load_state()

    # 글로벌 상태에서 초기화 상태 확인
    if state.get('system_initialized', False):
        st.session_state.system_initialized = True

    is_system_initialized = st.session_state.get('system_initialized', False)

    # 시스템이 초기화되지 않았고, orchestrator가 없으면 자동 초기화
    auto_init_failed = False
    auto_init_error = None
    if not is_system_initialized and 'orchestrator' not in st.session_state:
        try:
            if initialize_system():
                is_system_initialized = True
                st.rerun()
            else:
                auto_init_failed = True
        except Exception as e:
            logger.error(f"시스템 자동 초기화 오류: {e}")
            auto_init_error = str(e)

    # --- 3단 레이아웃 정의 (비율 조정) ---
    left_col, center_col, right_col = st.columns([0.8, 2.4, 1])

    # --- 왼쪽 컬럼: 제어판 ---
    with left_col:
        with st.container(border=True):
            # 자동 초기화 실패 시 경고 표시
            if auto_init_failed:
                st.warning("⚠️ 시스템 자동 초기화 실패. 수동으로 초기화해주세요.")
            elif auto_init_error:
                st.warning("⚠️ 시스템 자동 초기화 중 오류 발생")
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
            
            if st.button("🤖 통합 자동화 시스템", use_container_width=True, disabled=not is_system_initialized, help="자동화 시스템과 자율 에이전트가 통합된 대시보드"):
                st.session_state.page = "automation_dashboard"
                st.rerun()

            # 자동화 제어 버튼들 (상태 기반 개선)
            col1, col2 = st.columns(2)
            
            # 현재 자동화 상태 확인
            automation_active = st.session_state.get('automation_status', False)
            
            with col1:
                # 자동화가 이미 시작된 경우 버튼 비활성화
                button_disabled = not is_system_initialized or automation_active
                button_text = "🤖 자동화 시작됨" if automation_active else "🤖 자동화 시작"
                button_help = "이미 자동화가 실행 중입니다" if automation_active else "자동화 시스템을 시작합니다"
                
                if st.button(button_text, use_container_width=True, disabled=button_disabled, help=button_help):
                    with st.spinner("자동화 시스템 시작 중..."):
                        try:
                            from tools.automation_control_tool import automation_control_tool
                            
                            result = automation_control_tool(action='start')
                            
                            if result.get('success'):
                                st.session_state.automation_status = True
                                
                                # 자율 모니터링도 함께 시작
                                autonomous_success = start_autonomous_monitoring()
                                if autonomous_success:
                                    st.session_state.autonomous_monitoring = True
                                
                                # 글로벌 상태에 동기화
                                sync_automation_status(True, autonomous_success)
                                
                                if autonomous_success:
                                    st.success("✅ 자동화 + 자율 에이전트 시작!")
                                else:
                                    st.success("✅ 자동화 시작! (자율 에이전트는 수동 시작 필요)")
                            else:
                                st.error(f"시작 실패: {result.get('error')}")
                        except Exception as e:
                            st.error(f"자동화 시작 오류: {str(e)}")
                        st.rerun()
            
            with col2:
                # 자동화가 중지된 경우 버튼 비활성화
                button_disabled = not is_system_initialized or not automation_active
                button_text = "🛑 자동화 중단" if automation_active else "🛑 중단됨"
                button_help = "자동화 시스템을 중단합니다" if automation_active else "자동화가 이미 중단되어 있습니다"
                
                if st.button(button_text, use_container_width=True, disabled=button_disabled, help=button_help):
                    with st.spinner("자동화 시스템 중단 중..."):
                        try:
                            from tools.automation_control_tool import automation_control_tool
                            result = automation_control_tool(action='stop')
                            if result.get('success'):
                                st.session_state.automation_status = False
                                st.session_state.autonomous_monitoring = False
                                
                                # 자율 모니터링도 함께 중지
                                stop_autonomous_monitoring()
                                
                                # 글로벌 상태에 동기화
                                sync_automation_status(False, False)
                                
                                st.info("🛑 자동화 + 자율 에이전트 중단")
                            else:
                                st.error(f"중단 실패: {result.get('error')}")
                        except Exception as e:
                            st.error(f"자동화 중단 오류: {str(e)}")
                        st.rerun()
            
            # 현재 상태 명확히 표시
            if is_system_initialized:
                if automation_active:
                    st.success("🟢 **자동화 시스템 활성 상태**", icon="✅")
                else:
                    st.info("⚫ **자동화 시스템 비활성 상태**", icon="⏸️")
                st.success("✅ 시스템 준비완료")
            else:
                st.error("❌ 초기화 필요")
                st.info("⚫ **자동화 시스템 비활성 상태**", icon="⏸️")

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
                st.markdown(f"""**API**: {'<span style="color: #16a34a;">✅ 연결됨</span>' if api_ok else '<span style="color: #dc2626;">❌ 연결 안됨</span>'}""", unsafe_allow_html=True)
                st.markdown(f"**아두이노**: <span style='color: {arduino_color};'>{arduino_status}</span>", unsafe_allow_html=True)

                # 통합 자동화 상태 표시 (시스템 초기화된 경우에만)
                automation_active = st.session_state.get('automation_status', False)
                autonomous_monitoring = st.session_state.get('autonomous_monitoring', False)

                # 통합 상태로 표시
                if automation_active and autonomous_monitoring:
                    st.markdown("**🤖 통합 자동화**: <span style='color: #16a34a;'>🟢 완전 활성</span>", unsafe_allow_html=True)
                elif automation_active:
                    st.markdown("**🤖 통합 자동화**: <span style='color: #f59e0b;'>🟡 부분 활성</span>", unsafe_allow_html=True)
                else:
                    st.markdown("**🤖 통합 자동화**: <span style='color: #6b7280;'>⚫ 비활성</span>", unsafe_allow_html=True)

                # 세부 상태 (간단히)
                if automation_active or autonomous_monitoring:
                    status_parts = []
                    if automation_active:
                        status_parts.append("기본 자동화")
                    if autonomous_monitoring:
                        status_parts.append("자율 에이전트")
                    st.caption(f"활성 구성요소: {', '.join(status_parts)}")

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
        with st.container(border=True):
            # 스타일 한 번만 렌더링
            render_message_styles()

            # 이전 메시지들 표시
            for i, message in enumerate(st.session_state.messages):
                # thinking 메시지는 기록에서 제외 (스트리밍 중에만 표시)
                if message.get("is_thinking", False):
                    continue

                if message["role"] == "user":
                    render_user_message(message)
                else:
                    render_assistant_message(message)

            # thinking 메시지가 있을 때 스트리밍 응답 처리 (채팅 컨테이너 안에서!)
            if (st.session_state.messages and
                st.session_state.messages[-1].get("is_thinking") and
                not st.session_state.get('processing_started', False)):

                # 처리 시작 플래그 설정 (중복 처리 방지)
                st.session_state.processing_started = True

                # 사용자 질문 가져오기
                user_prompt = st.session_state.messages[-2]["content"]

                # 시스템 초기화 확인
                if not st.session_state.get('system_initialized', False) or not st.session_state.get('orchestrator'):
                    st.error("❌ 시스템이 초기화되지 않았습니다. 좌측 사이드바에서 '🔄 시스템 초기화' 버튼을 클릭해주세요.")
                    # thinking 메시지를 에러 메시지로 교체
                    st.session_state.messages[-1] = {
                        "role": "assistant",
                        "content": "시스템이 초기화되지 않았습니다. 좌측 사이드바에서 **'🔄 시스템 초기화'** 버튼을 먼저 클릭해주세요.",
                        "timestamp": datetime.now().strftime("%H:%M")
                    }
                    st.session_state.processing_started = False
                    st.rerun()

                try:
                    # 스트리밍 응답 수집 및 실시간 표시
                    full_response = ""
                    tool_calls = None
                    tool_results = {}

                    # Streamlit의 chat_message를 사용하여 실시간 스트리밍
                    with st.chat_message("assistant", avatar="🤖"):
                        # 스트리밍 응답 생성 시작
                        start_time = time.time()

                        # 깔끔한 상태 표시
                        with st.status("🔍 질문 분석 및 답변 생성 중...", expanded=False) as status:
                            st.write("💭 질문 분석 중...")
                            stream_generator = st.session_state.orchestrator.process_query_sync(user_prompt, stream=True)
                            st.write("✨ 답변 생성 중...")
                            status.update(label="✅ 답변 생성 완료!", state="complete", expanded=False)

                        # 스트리밍 제너레이터
                        def stream_response():
                            nonlocal full_response, tool_calls, tool_results
                            for chunk in stream_generator:
                                if chunk.get("type") == "chunk":
                                    content = chunk["content"]
                                    full_response += content
                                    yield content
                                elif chunk.get("type") == "done":
                                    tool_calls = chunk.get("tool_calls")
                                    tool_results = chunk.get("tool_results", {})
                            
                            # 스트리밍 완료 후 통일된 후처리 적용
                            from utils.helpers import apply_consistent_formatting
                            full_response = apply_consistent_formatting(full_response)

                        # 실시간 스트리밍 표시
                        message_placeholder = st.empty()
                        streamed_content = message_placeholder.write_stream(stream_response())

                        # 스트리밍 완료 후 재렌더링하지 않음 - write_stream이 이미 올바르게 렌더링함
                        # message_placeholder는 그대로 유지

                        # 스트리밍 완료 후 추가 정보 표시
                        processing_time = time.time() - start_time

                        # 타임스탬프와 처리시간 표시
                        st.caption(f"🕐 {datetime.now().strftime('%H:%M')} | ⚡ {processing_time:.2f}초")

                        # PDF 다운로드 버튼 (헬퍼 함수 사용)
                        render_pdf_download_button(full_response, key_prefix="pdf_stream")

                        # 도구 실행 결과 표시 (헬퍼 함수 사용)
                        render_tool_results(tool_results)

                    # thinking 메시지를 실제 응답으로 교체 (rerun 없이)
                    # streamed_content를 사용하여 스트리밍 표시와 히스토리 저장이 동일하도록 함
                    st.session_state.messages[-1] = {
                        "role": "assistant",
                        "content": streamed_content,  # write_stream()이 반환한 실제 렌더링된 내용 사용
                        "tool_results": tool_results,
                        "timestamp": datetime.now().strftime("%H:%M"),
                        "processing_time": f"{processing_time:.2f}초",
                        "is_thinking": False
                    }

                    # 디버그 정보 업데이트
                    st.session_state.debug_info = {
                        "query": user_prompt,
                        "tool_calls": tool_calls or [],
                        "tool_results": tool_results,
                        "processing_time": f"{processing_time:.2f}초"
                    }

                    # 처리 완료 플래그 제거
                    if 'processing_started' in st.session_state:
                        del st.session_state.processing_started

                    st.toast("✅ 응답 완료!", icon="🎉")

                    # rerun 제거 - 스트리밍된 메시지를 그대로 유지

                except Exception as e:
                    # 오류 발생 시 thinking 메시지 제거하고 에러 메시지로 교체
                    logger.error(f"스트리밍 오류: {str(e)}")
                    error_message = f"❌ 오류가 발생했습니다: {str(e)}"
                    cleaned_error = clean_ai_response(error_message)
                    st.session_state.messages[-1] = {
                        "role": "assistant",
                        "content": cleaned_error,
                        "timestamp": datetime.now().strftime("%H:%M"),
                        "is_thinking": False
                    }

                    if 'processing_started' in st.session_state:
                        del st.session_state.processing_started

                    st.error(cleaned_error)
                    st.toast("❌ 오류 발생", icon="⚠️")
                    # rerun 제거 - 오류 메시지를 바로 표시

        # --- 자동 스크롤 (개선된 버전) ---
        # MutationObserver를 사용하여 채팅 내용 변경을 감지하고 자동으로 스크롤합니다.
        st.components.v1.html("""
        <script>
            // 이 스크립트는 페이지가 로드될 때 한 번만 실행되어 Observer를 설정합니다.
            const findChatContainer = () => {
                const containers = window.parent.document.querySelectorAll('div[data-testid="stVerticalBlock"]');
                for (let i = 0; i < containers.length; i++) {
                    if (containers[i].style.height === '650px') {
                        return containers[i];
                    }
                }
                return null;
            };

            const chatContainer = findChatContainer();

            if (chatContainer) {
                const observer = new MutationObserver((mutations) => {
                    // 내용 변경 시 스크롤을 맨 아래로 이동
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                });

                // 감시 시작
                observer.observe(chatContainer, {
                    childList: true,
                    subtree: true
                });
                
                // 페이지를 떠날 때 Observer 연결 해제 (메모리 누수 방지)
                window.parent.addEventListener('beforeunload', () => {
                    observer.disconnect();
                });
            }
        </script>
        """, height=0)

        # 사용자 입력 (플레이스홀더 개선)
        placeholder_text = "메시지를 입력하세요..."
        # AI 응답 생성 중일 때 입력창 비활성화 - thinking 메시지가 있으면 처리 중으로 간주
        is_processing = (st.session_state.messages and 
                        st.session_state.messages[-1].get("is_thinking", False))
        if is_processing:
            placeholder_text = "AI가 응답 생성 중입니다..."
        
        if prompt := st.chat_input(placeholder_text, key="main_chat_input", disabled=is_processing):
            if not is_system_initialized:
                # 시스템 초기화 강제 실행
                st.toast("⚠️ 시스템 초기화를 자동으로 실행합니다...", icon="🔄")
                with st.spinner("시스템 초기화 중..."):
                    if initialize_system():
                        st.toast("✅ 시스템 초기화 완료!", icon="🎉")
                        st.rerun()
                    else:
                        st.error("❌ 시스템 초기화 실패! 수동으로 초기화해주세요.")
                        return
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

    # --- 오른쪽 컬럼: 파일 관리 ---
    with right_col:
        if not is_system_initialized:
            # 초기화되지 않은 경우 안내 메시지만 표시
            with st.container(border=True):
                st.info("⚠️ 시스템 초기화 후\n오른쪽 위젯이 표시됩니다.", icon="ℹ️")

        # 시스템 초기화 후에만 모든 위젯 표시
        if is_system_initialized:
            # 수위 모니터링 대시보드
            with st.container(border=True):
                st.subheader("💧 수위 모니터링")
                # 배수지 선택 버튼들
                col1, col2 = st.columns(2)
                with col1:
                    gagok_btn = st.button("🏔️ 가곡", use_container_width=True, key="gagok_btn")
                with col2:
                    haeryong_btn = st.button("🌊 해룡", use_container_width=True, key="haeryong_btn")
                
                # 선택된 배수지 상태 초기화
                if 'selected_reservoir' not in st.session_state:
                    st.session_state.selected_reservoir = 'gagok'
                
                # 버튼 클릭 처리
                if gagok_btn:
                    st.session_state.selected_reservoir = 'gagok'
                elif haeryong_btn:
                    st.session_state.selected_reservoir = 'haeryong'
                
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
                                    {level:.1f}m
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

            # 자동화 모니터링 위젯
            with st.container(border=True):
                st.subheader("🤖 자동화 모니터링")
                # 세션 상태에서 일관된 상태 확인
                automation_active = st.session_state.get('automation_status', False)
                autonomous_monitoring = st.session_state.get('autonomous_monitoring', False)
                
                # 통합된 상태 표시
                if automation_active:
                    if autonomous_monitoring:
                        st.success("🟢 **자동화 + 자율 에이전트 활성**", icon="🤖")
                        st.markdown("**상태**: 통합 AI 시스템이 30초마다 분석 및 자동 제어")
                    else:
                        st.warning("🟡 **자동화 활성 (자율 에이전트 대기)**", icon="🤖")
                        st.markdown("**상태**: 기본 자동화만 활성화됨")
                else:
                    st.info("⚫ **자동화 시스템 비활성**", icon="⏸️")
                    st.markdown("**상태**: 수동 모드 - 시스템 제어 탭에서 시작 가능")
                
                # 자동화가 활성화된 경우에만 세부 정보 표시
                if automation_active:
                    # 최근 자동화 로그 가져오기 (시도)
                    try:
                        from tools.automation_control_tool import automation_control_tool
                        status_result = automation_control_tool(action='status')
                        
                        if status_result.get('success'):
                            recent_events = status_result.get('recent_events', [])[:3]  # 최근 3개만
                            
                            if recent_events:
                                st.markdown("**🔍 최근 활동:**")
                                for event in recent_events:
                                    timestamp = event.get('timestamp', '')
                                    if timestamp:
                                        # 시간만 표시 (HH:MM 형식)
                                        try:
                                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                            time_str = dt.strftime('%H:%M')
                                        except:
                                            time_str = timestamp[-8:-3] if len(timestamp) > 8 else timestamp
                                    else:
                                        time_str = "N/A"
                                    
                                    event_type = event.get('event_type', 'INFO')
                                    message = event.get('message', '')
                                    reservoir = event.get('reservoir_id', '')
                                    
                                    # 이벤트 타입별 아이콘
                                    if event_type == 'ERROR':
                                        icon = "🔴"
                                    elif event_type == 'WARNING':
                                        icon = "🟡"
                                    elif event_type == 'ACTION':
                                        icon = "⚡"
                                    else:
                                        icon = "ℹ️"
                                    
                                    # 메시지 줄이기
                                    short_msg = message[:40] + "..." if len(message) > 40 else message
                                    st.markdown(f"{icon} `{time_str}` {short_msg}")
                            else:
                                st.markdown("*활동 기록 없음*")
                        
                        # 시스템 건강 상태
                        system_health = status_result.get('system_health', {})
                        critical_count = len(system_health.get('critical_reservoirs', []))
                        warning_count = len(system_health.get('warning_reservoirs', []))
                        
                        if critical_count > 0:
                            st.error(f"🚨 위험: {critical_count}개 배수지", icon="⚠️")
                        elif warning_count > 0:
                            st.warning(f"⚠️ 주의: {warning_count}개 배수지", icon="📢")
                        else:
                            st.success("✅ 시스템 정상", icon="💚")
                            
                    except Exception as e:
                        logger.debug(f"자동화 상태 조회 오류: {e}")
                        st.info("자동화 에이전트 동작 중")
                        
                # 비활성 상태는 위에서 이미 표시했으므로 중복 제거
                
                # 상태 새로고침
                if st.button("🔄 상태 새로고침", use_container_width=True, key="refresh_automation"):
                    st.rerun()

            # 자율 에이전트 실시간 알림 위젯
            if st.session_state.get('autonomous_agent'):
                with st.container(border=True):
                    st.subheader("🔔 실시간 알림")
                    autonomous_agent = st.session_state.autonomous_agent

                    # 최근 알림 3개만 표시
                    notifications = autonomous_agent.get_notifications(limit=3)

                    if notifications:
                        for notification in notifications:
                            level_colors = {
                                "info": "#3b82f6",
                                "warning": "#f59e0b",
                                "critical": "#ef4444",
                                "emergency": "#dc2626"
                            }
                            level_icons = {
                                "info": "ℹ️",
                                "warning": "⚠️",
                                "critical": "🚨",
                                "emergency": "🆘"
                            }

                            # 알림 level 처리 (문자열 또는 enum 값)
                            level_str = notification.get('level', 'info')
                            if hasattr(level_str, 'value'):
                                level_str = level_str.value
                            elif hasattr(level_str, 'name'):
                                level_str = level_str.name
                            else:
                                level_str = str(level_str).lower()

                            color = level_colors.get(level_str.lower(), "#6b7280")
                            icon = level_icons.get(level_str.lower(), "📢")

                            with st.container():
                                # 알림 데이터 안전하게 추출
                                title = notification.get('title', notification.get('message', '알림'))
                                message = notification.get('message', '')
                                timestamp = notification.get('timestamp')
                                
                                # 타임스탬프 처리
                                if timestamp:
                                    if hasattr(timestamp, 'strftime'):
                                        time_str = timestamp.strftime('%H:%M:%S')
                                    else:
                                        # 문자열 형태의 timestamp 처리
                                        try:
                                            if isinstance(timestamp, str):
                                                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                                time_str = dt.strftime('%H:%M:%S')
                                            else:
                                                time_str = str(timestamp)
                                        except:
                                            time_str = str(timestamp)
                                else:
                                    time_str = "N/A"
                                
                                st.markdown(f"""
                                <div style="border-left: 3px solid {color}; padding: 8px 12px; margin: 6px 0; background: #f8fafc; border-radius: 0 6px 6px 0;">
                                    <strong style="color: {color};">{icon} {title}</strong><br>
                                    <small style="color: #6b7280;">{time_str}</small><br>
                                    <span style="font-size: 13px;">{message[:100]}{'...' if len(message) > 100 else ''}</span>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # 승인이 필요한 경우 미니 버튼
                                action_required = notification.get('action_required', False)
                                action_id = notification.get('action_id')
                                if action_required and action_id:
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        if st.button("✅", key=f"mini_approve_{action_id}", help="승인"):
                                            if autonomous_agent.approve_action(action_id):
                                                st.toast("승인 완료!", icon="✅")
                                                st.rerun()
                                    with col2:
                                        if st.button("❌", key=f"mini_reject_{action_id}", help="거부"):
                                            if autonomous_agent.reject_action(action_id):
                                                st.toast("거부 완료", icon="❌")
                                                st.rerun()
                    else:
                        st.info("🔕 현재 알림이 없습니다.")

            # 파일 업로드 위젯
            with st.container(border=True):
                st.subheader("📤 파일 업로드")

                # 업로드 완료 메시지 표시
                if 'upload_success_msg' in st.session_state:
                    st.success(st.session_state.upload_success_msg)
                    del st.session_state.upload_success_msg

                # 업로드 위젯 초기화를 위한 동적 키
                upload_key = st.session_state.get('upload_widget_key', 0)

                uploaded_file = st.file_uploader(
                    "파일 선택",
                    label_visibility="collapsed",
                    key=f"file_uploader_{upload_key}"
                )
                if uploaded_file:
                    if st.button("📤 업로드", use_container_width=True, type="primary"):
                        storage = st.session_state.get('storage')
                        if storage:
                            # 진행률 표시를 위한 컨테이너 생성
                            progress_container = st.container()
                            status_container = st.container()
                            
                            with progress_container:
                                progress_bar = st.progress(0)
                                status_text = st.empty()
                            
                            try:
                                # 1단계: 파일 데이터 읽기
                                status_text.text("📁 파일 데이터 읽는 중...")
                                progress_bar.progress(10)
                                file_data = uploaded_file.getvalue()
                                
                                # 2단계: 중복 파일 확인
                                status_text.text("🔍 중복 파일 확인 중...")
                                progress_bar.progress(20)
                                
                                # 중복 확인을 위한 별도 메서드 호출
                                existing_file = storage.check_file_exists(uploaded_file.name)
                                if existing_file:
                                    progress_bar.progress(100)
                                    status_text.text("⚠️ 파일이 이미 존재합니다.")
                                    st.warning(f"파일 '{uploaded_file.name}'이 이미 존재합니다. (ID: {existing_file['id']})")
                                    st.info("다른 이름으로 파일을 저장하거나 기존 파일을 사용하세요.")
                                    return
                                
                                # 3단계: 파일 내용 처리 및 임베딩 생성
                                status_text.text("🔄 파일 내용 처리 중...")
                                progress_bar.progress(30)
                                
                                # 파일 확장자 확인
                                file_extension = os.path.splitext(uploaded_file.name)[1].lower()
                                if file_extension in ['.pdf', '.txt', '.docx']:
                                    status_text.text("📄 문서 내용 분석 중...")
                                    progress_bar.progress(40)
                                    
                                    status_text.text("✂️ 텍스트 청크 분할 중...")
                                    progress_bar.progress(60)
                                    
                                    status_text.text("🧠 임베딩 생성 중...")
                                    progress_bar.progress(80)
                                
                                # 4단계: 파일 저장
                                status_text.text("💾 데이터베이스에 저장 중...")
                                progress_bar.progress(90)
                                
                                file_id = storage.save_file(file_data, uploaded_file.name, metadata={"source": "streamlit_upload"})
                                
                                if file_id:
                                    progress_bar.progress(100)
                                    status_text.text("✅ 업로드 완료!")

                                    # 파일 정보 준비
                                    file_size = len(file_data)
                                    if file_size > 1024 * 1024:
                                        size_str = f"{file_size / (1024 * 1024):.1f} MB"
                                    elif file_size > 1024:
                                        size_str = f"{file_size / 1024:.1f} KB"
                                    else:
                                        size_str = f"{file_size} bytes"

                                    # 청크 정보 (PDF, TXT, DOCX인 경우)
                                    chunk_info = ""
                                    if file_extension in ['.pdf', '.txt', '.docx']:
                                        chunk_count = storage.get_chunk_count(file_id)
                                        if chunk_count:
                                            chunk_info = f" | 청크: {chunk_count}개"

                                    # 성공 메시지를 세션에 저장 (다음 렌더링에서 표시)
                                    st.session_state.upload_success_msg = (
                                        f"✅ **'{uploaded_file.name}'** 업로드 완료!\n\n"
                                        f"📊 크기: {size_str} | ID: {file_id}{chunk_info}"
                                    )

                                    # 파일 목록 즉시 갱신을 위해 세션 상태 초기화
                                    if 'postgres_files' in st.session_state:
                                        del st.session_state['postgres_files']

                                    # 업로드 위젯 초기화를 위한 키 증가
                                    current_key = st.session_state.get('upload_widget_key', 0)
                                    st.session_state.upload_widget_key = current_key + 1

                                    # 즉시 새로고침 (메시지는 다음 렌더링에서 표시)
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    progress_bar.progress(0)
                                    status_text.text("❌ 업로드 실패")
                                    st.error("파일 업로드에 실패했습니다.")
                                    
                            except Exception as e:
                                progress_bar.progress(0)
                                status_text.text("❌ 오류 발생")
                                st.error(f"업로드 중 오류가 발생했습니다: {str(e)}")
                                logger.error(f"파일 업로드 오류: {e}")
                        else:
                            st.error("스토리지 시스템이 초기화되지 않았습니다.")

            # 파일 목록 위젯
            with st.container(border=True):
                st.subheader("📂 파일 목록")
                storage = st.session_state.get('storage')
                if storage:
                    # 파일 목록 조회 (캐시 사용)
                    if 'postgres_files' not in st.session_state:
                        with st.spinner("파일 목록 로딩 중..."):
                            try:
                                st.session_state.postgres_files = storage.list_files()
                            except Exception as e:
                                st.error(f"파일 목록 로딩 실패: {e}")
                                st.session_state.postgres_files = []

                    file_list = st.session_state.postgres_files

                    if not file_list:
                        st.info("📭 업로드된 파일이 없습니다.")
                    else:
                        st.success(f"📊 총 {len(file_list)}개의 파일")

                        for idx, file_info in enumerate(file_list):
                            file_id = file_info.get('_id')
                            filename = file_info.get('filename', 'N/A')

                            # 파일 크기 계산
                            file_size = file_info.get('length', 0)
                            if file_size > 1024 * 1024:
                                size_str = f"{file_size / (1024 * 1024):.2f} MB"
                            elif file_size > 1024:
                                size_str = f"{file_size / 1024:.2f} KB"
                            else:
                                size_str = f"{file_size} bytes"

                            # 업로드 날짜 파싱
                            upload_date = file_info.get('uploadDate', 'N/A')
                            if isinstance(upload_date, str):
                                try:
                                    upload_date = datetime.fromisoformat(upload_date.replace('Z', '+00:00'))
                                except:
                                    pass

                            if hasattr(upload_date, 'strftime'):
                                date_str = upload_date.strftime('%Y-%m-%d %H:%M')
                            else:
                                date_str = str(upload_date)

                            # 파일 카드
                            file_content_key = f'file_content_{file_id}'
                            with st.container(border=True):
                                col_info, col_btn = st.columns([3, 1])

                                with col_info:
                                    st.markdown(f"**📄 {filename}**")
                                    st.caption(f"📏 {size_str} | 📅 {date_str}")

                                with col_btn:
                                    # 2단계 다운로드: 먼저 파일 준비, 그 다음 다운로드
                                    if file_content_key not in st.session_state:
                                        # 다운로드 준비 버튼
                                        if st.button("⬇️", key=f"prepare_{idx}_{file_id}", use_container_width=True, help="클릭하여 다운로드 준비"):
                                            try:
                                                with st.spinner("파일 로딩 중..."):
                                                    file_content = storage.get_file_content(file_id)
                                                    if file_content:
                                                        st.session_state[file_content_key] = file_content
                                                        st.rerun()
                                                    else:
                                                        st.error("파일을 가져올 수 없습니다.")
                                            except Exception as e:
                                                st.error(f"오류: {str(e)}")
                                    else:
                                        # 실제 다운로드 버튼
                                        st.download_button(
                                            label="💾",
                                            data=st.session_state[file_content_key],
                                            file_name=filename,
                                            key=f"download_btn_{idx}_{file_id}",
                                            use_container_width=True,
                                            help="파일 다운로드"
                                        )
                else:
                    st.error("스토리지 시스템이 초기화되지 않았습니다.")


if __name__ == "__main__":
    # 초기 메시지 설정
    if len(st.session_state.messages) == 0:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "안녕하세요! 좌측의 **🔄 시스템 초기화**를 먼저 눌러주세요.",
            "timestamp": datetime.now().strftime("%H:%M")
        })
    main()