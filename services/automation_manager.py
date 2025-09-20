# services/automation_manager.py - 통합 자동화 관리 시스템

import threading
import time
import json
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from services.real_time_monitor import RealtimeMonitor, get_monitor
from services.decision_engine import IntelligentDecisionEngine, Decision, ActionType
from tools.water_level_monitoring_tool import WaterLevelMonitor
from utils.logger import setup_logger
from storage.postgresql_storage import PostgreSQLStorage

logger = setup_logger(__name__)

@dataclass
class AutomationEvent:
    timestamp: datetime
    event_type: str  # "DECISION", "ACTION", "ALERT", "ERROR"
    reservoir_id: str
    details: Dict[str, Any]
    severity: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"

class AutomationManager:
    """전체 자동화 시스템을 관리하는 통합 관리자"""
    
    def __init__(self):
        self.monitor = get_monitor()
        self.decision_engine = IntelligentDecisionEngine()
        self.water_monitor = WaterLevelMonitor()
        
        # 상태 관리
        self.is_automation_active = False
        self.automation_thread = None
        self.last_decisions = {}  # reservoir_id -> Decision
        self.historical_data = {}  # reservoir_id -> List[Dict]
        self.event_history = []
        
        # 설정
        self.config = {
            "automation_interval": 30,  # 30초마다 체크
            "max_history_size": 50,     # 최대 히스토리 크기
            "enable_learning": True,    # 학습 기능 활성화
            "enable_predictive_control": True,  # 예측 제어 활성화
            "safety_mode": True,        # 안전 모드 (수동 확인 필요한 경우)
        }
        
        # PostgreSQL 연결 (로깅용)
        try:
            self.storage = PostgreSQLStorage.get_instance()
        except Exception as e:
            logger.error(f"PostgreSQL 연결 실패: {e}")
            self.storage = None

    def start_automation(self) -> bool:
        """자동화 시스템 시작"""
        if self.is_automation_active:
            logger.warning("자동화가 이미 활성화되어 있습니다")
            return False
        
        try:
            logger.info("🤖 지능형 자동화 시스템 시작")
            
            # 실시간 모니터링 시작
            if not self.monitor.start_monitoring():
                logger.error("실시간 모니터링 시작 실패")
                return False
            
            # 자동화 루프 시작
            self.is_automation_active = True
            self.automation_thread = threading.Thread(
                target=self._automation_loop, 
                daemon=True,
                name="AutomationManagerThread"
            )
            self.automation_thread.start()
            
            self._log_event("SYSTEM", "automation", {
                "message": "자동화 시스템 시작",
                "config": self.config
            }, "HIGH")
            
            return True
            
        except Exception as e:
            logger.error(f"자동화 시작 중 오류: {e}")
            self.is_automation_active = False
            return False

    def stop_automation(self):
        """자동화 시스템 중단"""
        logger.info("🛑 자동화 시스템 중단 중...")
        
        self.is_automation_active = False
        
        # 모니터링 중단
        self.monitor.stop_monitoring()
        
        # 자동화 스레드 종료 대기
        if self.automation_thread and self.automation_thread.is_alive():
            self.automation_thread.join(timeout=5)
        
        self._log_event("SYSTEM", "automation", {
            "message": "자동화 시스템 중단"
        }, "MEDIUM")
        
        logger.info("자동화 시스템 중단 완료")

    def _automation_loop(self):
        """메인 자동화 루프"""
        logger.info("자동화 루프 시작")
        
        while self.is_automation_active:
            try:
                # 1. 현재 상태 수집
                current_status = self._collect_current_status()
                
                if current_status.get('success'):
                    reservoirs = current_status.get('reservoirs', [])
                    
                    # 2. 각 배수지에 대해 지능형 의사결정 수행
                    for reservoir in reservoirs:
                        self._process_reservoir_automation(reservoir)
                    
                    # 3. 시스템 상태 업데이트
                    self._update_system_status()
                    
                else:
                    logger.error(f"상태 수집 실패: {current_status.get('error')}")
                    self._log_event("SYSTEM", "error", {
                        "message": "상태 수집 실패",
                        "error": current_status.get('error')
                    }, "HIGH")
                
            except Exception as e:
                logger.error(f"자동화 루프 오류: {e}")
                self._log_event("SYSTEM", "error", {
                    "message": "자동화 루프 오류",
                    "error": str(e)
                }, "CRITICAL")
            
            # 다음 사이클까지 대기
            time.sleep(self.config["automation_interval"])

    def _collect_current_status(self) -> Dict[str, Any]:
        """현재 시스템 상태 수집"""
        try:
            # 수위 모니터링 데이터 수집
            water_status = self.water_monitor.get_current_status()
            
            # 모니터링 시스템 상태 수집  
            monitor_status = self.monitor.get_monitoring_status()
            
            return {
                "success": True,
                "water_status": water_status,
                "monitor_status": monitor_status,
                "reservoirs": water_status.get('reservoirs', []) if water_status.get('success') else []
            }
            
        except Exception as e:
            logger.error(f"상태 수집 중 오류: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _process_reservoir_automation(self, reservoir_data: Dict[str, Any]):
        """배수지별 자동화 처리"""
        reservoir_id = reservoir_data.get('reservoir_id')
        if not reservoir_id:
            return
        
        try:
            # 1. 히스토리 데이터 준비
            historical_context = self.historical_data.get(reservoir_id, [])
            
            # 2. 지능형 의사결정 수행
            decision = self.decision_engine.make_decision(reservoir_data, historical_context)
            
            # 3. 의사결정 기록
            self.last_decisions[reservoir_id] = decision
            
            # 4. 의사결정 로깅
            self._log_event("DECISION", reservoir_id, {
                "decision": {
                    "action": decision.action.value,
                    "target_pumps": decision.target_pumps,
                    "confidence": decision.confidence,
                    "urgency": decision.urgency.name,
                    "reasoning": decision.reasoning
                },
                "current_level": reservoir_data.get('current_level'),
                "predicted_outcome": decision.predicted_outcome
            }, decision.urgency.name)
            
            # 5. 자동 실행 여부 결정
            should_auto_execute = self._should_auto_execute(decision)
            
            if should_auto_execute:
                # 6. 자동 실행
                self._execute_decision(decision)
            else:
                # 7. 수동 확인 필요
                self._request_manual_approval(decision)
            
            # 8. 히스토리 업데이트
            self._update_history(reservoir_id, reservoir_data)
            
        except Exception as e:
            logger.error(f"[{reservoir_id}] 자동화 처리 중 오류: {e}")
            self._log_event("ERROR", reservoir_id, {
                "message": "자동화 처리 오류",
                "error": str(e)
            }, "HIGH")

    def _should_auto_execute(self, decision: Decision) -> bool:
        """자동 실행 여부 판단"""
        # 안전 모드에서는 CRITICAL 이상만 자동 실행
        if self.config["safety_mode"]:
            return decision.urgency.value >= 4  # CRITICAL 이상
        
        # 일반 모드에서는 MEDIUM 이상 자동 실행
        return decision.urgency.value >= 2

    def _execute_decision(self, decision: Decision):
        """의사결정 실행"""
        try:
            reservoir_id = decision.reservoir_id
            action = decision.action
            target_pumps = decision.target_pumps
            
            logger.info(f"[{reservoir_id}] 자동 실행: {action.value} - {target_pumps}")
            
            if action == ActionType.EMERGENCY_ALL_ON:
                # 모든 펌프 긴급 가동
                for pump_name in target_pumps:
                    result = self.monitor.manual_override(reservoir_id, pump_name, "ON")
                    self._log_action_result(reservoir_id, pump_name, "ON", result)
                    
            elif action == ActionType.PUMP_ON:
                # 지정된 펌프 가동
                for pump_name in target_pumps:
                    result = self.monitor.manual_override(reservoir_id, pump_name, "ON")
                    self._log_action_result(reservoir_id, pump_name, "ON", result)
                    
            elif action == ActionType.PUMP_OFF:
                # 지정된 펌프 중단
                for pump_name in target_pumps:
                    result = self.monitor.manual_override(reservoir_id, pump_name, "OFF")
                    self._log_action_result(reservoir_id, pump_name, "OFF", result)
                    
            elif action == ActionType.MAINTAIN:
                # 현상 유지
                self._log_event("ACTION", reservoir_id, {
                    "action": "MAINTAIN",
                    "message": "현상 유지 결정"
                }, "LOW")
                
            # 실행 결과 평가 예약 (5분 후)
            threading.Timer(300, self._evaluate_decision_outcome, args=[decision]).start()
            
        except Exception as e:
            logger.error(f"의사결정 실행 중 오류: {e}")
            self._log_event("ERROR", decision.reservoir_id, {
                "message": "의사결정 실행 오류",
                "error": str(e)
            }, "HIGH")

    def _request_manual_approval(self, decision: Decision):
        """수동 승인 요청"""
        logger.warning(f"[{decision.reservoir_id}] 수동 승인 필요: {decision.action.value}")
        
        self._log_event("ALERT", decision.reservoir_id, {
            "message": "수동 승인 필요",
            "decision": {
                "action": decision.action.value,
                "reasoning": decision.reasoning,
                "confidence": decision.confidence,
                "urgency": decision.urgency.name
            }
        }, "HIGH")
        
        # 여기에 추후 웹 알림, 이메일 등 추가 가능

    def _log_action_result(self, reservoir_id: str, pump_name: str, action: str, result: Dict[str, Any]):
        """펌프 제어 결과 로깅"""
        success = result.get('success', False)
        severity = "LOW" if success else "HIGH"
        
        self._log_event("ACTION", reservoir_id, {
            "pump_name": pump_name,
            "action": action,
            "success": success,
            "result": result
        }, severity)

    def _evaluate_decision_outcome(self, decision: Decision):
        """의사결정 결과 평가"""
        try:
            # 현재 상태 다시 수집
            current_status = self._collect_current_status()
            
            if current_status.get('success'):
                reservoirs = current_status.get('reservoirs', [])
                reservoir_data = None
                
                for res in reservoirs:
                    if res.get('reservoir_id') == decision.reservoir_id:
                        reservoir_data = res
                        break
                
                if reservoir_data:
                    # 결과 평가
                    evaluation = self.decision_engine.evaluate_decision_outcome(decision, reservoir_data)
                    
                    self._log_event("EVALUATION", decision.reservoir_id, {
                        "decision_action": decision.action.value,
                        "evaluation": evaluation,
                        "current_level": reservoir_data.get('current_level')
                    }, "LOW")
                    
        except Exception as e:
            logger.error(f"의사결정 평가 중 오류: {e}")

    def _update_history(self, reservoir_id: str, reservoir_data: Dict[str, Any]):
        """히스토리 데이터 업데이트"""
        if reservoir_id not in self.historical_data:
            self.historical_data[reservoir_id] = []
        
        # 타임스탬프 추가
        data_with_timestamp = {
            **reservoir_data,
            "timestamp": datetime.now().isoformat()
        }
        
        self.historical_data[reservoir_id].append(data_with_timestamp)
        
        # 최대 크기 제한
        max_size = self.config["max_history_size"]
        if len(self.historical_data[reservoir_id]) > max_size:
            self.historical_data[reservoir_id] = self.historical_data[reservoir_id][-max_size:]

    def _update_system_status(self):
        """시스템 상태 업데이트"""
        # 전체 시스템 헬스 체크
        try:
            monitor_status = self.monitor.get_monitoring_status()
            
            if not monitor_status.get("is_active"):
                self._log_event("ALERT", "system", {
                    "message": "모니터링 시스템이 비활성화됨"
                }, "HIGH")
            
            if not monitor_status.get("arduino_connected"):
                self._log_event("ALERT", "system", {
                    "message": "아두이노 연결이 끊어짐"
                }, "MEDIUM")
                
        except Exception as e:
            logger.error(f"시스템 상태 업데이트 중 오류: {e}")

    def _log_event(self, event_type: str, reservoir_id: str, details: Dict[str, Any], severity: str):
        """이벤트 로깅"""
        event = AutomationEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            reservoir_id=reservoir_id,
            details=details,
            severity=severity
        )
        
        self.event_history.append(event)
        
        # 최대 1000개 이벤트 유지
        if len(self.event_history) > 1000:
            self.event_history = self.event_history[-1000:]
        
        # PostgreSQL에 로깅 (옵션)
        if self.storage:
            self._save_event_to_db(event)
        
        # 로그 레벨에 따른 콘솔 출력
        log_message = f"[{event_type}] {reservoir_id}: {details.get('message', json.dumps(details, ensure_ascii=False)[:100])}"
        
        if severity in ["CRITICAL", "HIGH"]:
            logger.error(log_message)
        elif severity == "MEDIUM":
            logger.warning(log_message)
        else:
            logger.info(log_message)

    def _save_event_to_db(self, event: AutomationEvent):
        """이벤트를 데이터베이스에 저장"""
        try:
            # 간단한 로그 테이블에 저장 (테이블이 존재한다면)
            # 실제 구현에서는 적절한 테이블 스키마 필요
            pass
        except Exception as e:
            logger.debug(f"DB 이벤트 저장 실패: {e}")

    def get_automation_status(self) -> Dict[str, Any]:
        """자동화 시스템 현재 상태"""
        return {
            "is_active": self.is_automation_active,
            "config": self.config,
            "monitor_status": self.monitor.get_monitoring_status(),
            "last_decisions": {
                reservoir_id: {
                    "action": decision.action.value,
                    "confidence": decision.confidence,
                    "urgency": decision.urgency.name,
                    "reasoning": decision.reasoning,
                    "timestamp": decision.timestamp.isoformat() if hasattr(decision, 'timestamp') else datetime.now().isoformat()
                }
                for reservoir_id, decision in self.last_decisions.items()
            },
            "recent_events": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "type": event.event_type,
                    "reservoir_id": event.reservoir_id,
                    "severity": event.severity,
                    "message": event.details.get('message', str(event.details)[:100])
                }
                for event in self.event_history[-20:]  # 최근 20개 이벤트
            ]
        }

    def get_learning_summary(self) -> Dict[str, Any]:
        """학습 현황 요약"""
        return self.decision_engine.get_learning_summary()

    def manual_override_automation(self, reservoir_id: str, pump_name: str, action: str, duration: Optional[int] = None) -> Dict[str, Any]:
        """수동 제어 (자동화 시스템 우회)"""
        try:
            result = self.monitor.manual_override(reservoir_id, pump_name, action, duration)
            
            self._log_event("MANUAL", reservoir_id, {
                "pump_name": pump_name,
                "action": action,
                "duration": duration,
                "result": result,
                "message": f"수동 제어: {pump_name} {action}"
            }, "MEDIUM")
            
            return result
            
        except Exception as e:
            logger.error(f"수동 제어 중 오류: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """설정 업데이트"""
        try:
            self.config.update(new_config)
            
            self._log_event("CONFIG", "system", {
                "message": "설정 업데이트",
                "new_config": new_config
            }, "LOW")
            
            return True
            
        except Exception as e:
            logger.error(f"설정 업데이트 중 오류: {e}")
            return False

# 전역 자동화 관리자 인스턴스
_global_automation_manager = None

def get_automation_manager() -> AutomationManager:
    """전역 자동화 관리자 인스턴스 반환"""
    global _global_automation_manager
    if _global_automation_manager is None:
        _global_automation_manager = AutomationManager()
    return _global_automation_manager