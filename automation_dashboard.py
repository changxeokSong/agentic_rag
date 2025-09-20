# automation_dashboard_simple.py - 심플한 자동화 시스템 대시보드

import streamlit as st
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any
import threading
import time

# 로컬 모듈 임포트
from services.logging_system import get_automation_logger, LogLevel, EventType
from utils.state_manager import get_state_manager
from utils.helpers import get_current_timestamp, get_session_state_value, set_session_state_value
from utils.async_helpers import get_async_state_manager, get_streamlit_state_sync
from tools.automation_control_tool import automation_control_tool

# 페이지 설정
st.set_page_config(
    page_title="자동화 시스템 대시보드",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 간소화된 CSS 스타일
st.markdown("""
<style>
    .main-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 1rem;
        color: white;
        margin-bottom: 1rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .status-card {
        background: white;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #28a745;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .control-button {
        background: #007bff;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        cursor: pointer;
        margin: 0.2rem;
    }
    
    .log-entry {
        background: #f8f9fa;
        padding: 0.75rem;
        margin: 0.3rem 0;
        border-radius: 0.5rem;
        border-left: 3px solid #007bff;
        font-family: monospace;
        font-size: 0.85rem;
    }
    
    .error-log { border-left-color: #dc3545; }
    .warning-log { border-left-color: #ffc107; }
    .info-log { border-left-color: #17a2b8; }
    
    /* 로딩 스피너 숨기기 */
    .stSpinner > div {
        display: none !important;
    }
    
    /* 자동 새로고침 방지 */
    .stApp {
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

class SimpleAutomationDashboard:
    def __init__(self):
        self.logger = get_automation_logger()
        self.state_manager = get_state_manager()
        self.async_manager = get_async_state_manager()
        self.state_sync = get_streamlit_state_sync()
        
        # 세션 상태 초기화
        self._init_session_state()
    
    def _init_session_state(self):
        """세션 상태 초기화"""
        if 'last_update' not in st.session_state:
            st.session_state.last_update = get_current_timestamp()
        
        if 'automation_status' not in st.session_state:
            st.session_state.automation_status = False
            
        if 'autonomous_monitoring' not in st.session_state:
            st.session_state.autonomous_monitoring = False
            
        if 'system_initialized' not in st.session_state:
            st.session_state.system_initialized = True
            
        if 'last_logs' not in st.session_state:
            st.session_state.last_logs = []
            
        if 'dashboard_data' not in st.session_state:
            st.session_state.dashboard_data = {}
    
    def run(self):
        """메인 대시보드 실행"""
        try:
            # 헤더
            st.markdown("""
            <div class="main-card">
                <h1>🤖 자동화 시스템 대시보드</h1>
                <p>실시간 모니터링 및 제어</p>
            </div>
            """, unsafe_allow_html=True)
            
            # 안전한 데이터 로드
            try:
                self._load_data_async()
            except Exception as e:
                st.warning(f"초기 데이터 로드 실패: {e}")
                # 기본값으로 초기화
                st.session_state.automation_status = False
                st.session_state.autonomous_monitoring = False
                st.session_state.last_logs = []
            
            # 메인 컨테이너
            col1, col2 = st.columns([2, 1])
            
            with col1:
                self._render_main_status()
                self._render_controls()
            
            with col2:
                self._render_logs()
            
            # 자동 업데이트 (새로고침 없이)
            self._setup_auto_update()
            
        except Exception as e:
            st.error(f"대시보드 실행 중 오류 발생: {e}")
            st.info("페이지를 새로고침해 주세요.")
            
            # 오류 정보를 콘솔에 출력
            import traceback
            print(f"Dashboard Error: {e}")
            print(traceback.format_exc())
    
    def _load_data_async(self):
        """비동기로 데이터 로드 (캐시 사용으로 성능 향상)"""
        # 스로틀링 체크 (마지막 업데이트로부터 2초 이상 경과 시에만 실행)
        current_time = time.time()
        last_load_time = getattr(self, '_last_load_time', 0)
        
        if current_time - last_load_time < 2.0:
            return  # 스로틀링 적용
        
        self._last_load_time = current_time
        
        def fetch_status():
            if self.state_manager:
                return self.state_manager.is_automation_active()
            return False, False
        
        def fetch_logs():
            try:
                return self.logger.get_recent_logs(limit=10, level=LogLevel.INFO)
            except Exception as e:
                print(f"로그 가져오기 오류: {e}")
                return []
        
        try:
            # 캐시된 데이터 사용 (성능 향상)
            status_data = self.async_manager.get_cached_data(
                'automation_status', 
                fetch_status
            )
            
            if status_data:
                automation_status, autonomous_monitoring = status_data
                
                # 배치 업데이트 (불필요한 rerun 방지)
                updates = {
                    'automation_status': automation_status,
                    'autonomous_monitoring': autonomous_monitoring,
                    'last_update': get_current_timestamp()
                }
                
                self.state_sync.batch_update_state(updates, rerun=False)
            
            # 로그도 캐시 사용
            logs = self.async_manager.get_cached_data('recent_logs', fetch_logs)
            if logs:
                st.session_state.last_logs = logs
                
        except Exception as e:
            # 에러 시 기존 상태 유지
            pass
    
    def _render_main_status(self):
        """메인 상태 표시"""
        st.subheader("🔧 시스템 상태")
        
        # 자동화 상태 카드
        automation_active = st.session_state.get('automation_status', False)
        monitoring_active = st.session_state.get('autonomous_monitoring', False)
        
        if automation_active and monitoring_active:
            status_icon = "🟢"
            status_text = "완전 활성"
            border_color = "#28a745"
        elif automation_active or monitoring_active:
            status_icon = "🟡"
            status_text = "부분 활성"
            border_color = "#ffc107"
        else:
            status_icon = "🔴"
            status_text = "비활성"
            border_color = "#dc3545"
        
        st.markdown(f"""
        <div style="background: white; padding: 1rem; border-radius: 0.5rem; 
                    border-left: 4px solid {border_color}; margin: 0.5rem 0;">
            <h3>{status_icon} AI 자동화 상태: {status_text}</h3>
            <p><strong>자동화 엔진:</strong> {'✅ 활성' if automation_active else '❌ 비활성'}</p>
            <p><strong>자율 모니터링:</strong> {'✅ 활성' if monitoring_active else '❌ 비활성'}</p>
            <p><strong>마지막 업데이트:</strong> {get_current_timestamp()}</p>
        </div>
        """, unsafe_allow_html=True)
    
    def _render_controls(self):
        """제어 패널"""
        st.subheader("⚙️ 제어 패널")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("🚀 자동화 시작", key="start_auto", type="primary"):
                self._execute_action("start")
        
        with col2:
            if st.button("⏹️ 자동화 중지", key="stop_auto", type="secondary"):
                self._execute_action("stop")
        
        with col3:
            if st.button("📊 상태 확인", key="check_status"):
                self._execute_action("status")
        
        with col4:
            if st.button("🔧 Arduino 점검", key="check_arduino"):
                self._execute_action("debug_arduino")
        
        # 빠른 액션 결과 표시 (auto-dismiss)
        if 'last_action_result' in st.session_state and st.session_state.last_action_result:
            result = st.session_state.last_action_result
            
            # 성공/실패에 따른 표시
            if result.get('success'):
                if 'detailed_report' in result:
                    st.success("✅ 작업 완료")
                    with st.expander("📋 상세 결과 보기", expanded=False):
                        st.markdown(result['detailed_report'])
                else:
                    st.success(f"✅ {result.get('message', '작업 완료')}")
            else:
                st.error(f"❌ {result.get('error', '작업 실패')}")
            
            # 5초 후 자동 제거 (JavaScript 사용)
            st.markdown("""
            <script>
                setTimeout(function() {
                    const alerts = document.querySelectorAll('[data-testid="stAlert"]');
                    alerts.forEach(alert => {
                        if (alert.textContent.includes('✅') || alert.textContent.includes('❌')) {
                            alert.style.transition = 'opacity 0.5s ease';
                            alert.style.opacity = '0';
                            setTimeout(() => alert.remove(), 500);
                        }
                    });
                }, 5000);
            </script>
            """, unsafe_allow_html=True)
            
            # 결과 표시 후 제거
            st.session_state.last_action_result = None
    
    def _execute_action(self, action: str):
        """액션 실행 (안전한 오류 처리)"""
        try:
            # 스피너 없이 빠른 실행
            result = automation_control_tool(action=action)
            
            if result:
                st.session_state.last_action_result = result
                
                # 상태 변경 시 캐시 무효화 후 즉시 반영
                if action in ['start', 'stop']:
                    self.async_manager.clear_cache('automation_status')
                    self._load_data_async()
                
                # Arduino 액션 시 로그 캐시도 무효화
                if action in ['debug_arduino', 'test_arduino_connection']:
                    self.async_manager.clear_cache('recent_logs')
                
                st.rerun()
            else:
                st.session_state.last_action_result = {
                    "success": False,
                    "error": "액션 실행 결과를 받지 못했습니다"
                }
                st.rerun()
                
        except Exception as e:
            error_msg = f"액션 '{action}' 실행 중 오류: {str(e)}"
            st.session_state.last_action_result = {
                "success": False,
                "error": error_msg
            }
            # 오류를 콘솔에도 출력
            print(f"Dashboard Error: {error_msg}")
            st.rerun()
    
    def _render_logs(self):
        """로그 표시 (캐시된 데이터 사용)"""
        st.subheader("📝 최근 로그")
        
        # 캐시된 로그 사용 (성능 향상)
        logs = st.session_state.get('last_logs', [])
        
        if logs:
            log_container = st.container()
            with log_container:
                for log in logs[-10:]:  # 최신 10개만
                    level = log.get('level', 'INFO')
                    timestamp = log.get('timestamp', '')
                    message = log.get('message', '')
                    
                    # 로그 레벨별 스타일링
                    if level in ['ERROR', 'CRITICAL']:
                        css_class = "error-log"
                    elif level == 'WARNING':
                        css_class = "warning-log"
                    else:
                        css_class = "info-log"
                    
                    # 시간 포맷팅 (HH:MM:SS만 표시)
                    try:
                        time_str = timestamp.split(' ')[1][:8] if ' ' in timestamp else timestamp[:8]
                    except:
                        time_str = timestamp[:8] if timestamp else ""
                    
                    st.markdown(f"""
                    <div class="log-entry {css_class}">
                        <strong>{time_str}</strong> [{level}] {message}
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("로그를 로드하는 중...")
            
        # 로그 새로고침 버튼 (선택적)
        if st.button("🔄 로그 새로고침", key="refresh_logs"):
            self.async_manager.clear_cache('recent_logs')
            self._load_data_async()
    
    def _setup_auto_update(self):
        """자동 업데이트 설정 (새로고침 최소화)"""
        # 현재 시간 표시
        current_time = get_current_timestamp()
        
        # 마지막 업데이트 시간 확인
        last_update = st.session_state.get('last_auto_update', 0)
        current_timestamp = time.time()
        
        # 1분마다 데이터 업데이트 (필요한 경우만)
        if current_timestamp - last_update > 60:
            st.session_state.last_auto_update = current_timestamp
            
            # 백그라운드에서 데이터 새로고침
            threading.Thread(
                target=self._background_update,
                daemon=True
            ).start()
        
        # 상태 표시 (우하단 작은 알림)
        st.markdown(f"""
        <div style="position: fixed; bottom: 10px; right: 10px; 
                    background: rgba(0,0,0,0.7); color: white; 
                    padding: 0.3rem 0.6rem; border-radius: 0.3rem; 
                    font-size: 0.7rem; z-index: 1000;">
            ⏰ {current_time}
        </div>
        """, unsafe_allow_html=True)
    
    def _background_update(self):
        """백그라운드에서 데이터 업데이트"""
        try:
            # 상태 확인
            if self.state_manager:
                automation_status, autonomous_monitoring = self.state_manager.is_automation_active()
                
                # 상태가 변경된 경우만 업데이트
                current_auto = st.session_state.get('automation_status', False)
                current_monitoring = st.session_state.get('autonomous_monitoring', False)
                
                if (automation_status != current_auto or 
                    autonomous_monitoring != current_monitoring):
                    
                    # 캐시 무효화 후 다음 로드에서 새 데이터 사용
                    self.async_manager.clear_cache('automation_status')
                    
                    # 상태 변경 알림 (선택적)
                    status_change = {
                        'status_changed': True,
                        'change_time': get_current_timestamp()
                    }
                    st.session_state.update(status_change)
            
        except Exception as e:
            # 백그라운드 오류는 조용히 처리
            pass

def main():
    """메인 함수"""
    try:
        dashboard = SimpleAutomationDashboard()
        dashboard.run()
    except Exception as e:
        st.error(f"대시보드 실행 오류: {e}")
        st.info("페이지를 새로고침해주세요.")

if __name__ == "__main__":
    main()