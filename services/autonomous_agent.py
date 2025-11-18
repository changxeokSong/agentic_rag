# services/autonomous_agent.py - LM Studio 기반 자율형 에이전트

import asyncio
import threading
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from enum import Enum

from models.lm_studio import LMStudioClient
from services.logging_system import get_automation_logger, LogLevel, EventType
from services.database_connector import get_database_connector
from utils.logger import setup_logger
from utils.state_manager import get_state_manager

logger = setup_logger(__name__)


class AlertLevel(Enum):
    """알림 등급"""
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
    action_id: Optional[str] = None


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
    """LM Studio 기반 자율형 AI 에이전트"""

    # 운영 설정 변수
    DECISION_INTERVAL_SECONDS = 10  # 의사결정 간격(초)
    ERROR_RETRY_DELAY_SECONDS = 5  # 오류 발생 시 재시도 대기 시간(초)
    MAX_RETRY_ATTEMPTS = 3          # 최대 재시도 횟수

    def __init__(self, lm_client: LMStudioClient):
        self.lm_client = lm_client
        self.automation_logger = get_automation_logger()
        self.is_running = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.decision_interval = self.DECISION_INTERVAL_SECONDS
        self.allowed_reservoirs: Optional[Set[str]] = None

        # AI 에이전트 시스템 프롬프트
        self.system_prompt = (
            """
운영 규칙 및 펌프 제어 로직:

[저수지 목록]
저수지1: 가곡 저수지 (reservoir_id="gagok")
저수지2: 해룡 저수지 (reservoir_id="haeryong")

[제어 규칙 - 수위 기준]
1. 가곡 수위 < 40m → 저수지1 펌프 ON (PUMP_ON)
2. 가곡 수위 > 80m → 저수지1 펌프 OFF (PUMP_OFF)
3. 해룡 수위 < 40m → 저수지2 펌프 ON (PUMP_ON)
4. 해룡 수위 > 80m → 저수지2 펌프 OFF (PUMP_OFF)

[주의] 여러 저수지에 대해 동시 결정을 내려도 된다. 조건이 모호하면 actions에 이유를 포함한다.

[응답 예시]
입력: 가곡=30m, 해룡=85m
출력:
{
  "decision": "PUMP_CONTROL",
  "actions": [
    {"reservoir_id": "gagok", "action": "PUMP_ON", "reason": "가곡 30m < 40m"},
    {"reservoir_id": "haeryong", "action": "PUMP_OFF", "reason": "해룡 85m > 80m"}
  ],
  "message": "가곡 ON, 해룡 OFF"
}

입력: 가곡=10m, 해룡=50m
출력:
{
  "decision": "PUMP_CONTROL",
  "actions": [
    {"reservoir_id": "gagok", "action": "PUMP_ON", "reason": "가곡 10m < 40m"}
  ],
  "message": "가곡 ON"
}

입력: 가곡=50m, 해룡=50m
출력:
{
  "decision": "STABLE",
  "actions": [],
  "message": "안정"
}

JSON만 출력한다.
"""
        )

    # ------------------------------
    # Lifecycle
    # ------------------------------
    def start_monitoring(self) -> bool:
        """자율 모니터링 시작"""
        if self.is_running:
            logger.warning("이미 모니터링이 실행 중입니다.")
            return False

        self.is_running = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()

        self.automation_logger.info(EventType.SYSTEM, "system", "자율형 AI 에이전트 모니터링 시작")
        logger.info("자율형 AI 에이전트가 시작되었습니다.")
        return True

    def stop_monitoring(self) -> bool:
        """자율 모니터링 종료"""
        if not self.is_running:
            logger.warning("모니터링이 실행 중이 아닙니다.")
            return False

        self.is_running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)

        self.automation_logger.info(EventType.SYSTEM, "system", "자율형 AI 에이전트 모니터링 종료")
        logger.info("자율형 AI 에이전트가 종료되었습니다.")
        return True

    def _monitoring_loop(self):
        """메인 모니터링 루프"""
        logger.info("AI 에이전트 모니터링 루프 시작")

        while self.is_running:
            try:
                # 현재 시스템 상태 수집
                system_state = self._collect_system_state()

                # AI로 의사결정 요청
                decision = self._make_ai_decision(system_state)

                if decision:
                    # AI 결정사항 실행
                    self._execute_decision(decision)

                # 다음 턴 대기
                time.sleep(self.decision_interval)

            except Exception as e:
                logger.error(f"모니터링 루프 오류: {e}")
                self.automation_logger.error(EventType.ERROR, "system", f"모니터링 오류: {str(e)}")
                time.sleep(self.ERROR_RETRY_DELAY_SECONDS)

        logger.info("AI 에이전트 모니터링 루프 종료")

    # ------------------------------
    # State
    # ------------------------------
    def _collect_system_state(self) -> SystemState:
        """현재 시스템 상태 수집 - 기본 DB 우선"""
        try:
            db_connector = get_database_connector()
            reservoir_data = db_connector.get_latest_water_data()

            if not reservoir_data:
                # DB 조회 실패 시 저장 상태 사용
                logger.warning("DB에서 데이터 조회 실패, 저장 상태 사용")
                state_manager = get_state_manager()
                state = state_manager.load_state()
                reservoir_data = state.get("reservoir_data", {})
            else:
                # 최신 데이터 저장
                state_manager = get_state_manager()
                state = state_manager.load_state()
                state["reservoir_data"] = reservoir_data
                state_manager.save_state(state)
                logger.info(f"DB에서 {len(reservoir_data)}개 저수지 데이터 수집 완료")

            state_manager = get_state_manager()
            state = state_manager.load_state()
            arduino_connected = state.get("arduino_connected", False)

            # 최근 알림 조회
            recent_logs = self.automation_logger.get_recent_logs(limit=10)
            recent_alerts = [log for log in recent_logs if log.get("level") in ["WARNING", "ERROR", "CRITICAL"]]

            # 시스템 건강 상태 판단
            critical_reservoirs = [
                res_id for res_id, data in reservoir_data.items()
                if data.get("water_level", 0) >= data.get("alert_level", float("inf"))
            ]

            if critical_reservoirs:
                system_health = "CRITICAL"
            elif any(data.get("water_level", 0) >= data.get("alert_level", 1) * 0.8 for data in reservoir_data.values() if "alert_level" in data):
                system_health = "WARNING"
            else:
                system_health = "NORMAL"

            return SystemState(
                timestamp=datetime.now(),
                reservoir_data=reservoir_data,
                arduino_connected=arduino_connected,
                recent_alerts=recent_alerts,
                system_health=system_health,
                automation_active=True,
            )

        except Exception as e:
            logger.error(f"시스템 상태 수집 오류: {e}")
            return SystemState(
                timestamp=datetime.now(),
                reservoir_data={},
                arduino_connected=False,
                recent_alerts=[],
                system_health="ERROR",
                automation_active=False,
            )

    def _get_allowed_reservoirs(self) -> Set[str]:
        """허용된 저수지 ID 목록 (DB 설정 기반)"""
        if self.allowed_reservoirs is not None:
            return self.allowed_reservoirs
        try:
            db_connector = get_database_connector()
            self.allowed_reservoirs = set(db_connector.reservoirs.keys())
        except Exception as e:
            logger.warning(f"허용 저수지 목록 조회 실패: {e}")
            self.allowed_reservoirs = set()
        return self.allowed_reservoirs

    def _is_simulation_mode(self) -> bool:
        """시뮬레이션 모드 확인"""
        try:
            state = get_state_manager().load_state()
            return state.get("simulation_mode", True)
        except Exception as e:
            logger.warning(f"시뮬레이션 모드 확인 실패: {e}")
            return True

    # ------------------------------
    # Decision
    # ------------------------------
    def _make_ai_decision(self, system_state: SystemState) -> Optional[Dict[str, Any]]:
        """AI에게 의사결정 요청"""
        try:
            # 글로벌 상태 로드
            state_manager = get_state_manager()
            global_state = state_manager.load_state()

            # 상태 요약(프롬프트 입력용)
            state_summary = {
                "timestamp": system_state.timestamp.isoformat(),
                "reservoirs": system_state.reservoir_data,
                "arduino_connected": system_state.arduino_connected,
                "system_health": system_state.system_health,
                "recent_alerts_count": len(system_state.recent_alerts),
                "simulation_mode": global_state.get("simulation_mode", True),
            }

            logger.info("=== AI 의사결정 시작 ===")
            logger.info(f"전달 저수지 수: {len(system_state.reservoir_data)}")
            for res_id, data in system_state.reservoir_data.items():
                logger.info(f"  - {res_id}: 수위={data.get('water_level', 0)}m, 펌프={data.get('pump_status', 'UNKNOWN')}")
            logger.info(f"전체 데이터: {json.dumps(system_state.reservoir_data, indent=2, ensure_ascii=False)}")

            user_message = (
                "현재 시스템 상태:\n"
                + json.dumps(state_summary, indent=2, ensure_ascii=False)
                + "\n\n상태를 분석하고 필요한 제어 조치를 JSON 형식으로만 응답하세요."
            )

            # LM Studio 호출 (OpenAI 호환 인터페이스)
            try:
                response = self.lm_client.client.chat.completions.create(
                    model=self.lm_client.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.3,
                    max_tokens=1000,
                )
            except Exception as api_error:
                logger.error(f"LM Studio API 호출 오류: {api_error}")
                return None

            if response and hasattr(response, "choices") and len(response.choices) > 0:
                ai_response = response.choices[0].message.content

                # JSON 디코딩 시도 (```json 코드블록 대응)
                try:
                    text = ai_response.strip()
                    if "```json" in text:
                        s = text.find("```json") + 7
                        e = text.find("```", s)
                        text = text[s:e].strip()
                    elif text.startswith("```"):
                        s = text.find("```") + 3
                        e = text.rfind("```")
                        text = text[s:e].strip()

                    decision = json.loads(text)

                    logger.info("AI 응답 파싱 성공")
                    logger.info(f"  - decision: {decision.get('decision', 'UNKNOWN')}")
                    logger.info(f"  - actions 수: {len(decision.get('actions', []))}")
                    for i, action in enumerate(decision.get("actions", [])):
                        logger.info(
                            f"    액션 {i+1}: {action.get('reservoir_id')} -> {action.get('action')} ({action.get('reason', '')})"
                        )
                    logger.info("=== AI 의사결정 종료 ===")

                    # 로그 적재
                    self.automation_logger.log(
                        LogLevel.INFO,
                        EventType.DECISION,
                        "system",
                        f"AI 결정: {decision.get('decision', 'UNKNOWN')} - {decision.get('message', '')}",
                        {"ai_decision": decision, "system_state": state_summary},
                    )

                    return decision

                except json.JSONDecodeError as e:
                    logger.error(f"AI 응답 JSON 파싱 실패: {e}")
                    logger.error(f"AI 원문 응답: {ai_response}")
                    self.automation_logger.error(EventType.ERROR, "system", f"AI 응답 파싱 실패: {str(e)}")
                    return None

            return None

        except Exception as e:
            logger.error(f"AI 의사결정 처리 오류: {e}")
            self.automation_logger.error(EventType.ERROR, "system", f"AI 의사결정 오류: {str(e)}")
            return None


    # Validation helpers
    # ------------------------------
    def _get_allowed_reservoirs(self) -> Set[str]:
        """Return allowed reservoir ids from DB config"""
        if self.allowed_reservoirs is not None:
            return self.allowed_reservoirs
        try:
            db_connector = get_database_connector()
            self.allowed_reservoirs = set(db_connector.reservoirs.keys())
        except Exception as e:
            logger.warning(f"허용 배수지 목록 조회 실패: {e}")
            self.allowed_reservoirs = set()
        return self.allowed_reservoirs

    def _is_simulation_mode(self) -> bool:
        """Check simulation mode flag"""
        try:
            state = get_state_manager().load_state()
            return state.get("simulation_mode", True)
        except Exception as e:
            logger.warning(f"시뮬레이션 모드 확인 실패: {e}")
            return True

    # ------------------------------
    # Action Execution
    # ------------------------------
    def _execute_decision(self, decision: Dict[str, Any]):
        """AI 결정사항 실행 - 안전 게이트 포함"""
        try:
            actions = decision.get("actions", [])
            priority = decision.get("priority", "LOW")
            simulation_mode = self._is_simulation_mode()
            allowed_reservoirs = self._get_allowed_reservoirs()

            for action in actions:
                res_id = action.get("reservoir_id")
                act = action.get("action")
                reason = action.get("reason", "")

                if not res_id or not act:
                    continue

                # 허용되지 않은 배수지 차단
                if allowed_reservoirs and res_id not in allowed_reservoirs:
                    warn_msg = f"허용되지 않은 배수지 ID로 명령 수신: {res_id}"
                    logger.warning(warn_msg)
                    self.automation_logger.warning(
                        EventType.ACTION,
                        res_id,
                        warn_msg,
                        {"action": action}
                    )
                    continue

                act_upper = act.upper()

                # 시뮬레이션 모드: 하드웨어/DB 건너뛰고 상태만 기록
                if simulation_mode and act_upper in ("PUMP_ON", "PUMP_OFF", "PUMP_AUTO", "ON", "OFF"):
                    try:
                        state_manager = get_state_manager()
                        state = state_manager.load_state()
                        state.setdefault("pump_status", {})[res_id] = act_upper.replace("PUMP_", "")
                        state_manager.save_state(state)
                    except Exception as state_error:
                        logger.warning(f"시뮬레이션 상태 저장 실패: {state_error}")

                    self.automation_logger.info(
                        EventType.ACTION,
                        res_id,
                        f"시뮬레이션 모드 - 하드웨어 제어 스킵: {act_upper}",
                        {"action": action, "priority": priority, "simulation_mode": True}
                    )
                    continue

                # 실제 실행
                if act_upper in ("PUMP_ON", "ON"):
                    self._control_pump(res_id, "ON", reason)
                elif act_upper in ("PUMP_OFF", "OFF"):
                    self._control_pump(res_id, "OFF", reason)
                elif act_upper == "PUMP_AUTO":
                    self._control_pump(res_id, "AUTO", reason)
                elif act_upper == "ALERT":
                    self._send_alert(res_id, reason, priority)

                # 실행 로그
                self.automation_logger.log(
                    LogLevel.WARNING if priority in ["HIGH", "CRITICAL"] else LogLevel.INFO,
                    EventType.ACTION,
                    res_id,
                    f"AI 액션 실행: {act_upper} - {reason}",
                    {"action": action, "priority": priority}
                )

        except Exception as e:
            logger.error(f"AI 결정사항 실행 오류: {e}")
            self.automation_logger.error(EventType.ERROR, "system", f"액션 실행 오류: {str(e)}")

    def _control_pump(self, reservoir_id: str, status: str, reason: str) -> Dict[str, Any]:
        """Pump control with safety gates (hardware + DB)"""
        arduino_success = False
        db_success = False

        try:
            allowed_reservoirs = self._get_allowed_reservoirs()
            if allowed_reservoirs and reservoir_id not in allowed_reservoirs:
                error_msg = f"허용되지 않은 배수지 ID: {reservoir_id}"
                logger.error(error_msg)
                self.automation_logger.error(
                    EventType.ERROR,
                    reservoir_id,
                    error_msg,
                    {"requested_status": status, "reason": reason}
                )
                return {"success": False, "error": error_msg, "connection_status": "invalid_reservoir"}

            if self._is_simulation_mode():
                try:
                    state_manager = get_state_manager()
                    state = state_manager.load_state()
                    state.setdefault("pump_status", {})[reservoir_id] = status
                    state_manager.save_state(state)
                except Exception as state_error:
                    logger.warning(f"시뮬레이션 펌프 상태 기록 실패: {state_error}")

                self.automation_logger.info(
                    EventType.ACTION,
                    reservoir_id,
                    f"시뮬레이션 모드 - 펌프 명령 기록만 수행: {status}",
                    {
                        "pump_status": status,
                        "reason": reason,
                        "simulation_mode": True
                    }
                )
                return {"success": True, "message": f"시뮬레이션 모드 - 펌프 {reservoir_id} {status} 기록", "connection_status": "simulation"}

            # 1) Arduino 제어
            arduino_result = self._control_arduino_pump(reservoir_id, status, reason)
            arduino_success = arduino_result.get("success", False)

            # 2) DB 업데이트
            try:
                db_connector = get_database_connector()
                db_success = db_connector.update_pump_status(reservoir_id, status)
            except Exception as db_e:
                logger.warning(f"데이터베이스 업데이트 실패: {db_e}")
                db_success = False

            # 3) 글로벌 상태 업데이트
            if arduino_success or db_success:
                try:
                    state_manager = get_state_manager()
                    state = state_manager.load_state()
                    state.setdefault("pump_status", {})[reservoir_id] = status
                    state_manager.save_state(state)
                except Exception as state_e:
                    logger.warning(f"글로벌 상태 업데이트 실패: {state_e}")

            # 4) 결과 로깅
            if arduino_success and db_success:
                self.automation_logger.info(
                    EventType.ACTION,
                    reservoir_id,
                    f"AI 펌프 제어 전체 성공: {status}",
                    {
                        "pump_status": status,
                        "reason": reason,
                        "arduino_success": True,
                        "database_updated": True,
                        "arduino_details": arduino_result
                    }
                )
            elif arduino_success:
                self.automation_logger.warning(
                    EventType.ACTION,
                    reservoir_id,
                    f"AI 펌프 하드웨어 제어 성공 (DB 실패): {status}",
                    {
                        "pump_status": status,
                        "reason": reason,
                        "arduino_success": True,
                        "database_updated": False,
                        "arduino_details": arduino_result
                    }
                )
            elif db_success:
                self.automation_logger.warning(
                    EventType.ACTION,
                    reservoir_id,
                    f"AI 펌프 DB 업데이트만 성공 (하드웨어 실패): {status}",
                    {
                        "pump_status": status,
                        "reason": reason,
                        "arduino_success": False,
                        "database_updated": True,
                        "arduino_error": arduino_result.get('error', 'Arduino 제어 실패')
                    }
                )
            else:
                self.automation_logger.error(
                    EventType.ERROR,
                    reservoir_id,
                    f"AI 펌프 제어 전체 실패: {status}",
                    {
                        "pump_status": status,
                        "reason": reason,
                        "arduino_success": False,
                        "database_updated": False,
                        "arduino_error": arduino_result.get('error', 'Arduino 연결 실패')
                    }
                )

            return {"success": arduino_success or db_success, "arduino_success": arduino_success, "database_updated": db_success}

        except Exception as e:
            logger.error(f"펌프 제어 전체 오류: {e}")
            self.automation_logger.error(EventType.ERROR, reservoir_id, f"펌프 제어 예외 오류: {str(e)}", {"reason": reason})
            return {"success": False, "error": str(e)}
def _control_arduino_pump(self, reservoir_id: str, status: str, reason: str) -> Dict[str, Any]:
        """Arduino를 통해 펌프 제어"""
        try:
            from utils.helpers import get_arduino_tool
            arduino_tool = get_arduino_tool()

            if arduino_tool is None:
                return {
                    "success": False,
                    "error": "Arduino 도구 초기화 실패",
                    "connection_status": "tool_import_failed",
                }

            # 연결 확인 및 자동 연결 시도
            if not arduino_tool._is_connected():
                logger.info("Arduino가 연결되지 않음. 자동 연결 시도...")
                try:
                    connect_result = arduino_tool.execute(action="connect")

                    if connect_result and connect_result.get("success"):
                        logger.info(f"Arduino 자동 연결 성공: {connect_result.get('port', 'Unknown')}")

                        # 상태 저장 업데이트
                        try:
                            state_manager = get_state_manager()
                            state = state_manager.load_state()
                            state["arduino_connected"] = True
                            state["arduino_port"] = connect_result.get("port")
                            state["simulation_mode"] = (connect_result.get("port") == "SIMULATION")
                            state_manager.save_state(state)
                            logger.info("Arduino 연결 상태를 저장 상태에 반영")
                        except Exception as state_error:
                            logger.warning(f"상태 저장 업데이트 실패: {state_error}")

                        self.automation_logger.info(
                            EventType.SYSTEM,
                            reservoir_id,
                            "Arduino 자동 연결 성공",
                            {"port": connect_result.get("port"), "connection_method": "auto_reconnect"},
                        )
                    else:
                        error_msg = connect_result.get("error", "Arduino 연결 실패") if connect_result else "Arduino 연결 실패"
                        self.automation_logger.warning(
                            EventType.ERROR,
                            reservoir_id,
                            f"Arduino 자동 연결 실패 - 요청 상태: {status}",
                            {
                                "requested_status": status,
                                "reason": reason,
                                "arduino_port": getattr(arduino_tool, "arduino_port", "Unknown"),
                                "connection_attempt": True,
                                "connection_error": error_msg,
                            },
                        )
                        return {
                            "success": False,
                            "error": f"Arduino 연결 실패: {error_msg}",
                            "connection_status": "connection_failed",
                            "port": getattr(arduino_tool, "arduino_port", None),
                            "suggestion": "Arduino USB 연결을 확인하고, 장치에서 '시작 초기화'를 다시 실행하세요.",
                        }
                except Exception as conn_error:
                    logger.error(f"Arduino 연결 시도 중 예외: {conn_error}")
                    self.automation_logger.error(
                        EventType.ERROR,
                        reservoir_id,
                        f"Arduino 자동 연결 예외: {str(conn_error)}",
                        {"requested_status": status, "reason": reason, "exception": str(conn_error)},
                    )
                    return {
                        "success": False,
                        "error": f"Arduino 자동 연결 예외: {str(conn_error)}",
                        "connection_status": "connection_exception",
                        "exception": str(conn_error),
                    }

            # 펌프 채널 결정 (간단 매핑)
            if reservoir_id.endswith("_1") or "gagok" in reservoir_id:
                pump_action = f"pump1_{'on' if status.upper() == 'ON' else 'off'}"
                pump_id = 1
            elif reservoir_id.endswith("_2") or "haeryong" in reservoir_id:
                pump_action = f"pump2_{'on' if status.upper() == 'ON' else 'off'}"
                pump_id = 2
            else:
                pump_action = f"pump1_{'on' if status.upper() == 'ON' else 'off'}"
                pump_id = 1
                logger.warning(
                    f"reservoir_id '{reservoir_id}'에서 펌프 채널을 특정할 수 없어 펌프1로 기본 처리합니다."
                )

            # 펌프 제어 실행
            result = arduino_tool.execute(action=pump_action, duration=None)

            if result.get("success"):
                self.automation_logger.info(
                    EventType.ACTION,
                    reservoir_id,
                    f"Arduino 펌프{pump_id} 제어 성공: {status}",
                    {
                        "pump_id": pump_id,
                        "pump_status": status,
                        "reason": reason,
                        "arduino_response": result.get("message", ""),
                        "ack_received": result.get("ack_received", False),
                    },
                )
                return {
                    "success": True,
                    "message": f"Arduino 펌프{pump_id} {status} 제어 성공",
                    "pump_id": pump_id,
                    "arduino_response": result.get("message", ""),
                    "ack_received": result.get("ack_received", False),
                    "connection_status": "connected",
                }
            else:
                error_msg = result.get("error", "알 수 없는 오류")
                self.automation_logger.error(
                    EventType.ERROR,
                    reservoir_id,
                    f"Arduino 펌프{pump_id} 제어 실패: {error_msg}",
                    {
                        "pump_id": pump_id,
                        "requested_status": status,
                        "reason": reason,
                        "arduino_error": error_msg,
                    },
                )
                return {
                    "success": False,
                    "error": f"Arduino 펌프{pump_id} 제어 실패: {error_msg}",
                    "pump_id": pump_id,
                    "arduino_error": error_msg,
                    "connection_status": "connected_but_failed",
                }

        except Exception as e:
            error_details = f"Arduino 펌프 제어 예외: {str(e)}"
            logger.error(error_details)
            self.automation_logger.error(
                EventType.ERROR,
                reservoir_id,
                error_details,
                {"requested_status": status, "reason": reason, "exception": str(e)},
            )
            return {
                "success": False,
                "error": error_details,
                "connection_status": "exception_occurred",
                "exception": str(e),
            }

    def _send_alert(self, reservoir_id: str, reason: str, priority: str):
        """알림 전송"""
        try:
            alert_message = f"[우선순위 {priority}] 알림: {reservoir_id} - {reason}"
            self.automation_logger.log(
                LogLevel.CRITICAL if priority == "CRITICAL" else LogLevel.WARNING,
                EventType.ALERT,
                reservoir_id,
                alert_message,
                {"priority": priority, "reason": reason},
            )
            logger.warning(alert_message)
        except Exception as e:
            logger.error(f"알림 전송 오류: {e}")

    # ------------------------------
    # Public API
    # ------------------------------
    def get_status(self) -> Dict[str, Any]:
        """현재 에이전트 상태 반환"""
        return {
            "is_running": self.is_running,
            "decision_interval": self.decision_interval,
            "thread_active": self.monitoring_thread.is_alive() if self.monitoring_thread else False,
        }

    def get_notifications(self, limit: int = 10, unread_only: bool = False) -> List[Dict[str, Any]]:
        """알림 목록 반환 - 로깅 시스템에서 수집"""
        try:
            recent_logs = self.automation_logger.get_recent_logs(limit=limit)

            notifications: List[Dict[str, Any]] = []
            for log in recent_logs:
                # 타임스탬프 정규화
                ts = log.get("timestamp", "")
                if isinstance(ts, str):
                    try:
                        if ts:
                            ts_obj = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        else:
                            ts_obj = datetime.now()
                    except (ValueError, AttributeError):
                        ts_obj = datetime.now()
                elif hasattr(ts, "strftime"):
                    ts_obj = ts
                else:
                    ts_obj = datetime.now()

                notification = {
                    "id": f"log_{str(ts_obj).replace(':', '').replace('-', '').replace(' ', '')}",
                    "timestamp": ts_obj,
                    "level": log.get("level", "INFO").lower(),
                    "title": f"{log.get('event_type', 'System')} Alert",
                    "message": log.get("message", ""),
                    "read": False,
                }
                notifications.append(notification)

            return notifications[:limit]

        except Exception as e:
            logger.error(f"알림 조회 오류: {e}")
            return []

    def add_notification(self, message: str, level: str = "info", data: Optional[Dict[str, Any]] = None):
        """알림 추가 - 로깅 시스템 사용"""
        try:
            payload = data or {}
            if level in ("critical", "emergency"):
                self.automation_logger.critical(EventType.ALERT, "system", message, payload)
            elif level == "warning":
                self.automation_logger.warning(EventType.ALERT, "system", message, payload)
            else:
                self.automation_logger.info(EventType.ALERT, "system", message, payload)

            logger.info(f"알림 추가: [{level.upper()}] {message}")
        except Exception as e:
            logger.error(f"알림 추가 오류: {e}")

    def mark_notification_read(self, notification_id: str) -> bool:
        """알림을 읽음 표시(현재는 로컬 처리만)"""
        logger.debug(f"알림 읽음 표시: {notification_id}")
        return True

    def clear_old_notifications(self, hours: int = 24) -> int:
        """오래된 알림 정리(로깅 시스템에 의존)"""
        try:
            logger.info(f"{hours}시간 이전 알림 정리 요청")
            return 0  # 실제 삭제는 로깅 시스템 정책을 따름
        except Exception as e:
            logger.error(f"알림 정리 오류: {e}")
            return 0


# 전역 에이전트 인스턴스
_global_agent: Optional[AutonomousAgent] = None


def get_autonomous_agent(lm_client: Optional[LMStudioClient] = None) -> Optional[AutonomousAgent]:
    """전역 자율 에이전트 인스턴스 반환"""
    global _global_agent
    if _global_agent is None and lm_client:
        _global_agent = AutonomousAgent(lm_client)
    return _global_agent


def update_global_state_from_streamlit():
    """Streamlit에서 저장 상태 동기화(메인 페이지에서 호출)"""
    state_manager = get_state_manager()
    state_manager.sync_from_streamlit()


def get_global_state():
    """저장 상태 매니저 반환"""
    return get_state_manager()


def test_ai_decision_making() -> bool:
    """AI 의사결정 테스트 유틸"""
    try:
        import streamlit as st
        if hasattr(st.session_state, "lm_studio_client"):
            agent = get_autonomous_agent(st.session_state.lm_studio_client)
            if agent:
                system_state = agent._collect_system_state()
                logger.info(f"상태 수집 완료: {len(system_state.reservoir_data)}개 저수지")

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
            logger.error("LM Studio 클라이언트가 세션에 없습니다")
            return False
    except Exception as e:
        logger.error(f"AI 의사결정 테스트 오류: {e}")
        return False


