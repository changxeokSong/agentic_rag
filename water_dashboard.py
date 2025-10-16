# water_dashboard.py - 수위 모니터링 대시보드

import streamlit as st
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime
from utils.logger import setup_logger
from utils.arduino_direct import DirectArduinoComm

logger = setup_logger(__name__)

def init_dashboard_session():
    """대시보드 세션 상태 초기화 (상태 유지 포함)"""
    from utils.state_manager import get_state_manager

    state_manager = get_state_manager()

    # 상태 유지: 글로벌 상태에서 복원
    if 'dashboard_data' not in st.session_state:
        dashboard_data = state_manager.get_dashboard_data()
        # dashboard_data가 dict인 경우 list로 변환
        if isinstance(dashboard_data, dict):
            st.session_state.dashboard_data = []
        elif isinstance(dashboard_data, list):
            st.session_state.dashboard_data = dashboard_data
        else:
            st.session_state.dashboard_data = []
    
    if 'last_update' not in st.session_state:
        st.session_state.last_update = None
    
    # 사용자 인터랙션 추적을 위한 상태 추가
    if 'user_interaction' not in st.session_state:
        st.session_state.user_interaction = False
    
    if 'pump_control_in_progress' not in st.session_state:
        st.session_state.pump_control_in_progress = False
    
    # 수동 새로고침 여부 추적
    if 'manual_refresh_clicked' not in st.session_state:
        st.session_state.manual_refresh_clicked = False
    
    # 마지막으로 성공한 데이터 저장 (상태 유지용)
    if 'last_successful_data' not in st.session_state:
        st.session_state.last_successful_data = state_manager.get_last_successful_data()
    
    # 직접 아두이노 통신 객체 초기화 (app에서 공유된 상태 사용)
    if 'direct_arduino' not in st.session_state:
        # app에서 공유된 아두이노 연결이 있으면 사용, 없으면 새로 생성
        if 'shared_arduino' in st.session_state and st.session_state.shared_arduino:
            st.session_state.direct_arduino = st.session_state.shared_arduino
        else:
            st.session_state.direct_arduino = DirectArduinoComm()
            # 주의: 객체만 생성하고 자동 연결은 하지 않음

def get_water_level_data():
    """아두이노에서 현재 수위 데이터 직접 가져오기 (LLM 우회)"""
    try:
        arduino_comm = st.session_state.direct_arduino
        
        # 연결 확인 (자동 연결 제거)
        if not arduino_comm.is_connected():
            return {"error": "아두이노에 연결되지 않았습니다. 사이드바에서 '🔗 아두이노 연결' 버튼을 클릭하세요."}
        
        # 수위 데이터 읽기 (직접 통신)
        water_result = arduino_comm.read_water_level()
        
        # 펌프 상태 읽기 (직접 통신)
        pump_result = arduino_comm.get_pump_status()
        
        return {
            "water_data": water_result,
            "pump_data": pump_result,
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"수위 데이터 가져오기 오류: {e}")
        return {"error": str(e)}

def create_water_level_gauge(channel, level, status_color, channel_name=None):
    """수위 게이지 차트 생성"""
    # 채널 이름 매핑
    if channel_name is None:
        if channel == 2:
            channel_name = "가곡 배수지"
        elif channel == 8:
            channel_name = "해룡 배수지"
        else:
            channel_name = f"채널 {channel}"

    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = level,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': f"{channel_name} 수위 (m)"},
        number = {'suffix': "m"},
        gauge = {
            'axis': {'range': [None, 120]},
            'bar': {'color': status_color},
            'steps': [
                {'range': [0, 30], 'color': "lightgray"},
                {'range': [30, 70], 'color': "gray"},
                {'range': [70, 120], 'color': "darkgray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 100
            }
        }
    ))
    
    fig.update_layout(
        height=300,
        font={'color': "darkblue", 'family': "Arial"},
        margin=dict(l=20, r=20, t=60, b=20)
    )
    
    return fig

def create_historical_chart(data_history):
    """시간대별 수위 변화 차트 생성"""
    if not data_history:
        return None
        
    df = pd.DataFrame(data_history)
    
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('수위 변화', '펌프 상태'),
        vertical_spacing=0.1,
        specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
    )
    
    # 수위 데이터 차트 - 채널별로 데이터 그룹화
    if 'channel_levels' in df.columns:
        # 채널별로 데이터 수집
        channel_data = {}
        for _, row in df.iterrows():
            if row['channel_levels'] and isinstance(row['channel_levels'], dict):
                for channel, level in row['channel_levels'].items():
                    try:
                        channel_key = int(channel)
                    except (ValueError, TypeError):
                        continue
                    
                    if channel_key not in channel_data:
                        channel_data[channel_key] = {'timestamps': [], 'levels': []}
                    channel_data[channel_key]['timestamps'].append(row['timestamp'])
                    channel_data[channel_key]['levels'].append(level)
        
        # 채널별로 하나의 trace만 생성 (채널 1=가곡, 채널 2=해룡)
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
        channel_names = {2: '가곡 배수지', 8: '해룡 배수지'}

        for i, (channel, data) in enumerate(sorted(channel_data.items())):
            channel_label = channel_names.get(channel, f'채널 {channel}')
            fig.add_trace(
                go.Scatter(
                    x=data['timestamps'],
                    y=data['levels'],
                    mode='lines+markers',
                    name=channel_label,
                    line=dict(width=2, color=colors[i % len(colors)]),
                    connectgaps=True
                ),
                row=1, col=1
            )
    
    # 펌프 상태 차트 (On=1, Off=0) - 펌프별로 데이터 그룹화
    pump1_data = {'timestamps': [], 'status': []}
    pump2_data = {'timestamps': [], 'status': []}
    
    for _, row in df.iterrows():
        if row.get('pump_status') and isinstance(row['pump_status'], dict):
            pump1_status = 1 if row['pump_status'].get('pump1') == 'ON' else 0
            pump2_status = 1 if row['pump_status'].get('pump2') == 'ON' else 0
            
            pump1_data['timestamps'].append(row['timestamp'])
            pump1_data['status'].append(pump1_status)
            
            pump2_data['timestamps'].append(row['timestamp'])
            pump2_data['status'].append(pump2_status)
    
    # 펌프별로 하나의 trace만 생성
    if pump1_data['timestamps']:
        fig.add_trace(
            go.Scatter(
                x=pump1_data['timestamps'],
                y=pump1_data['status'],
                mode='lines+markers',
                name='펌프 1',
                line=dict(color='#dc2626', width=3),
                connectgaps=True
            ),
            row=2, col=1
        )
    
    if pump2_data['timestamps']:
        fig.add_trace(
            go.Scatter(
                x=pump2_data['timestamps'],
                y=pump2_data['status'],
                mode='lines+markers',
                name='펌프 2',
                line=dict(color='#2563eb', width=3),
                connectgaps=True
            ),
            row=2, col=1
        )
    
    fig.update_layout(
        height=600,
        showlegend=True,
        title_text="수위 및 펌프 상태 히스토리"
    )
    
    fig.update_xaxes(title_text="시간", row=2, col=1)
    fig.update_yaxes(title_text="수위 (m)", row=1, col=1)
    fig.update_yaxes(title_text="펌프 상태", row=2, col=1, range=[-0.1, 1.1])
    
    return fig

def control_pump(pump_id, action, duration=None):
    """펌프 직접 제어 함수 (LLM 우회)"""
    try:
        arduino_comm = st.session_state.direct_arduino
        
        # 연결 확인 (자동 연결 제거)
        if not arduino_comm.is_connected():
            return {"error": "아두이노에 연결되지 않았습니다. 사이드바에서 '🔗 아두이노 연결' 버튼을 클릭하세요."}
        
        # 펌프 제어 명령 실행 (직접 통신)
        if action == "on":
            result = arduino_comm.control_pump(pump_id, "ON", duration)
        else:
            result = arduino_comm.control_pump(pump_id, "OFF")
        
        return result
        
    except Exception as e:
        logger.error(f"펌프 제어 오류: {e}")
        return {"error": str(e)}

def main():
    """대시보드 메인 함수"""
    st.set_page_config(
        page_title="수위 모니터링 대시보드",
        page_icon="💧",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 다크 모드 호환 CSS 추가 (app.py와 동일)
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
    
    # 세션 초기화
    init_dashboard_session()
    
    # 아두이노 연결 상태 확인 (시스템 초기화 불필요)
    arduino_comm = st.session_state.direct_arduino
    is_arduino_connected = arduino_comm.is_connected()
    
    # 연결 상태 표시 (실제 연결 상태만 기준)
    if not is_arduino_connected:
        connection_status = "❌ 연결 안됨"
        status_color = "#dc2626"
    elif arduino_comm.arduino_port == "SIMULATION":
        connection_status = "🔄 시뮬레이션 모드"
        status_color = "#f59e0b"
    elif is_arduino_connected and arduino_comm.arduino_port:
        # 실제 연결된 상태에서만 포트 이름 표시
        port_name = arduino_comm.arduino_port
        if "\\" in port_name:
            port_name = port_name.split("\\")[-1]
        elif "/" in port_name:
            port_name = port_name.split("/")[-1]
        connection_status = f"✅ 연결됨 ({port_name})"
        status_color = "#16a34a"
    else:
        connection_status = "❌ 연결 안됨"
        status_color = "#dc2626"
    
    st.sidebar.markdown(f"""
    <div style="padding: 12px; background: {status_color}15; border: 2px solid {status_color}; 
                border-radius: 8px; margin: 10px 0;">
        <h4 style="margin: 0; color: {status_color};">아두이노 상태</h4>
        <p style="margin: 5px 0 0 0; color: {status_color}; font-weight: bold;">{connection_status}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 연결 제어 버튼 (연결되지 않은 경우만 표시)
    if not is_arduino_connected:
        if st.sidebar.button("🔗 아두이노 연결", type="primary", use_container_width=True):
            with st.sidebar:
                with st.spinner("아두이노 연결 중..."):
                    if arduino_comm.connect():
                        st.success("아두이노 연결 성공!")
                        st.rerun()
                    else:
                        st.error("아두이노 연결 실패!")
    else:
        if st.sidebar.button("🔌 연결 해제", type="secondary", use_container_width=True):
            arduino_comm.disconnect()
            st.sidebar.success("연결이 해제되었습니다.")
            st.rerun()
    
    # 메인 앱으로 돌아가기 버튼
    if st.sidebar.button("🏠 메인 앱으로 돌아가기", type="primary", use_container_width=True):
        st.session_state.page = "main"
        st.rerun()
    
    # 시스템 재초기화 버튼 (필요시에만)
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 대시보드 재초기화", type="secondary", use_container_width=True):
        # 대시보드 데이터만 초기화 (아두이노 연결은 유지)
        st.session_state.dashboard_data = []
        st.session_state.last_update = None
        st.session_state.last_successful_data = None
        st.session_state.manual_refresh_clicked = False
        
        st.sidebar.success("대시보드가 재초기화되었습니다!")
        st.rerun()
    
    # 헤더
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                border-radius: 15px; margin-bottom: 2rem; color: white; 
                box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);">
        <h1 style="margin: 0; font-size: 2.5em; font-weight: 700; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); color: white !important;">
            💧 수위 모니터링 대시보드
        </h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.2em; opacity: 0.9; color: white !important;">
            실시간 수위 센서 및 펌프 제어 시스템
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # 상단 제어 패널
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # 아두이노가 연결되지 않은 경우 버튼 비활성화
        refresh_disabled = not is_arduino_connected
        if st.button("🔄 수동 새로고침", type="primary", use_container_width=True, disabled=refresh_disabled):
            # 수동 새로고침 시 플래그 설정
            st.session_state.manual_refresh_clicked = True
            st.session_state.user_interaction = True
            st.rerun()
        
        if refresh_disabled:
            st.caption("⚠️ 아두이노 연결이 필요합니다")
    
    with col2:
        if st.button("🏠 메인으로", use_container_width=True):
            st.session_state.page = "main"
            st.rerun()
    
    # 현재 데이터 가져오기 (아두이노 연결 상태에 따라)
    current_data = None
    should_fetch_data = st.session_state.manual_refresh_clicked
    
    if not is_arduino_connected:
        # 연결되지 않은 경우
        if st.session_state.last_successful_data:
            current_data = st.session_state.last_successful_data
            st.warning("⚠️ 아두이노 연결이 끊어졌습니다. 마지막 데이터를 표시합니다.")
        else:
            st.error("❌ **아두이노 연결이 필요합니다**")
            st.info("💡 사이드바에서 '🔗 아두이노 연결' 버튼을 클릭하여 연결하세요.")
            current_data = {"error": "아두이노가 연결되지 않았습니다"}
    elif should_fetch_data:
        # 연결된 상태에서 새로고침 요청
        current_data = get_water_level_data()
        st.session_state.manual_refresh_clicked = False
        
        # 성공한 데이터인 경우 저장
        if current_data and "error" not in current_data:
            # 상태 관리자에도 저장
            from utils.state_manager import get_state_manager
            state_manager = get_state_manager()
            state_manager.save_last_successful_data(current_data)
    else:
        # 연결되어 있지만 새로고침하지 않은 경우
        if st.session_state.last_successful_data:
            current_data = st.session_state.last_successful_data
            st.info("ℹ️ 이전 데이터를 표시합니다. 최신 데이터를 보려면 '🔄 수동 새로고침' 버튼을 클릭하세요.")
        else:
            st.info("📊 데이터를 가져오려면 '🔄 수동 새로고침' 버튼을 클릭하세요.")
            current_data = {"error": "새로고침이 필요합니다"}
    
    if current_data and "error" not in current_data:
        water_data = current_data.get("water_data", {})
        pump_data = current_data.get("pump_data", {})
        
        # 히스토리에 추가 (성공한 데이터만)
        if water_data.get("success", False):
            history_entry = {
                "timestamp": current_data["timestamp"],
                "channel_levels": water_data.get("channel_levels", {}),
                "average_level": water_data.get("average_water_level", 0),
                "pump_status": pump_data.get("pump_status", {})
            }
            
            # 히스토리 관리 (최대 100개 항목)
            # dashboard_data가 dict인 경우 list로 변환 (안전 장치)
            if isinstance(st.session_state.dashboard_data, dict):
                st.session_state.dashboard_data = []

            st.session_state.dashboard_data.append(history_entry)
            if len(st.session_state.dashboard_data) > 100:
                st.session_state.dashboard_data = st.session_state.dashboard_data[-100:]
            
            # 상태 관리자에도 저장
            from utils.state_manager import get_state_manager
            state_manager = get_state_manager()
            state_manager.save_dashboard_data(history_entry)
            
            st.session_state.last_update = current_data["timestamp"]
        
        # 마지막 업데이트 시간 표시 (상단에 위치)
        display_time = None
        if st.session_state.last_update:
            display_time = st.session_state.last_update
        elif st.session_state.last_successful_data and current_data == st.session_state.last_successful_data:
            # 저장된 데이터를 사용하는 경우 해당 데이터의 타임스탬프 사용
            display_time = st.session_state.last_successful_data.get("timestamp")
        
        if display_time:
            if isinstance(display_time, datetime):
                time_str = display_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                time_str = str(display_time)
            
            # 저장된 데이터를 사용하는지 확인
            is_cached = (st.session_state.last_successful_data and 
                        current_data == st.session_state.last_successful_data and 
                        not should_fetch_data)
            
            status_text = "마지막 업데이트" if not is_cached else "마지막 업데이트 (저장된 데이터)"
            
            st.markdown(f"""
            <div style="text-align: center; padding: 12px; background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); 
                       border-radius: 10px; margin: 15px 0; border: 1px solid #cbd5e1;
                       box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <div style="font-size: 0.9em; font-weight: 600; color: #475569; margin-bottom: 4px;">
                    📅 {status_text}
                </div>
                <div style="font-size: 1.1em; font-weight: 700; color: #1e293b;">
                    {time_str}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # 현재 상태 표시
        st.markdown("## 📊 현재 상태")
        
        if water_data.get("success", False):
            channel_levels = water_data.get("channel_levels", {})
            
            # 시뮬레이션 모드 표시
            if arduino_comm.arduino_port == "SIMULATION" or water_data.get("simulation", False):
                st.info("🔄 **시뮬레이션 모드** - 실제 센서 데이터가 아닙니다")
            
            # 수위 게이지들 (채널 1, 2만 표시)
            # 채널 1, 2만 필터링
            filtered_channels = {k: v for k, v in channel_levels.items() if k in [2, 8]}
            gauge_cols = st.columns(len(filtered_channels) if filtered_channels else 2)

            channel_names = {2: '가곡 배수지', 8: '해룡 배수지'}

            for i, (channel, level) in enumerate(sorted(filtered_channels.items())):
                with gauge_cols[i]:
                    # 상태 색상 결정
                    if level <= 10:
                        status_color = "#dc2626"  # 빨강
                        status_text = "매우 낮음"
                    elif level <= 30:
                        status_color = "#f59e0b"  # 주황
                        status_text = "낮음"
                    elif level <= 70:
                        status_color = "#10b981"  # 초록
                        status_text = "보통"
                    elif level <= 90:
                        status_color = "#3b82f6"  # 파랑
                        status_text = "높음"
                    else:
                        status_color = "#8b5cf6"  # 보라
                        status_text = "매우 높음"

                    # 채널 이름
                    channel_label = channel_names.get(channel, f"채널 {channel}")

                    # 게이지 차트
                    fig = create_water_level_gauge(channel, level, status_color, channel_label)
                    st.plotly_chart(fig, use_container_width=True)

                    # 상태 텍스트
                    simulation_badge = " (시뮬레이션)" if (arduino_comm.arduino_port == "SIMULATION" or water_data.get("simulation", False)) else ""
                    st.markdown(f"""
                    <div style="text-align: center; padding: 10px; background: {status_color}20;
                                border-radius: 10px; border: 2px solid {status_color};">
                        <h4 style="margin: 0; color: {status_color};">{channel_label}{simulation_badge}</h4>
                        <p style="margin: 5px 0; font-size: 1.2em; font-weight: bold;">{level:.1f}m</p>
                        <p style="margin: 0; color: {status_color};">{status_text}</p>
                    </div>
                    """, unsafe_allow_html=True)
        
        else:
            st.error(f"수위 데이터 오류: {water_data.get('error', '알 수 없는 오류')}")
            # 에러 상황에서도 기본 레이아웃 유지
            st.info("💡 **해결 방법**: 사이드바에서 아두이노 연결을 확인하거나 '🔗 아두이노 연결' 버튼을 클릭하세요")
    
    else:
        st.error(f"데이터 로드 실패: {current_data.get('error', '알 수 없는 오류') if current_data else '데이터 없음'}")
    
    st.markdown("---")
    
    # 펌프 제어 패널
    st.markdown("## ⚙️ 펌프 제어")
    
    pump_col1, pump_col2 = st.columns(2)
    
    # 현재 펌프 상태 가져오기
    current_pump_status = {}
    if current_data and "error" not in current_data:
        pump_data = current_data.get("pump_data", {})
        if pump_data.get("success", False):
            current_pump_status = pump_data.get("pump_status", {})
    
    with pump_col1:
        st.markdown("### 💧 펌프 1 (급수 펌프)")
        st.caption("외부 → 가곡 배수지로 물 공급")
        pump1_status = current_pump_status.get("pump1", "Unknown")
        
        # 상태 표시
        if pump1_status == "ON":
            st.markdown("""
            <div style="padding: 15px; background: #10b98120; border: 2px solid #10b981; 
                        border-radius: 10px; text-align: center;">
                <h3 style="margin: 0; color: #10b981;">🟢 작동 중</h3>
            </div>
            """, unsafe_allow_html=True)
        elif pump1_status == "OFF":
            st.markdown("""
            <div style="padding: 15px; background: #dc262620; border: 2px solid #dc2626; 
                        border-radius: 10px; text-align: center;">
                <h3 style="margin: 0; color: #dc2626;">🔴 정지</h3>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="padding: 15px; background: #6b728020; border: 2px solid #6b7280; 
                        border-radius: 10px; text-align: center;">
                <h3 style="margin: 0; color: #6b7280;">❓ 알 수 없음</h3>
            </div>
            """, unsafe_allow_html=True)
        
        # 패딩 추가
        st.markdown("<div style='margin: 15px 0;'></div>", unsafe_allow_html=True)
        
        # 제어 버튼
        col1_1, col1_2 = st.columns(2)
        pump_control_disabled = not is_arduino_connected
        
        with col1_1:
            if st.button("🟢 급수 펌프 켜기", key="pump1_on", use_container_width=True, disabled=pump_control_disabled):
                st.session_state.pump_control_in_progress = True
                st.session_state.user_interaction = True
                time.sleep(1)
                result = control_pump(1, "on")
                if result.get("success", False):
                    st.success("급수 펌프(펌프1)가 켜졌습니다!")
                    st.session_state.manual_refresh_clicked = True
                    st.session_state.pump_control_in_progress = False
                    st.rerun()
                else:
                    st.error(f"펌프 제어 실패: {result.get('error', '알 수 없는 오류')}")
                    st.session_state.pump_control_in_progress = False

        with col1_2:
            if st.button("🔴 급수 펌프 끄기", key="pump1_off", use_container_width=True, disabled=pump_control_disabled):
                st.session_state.pump_control_in_progress = True
                st.session_state.user_interaction = True
                result = control_pump(1, "off")
                if result.get("success", False):
                    st.success("급수 펌프(펌프1)가 꺼졌습니다!")
                    st.session_state.manual_refresh_clicked = True
                    st.session_state.pump_control_in_progress = False
                    st.rerun()
                else:
                    st.error(f"펌프 제어 실패: {result.get('error', '알 수 없는 오류')}")
                    st.session_state.pump_control_in_progress = False
        
        if pump_control_disabled:
            st.caption("⚠️ 펌프 제어를 위해서는 아두이노 연결이 필요합니다")
    
    with pump_col2:
        st.markdown("### 🔄 펌프 2 (이송 펌프)")
        st.caption("가곡 배수지 → 해룡 배수지로 물 이송")
        pump2_status = current_pump_status.get("pump2", "Unknown")  
        
        # 상태 표시
        if pump2_status == "ON":
            st.markdown("""
            <div style="padding: 15px; background: #10b98120; border: 2px solid #10b981; 
                        border-radius: 10px; text-align: center;">
                <h3 style="margin: 0; color: #10b981;">🟢 작동 중</h3>
            </div>
            """, unsafe_allow_html=True)
        elif pump2_status == "OFF":
            st.markdown("""
            <div style="padding: 15px; background: #dc262620; border: 2px solid #dc2626; 
                        border-radius: 10px; text-align: center;">
                <h3 style="margin: 0; color: #dc2626;">🔴 정지</h3>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="padding: 15px; background: #6b728020; border: 2px solid #6b7280; 
                        border-radius: 10px; text-align: center;">
                <h3 style="margin: 0; color: #6b7280;">❓ 알 수 없음</h3>
            </div>
            """, unsafe_allow_html=True)
        
        # 패딩 추가
        st.markdown("<div style='margin: 15px 0;'></div>", unsafe_allow_html=True)
        
        # 제어 버튼
        col2_1, col2_2 = st.columns(2)
        with col2_1:
            if st.button("🟢 이송 펌프 켜기", key="pump2_on", use_container_width=True, disabled=pump_control_disabled):
                st.session_state.pump_control_in_progress = True
                st.session_state.user_interaction = True
                result = control_pump(2, "on")
                if result.get("success", False):
                    st.success("이송 펌프(펌프2)가 켜졌습니다!")
                    st.session_state.manual_refresh_clicked = True
                    st.session_state.pump_control_in_progress = False
                    st.rerun()
                else:
                    st.error(f"펌프 제어 실패: {result.get('error', '알 수 없는 오류')}")
                    st.session_state.pump_control_in_progress = False
        
        with col2_2:
            if st.button("🔴 이송 펌프 끄기", key="pump2_off", use_container_width=True, disabled=pump_control_disabled):
                st.session_state.pump_control_in_progress = True
                st.session_state.user_interaction = True
                result = control_pump(2, "off")
                if result.get("success", False):
                    st.success("이송 펌프(펌프2)가 꺼졌습니다!")
                    st.session_state.manual_refresh_clicked = True
                    st.session_state.pump_control_in_progress = False
                    st.rerun()
                else:
                    st.error(f"펌프 제어 실패: {result.get('error', '알 수 없는 오류')}")
                    st.session_state.pump_control_in_progress = False
        
        if pump_control_disabled:
            st.caption("⚠️ 펌프 제어를 위해서는 아두이노 연결이 필요합니다")
    
    st.markdown("---")
    
    # 히스토리 차트
    # dashboard_data가 list인지 확인 (안전 장치)
    if not isinstance(st.session_state.dashboard_data, list):
        st.session_state.dashboard_data = []

    if st.session_state.dashboard_data:
        st.markdown("## 📈 히스토리")

        # 시간 범위 선택 (기본값 추적)
        if 'history_time_range' not in st.session_state:
            st.session_state.history_time_range = 30

        time_range = st.selectbox(
            "표시할 시간 범위",
            options=[10, 30, 60, 100],
            index=[10, 30, 60, 100].index(st.session_state.history_time_range) if st.session_state.history_time_range in [10, 30, 60, 100] else 1,
            format_func=lambda x: f"최근 {x}개 데이터",
            key="history_time_range_select"
        )

        # 시간 범위 변경 시 사용자 인터랙션 플래그 설정
        if time_range != st.session_state.history_time_range:
            st.session_state.history_time_range = time_range
            st.session_state.user_interaction = True

        # 데이터 필터링
        recent_data = st.session_state.dashboard_data[-time_range:]
        
        # 히스토리 차트 생성
        history_fig = create_historical_chart(recent_data)
        if history_fig:
            st.plotly_chart(history_fig, use_container_width=True)
        else:
            st.info("히스토리 데이터가 부족합니다.")
    
    # 자동 새로고침 기능 제거됨: 관련 로직 삭제

if __name__ == "__main__":
    main()