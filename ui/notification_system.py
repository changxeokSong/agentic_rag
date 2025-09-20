# ui/notification_system.py

import streamlit as st
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio

from services.autonomous_agent import AutonomousAgent, UserNotification, AlertLevel

class NotificationUI:
    """알림 시스템 UI 컴포넌트"""
    
    def __init__(self, autonomous_agent: AutonomousAgent):
        self.agent = autonomous_agent
    
    def render_notification_panel(self):
        """알림 패널 렌더링"""
        st.subheader("🔔 실시간 알림")
        
        # 알림 목록 가져오기 (개선된 버전)
        try:
            notifications = self.agent.get_notifications(limit=10) if hasattr(self.agent, 'get_notifications') else []
        except Exception as e:
            st.error(f"알림 가져오기 실패: {e}")
            notifications = []
        
        if not notifications:
            st.info("현재 알림이 없습니다.")
            return
        
        # 알림 필터
        col1, col2 = st.columns([3, 1])
        with col1:
            show_levels = st.multiselect(
                "알림 레벨 필터",
                options=[level.value for level in AlertLevel],
                default=[level.value for level in AlertLevel],
                key="notification_filter"
            )
        with col2:
            if st.button("🔄 새로고침", key="refresh_notifications"):
                st.rerun()
        
        # 필터링된 알림 표시
        filtered_notifications = [
            n for n in notifications 
            if n.level.value in show_levels
        ]
        
        for notification in filtered_notifications:
            self._render_notification_item(notification)
    
    def _render_notification_item(self, notification: UserNotification):
        """개별 알림 아이템 렌더링"""
        # 레벨별 색상 및 아이콘
        level_config = {
            AlertLevel.INFO: {"color": "blue", "icon": "ℹ️", "container": st.info},
            AlertLevel.WARNING: {"color": "orange", "icon": "⚠️", "container": st.warning},
            AlertLevel.CRITICAL: {"color": "red", "icon": "🚨", "container": st.error},
            AlertLevel.EMERGENCY: {"color": "red", "icon": "🆘", "container": st.error}
        }
        
        config = level_config[notification.level]
        
        with st.container():
            # 알림 헤더
            col1, col2, col3 = st.columns([6, 2, 2])
            with col1:
                st.markdown(f"**{config['icon']} {notification.title}**")
            with col2:
                st.markdown(f"*{notification.level.value.upper()}*")
            with col3:
                time_ago = self._get_time_ago(notification.timestamp)
                st.markdown(f"*{time_ago}*")
            
            # 알림 내용
            st.markdown(notification.message)
            
            # 액션이 필요한 경우 승인 버튼 표시
            if notification.action_required and notification.action_id:
                self._render_approval_buttons(notification.action_id)
            
            st.divider()
    
    def _render_approval_buttons(self, action_id: str):
        """승인 버튼 렌더링"""
        col1, col2, col3 = st.columns([1, 1, 4])
        
        with col1:
            if st.button("✅ 승인", key=f"approve_{action_id}"):
                success = self.agent.approve_action(action_id)
                if success:
                    st.success("조치가 승인되어 실행되었습니다.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("조치 승인 실패")
        
        with col2:
            if st.button("❌ 거부", key=f"reject_{action_id}"):
                success = self.agent.reject_action(action_id)
                if success:
                    st.info("조치가 거부되었습니다.")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("조치 거부 실패")
    
    def _get_time_ago(self, timestamp: datetime) -> str:
        """시간 전 표시"""
        now = datetime.now()
        diff = now - timestamp
        
        if diff.total_seconds() < 60:
            return "방금 전"
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes}분 전"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours}시간 전"
        else:
            days = int(diff.total_seconds() / 86400)
            return f"{days}일 전"
    
    def render_pending_approvals(self):
        """대기 중인 승인 요청 렌더링"""
        st.subheader("⏳ 승인 대기 중인 조치")
        
        pending = self.agent.get_pending_approvals()
        
        if not pending:
            st.info("현재 승인 대기 중인 조치가 없습니다.")
            return
        
        for approval in pending:
            with st.expander(f"🔄 {approval['description']}", expanded=True):
                st.write(f"**상황:** {approval['situation']}")
                st.write(f"**예상 효과:** {approval['estimated_impact']}")
                st.write(f"**요청 시간:** {approval['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ 승인 처리", key=f"process_approve_{approval['action_id']}"):
                        success = self.agent.approve_action(approval['action_id'])
                        if success:
                            st.success("조치가 승인되어 실행되었습니다!")
                            st.rerun()
                        else:
                            st.error("조치 승인 처리에 실패했습니다.")
                
                with col2:
                    if st.button("❌ 거부 처리", key=f"process_reject_{approval['action_id']}"):
                        success = self.agent.reject_action(approval['action_id'])
                        if success:
                            st.info("조치가 거부되었습니다.")
                            st.rerun()
                        else:
                            st.error("조치 거부 처리에 실패했습니다.")

    def render_system_status(self):
        """시스템 상태 렌더링"""
        st.subheader("🤖 자율 에이전트 상태")
        
        # 개선된 상태 확인
        try:
            if hasattr(self.agent, 'get_status'):
                status = self.agent.get_status()
            elif hasattr(self.agent, 'get_system_status'):
                status = self.agent.get_system_status()
            else:
                # 호환성을 위한 기본 상태
                status = {
                    "is_monitoring": getattr(self.agent, 'is_running', False),
                    "monitoring_interval": getattr(self.agent, 'monitoring_interval', 30),
                    "pending_approvals_count": len(getattr(self.agent, 'pending_approvals', [])),
                    "total_actions": getattr(self.agent, 'total_actions', 0)
                }
        except Exception as e:
            st.error(f"상태 확인 중 오류: {e}")
            status = {"is_monitoring": False, "monitoring_interval": 30, "pending_approvals_count": 0, "total_actions": 0}
        
        # 상태 표시
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # 세션 상태와 에이전트 내부 상태를 모두 확인
            session_monitoring = st.session_state.get('autonomous_monitoring', False)
            agent_monitoring = status.get("is_monitoring", False)
            
            # 두 상태가 다르면 세션 상태를 우선으로 하고 동기화
            if session_monitoring != agent_monitoring:
                actual_monitoring = session_monitoring
                if hasattr(self.agent, 'is_monitoring'):
                    self.agent.is_monitoring = session_monitoring
            else:
                actual_monitoring = agent_monitoring
            
            monitoring_status = "🟢 실행 중" if actual_monitoring else "🔴 중지됨"
            st.metric("모니터링 상태", monitoring_status)
        
        with col2:
            st.metric("모니터링 주기", f"{status['monitoring_interval']}초")
        
        with col3:
            pending_count = status.get("pending_approvals_count", status.get("pending_approvals", 0))
            st.metric("대기 중인 승인", pending_count)
        
        with col4:
            total_actions = status.get("total_actions", status.get("total_actions_executed", 0))
            st.metric("총 실행된 조치", total_actions)
        
        # 추가 상태 정보 (오류 카운트, 마지막 체크 시간)
        if status.get("error_count", 0) > 0:
            st.warning(f"⚠️ 오류 발생 횟수: {status['error_count']}/{status.get('max_errors', 5)}")
        
        if status.get("last_check_time"):
            try:
                from datetime import datetime
                last_check = datetime.fromisoformat(status["last_check_time"])
                time_diff = (datetime.now() - last_check).total_seconds()
                if time_diff > status.get("monitoring_interval", 30) * 2:
                    st.warning(f"⚠️ 마지막 체크: {last_check.strftime('%H:%M:%S')} (지연됨)")
                else:
                    st.info(f"✅ 마지막 체크: {last_check.strftime('%H:%M:%S')}")
            except Exception:
                pass
        
        # 제어 버튼
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if not status["is_monitoring"]:
                if st.button("▶️ 모니터링 시작"):
                    # 백그라운드 스레드에서 모니터링 시작
                    import threading
                    def start_monitoring():
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(self.agent.start_monitoring())
                        except Exception as e:
                            st.session_state.monitoring_error = str(e)
                        finally:
                            loop.close()
                    
                    thread = threading.Thread(target=start_monitoring, daemon=True)
                    thread.start()
                    st.session_state.monitoring_thread = thread
                    st.success("자율 모니터링을 시작했습니다.")
                    time.sleep(1)
                    st.rerun()
            else:
                if st.button("⏸️ 모니터링 중지"):
                    self.agent.stop_monitoring()
                    if hasattr(st.session_state, 'monitoring_thread'):
                        del st.session_state.monitoring_thread
                    st.info("자율 모니터링을 중지했습니다.")
                    time.sleep(1)
                    st.rerun()
        
        with col2:
            if st.button("🗑️ 오래된 알림 정리"):
                self.agent.clear_old_notifications()
                st.success("24시간 이전 알림을 정리했습니다.")
                st.rerun()
    
    def render_action_history(self):
        """액션 히스토리 렌더링"""
        st.subheader("📈 자동 조치 이력")
        
        if not self.agent.action_history:
            st.info("아직 실행된 자동 조치가 없습니다.")
            return
        
        # 최근 20개 액션 표시
        recent_actions = sorted(
            self.agent.action_history, 
            key=lambda x: x["timestamp"], 
            reverse=True
        )[:20]
        
        for action_record in recent_actions:
            action = action_record["action"]
            situation = action_record["situation"]
            timestamp = action_record["timestamp"]
            execution_type = action_record["execution_type"]
            
            with st.expander(
                f"📋 {timestamp.strftime('%H:%M:%S')} - {action.description}", 
                expanded=False
            ):
                st.write(f"**상황:** {situation.description}")
                st.write(f"**실행 유형:** {'자동 실행' if execution_type == 'automatic' else '승인 후 실행'}")
                st.write(f"**예상 효과:** {action.estimated_impact}")
                
                if "result" in action_record:
                    result = action_record["result"]
                    if isinstance(result, dict) and "error" not in result:
                        st.success("✅ 조치 성공")
                    else:
                        st.error(f"❌ 조치 실패: {result}")


class AutoNotificationDisplay:
    """자동 알림 팝업 표시"""
    
    @staticmethod
    def show_critical_alert(message: str, title: str = "긴급 상황"):
        """긴급 알림 표시"""
        st.error(f"🚨 **{title}**")
        st.error(message)
        
        # 사운드 알림 (브라우저에서 지원하는 경우)
        st.markdown("""
        <script>
        if ('speechSynthesis' in window) {
            var utterance = new SpeechSynthesisUtterance('긴급 상황이 발생했습니다');
            utterance.lang = 'ko-KR';
            speechSynthesis.speak(utterance);
        }
        </script>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def show_warning_alert(message: str, title: str = "경고"):
        """경고 알림 표시"""
        st.warning(f"⚠️ **{title}**")
        st.warning(message)
    
    @staticmethod
    def show_info_alert(message: str, title: str = "알림"):
        """정보 알림 표시"""
        st.info(f"ℹ️ **{title}**")
        st.info(message)
    
    @staticmethod
    def show_floating_notification(message: str, level: AlertLevel):
        """부동 알림 표시"""
        if level == AlertLevel.EMERGENCY:
            color = "red"
            icon = "🚨"
        elif level == AlertLevel.CRITICAL:
            color = "red"
            icon = "🔴"
        elif level == AlertLevel.WARNING:
            color = "orange"
            icon = "⚠️"
        else:
            color = "blue"
            icon = "ℹ️"
        
        # CSS를 사용한 부동 알림 (우상단에 표시)
        st.markdown(f"""
        <div style="
            position: fixed;
            top: 10px;
            right: 10px;
            background-color: {color};
            color: white;
            padding: 10px 15px;
            border-radius: 5px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            z-index: 9999;
            max-width: 300px;
            font-size: 14px;
        ">
            <strong>{icon} 실시간 알림</strong><br>
            {message}
        </div>
        """, unsafe_allow_html=True)


def render_autonomous_dashboard(autonomous_agent: AutonomousAgent):
    """자율 시스템 대시보드 렌더링"""
    st.title("🤖 자율 에이전트 대시보드")
    
    # 알림 UI 초기화
    notification_ui = NotificationUI(autonomous_agent)
    
    # 탭 구성
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔔 실시간 알림", 
        "⏳ 승인 대기", 
        "🤖 시스템 상태", 
        "📈 조치 이력"
    ])
    
    with tab1:
        notification_ui.render_notification_panel()
    
    with tab2:
        notification_ui.render_pending_approvals()
    
    with tab3:
        notification_ui.render_system_status()
    
    with tab4:
        notification_ui.render_action_history()
    
    # 자동 새로고침 (30초마다)
    st.markdown("""
    <script>
    setTimeout(function(){
        window.location.reload(1);
    }, 30000);
    </script>
    """, unsafe_allow_html=True)