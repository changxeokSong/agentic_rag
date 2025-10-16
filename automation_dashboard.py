# automation_dashboard.py - 자동화 시스템 대시보드 (가곡/해룡 배수지 특화)

import streamlit as st
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
import threading
import time
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 로컬 모듈 임포트
from services.logging_system import get_automation_logger, LogLevel, EventType
from utils.state_manager import get_state_manager
from utils.helpers import get_current_timestamp, get_session_state_value, set_session_state_value
from utils.async_helpers import get_async_state_manager, get_streamlit_state_sync
from tools.automation_control_tool import automation_control_tool
from storage.postgresql_storage import PostgreSQLStorage

# 페이지 설정
st.set_page_config(
    page_title="자동화 시스템 대시보드",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 최소한의 CSS 스타일 (Streamlit 네이티브 스타일 사용)
st.markdown("""
<style>
    /* 컨테이너 간격 조정 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* 메트릭 카드 간격 */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }

    /* 구분선 스타일 */
    hr {
        margin: 1.5rem 0;
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

        # 배수지 데이터 초기화
        if 'reservoir_data' not in st.session_state:
            st.session_state.reservoir_data = {
                'gagok': {'name': '가곡 배수지', 'level': 0, 'pump': 'OFF', 'status': 'unknown'},
                'haeryong': {'name': '해룡 배수지', 'level': 0, 'pump': 'OFF', 'status': 'unknown'}
            }
    
    def run(self):
        """메인 대시보드 실행"""
        try:
            # 사이드바 구성
            self._render_sidebar()

            # 헤더
            st.title("🤖 자동화 시스템 대시보드")
            st.caption("가곡/해룡 배수지 실시간 모니터링 및 제어")
            st.divider()

            # 안전한 데이터 로드
            try:
                self._load_data_async()
                self._load_reservoir_data()
            except Exception as e:
                st.warning(f"초기 데이터 로드 실패: {e}")
                # 기본값으로 초기화
                st.session_state.automation_status = False
                st.session_state.autonomous_monitoring = False
                st.session_state.last_logs = []

            # === 첫 번째 섹션: 시스템 상태 (전체 폭) ===
            self._render_main_status()

            st.divider()

            # === 두 번째 섹션: 빠른 제어 (컴팩트) ===
            self._render_controls()

            st.divider()

            # === 세 번째 섹션: 배수지 상태 (1:1 비율) ===
            st.subheader("💧 배수지 실시간 상태")

            col_gagok, col_haeryong = st.columns(2)

            with col_gagok:
                self._render_reservoir_card('gagok')

            with col_haeryong:
                self._render_reservoir_card('haeryong')

            st.divider()

            # === 네 번째 섹션: 수위 그래프 (전체 폭) ===
            self._render_water_level_graph()

            st.divider()

            # === 다섯 번째 섹션: 활동 로그 (전체 폭) ===
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

    def _render_sidebar(self):
        """사이드바 렌더링"""
        # 시스템 상태 표시
        automation_active = st.session_state.get('automation_status', False)
        monitoring_active = st.session_state.get('autonomous_monitoring', False)

        # 상태 색상 및 텍스트
        if automation_active and monitoring_active:
            status_color = "#16a34a"  # 녹색
            status_text = "🟢 완전 활성"
        elif automation_active or monitoring_active:
            status_color = "#f59e0b"  # 주황색
            status_text = "🟡 부분 활성"
        else:
            status_color = "#6b7280"  # 회색
            status_text = "🔴 비활성"

        st.sidebar.markdown(f"""
        <div style="padding: 12px; background: {status_color}15; border: 2px solid {status_color};
                    border-radius: 8px; margin: 10px 0;">
            <h4 style="margin: 0; color: {status_color};">자동화 상태</h4>
            <p style="margin: 5px 0 0 0; color: {status_color}; font-weight: bold;">{status_text}</p>
        </div>
        """, unsafe_allow_html=True)

        # 네비게이션 버튼
        st.sidebar.markdown("### 🧭 네비게이션")

        if st.sidebar.button("🏠 메인 페이지", type="primary", use_container_width=True):
            st.session_state.page = "main"
            st.rerun()

        if st.sidebar.button("💧 수위 대시보드", type="secondary", use_container_width=True):
            st.session_state.page = "water_dashboard"
            st.rerun()

        st.sidebar.markdown("---")

        # 빠른 액션
        st.sidebar.markdown("### ⚡ 빠른 액션")

        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("🚀", key="sidebar_start", use_container_width=True, disabled=automation_active, help="시작"):
                self._execute_action("start")
        with col2:
            if st.button("⏹️", key="sidebar_stop", use_container_width=True, disabled=not automation_active, help="중지"):
                self._execute_action("stop")

        st.sidebar.markdown("---")

        # 시스템 정보
        st.sidebar.markdown("### 📊 시스템 정보")

        gagok_data = st.session_state.reservoir_data.get('gagok', {})
        haeryong_data = st.session_state.reservoir_data.get('haeryong', {})

        st.sidebar.caption(f"**가곡 수위:** {gagok_data.get('level', 0):.1f}%")
        st.sidebar.caption(f"**해룡 수위:** {haeryong_data.get('level', 0):.1f}%")

        st.sidebar.markdown("---")

        # 새로고침
        if st.sidebar.button("🔄 대시보드 새로고침", type="secondary", use_container_width=True):
            self.async_manager.clear_cache('automation_status')
            self.async_manager.clear_cache('recent_logs')
            st.session_state.reservoir_data = {
                'gagok': {'name': '가곡 배수지', 'level': 0, 'pump': 'OFF', 'status': 'unknown'},
                'haeryong': {'name': '해룡 배수지', 'level': 0, 'pump': 'OFF', 'status': 'unknown'}
            }
            st.rerun()

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
        automation_active = st.session_state.get('automation_status', False)
        monitoring_active = st.session_state.get('autonomous_monitoring', False)

        # 자동화 상태 결정
        if automation_active and monitoring_active:
            status_icon = "🟢"
            status_text = "완전 활성"
            status_message = "모든 시스템이 정상 작동 중"
        elif automation_active or monitoring_active:
            status_icon = "🟡"
            status_text = "부분 활성"
            status_message = "일부 시스템만 활성화됨"
        else:
            status_icon = "🔴"
            status_text = "비활성"
            status_message = "자동화 시스템 중지됨"

        # 배수지 상태 요약
        gagok_data = st.session_state.reservoir_data.get('gagok', {})
        haeryong_data = st.session_state.reservoir_data.get('haeryong', {})

        critical_count = sum(1 for data in [gagok_data, haeryong_data] if data.get('status') == 'critical')
        warning_count = sum(1 for data in [gagok_data, haeryong_data] if data.get('status') == 'warning')
        normal_count = 2 - critical_count - warning_count

        # 상태 표시
        st.subheader(f"{status_icon} AI 자동화: {status_text}")
        st.caption(status_message)

        # 메트릭 3개 컬럼
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                label="🤖 자동화 엔진",
                value="활성" if automation_active else "비활성",
                delta="정상" if automation_active else "중지",
                delta_color="normal" if automation_active else "inverse"
            )

        with col2:
            st.metric(
                label="🔍 자율 모니터링",
                value="활성" if monitoring_active else "비활성",
                delta="실행중" if monitoring_active else "대기",
                delta_color="normal" if monitoring_active else "inverse"
            )

        with col3:
            reservoir_status = f"{normal_count}/2 정상"
            reservoir_delta = "정상" if critical_count == 0 and warning_count == 0 else f"{critical_count + warning_count}개 이상"
            st.metric(
                label="💧 배수지 상태",
                value=reservoir_status,
                delta=reservoir_delta,
                delta_color="normal" if critical_count == 0 and warning_count == 0 else "inverse"
            )

        # 알림 메시지
        if critical_count > 0:
            st.error(f"🚨 {critical_count}개 배수지가 위험 수위입니다!", icon="🚨")
        elif warning_count > 0:
            st.warning(f"⚠️ {warning_count}개 배수지가 경고 수위입니다.", icon="⚠️")

        st.caption(f"⏰ 마지막 업데이트: {get_current_timestamp()}")
    
    def _render_controls(self):
        """제어 패널"""
        st.subheader("⚙️ 빠른 제어")

        automation_active = st.session_state.get('automation_status', False)

        # 4개 버튼 한 행 배치
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button(
                "🚀 시작",
                key="start_auto",
                type="primary",
                use_container_width=True,
                help="이미 실행 중" if automation_active else "자동화 시스템 시작",
                disabled=automation_active
            ):
                self._execute_action("start")

        with col2:
            if st.button(
                "⏹️ 중지",
                key="stop_auto",
                use_container_width=True,
                help="이미 중지됨" if not automation_active else "자동화 시스템 중지",
                disabled=not automation_active
            ):
                self._execute_action("stop")

        with col3:
            if st.button("📊 상태", key="check_status", use_container_width=True, help="시스템 상태 확인"):
                self._execute_action("status")

        with col4:
            if st.button("🔧 점검", key="check_arduino", use_container_width=True, help="Arduino 연결 점검"):
                self._execute_action("debug_arduino")

        # 시각적 피드백
        if automation_active:
            st.info("🟢 자동화 시스템 **활성** (중지하려면 '중지' 버튼 클릭)", icon="ℹ️")
        else:
            st.info("⚫ 자동화 시스템 **비활성** (시작하려면 '시작' 버튼 클릭)", icon="ℹ️")

        # 액션 결과 표시
        if 'last_action_result' in st.session_state and st.session_state.last_action_result:
            result = st.session_state.last_action_result

            if result.get('success'):
                if 'detailed_report' in result:
                    st.success("✅ 작업 완료", icon="✅")
                    with st.expander("📋 상세 결과", expanded=False):
                        st.markdown(result['detailed_report'])
                else:
                    st.success(f"✅ {result.get('message', '완료')}", icon="✅")
            else:
                st.error(f"❌ {result.get('error', '실패')}", icon="❌")

            # 결과 제거
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
    
    def _load_reservoir_data(self):
        """배수지 데이터 로드 (PostgreSQL에서)"""
        try:
            storage = PostgreSQLStorage.get_instance()

            # 최신 데이터 1개 조회
            query = """
                SELECT measured_at,
                       gagok_water_level, gagok_pump_a,
                       haeryong_water_level, haeryong_pump_a
                FROM water
                ORDER BY measured_at DESC
                LIMIT 1
            """

            with storage._connection.cursor() as cursor:
                cursor.execute(query)
                row = cursor.fetchone()

                if row:
                    measured_at, gagok_level, gagok_pump, haeryong_level, haeryong_pump = row

                    # 가곡 배수지 데이터 업데이트
                    if gagok_level is not None:
                        st.session_state.reservoir_data['gagok'].update({
                            'level': float(gagok_level),
                            'pump': 'ON' if gagok_pump and gagok_pump > 0 else 'OFF',
                            'status': self._get_level_status(float(gagok_level)),
                            'last_update': measured_at
                        })

                    # 해룡 배수지 데이터 업데이트
                    if haeryong_level is not None:
                        st.session_state.reservoir_data['haeryong'].update({
                            'level': float(haeryong_level),
                            'pump': 'ON' if haeryong_pump and haeryong_pump > 0 else 'OFF',
                            'status': self._get_level_status(float(haeryong_level)),
                            'last_update': measured_at
                        })

        except Exception as e:
            print(f"배수지 데이터 로드 실패: {e}")
            # 실패 시 기존 데이터 유지

    def _get_level_status(self, level: float) -> str:
        """수위 레벨에 따른 상태 반환"""
        if level <= 10:
            return 'critical'  # 매우 낮음
        elif level <= 30:
            return 'warning'   # 낮음
        elif level <= 70:
            return 'normal'    # 정상
        elif level <= 90:
            return 'high'      # 높음
        else:
            return 'very_high' # 매우 높음

    def _render_reservoir_card(self, reservoir_id: str):
        """배수지 상태 카드"""
        data = st.session_state.reservoir_data.get(reservoir_id, {})
        name = data.get('name', reservoir_id)
        level = data.get('level', 0)
        pump = data.get('pump', 'OFF')
        status = data.get('status', 'unknown')
        last_update = data.get('last_update', 'N/A')

        # 상태 매핑
        status_map = {
            'critical': ('🔴', '매우 낮음', 'inverse', '위험'),
            'warning': ('🟡', '낮음', 'off', '주의'),
            'normal': ('🟢', '정상', 'normal', '정상'),
            'high': ('🔵', '높음', 'off', '높음'),
            'very_high': ('🔵', '매우 높음', 'off', '높음'),
            'unknown': ('⚪', '알 수 없음', 'off', 'N/A')
        }

        icon, status_kr, delta_color, delta_text = status_map.get(status, status_map['unknown'])
        pump_text = '작동중' if pump == 'ON' else '정지'

        with st.container():
            st.markdown(f"#### {icon} {name}")
            st.progress(level / 100, text=f"수위: {level:.1f}% ({status_kr})")

            # 메트릭
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label="💧 수위", value=f"{level:.1f}%", delta=delta_text, delta_color=delta_color)
            with col2:
                pump_delta_color = "normal" if pump == 'ON' else "off"
                st.metric(label="⚙️ 펌프", value=pump_text, delta="작동" if pump == 'ON' else "대기", delta_color=pump_delta_color)

            # 알림
            if status == 'critical':
                st.error("🚨 긴급: 수위 매우 낮음!", icon="🚨")
            elif status == 'warning':
                st.warning("⚠️ 주의: 수위 낮음", icon="⚠️")

            st.caption(f"🕐 {last_update}")

    def _render_water_level_graph(self):
        """수위 그래프 렌더링 (최근 24시간)"""
        st.subheader("📊 24시간 수위 변화 추이")

        try:
            storage = PostgreSQLStorage.get_instance()

            # 최근 24시간 데이터 조회
            query = """
                SELECT measured_at, gagok_water_level, haeryong_water_level
                FROM water
                WHERE measured_at >= NOW() - INTERVAL '24 hours'
                ORDER BY measured_at ASC
            """

            df = pd.read_sql_query(query, storage._connection)

            if len(df) > 0:
                # Plotly 그래프 생성
                fig = go.Figure()

                # 가곡 배수지 라인
                fig.add_trace(go.Scatter(
                    x=df['measured_at'],
                    y=df['gagok_water_level'],
                    mode='lines+markers',
                    name='가곡 배수지',
                    line=dict(color='#007bff', width=3),
                    marker=dict(size=6),
                    hovertemplate='<b>가곡</b><br>시간: %{x}<br>수위: %{y:.1f}%<extra></extra>'
                ))

                # 해룡 배수지 라인
                fig.add_trace(go.Scatter(
                    x=df['measured_at'],
                    y=df['haeryong_water_level'],
                    mode='lines+markers',
                    name='해룡 배수지',
                    line=dict(color='#28a745', width=3),
                    marker=dict(size=6),
                    hovertemplate='<b>해룡</b><br>시간: %{x}<br>수위: %{y:.1f}%<extra></extra>'
                ))

                # 레이아웃 설정
                fig.update_layout(
                    xaxis_title='시간',
                    yaxis_title='수위 (%)',
                    hovermode='x unified',
                    height=450,
                    margin=dict(l=20, r=20, t=20, b=20),
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="center",
                        x=0.5
                    ),
                    plot_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(
                        gridcolor='rgba(128,128,128,0.2)',
                        range=[0, 100]
                    )
                )

                # 수위 경계선 추가 (위험 수준)
                fig.add_hline(y=10, line_dash="dot", line_color="red", line_width=1,
                             annotation_text="매우 낮음", annotation_position="right")
                fig.add_hline(y=30, line_dash="dash", line_color="orange", line_width=1,
                             annotation_text="낮음", annotation_position="right")
                fig.add_hline(y=70, line_dash="dash", line_color="blue", line_width=1,
                             annotation_text="높음", annotation_position="right")

                st.plotly_chart(fig, use_container_width=True)

                # 통계 정보 표시
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📈 데이터 포인트", f"{len(df):,}개")
                with col2:
                    gagok_avg = df['gagok_water_level'].mean()
                    st.metric("💧 가곡 평균", f"{gagok_avg:.1f}%")
                with col3:
                    haeryong_avg = df['haeryong_water_level'].mean()
                    st.metric("💧 해룡 평균", f"{haeryong_avg:.1f}%")
            else:
                st.info("📭 표시할 데이터가 없습니다. 데이터가 수집되면 그래프가 표시됩니다.")

        except Exception as e:
            st.error(f"❌ 그래프 로드 실패: {e}")
            print(f"Graph error: {e}")

    def _render_logs(self):
        """로그 표시"""
        col_header, col_button = st.columns([3, 1])

        with col_header:
            st.subheader("📝 최근 활동 로그")

        with col_button:
            if st.button("🔄", key="refresh_logs", use_container_width=True, help="로그 새로고침"):
                self.async_manager.clear_cache('recent_logs')
                self._load_data_async()
                st.rerun()

        logs = st.session_state.get('last_logs', [])

        if logs:
            tab_all, tab_error, tab_warning, tab_info = st.tabs(["🗂️ 전체", "❌ 에러", "⚠️ 경고", "ℹ️ 정보"])

            with tab_all:
                self._render_log_items(logs[-20:], None)

            with tab_error:
                error_logs = [log for log in logs if log.get('level') in ['ERROR', 'CRITICAL']]
                self._render_log_items(error_logs[-20:], 'ERROR')

            with tab_warning:
                warning_logs = [log for log in logs if log.get('level') == 'WARNING']
                self._render_log_items(warning_logs[-20:], 'WARNING')

            with tab_info:
                info_logs = [log for log in logs if log.get('level') == 'INFO']
                self._render_log_items(info_logs[-20:], 'INFO')
        else:
            st.info("📭 로그 로딩 중...")

    def _render_log_items(self, logs, log_type):
        """로그 아이템 렌더링"""
        if not logs:
            st.info(f"📭 {log_type if log_type else '전체'} 로그 없음")
            return

        # 로그 레벨 아이콘 매핑
        level_icons = {
            'ERROR': '❌', 'CRITICAL': '❌',
            'WARNING': '⚠️',
            'INFO': 'ℹ️'
        }

        for log in reversed(logs):
            level = log.get('level', 'INFO')
            timestamp = log.get('timestamp', '')
            message = log.get('message', '')

            # 시간 추출
            try:
                time_str = timestamp.split(' ')[1][:8] if ' ' in timestamp else timestamp[:8]
            except:
                time_str = timestamp[:8] if timestamp else "N/A"

            icon = level_icons.get(level, 'ℹ️')
            preview = message[:60] + ('...' if len(message) > 60 else '')

            with st.expander(f"{icon} {time_str} | {preview}", expanded=False):
                st.markdown(f"**레벨:** {level}")
                st.markdown(f"**시간:** {timestamp}")
                st.text(message)
    
    def _setup_auto_update(self):
        """자동 업데이트 설정 (새로고침 최소화)"""
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