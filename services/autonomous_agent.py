# services/autonomous_agent.py - LM Studio 기반 자율적 자동화 AI 에이전트

import asyncio
import threading
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from models.lm_studio import LMStudioClient
from services.logging_system import get_automation_logger, LogLevel, EventType
from services.database_connector import get_database_connector
from utils.logger import setup_logger
from enum import Enum
from dataclasses import dataclass

logger = setup_logger(__name__)

class AlertLevel(Enum):
    """알림 레벨"""
    INFO = "info"
    WARNING = "warning" 
    CRITICAL = "critical"
    EMERGENCY = "emergency"

@dataclass
class UserNotification:
    """사용자 알림"""
    id: str
    timestamp: str
    level: AlertLevel
    title: str
    message: str
    action_required: bool = False
    action_id: str = None

# 글로벌 상태는 utils/state_manager.py로 이관됨
from utils.state_manager import get_state_manager

@dataclass
class SystemState:
    """시스템 현재 상태"""
    timestamp: datetime
    reservoir_data: Dict[str, Dict[str, Any]]
    arduino_connected: bool
    recent_alerts: List[Dict[str, Any]]
    system_health: str
    automation_active: bool

class AutonomousAgent:
    """LM Studio 기반 자율적 AI 에이전트"""
    
    # 시스템 설정 상수
    DECISION_INTERVAL_SECONDS = 30  # 의사결정 주기 (초)
    ERROR_RETRY_DELAY_SECONDS = 10  # 오류 시 재시도 지연 시간 (초)
    MAX_RETRY_ATTEMPTS = 3  # 최대 재시도 횟수
    
    def __init__(self, lm_client: LMStudioClient):
        self.lm_client = lm_client
        self.automation_logger = get_automation_logger()
        self.is_running = False
        self.monitoring_thread = None
        self.decision_interval = self.DECISION_INTERVAL_SECONDS
        
        # AI 에이전트 프롬프트
        self.system_prompt = """당신은 배수지 수위 관리 전문 AI 에이전트입니다.

주요 역할:
1. 4개 배수지(automation, reservoir_1, reservoir_2, reservoir_3)의 수위를 실시간 모니터링
2. 위험 상황 감지 시 즉시 대응 조치 실행
3. 예방적 관리를 통한 시스템 최적화
4. 모든 의사결정을 로그에 기록

판단 기준:
- 수위 95% 이상: 긴급 상황 (즉시 펌프 ON)
- 수위 80-95%: 주의 상황 (펌프 AUTO 또는 ON)
- 수위 20% 미만: 점검 필요 (펌프 OFF)
- 펌프 연속 실패: 알림 발송

응답 형식: JSON만 출력
{
  "decision": "판단 결과 (NORMAL/CAUTION/EMERGENCY/MAINTENANCE)",
  "actions": [
    {
      "reservoir_id": "대상 배수지",
      "action": "실행할 작업 (PUMP_ON/PUMP_OFF/PUMP_AUTO/ALERT)",
      "reason": "판단 이유"
    }
  ],
  "message": "상황 요약 메시지",
  "priority": "우선순위 (LOW/MEDIUM/HIGH/CRITICAL)"
}

현재 시스템 상태를 분석하고 필요한 조치를 결정하세요."""

    def start_monitoring(self):
        """자동화 모니터링 시작"""
        if self.is_running:
            logger.warning("이미 자동화가 실행 중입니다")
            return False
        
        self.is_running = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        self.automation_logger.info(EventType.SYSTEM, "system", "자율적 AI 에이전트 모니터링 시작")
        logger.info("자율적 AI 에이전트가 시작되었습니다")
        return True
    
    def stop_monitoring(self):
        """자동화 모니터링 중지"""
        if not self.is_running:
            logger.warning("자동화가 실행되지 않고 있습니다")
            return False
        
        self.is_running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        self.automation_logger.info(EventType.SYSTEM, "system", "자율적 AI 에이전트 모니터링 중지")
        logger.info("자율적 AI 에이전트가 중지되었습니다")
        return True
    
    def _monitoring_loop(self):
        """메인 모니터링 루프"""
        logger.info("AI 에이전트 모니터링 루프 시작")
        
        while self.is_running:
            try:
                # 현재 시스템 상태 수집
                system_state = self._collect_system_state()
                
                # AI에게 상황 분석 요청
                decision = self._make_ai_decision(system_state)
                
                if decision:
                    # AI 결정사항 실행
                    self._execute_decision(decision)
                
                # 다음 판단까지 대기
                time.sleep(self.decision_interval)
                
            except Exception as e:
                logger.error(f"모니터링 루프 오류: {e}")
                self.automation_logger.error(EventType.ERROR, "system", f"모니터링 오류: {str(e)}")
                time.sleep(self.ERROR_RETRY_DELAY_SECONDS)  # 오류 시 재시도 지연
        
        logger.info("AI 에이전트 모니터링 루프 종료")
    
    def _collect_system_state(self) -> SystemState:
        """현재 시스템 상태 수집 - 실제 데이터베이스 기반"""
        try:
            # 데이터베이스에서 실시간 데이터 수집
            db_connector = get_database_connector()
            reservoir_data = db_connector.get_latest_water_data()
            
            if not reservoir_data:
                # 데이터베이스에서 데이터를 가져올 수 없는 경우 글로벌 상태 사용
                logger.warning("데이터베이스에서 데이터 조회 실패, 글로벌 상태 사용")
                state_manager = get_state_manager()
                state = state_manager.load_state()
                reservoir_data = state.get('reservoir_data', {})
            else:
                # 성공적으로 데이터베이스에서 가져온 경우 글로벌 상태 업데이트
                state_manager = get_state_manager()
                state = state_manager.load_state()
                state['reservoir_data'] = reservoir_data
                state_manager.save_state(state)
                logger.info(f"데이터베이스에서 {len(reservoir_data)}개 배수지 데이터 수집 완료")
            
            state_manager = get_state_manager()
            state = state_manager.load_state()
            arduino_connected = state.get('arduino_connected', False)
            
            # 최근 알림 조회
            recent_logs = self.automation_logger.get_recent_logs(limit=10)
            recent_alerts = [log for log in recent_logs if log.get('level') in ['WARNING', 'ERROR', 'CRITICAL']]
            
            # 시스템 건강 상태 판단
            critical_reservoirs = [
                res_id for res_id, data in reservoir_data.items() 
                if data['water_level'] >= data['alert_level']
            ]
            
            if critical_reservoirs:
                system_health = "CRITICAL"
            elif any(data['water_level'] >= data['alert_level'] * 0.8 for data in reservoir_data.values()):
                system_health = "WARNING"
            else:
                system_health = "NORMAL"
            
            return SystemState(
                timestamp=datetime.now(),
                reservoir_data=reservoir_data,
                arduino_connected=arduino_connected,
                recent_alerts=recent_alerts,
                system_health=system_health,
                automation_active=True
            )
            
        except Exception as e:
            logger.error(f"시스템 상태 수집 오류: {e}")
            # 기본값 반환
            return SystemState(
                timestamp=datetime.now(),
                reservoir_data={},
                arduino_connected=False,
                recent_alerts=[],
                system_health="ERROR",
                automation_active=False
            )
    
    def _make_ai_decision(self, system_state: SystemState) -> Optional[Dict[str, Any]]:
        """AI에게 의사결정 요청"""
        try:
            # 글로벌 상태 가져오기
            state_manager = get_state_manager()
            global_state = state_manager.load_state()
            
            # 시스템 상태를 AI가 이해할 수 있는 형태로 변환
            state_summary = {
                "timestamp": system_state.timestamp.isoformat(),
                "reservoirs": system_state.reservoir_data,
                "arduino_connected": system_state.arduino_connected,
                "system_health": system_state.system_health,
                "recent_alerts_count": len(system_state.recent_alerts),
                "simulation_mode": global_state.get('simulation_mode', True)
            }
            
            user_message = f"""현재 시스템 상태:
{json.dumps(state_summary, indent=2, ensure_ascii=False)}

위 상태를 분석하고 필요한 조치를 JSON 형식으로 응답해주세요."""
            
            # LM Studio에 요청 (OpenAI 클라이언트 방식)
            try:
                response = self.lm_client.client.chat.completions.create(
                    model=self.lm_client.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.3,
                    max_tokens=1000
                )
            except Exception as api_error:
                logger.error(f"LM Studio API 호출 오류: {api_error}")
                return None
            
            if response and hasattr(response, 'choices') and len(response.choices) > 0:
                ai_response = response.choices[0].message.content
                
                # JSON 파싱 시도
                try:
                    # JSON 부분만 추출 (```json 코드 블록 처리)
                    if "```json" in ai_response:
                        json_start = ai_response.find("```json") + 7
                        json_end = ai_response.find("```", json_start)
                        ai_response = ai_response[json_start:json_end].strip()
                    elif "```" in ai_response:
                        json_start = ai_response.find("```") + 3
                        json_end = ai_response.rfind("```")
                        ai_response = ai_response[json_start:json_end].strip()
                    
                    decision = json.loads(ai_response)
                    
                    # 의사결정 로그 기록
                    self.automation_logger.log(
                        LogLevel.INFO,
                        EventType.DECISION,
                        "system",
                        f"AI 판단: {decision.get('decision', 'UNKNOWN')} - {decision.get('message', '')}",
                        {"ai_decision": decision, "system_state": state_summary}
                    )
                    
                    return decision
                    
                except json.JSONDecodeError as e:
                    logger.error(f"AI 응답 JSON 파싱 실패: {e}")
                    logger.error(f"AI 원본 응답: {ai_response}")
                    self.automation_logger.error(EventType.ERROR, "system", f"AI 응답 파싱 실패: {str(e)}")
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"AI 의사결정 요청 오류: {e}")
            self.automation_logger.error(EventType.ERROR, "system", f"AI 의사결정 오류: {str(e)}")
            return None
    
    def _execute_decision(self, decision: Dict[str, Any]):
        """AI 결정사항 실행"""
        try:
            actions = decision.get('actions', [])
            priority = decision.get('priority', 'LOW')
            
            for action in actions:
                reservoir_id = action.get('reservoir_id', 'unknown')
                action_type = action.get('action', 'NONE')
                reason = action.get('reason', 'AI 판단')
                
                # 액션 실행
                if action_type == 'PUMP_ON':
                    self._control_pump(reservoir_id, 'ON', reason)
                elif action_type == 'PUMP_OFF':
                    self._control_pump(reservoir_id, 'OFF', reason)
                elif action_type == 'PUMP_AUTO':
                    self._control_pump(reservoir_id, 'AUTO', reason)
                elif action_type == 'ALERT':
                    self._send_alert(reservoir_id, reason, priority)
                
                # 실행 로그
                self.automation_logger.log(
                    LogLevel.WARNING if priority in ['HIGH', 'CRITICAL'] else LogLevel.INFO,
                    EventType.ACTION,
                    reservoir_id,
                    f"AI 액션 실행: {action_type} - {reason}",
                    {"action": action, "priority": priority}
                )
            
        except Exception as e:
            logger.error(f"AI 결정사항 실행 오류: {e}")
            self.automation_logger.error(EventType.ERROR, "system", f"액션 실행 오류: {str(e)}")
    
    def _control_pump(self, reservoir_id: str, status: str, reason: str):
        """펌프 제어 - Arduino 하드웨어 제어 + 데이터베이스 연동"""
        arduino_success = False
        db_success = False
        
        try:
            # === 1. Arduino 하드웨어 펌프 제어 시도 ===
            arduino_result = self._control_arduino_pump(reservoir_id, status, reason)
            arduino_success = arduino_result.get('success', False)
            
            # === 2. 데이터베이스에 펌프 상태 업데이트 ===
            try:
                db_connector = get_database_connector()
                db_success = db_connector.update_pump_status(reservoir_id, status)
            except Exception as db_e:
                logger.warning(f"데이터베이스 업데이트 실패: {db_e}")
                db_success = False
            
            # === 3. 글로벌 상태 업데이트 ===
            if arduino_success or db_success:
                try:
                    state_manager = get_state_manager()
                    state = state_manager.load_state()
                    if 'pump_status' not in state:
                        state['pump_status'] = {}
                    state['pump_status'][reservoir_id] = status
                    state_manager.save_state(state)
                except Exception as state_e:
                    logger.warning(f"글로벌 상태 업데이트 실패: {state_e}")
            
            # === 4. 결과에 따른 로깅 ===
            if arduino_success and db_success:
                logger.info(f"AI 펌프 제어 완전 성공: {reservoir_id} -> {status} (이유: {reason})")
                self.automation_logger.info(
                    EventType.ACTION,
                    reservoir_id,
                    f"AI 펌프 제어 완전 성공: {status}",
                    {
                        "pump_status": status,
                        "reason": reason,
                        "arduino_success": True,
                        "database_updated": True,
                        "arduino_details": arduino_result
                    }
                )
            elif arduino_success:
                logger.info(f"AI 펌프 하드웨어 제어 성공 (DB 실패): {reservoir_id} -> {status} (이유: {reason})")
                self.automation_logger.warning(
                    EventType.ACTION,
                    reservoir_id,
                    f"AI 펌프 하드웨어 제어 성공 (DB 업데이트 실패): {status}",
                    {
                        "pump_status": status,
                        "reason": reason,
                        "arduino_success": True,
                        "database_updated": False,
                        "arduino_details": arduino_result
                    }
                )
            elif db_success:
                logger.warning(f"AI 펌프 DB 업데이트만 성공 (하드웨어 실패): {reservoir_id} -> {status} (이유: {reason})")
                self.automation_logger.warning(
                    EventType.ACTION,
                    reservoir_id,
                    f"AI 펌프 DB 업데이트만 성공 (Arduino 연결 없음): {status}",
                    {
                        "pump_status": status,
                        "reason": reason,
                        "arduino_success": False,
                        "database_updated": True,
                        "arduino_error": arduino_result.get('error', 'Arduino 연결 실패')
                    }
                )
            else:
                logger.error(f"AI 펌프 제어 완전 실패: {reservoir_id} -> {status} (이유: {reason})")
                self.automation_logger.error(
                    EventType.ERROR,
                    reservoir_id,
                    f"AI 펌프 제어 완전 실패: {status}",
                    {
                        "pump_status": status,
                        "reason": reason,
                        "arduino_success": False,
                        "database_updated": False,
                        "arduino_error": arduino_result.get('error', 'Arduino 연결 실패')
                    }
                )
            
        except Exception as e:
            logger.error(f"펌프 제어 전체 오류: {e}")
            self.automation_logger.error(
                EventType.ERROR,
                reservoir_id,
                f"펌프 제어 예외 오류: {str(e)}",
                {"reason": reason}
            )
    
    def _control_arduino_pump(self, reservoir_id: str, status: str, reason: str) -> Dict[str, Any]:
        """Arduino 하드웨어 펌프 제어 시도"""
        try:
            # Arduino 도구 가져오기
            from utils.helpers import get_arduino_tool
            arduino_tool = get_arduino_tool()
            
            if arduino_tool is None:
                return {
                    "success": False,
                    "error": "Arduino 도구 초기화 실패",
                    "connection_status": "tool_import_failed"
                }
            
            # Arduino 연결 상태 확인
            if not arduino_tool._is_connected():
                self.automation_logger.warning(
                    EventType.ERROR,
                    reservoir_id,
                    f"Arduino 연결되지 않음 - 펌프 제어 불가: {status}",
                    {
                        "requested_status": status,
                        "reason": reason,
                        "arduino_port": getattr(arduino_tool, 'arduino_port', 'Unknown'),
                        "connection_attempt": False
                    }
                )
                
                return {
                    "success": False,
                    "error": "Arduino가 연결되지 않았습니다",
                    "connection_status": "disconnected",
                    "port": getattr(arduino_tool, 'arduino_port', None),
                    "suggestion": "시스템 제어판에서 '시스템 초기화'를 다시 실행하거나 Arduino 연결을 확인하세요"
                }
            
            # 실제 펌프 명령 매핑 (reservoir_id에서 펌프 번호 추출)
            if reservoir_id.endswith('_1') or '1' in reservoir_id:
                pump_action = f"pump1_{'on' if status == 'ON' else 'off'}"
                pump_id = 1
            elif reservoir_id.endswith('_2') or '2' in reservoir_id:
                pump_action = f"pump2_{'on' if status == 'ON' else 'off'}"
                pump_id = 2
            else:
                # 기본값으로 펌프1 사용
                pump_action = f"pump1_{'on' if status == 'ON' else 'off'}"
                pump_id = 1
                logger.warning(f"reservoir_id '{reservoir_id}'에서 펌프 번호를 확인할 수 없어 펌프1을 기본값으로 사용합니다")
            
            # Arduino 펌프 제어 실행
            result = arduino_tool.execute(
                action=pump_action,
                duration=None  # 자동화에서는 수동 종료를 기본으로 함
            )
            
            if result.get('success'):
                self.automation_logger.info(
                    EventType.ACTION,
                    reservoir_id,
                    f"Arduino 펌프{pump_id} 제어 성공: {status}",
                    {
                        "pump_id": pump_id,
                        "pump_status": status,
                        "reason": reason,
                        "arduino_response": result.get('message', ''),
                        "ack_received": result.get('ack_received', False)
                    }
                )
                
                return {
                    "success": True,
                    "message": f"Arduino 펌프{pump_id} {status} 제어 성공",
                    "pump_id": pump_id,
                    "arduino_response": result.get('message', ''),
                    "ack_received": result.get('ack_received', False),
                    "connection_status": "connected"
                }
            else:
                error_msg = result.get('error', '알 수 없는 오류')
                self.automation_logger.error(
                    EventType.ERROR,
                    reservoir_id,
                    f"Arduino 펌프{pump_id} 제어 실패: {error_msg}",
                    {
                        "pump_id": pump_id,
                        "requested_status": status,
                        "reason": reason,
                        "arduino_error": error_msg
                    }
                )
                
                return {
                    "success": False,
                    "error": f"Arduino 펌프{pump_id} 제어 실패: {error_msg}",
                    "pump_id": pump_id,
                    "arduino_error": error_msg,
                    "connection_status": "connected_but_failed"
                }
                
        except Exception as e:
            error_details = f"Arduino 펌프 제어 예외: {str(e)}"
            logger.error(error_details)
            self.automation_logger.error(
                EventType.ERROR,
                reservoir_id,
                error_details,
                {
                    "requested_status": status,
                    "reason": reason,
                    "exception": str(e)
                }
            )
            
            return {
                "success": False,
                "error": error_details,
                "connection_status": "exception_occurred",
                "exception": str(e)
            }
    
    def _send_alert(self, reservoir_id: str, reason: str, priority: str):
        """알림 발송"""
        try:
            alert_message = f"🚨 {priority} 알림: {reservoir_id} - {reason}"
            
            self.automation_logger.log(
                LogLevel.CRITICAL if priority == 'CRITICAL' else LogLevel.WARNING,
                EventType.ALERT,
                reservoir_id,
                alert_message,
                {"priority": priority, "reason": reason}
            )
            
            logger.warning(alert_message)
            
        except Exception as e:
            logger.error(f"알림 발송 오류: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """현재 에이전트 상태 반환"""
        return {
            "is_running": self.is_running,
            "decision_interval": self.decision_interval,
            "thread_active": self.monitoring_thread.is_alive() if self.monitoring_thread else False
        }
    
    def get_notifications(self, limit: int = 10, unread_only: bool = False):
        """알림 목록 반환 - 로깅 시스템에서 가져오기"""
        try:
            # 자동화 로거에서 최근 로그 가져오기
            recent_logs = self.automation_logger.get_recent_logs(limit=limit)
            
            notifications = []
            for log in recent_logs:
                # 타임스탬프 처리 (문자열을 datetime으로 변환)
                timestamp = log.get('timestamp', '')
                if isinstance(timestamp, str):
                    try:
                        from datetime import datetime
                        if timestamp:
                            # ISO 형식 문자열을 datetime으로 변환
                            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        else:
                            timestamp = datetime.now()
                    except (ValueError, AttributeError):
                        timestamp = datetime.now()
                elif not hasattr(timestamp, 'strftime'):
                    # datetime이 아닌 경우 현재 시간으로 설정
                    timestamp = datetime.now()
                
                # 로그를 알림 형태로 변환
                notification = {
                    'id': f"log_{str(timestamp).replace(':', '').replace('-', '').replace(' ', '')}",
                    'timestamp': timestamp,
                    'level': log.get('level', 'INFO').lower(),
                    'title': f"{log.get('event_type', 'System')} Alert",
                    'message': log.get('message', ''),
                    'read': False
                }
                notifications.append(notification)
            
            return notifications[:limit]
            
        except Exception as e:
            logger.error(f"알림 조회 오류: {e}")
            return []
    
    def add_notification(self, message: str, level: str = "info", data: Dict = None):
        """알림 추가 - 로깅 시스템 활용"""
        try:
            # 로그 레벨에 따라 적절한 로깅
            if level == "critical" or level == "emergency":
                self.automation_logger.critical(EventType.ALERT, "system", message, data or {})
            elif level == "warning":
                self.automation_logger.warning(EventType.ALERT, "system", message, data or {})
            else:
                self.automation_logger.info(EventType.ALERT, "system", message, data or {})
                
            logger.info(f"알림 추가: [{level.upper()}] {message}")
            
        except Exception as e:
            logger.error(f"알림 추가 오류: {e}")
    
    def mark_notification_read(self, notification_id: str):
        """알림을 읽음으로 표시 - 현재 구현에서는 로그만 남김"""
        logger.debug(f"알림 읽음 표시: {notification_id}")
        return True
    
    def clear_old_notifications(self, hours: int = 24):
        """오래된 알림 정리 - 로깅 시스템에 위임"""
        try:
            # 로깅 시스템의 자동 정리 기능 활용
            logger.info(f"{hours}시간 이전 알림 정리 요청")
            return 0  # 실제 정리된 개수는 로깅 시스템이 관리
        except Exception as e:
            logger.error(f"알림 정리 오류: {e}")
            return 0

# 전역 에이전트 인스턴스
_global_agent = None

def get_autonomous_agent(lm_client: Optional[LMStudioClient] = None) -> Optional[AutonomousAgent]:
    """전역 자율 에이전트 인스턴스 반환"""
    global _global_agent
    
    if _global_agent is None and lm_client:
        _global_agent = AutonomousAgent(lm_client)
    
    return _global_agent

def update_global_state_from_streamlit():
    """Streamlit에서 글로벌 상태 업데이트 (메인 스레드에서 호출)"""
    state_manager = get_state_manager()
    state_manager.sync_from_streamlit()

def get_global_state():
    """글로벌 상태 인스턴스 반환 - 이제 state_manager를 사용"""
    return get_state_manager()

def test_ai_decision_making():
    """AI 의사결정 테스트 함수"""
    try:
        import streamlit as st
        if hasattr(st.session_state, 'lm_studio_client'):
            agent = get_autonomous_agent(st.session_state.lm_studio_client)
            if agent:
                system_state = agent._collect_system_state()
                logger.info(f"시스템 상태 수집 완료: {len(system_state.reservoir_data)}개 배수지")
                
                decision = agent._make_ai_decision(system_state)
                if decision:
                    logger.info(f"AI 의사결정 성공: {decision.get('decision', 'Unknown')}")
                    return True
                else:
                    logger.warning("AI 의사결정 실패")
                    return False
            else:
                logger.error("AI 에이전트 초기화 실패")
                return False
        else:
            logger.error("LM Studio 클라이언트가 초기화되지 않음")
            return False
    except Exception as e:
        logger.error(f"AI 의사결정 테스트 오류: {e}")
        return False