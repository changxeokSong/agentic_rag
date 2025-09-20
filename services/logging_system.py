# services/logging_system.py - 자동화 전용 로깅 및 알림 시스템

import json
import csv
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from pathlib import Path

from storage.postgresql_storage import PostgreSQLStorage
from utils.logger import setup_logger

logger = setup_logger(__name__)

class LogLevel(Enum):
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4

class EventType(Enum):
    SYSTEM = "SYSTEM"
    DECISION = "DECISION"
    ACTION = "ACTION"
    ALERT = "ALERT"
    ERROR = "ERROR"
    MANUAL = "MANUAL"
    EVALUATION = "EVALUATION"

@dataclass
class LogEntry:
    timestamp: datetime
    level: LogLevel
    event_type: EventType
    reservoir_id: str
    message: str
    details: Dict[str, Any]
    session_id: Optional[str] = None

@dataclass
class AlertRule:
    name: str
    conditions: Dict[str, Any]  # {"water_level": {"min": 0, "max": 120}, "pump_failures": 3}
    actions: List[str]  # ["log", "console", "file", "database"]
    enabled: bool = True
    last_triggered: Optional[datetime] = None
    cooldown_minutes: int = 5

class AutomationLogger:
    """자동화 시스템 전용 로거"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # 로그 파일 설정
        self.current_session = self._generate_session_id()
        self.log_files = {
            "main": self.log_dir / f"automation_{datetime.now().strftime('%Y%m%d')}.log",
            "events": self.log_dir / f"events_{datetime.now().strftime('%Y%m%d')}.csv",
            "decisions": self.log_dir / f"decisions_{datetime.now().strftime('%Y%m%d')}.json",
            "alerts": self.log_dir / f"alerts_{datetime.now().strftime('%Y%m%d')}.log"
        }
        
        # 메모리 내 로그 버퍼
        self.log_buffer = []
        self.max_buffer_size = 1000
        
        # 알림 규칙
        self.alert_rules = self._setup_default_alert_rules()
        
        # PostgreSQL 연결
        try:
            self.storage = PostgreSQLStorage.get_instance()
            self._setup_database_tables()
        except Exception as e:
            logger.error(f"PostgreSQL 연결 실패 (로깅): {e}")
            self.storage = None
        
        # 스레드 안전성
        self.lock = threading.Lock()
        
        logger.info(f"자동화 로거 초기화 완료 - 세션: {self.current_session}")

    def _generate_session_id(self) -> str:
        """세션 ID 생성"""
        return f"AUTO_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _setup_default_alert_rules(self) -> List[AlertRule]:
        """기본 알림 규칙 설정"""
        return [
            AlertRule(
                name="critical_water_level",
                conditions={"water_level_above": 100},
                actions=["log", "console", "file"],
                cooldown_minutes=10
            ),
            AlertRule(
                name="emergency_water_level", 
                conditions={"water_level_above": 120},
                actions=["log", "console", "file", "database"],
                cooldown_minutes=5
            ),
            AlertRule(
                name="pump_failure",
                conditions={"pump_control_failure": True},
                actions=["log", "console", "file"],
                cooldown_minutes=15
            ),
            AlertRule(
                name="arduino_disconnection",
                conditions={"arduino_connected": False},
                actions=["log", "console", "file"],
                cooldown_minutes=30
            ),
            AlertRule(
                name="multiple_pump_failures",
                conditions={"failed_pumps_count_above": 2},
                actions=["log", "console", "file", "database"],
                cooldown_minutes=20
            )
        ]

    def _setup_database_tables(self):
        """데이터베이스 테이블 설정"""
        if not self.storage:
            return
        
        try:
            # automation_logs 테이블 생성
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS automation_logs (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                session_id VARCHAR(50),
                level VARCHAR(20) NOT NULL,
                event_type VARCHAR(20) NOT NULL,
                reservoir_id VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                details JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_automation_logs_timestamp ON automation_logs(timestamp);
            CREATE INDEX IF NOT EXISTS idx_automation_logs_reservoir ON automation_logs(reservoir_id);
            CREATE INDEX IF NOT EXISTS idx_automation_logs_type ON automation_logs(event_type);
            """
            
            self.storage.execute_query(create_table_sql, commit=True)
            logger.info("자동화 로그 테이블 준비 완료")
            
        except Exception as e:
            logger.error(f"데이터베이스 테이블 설정 오류: {e}")

    def log(self, level: LogLevel, event_type: EventType, reservoir_id: str, message: str, details: Dict[str, Any] = None):
        """로그 기록"""
        with self.lock:
            # 안전한 enum 정규화 (문자열/정수 입력 허용)
            try:
                if isinstance(level, str):
                    level_enum = getattr(LogLevel, level.upper(), LogLevel.INFO)
                elif isinstance(level, int):
                    level_enum = LogLevel(level) if level in [e.value for e in LogLevel] else LogLevel.INFO
                elif isinstance(level, LogLevel):
                    level_enum = level
                else:
                    level_enum = LogLevel.INFO
            except Exception:
                level_enum = LogLevel.INFO

            try:
                if isinstance(event_type, str):
                    event_enum = getattr(EventType, event_type.upper(), EventType.SYSTEM)
                elif isinstance(event_type, EventType):
                    event_enum = event_type
                else:
                    event_enum = EventType.SYSTEM
            except Exception:
                event_enum = EventType.SYSTEM

            entry = LogEntry(
                timestamp=datetime.now(),
                level=level_enum,
                event_type=event_enum,
                reservoir_id=reservoir_id,
                message=message,
                details=details or {},
                session_id=self.current_session
            )
            
            # 버퍼에 추가
            self.log_buffer.append(entry)
            
            # 버퍼 크기 제한
            if len(self.log_buffer) > self.max_buffer_size:
                self.log_buffer = self.log_buffer[-self.max_buffer_size:]
            
            # 다양한 출력 수행
            self._write_to_file(entry)
            self._write_to_console(entry)
            self._write_to_csv(entry)
            
            # 특별한 이벤트는 JSON으로 별도 저장
            if event_type == EventType.DECISION:
                self._write_decision_to_json(entry)
            
            # 데이터베이스 저장
            if self.storage and level.value >= LogLevel.INFO.value:
                self._write_to_database(entry)
            
            # 알림 규칙 확인
            self._check_alert_rules(entry)

    def _write_to_file(self, entry: LogEntry):
        """메인 로그 파일에 기록"""
        try:
            log_line = f"[{entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] [{entry.level.name}] [{entry.event_type.value}] [{entry.reservoir_id}] {entry.message}\n"
            
            with open(self.log_files["main"], "a", encoding="utf-8") as f:
                f.write(log_line)
                
        except Exception as e:
            logger.error(f"파일 로그 쓰기 오류: {e}")

    def _write_to_console(self, entry: LogEntry):
        """콘솔에 출력 - 중복 방지를 위해 직접 print 사용"""
        if entry.level.value >= LogLevel.INFO.value:
            timestamp = entry.timestamp.strftime('%H:%M:%S')
            prefix = "🤖 [AUTO]"
            message = f"[{timestamp}] {prefix} [{entry.event_type.value}] {entry.reservoir_id}: {entry.message}"
            
            # 직접 출력하여 중복 로그 방지
            print(message)

    def _write_to_csv(self, entry: LogEntry):
        """CSV 파일에 이벤트 기록"""
        try:
            file_exists = self.log_files["events"].exists()
            
            with open(self.log_files["events"], "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                
                # 헤더 추가 (파일이 새로 생성된 경우)
                if not file_exists:
                    writer.writerow([
                        "timestamp", "session_id", "level", "event_type", 
                        "reservoir_id", "message", "details"
                    ])
                
                writer.writerow([
                    entry.timestamp.isoformat(),
                    entry.session_id,
                    entry.level.name,
                    entry.event_type.value,
                    entry.reservoir_id,
                    entry.message,
                    json.dumps(entry.details, ensure_ascii=False, separators=(',', ':'))
                ])
                
        except Exception as e:
            logger.error(f"CSV 로그 쓰기 오류: {e}")

    def _write_decision_to_json(self, entry: LogEntry):
        """의사결정 로그를 JSON 파일에 저장"""
        try:
            decision_data = {
                "timestamp": entry.timestamp.isoformat(),
                "session_id": entry.session_id,
                "reservoir_id": entry.reservoir_id,
                "message": entry.message,
                "details": entry.details
            }
            
            # 기존 데이터 로드
            decisions = []
            if self.log_files["decisions"].exists():
                try:
                    with open(self.log_files["decisions"], "r", encoding="utf-8") as f:
                        decisions = json.load(f)
                except:
                    decisions = []
            
            decisions.append(decision_data)
            
            # 최근 100개만 유지
            if len(decisions) > 100:
                decisions = decisions[-100:]
            
            with open(self.log_files["decisions"], "w", encoding="utf-8") as f:
                json.dump(decisions, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"의사결정 JSON 로그 쓰기 오류: {e}")

    def _write_to_database(self, entry: LogEntry):
        """데이터베이스에 로그 저장"""
        try:
            if not self.storage:
                return
            
            insert_sql = """
            INSERT INTO automation_logs (timestamp, session_id, level, event_type, reservoir_id, message, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            self.storage.execute_query(
                insert_sql,
                params=(
                    entry.timestamp,
                    entry.session_id,
                    entry.level.name,
                    entry.event_type.value,
                    entry.reservoir_id,
                    entry.message,
                    json.dumps(entry.details)
                ),
                commit=True
            )
            
        except Exception as e:
            logger.debug(f"데이터베이스 로그 저장 오류: {e}")

    def _check_alert_rules(self, entry: LogEntry):
        """알림 규칙 확인 및 실행"""
        try:
            current_time = datetime.now()
            
            for rule in self.alert_rules:
                if not rule.enabled:
                    continue
                
                # 쿨다운 확인
                if (rule.last_triggered and 
                    current_time - rule.last_triggered < timedelta(minutes=rule.cooldown_minutes)):
                    continue
                
                # 조건 확인
                if self._match_alert_conditions(entry, rule.conditions):
                    self._trigger_alert(entry, rule)
                    rule.last_triggered = current_time
                    
        except Exception as e:
            logger.error(f"알림 규칙 확인 중 오류: {e}")

    def _match_alert_conditions(self, entry: LogEntry, conditions: Dict[str, Any]) -> bool:
        """알림 조건 매칭"""
        try:
            details = entry.details
            
            # 수위 기반 조건
            if "water_level_above" in conditions:
                water_level = details.get("current_level", 0)
                if water_level > conditions["water_level_above"]:
                    return True
            
            # 펌프 실패 조건
            if "pump_control_failure" in conditions:
                pump_success = details.get("result", {}).get("success", True)
                if not pump_success and conditions["pump_control_failure"]:
                    return True
            
            # 아두이노 연결 조건 (명시적으로 연결 상태가 제공된 경우만)
            if "arduino_connected" in conditions:
                # details에 arduino_connected가 명시적으로 있을 때만 확인
                if "arduino_connected" in details:
                    arduino_connected = details.get("arduino_connected")
                    if arduino_connected != conditions["arduino_connected"]:
                        return True
            
            # 다중 펌프 실패 조건
            if "failed_pumps_count_above" in conditions:
                failed_pumps = details.get("failed_pumps_count", 0)
                if failed_pumps > conditions["failed_pumps_count_above"]:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"알림 조건 매칭 중 오류: {e}")
            return False

    def _trigger_alert(self, entry: LogEntry, rule: AlertRule):
        """알림 실행"""
        alert_message = f"🚨 ALERT: {rule.name} - {entry.message}"
        
        try:
            # 콘솔 출력 (중복 방지를 위해 직접 print 사용)
            if "console" in rule.actions:
                timestamp = entry.timestamp.strftime('%H:%M:%S')
                print(f"[{timestamp}] 🤖 [AUTO] [ALERT] {entry.reservoir_id}: {alert_message}")
            
            # 파일 기록
            if "file" in rule.actions:
                with open(self.log_files["alerts"], "a", encoding="utf-8") as f:
                    f.write(f"[{entry.timestamp.isoformat()}] {alert_message}\n")
            
            # 데이터베이스 기록 (재귀 호출 방지)
            if "database" in rule.actions and self.storage:
                try:
                    insert_sql = """
                    INSERT INTO automation_logs (timestamp, session_id, level, event_type, reservoir_id, message, details)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    self.storage.execute_query(
                        insert_sql,
                        params=(
                            entry.timestamp,
                            entry.session_id,
                            'CRITICAL',
                            'ALERT',
                            entry.reservoir_id,
                            f"Alert triggered: {rule.name}",
                            json.dumps({"rule": rule.name, "original_message": entry.message})
                        ),
                        commit=True
                    )
                except Exception as db_e:
                    print(f"데이터베이스 알림 저장 오류: {db_e}")
            
        except Exception as e:
            print(f"알림 실행 중 오류: {e}")

    # 편의 메서드들
    def info(self, event_type: EventType, reservoir_id: str, message: str, details: Dict[str, Any] = None):
        self.log(LogLevel.INFO, event_type, reservoir_id, message, details)
    
    def warning(self, event_type: EventType, reservoir_id: str, message: str, details: Dict[str, Any] = None):
        self.log(LogLevel.WARNING, event_type, reservoir_id, message, details)
    
    def error(self, event_type: EventType, reservoir_id: str, message: str, details: Dict[str, Any] = None):
        self.log(LogLevel.ERROR, event_type, reservoir_id, message, details)
    
    def critical(self, event_type: EventType, reservoir_id: str, message: str, details: Dict[str, Any] = None):
        self.log(LogLevel.CRITICAL, event_type, reservoir_id, message, details)

    def get_recent_logs(self, limit: int = 50, level: LogLevel = LogLevel.DEBUG) -> List[Dict[str, Any]]:
        """최근 로그 조회"""
        with self.lock:
            try:
                # level 파라미터가 LogLevel enum인지 확인하고 안전하게 처리
                if isinstance(level, str):
                    # 문자열인 경우 LogLevel로 변환
                    level_value = getattr(LogLevel, level.upper(), LogLevel.DEBUG).value
                elif isinstance(level, LogLevel):
                    level_value = level.value
                else:
                    level_value = LogLevel.DEBUG.value
                
                filtered_logs = [
                    entry for entry in self.log_buffer 
                    if hasattr(entry.level, 'value') and entry.level.value >= level_value
                ]
                
                return [
                    {
                        "timestamp": entry.timestamp.isoformat() if hasattr(entry.timestamp, 'isoformat') else str(entry.timestamp),
                        "level": entry.level.name if hasattr(entry.level, 'name') else str(entry.level),
                        "event_type": entry.event_type.value if hasattr(entry.event_type, 'value') else str(entry.event_type),
                        "reservoir_id": str(entry.reservoir_id),
                        "message": str(entry.message),
                        "details": entry.details if entry.details else {}
                    }
                    for entry in filtered_logs[-limit:]
                ]
            except Exception as e:
                # 오류 발생 시 빈 리스트 반환
                logger.error(f"로그 조회 중 오류: {e}")
                return []

    def get_logs_by_reservoir(self, reservoir_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        """특정 배수지 로그 조회"""
        with self.lock:
            try:
                reservoir_logs = [
                    entry for entry in self.log_buffer 
                    if str(entry.reservoir_id) == str(reservoir_id)
                ]
                
                return [
                    {
                        "timestamp": entry.timestamp.isoformat() if hasattr(entry.timestamp, 'isoformat') else str(entry.timestamp),
                        "level": entry.level.name if hasattr(entry.level, 'name') else str(entry.level),
                        "event_type": entry.event_type.value if hasattr(entry.event_type, 'value') else str(entry.event_type),
                        "reservoir_id": str(entry.reservoir_id),
                        "message": str(entry.message),
                        "details": entry.details if entry.details else {}
                    }
                    for entry in reservoir_logs[-limit:]
                ]
            except Exception as e:
                logger.error(f"배수지별 로그 조회 중 오류: {e}")
                return []

    def get_decision_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """의사결정 이력 조회"""
        try:
            if not self.log_files["decisions"].exists():
                return []
            
            with open(self.log_files["decisions"], "r", encoding="utf-8") as f:
                decisions = json.load(f)
                return decisions[-limit:] if decisions else []
                
        except Exception as e:
            logger.error(f"의사결정 이력 조회 오류: {e}")
            return []

    def export_logs(self, start_date: datetime, end_date: datetime, format: str = "csv") -> str:
        """로그 내보내기"""
        try:
            filtered_logs = [
                entry for entry in self.log_buffer
                if start_date <= entry.timestamp <= end_date
            ]
            
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if format.lower() == "csv":
                export_file = self.log_dir / f"export_{timestamp_str}.csv"
                
                with open(export_file, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "timestamp", "level", "event_type", "reservoir_id", "message", "details"
                    ])
                    
                    for entry in filtered_logs:
                        writer.writerow([
                            entry.timestamp.isoformat(),
                            entry.level.name,
                            entry.event_type.value,
                            entry.reservoir_id,
                            entry.message,
                            json.dumps(entry.details, ensure_ascii=False, separators=(',', ':'))
                        ])
                        
            elif format.lower() == "json":
                export_file = self.log_dir / f"export_{timestamp_str}.json"
                
                export_data = [
                    {
                        "timestamp": entry.timestamp.isoformat(),
                        "level": entry.level.name,
                        "event_type": entry.event_type.value,
                        "reservoir_id": entry.reservoir_id,
                        "message": entry.message,
                        "details": entry.details
                    }
                    for entry in filtered_logs
                ]
                
                with open(export_file, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            return str(export_file)
            
        except Exception as e:
            logger.error(f"로그 내보내기 오류: {e}")
            raise

    def add_alert_rule(self, rule: AlertRule) -> bool:
        """알림 규칙 추가"""
        try:
            self.alert_rules.append(rule)
            self.info(EventType.SYSTEM, "system", f"알림 규칙 추가: {rule.name}")
            return True
            
        except Exception as e:
            logger.error(f"알림 규칙 추가 오류: {e}")
            return False

    def cleanup_old_logs(self, days_to_keep: int = 30):
        """오래된 로그 파일 정리"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            for log_file in self.log_dir.glob("*.log"):
                if log_file.stat().st_mtime < cutoff_date.timestamp():
                    log_file.unlink()
                    logger.info(f"오래된 로그 파일 삭제: {log_file}")
            
            for csv_file in self.log_dir.glob("*.csv"):
                if csv_file.stat().st_mtime < cutoff_date.timestamp():
                    csv_file.unlink()
                    logger.info(f"오래된 CSV 파일 삭제: {csv_file}")
                    
        except Exception as e:
            logger.error(f"로그 정리 중 오류: {e}")

# 전역 자동화 로거 인스턴스
_global_automation_logger = None

def get_automation_logger() -> AutomationLogger:
    """전역 자동화 로거 인스턴스 반환"""
    global _global_automation_logger
    if _global_automation_logger is None:
        _global_automation_logger = AutomationLogger()
    return _global_automation_logger