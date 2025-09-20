# services/real_time_monitor.py - 실시간 모니터링 및 자동 제어 서비스

import threading
import time
import signal
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from tools.water_level_monitoring_tool import WaterLevelMonitor
from utils.arduino_direct import DirectArduinoComm
from utils.logger import setup_logger

logger = setup_logger(__name__)

class AlertLevel(Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"  
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"

@dataclass
class ReservoirStatus:
    reservoir_id: str
    current_level: float
    alert_level: AlertLevel
    pumps_active: List[str]
    last_updated: datetime
    
@dataclass
class ControlAction:
    timestamp: datetime
    reservoir_id: str
    action: str  # "PUMP_ON", "PUMP_OFF", "ALERT"
    target: str  # pump name or alert type
    reason: str
    success: bool
    details: Dict[str, Any]

class RealtimeMonitor:
    """실시간 수위 모니터링 및 자동 제어 서비스"""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval  # 체크 간격 (초)
        self.water_monitor = WaterLevelMonitor()
        self.arduino_comm = DirectArduinoComm()
        
        # 제어 규칙 설정
        self.control_rules = {
            # 수위별 임계값 설정 (cm)
            "thresholds": {
                "emergency": 120,    # 긴급 - 모든 펌프 가동
                "critical": 100,     # 위험 - 주 펌프 2개 가동
                "warning": 80,       # 주의 - 주 펌프 1개 가동
                "normal": 60,        # 정상 - 펌프 중단
                "low": 30           # 낮음 - 모든 펌프 중단
            },
            # 배수지별 펌프 우선순위
            "pump_priority": {
                "gagok": ["gagok_pump_a", "gagok_pump_b"],
                "haeryong": ["haeryong_pump_a", "haeryong_pump_b"], 
                "sangsa": ["sangsa_pump_a", "sangsa_pump_b", "sangsa_pump_c"]
            }
        }
        
        # 상태 추적
        self.current_status = {}
        self.control_history = []
        self.is_monitoring = False
        self.monitor_thread = None
        
        # 펌프 제어 쿨다운 (과도한 ON/OFF 방지)
        self.pump_cooldown = {}  # {pump_name: last_action_time}
        self.cooldown_duration = 300  # 5분

    def start_monitoring(self) -> bool:
        """모니터링 서비스 시작"""
        if self.is_monitoring:
            logger.warning("모니터링이 이미 실행 중입니다")
            return False
            
        try:
            logger.info(f"실시간 모니터링 서비스 시작 (간격: {self.check_interval}초)")
            self.is_monitoring = True
            
            # 아두이노 연결 초기화 (오류 무시)
            try:
                self.arduino_comm.connect()
            except Exception as e:
                logger.warning(f"아두이노 연결 중 오류 (계속 진행): {e}")
            
            # 모니터링 스레드 시작 (daemon=True로 메인 프로세스 종료 시 자동 종료)
            self.monitor_thread = threading.Thread(
                target=self._monitoring_loop, 
                daemon=True,
                name="WaterMonitorThread"
            )
            self.monitor_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"모니터링 시작 중 오류: {e}")
            self.is_monitoring = False
            return False

    def stop_monitoring(self):
        """모니터링 서비스 중단"""
        logger.info("실시간 모니터링 서비스 중단 중...")
        self.is_monitoring = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
            
        # 아두이노 연결 해제
        self.arduino_comm.disconnect()
        logger.info("모니터링 서비스 중단 완료")

    def _monitoring_loop(self):
        """메인 모니터링 루프"""
        while self.is_monitoring:
            try:
                # 1. 현재 수위 데이터 조회
                current_data = self.water_monitor.get_current_status()
                
                if current_data.get('success'):
                    reservoirs = current_data.get('reservoirs', [])
                    
                    # 2. 각 배수지 상태 분석 및 제어 결정
                    for reservoir in reservoirs:
                        self._analyze_and_control(reservoir)
                        
                else:
                    logger.error(f"수위 데이터 조회 실패: {current_data.get('error')}")
                    
            except Exception as e:
                logger.error(f"모니터링 루프 오류: {e}")
                
            # 다음 체크까지 대기
            time.sleep(self.check_interval)

    def _analyze_and_control(self, reservoir_data: Dict[str, Any]):
        """배수지 상태 분석 및 자동 제어 실행"""
        reservoir_id = reservoir_data.get('reservoir_id')
        if not reservoir_id:
            logger.error("reservoir_id가 없는 데이터를 건너뜁니다")
            return
            
        current_level = reservoir_data.get('current_level', 0)
        pump_statuses = reservoir_data.get('pump_statuses', {})
        
        logger.info(f"[{reservoir_id}] 현재 수위: {current_level}cm")
        
        # 1. 위험도 레벨 판정
        alert_level = self._determine_alert_level(current_level)
        
        # 2. 현재 상태 업데이트
        self.current_status[reservoir_id] = ReservoirStatus(
            reservoir_id=reservoir_id,
            current_level=current_level,
            alert_level=alert_level,
            pumps_active=[name for name, active in pump_statuses.items() if active],
            last_updated=datetime.now()
        )
        
        # 3. 제어 결정 및 실행
        control_actions = self._decide_control_actions(reservoir_id, current_level, pump_statuses)
        
        for action in control_actions:
            self._execute_control_action(action)

    def _determine_alert_level(self, water_level: float) -> AlertLevel:
        """수위에 따른 경고 레벨 판정"""
        thresholds = self.control_rules["thresholds"]
        
        if water_level >= thresholds["emergency"]:
            return AlertLevel.EMERGENCY
        elif water_level >= thresholds["critical"]:
            return AlertLevel.CRITICAL
        elif water_level >= thresholds["warning"]:
            return AlertLevel.WARNING
        else:
            return AlertLevel.NORMAL

    def _decide_control_actions(self, reservoir_id: str, current_level: float, pump_statuses: Dict[str, bool]) -> List[ControlAction]:
        """수위 기반 제어 행동 결정"""
        actions = []
        thresholds = self.control_rules["thresholds"]
        pump_priority = self.control_rules["pump_priority"].get(reservoir_id, [])
        
        now = datetime.now()
        
        # 긴급 상황 - 모든 펌프 가동
        if current_level >= thresholds["emergency"]:
            for pump_name in pump_priority:
                if not pump_statuses.get(pump_name.replace(f"{reservoir_id}_", ""), False):
                    if self._can_control_pump(pump_name, now):
                        actions.append(ControlAction(
                            timestamp=now,
                            reservoir_id=reservoir_id,
                            action="PUMP_ON",
                            target=pump_name,
                            reason=f"긴급 상황: 수위 {current_level}cm >= {thresholds['emergency']}cm",
                            success=False,
                            details={}
                        ))
                        
        # 위험 상황 - 주요 펌프 2개 가동
        elif current_level >= thresholds["critical"]:
            target_pumps = pump_priority[:2]  # 상위 2개 펌프
            
            for pump_name in target_pumps:
                pump_key = pump_name.replace(f"{reservoir_id}_", "")
                if not pump_statuses.get(pump_key, False):
                    if self._can_control_pump(pump_name, now):
                        actions.append(ControlAction(
                            timestamp=now,
                            reservoir_id=reservoir_id,
                            action="PUMP_ON",
                            target=pump_name,
                            reason=f"위험 상황: 수위 {current_level}cm >= {thresholds['critical']}cm",
                            success=False,
                            details={}
                        ))
            
            # 불필요한 펌프 중단
            for pump_name in pump_priority[2:]:
                pump_key = pump_name.replace(f"{reservoir_id}_", "")
                if pump_statuses.get(pump_key, False):
                    if self._can_control_pump(pump_name, now):
                        actions.append(ControlAction(
                            timestamp=now,
                            reservoir_id=reservoir_id,
                            action="PUMP_OFF",
                            target=pump_name,
                            reason=f"최적화: 위험 수준에서 2개 펌프만 필요",
                            success=False,
                            details={}
                        ))
                        
        # 주의 상황 - 주 펌프 1개만 가동
        elif current_level >= thresholds["warning"]:
            main_pump = pump_priority[0] if pump_priority else None
            
            if main_pump:
                pump_key = main_pump.replace(f"{reservoir_id}_", "")
                if not pump_statuses.get(pump_key, False):
                    if self._can_control_pump(main_pump, now):
                        actions.append(ControlAction(
                            timestamp=now,
                            reservoir_id=reservoir_id,
                            action="PUMP_ON",
                            target=main_pump,
                            reason=f"주의 상황: 수위 {current_level}cm >= {thresholds['warning']}cm",
                            success=False,
                            details={}
                        ))
            
            # 추가 펌프들은 중단
            for pump_name in pump_priority[1:]:
                pump_key = pump_name.replace(f"{reservoir_id}_", "")
                if pump_statuses.get(pump_key, False):
                    if self._can_control_pump(pump_name, now):
                        actions.append(ControlAction(
                            timestamp=now,
                            reservoir_id=reservoir_id,
                            action="PUMP_OFF",
                            target=pump_name,
                            reason=f"최적화: 주의 수준에서 1개 펌프만 필요",
                            success=False,
                            details={}
                        ))
                        
        # 정상 상황 - 모든 펌프 중단
        elif current_level < thresholds["normal"]:
            for pump_name in pump_priority:
                pump_key = pump_name.replace(f"{reservoir_id}_", "")
                if pump_statuses.get(pump_key, False):
                    if self._can_control_pump(pump_name, now):
                        actions.append(ControlAction(
                            timestamp=now,
                            reservoir_id=reservoir_id,
                            action="PUMP_OFF", 
                            target=pump_name,
                            reason=f"정상 상황: 수위 {current_level}cm < {thresholds['normal']}cm",
                            success=False,
                            details={}
                        ))
        
        return actions

    def _can_control_pump(self, pump_name: str, current_time: datetime) -> bool:
        """펌프 제어 쿨다운 확인"""
        last_action = self.pump_cooldown.get(pump_name)
        if last_action is None:
            return True
            
        time_diff = (current_time - last_action).total_seconds()
        return time_diff >= self.cooldown_duration

    def _execute_control_action(self, action: ControlAction):
        """제어 행동 실제 실행"""
        try:
            pump_name = action.target
            
            if action.action == "PUMP_ON":
                # 펌프 이름에서 번호 추출 (gagok_pump_a -> pump1)
                pump_id = self._extract_pump_id(pump_name)
                result = self.arduino_comm.control_pump(pump_id, "ON")
                
                if result.get('success'):
                    action.success = True
                    action.details = result
                    logger.info(f"✅ 펌프 ON 성공: {pump_name} (이유: {action.reason})")
                else:
                    action.success = False
                    action.details = result
                    logger.error(f"❌ 펌프 ON 실패: {pump_name} - {result.get('error')}")
                    
            elif action.action == "PUMP_OFF":
                pump_id = self._extract_pump_id(pump_name)
                result = self.arduino_comm.control_pump(pump_id, "OFF")
                
                if result.get('success'):
                    action.success = True
                    action.details = result
                    logger.info(f"⏹️ 펌프 OFF 성공: {pump_name} (이유: {action.reason})")
                else:
                    action.success = False
                    action.details = result
                    logger.error(f"❌ 펌프 OFF 실패: {pump_name} - {result.get('error')}")
            
            # 쿨다운 설정
            self.pump_cooldown[pump_name] = action.timestamp
            
        except Exception as e:
            logger.error(f"제어 행동 실행 중 오류: {e}")
            action.success = False
            action.details = {"error": str(e)}
        
        # 행동 기록 저장
        self.control_history.append(action)
        
        # 최근 100개 행동만 유지
        if len(self.control_history) > 100:
            self.control_history = self.control_history[-100:]

    def _extract_pump_id(self, pump_name: str) -> int:
        """펌프 이름에서 아두이노 펌프 ID 추출"""
        # gagok_pump_a -> 1, gagok_pump_b -> 2, etc.
        if 'pump_a' in pump_name:
            return 1
        elif 'pump_b' in pump_name:
            return 2
        elif 'pump_c' in pump_name:
            return 3
        else:
            return 1  # 기본값

    def get_monitoring_status(self) -> Dict[str, Any]:
        """현재 모니터링 상태 반환"""
        return {
            "is_active": self.is_monitoring,
            "check_interval": self.check_interval,
            "arduino_connected": self.arduino_comm.is_connected(),
            "current_status": {
                reservoir_id: {
                    "current_level": status.current_level,
                    "alert_level": status.alert_level.value,
                    "pumps_active": status.pumps_active,
                    "last_updated": status.last_updated.isoformat()
                }
                for reservoir_id, status in self.current_status.items()
            },
            "recent_actions": [
                {
                    "timestamp": action.timestamp.isoformat(),
                    "reservoir_id": action.reservoir_id,
                    "action": action.action,
                    "target": action.target,
                    "reason": action.reason,
                    "success": action.success
                }
                for action in self.control_history[-10:]  # 최근 10개 행동
            ]
        }

    def get_control_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """제어 이력 조회"""
        return [
            {
                "timestamp": action.timestamp.isoformat(),
                "reservoir_id": action.reservoir_id,
                "action": action.action,
                "target": action.target,
                "reason": action.reason,
                "success": action.success,
                "details": action.details
            }
            for action in self.control_history[-limit:]
        ]

    def manual_override(self, reservoir_id: str, pump_name: str, state: str, duration: Optional[int] = None) -> Dict[str, Any]:
        """수동 펌프 제어 (모니터링 시스템 우회)"""
        try:
            pump_id = self._extract_pump_id(pump_name)
            result = self.arduino_comm.control_pump(pump_id, state, duration)
            
            # 수동 제어 기록
            action = ControlAction(
                timestamp=datetime.now(),
                reservoir_id=reservoir_id,
                action=f"MANUAL_{state}",
                target=pump_name,
                reason=f"수동 제어 ({duration}초)" if duration else "수동 제어",
                success=result.get('success', False),
                details=result
            )
            
            self.control_history.append(action)
            
            return {
                "success": True,
                "message": f"수동 제어 완료: {pump_name} {state}",
                "details": result
            }
            
        except Exception as e:
            logger.error(f"수동 제어 중 오류: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# 전역 모니터링 인스턴스
_global_monitor = None

def get_monitor() -> RealtimeMonitor:
    """전역 모니터링 인스턴스 반환"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = RealtimeMonitor()
    return _global_monitor