# services/real_time_database_updater.py - 실시간 데이터베이스 업데이트 서비스

import threading
import time
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import psycopg2
import psycopg2.extras
from dataclasses import dataclass
import random
import numpy as np

from config import PG_DB_HOST, PG_DB_PORT, PG_DB_NAME, PG_DB_USER, PG_DB_PASSWORD
from utils.arduino_direct import DirectArduinoComm
from utils.logger import setup_logger

logger = setup_logger(__name__)

@dataclass
class WaterLevelReading:
    """수위 측정 데이터"""
    timestamp: datetime
    gagok_level: float
    haeryong_level: float
    sangsa_level: float
    gagok_pump_a: bool
    gagok_pump_b: bool
    haeryong_pump_a: bool
    haeryong_pump_b: bool
    sangsa_pump_a: bool
    sangsa_pump_b: bool
    sangsa_pump_c: bool
    
class RealTimeDatabaseUpdater:
    """실시간 수위 데이터 수집 및 데이터베이스 업데이트 서비스"""
    
    def __init__(self, update_interval: int = 60):
        self.update_interval = update_interval  # 업데이트 간격 (초)
        
        # 데이터베이스 연결 정보
        self.db_config = {
            'host': PG_DB_HOST,
            'port': PG_DB_PORT,
            'database': PG_DB_NAME,
            'user': PG_DB_USER,
            'password': PG_DB_PASSWORD
        }
        
        # 아두이노 통신 객체
        self.arduino_comm = DirectArduinoComm()
        
        # 서비스 상태
        self.is_running = False
        self.update_thread = None
        self.last_reading = None
        self.readings_count = 0
        
        # 시뮬레이션 모드 (아두이노가 연결되지 않았을 때)
        self.simulation_mode = False
        self.simulation_base_levels = {
            'gagok': 75.0,
            'haeryong': 68.0,
            'sangsa': 82.0
        }
        
    def start_updating(self) -> bool:
        """실시간 데이터베이스 업데이트 서비스 시작"""
        if self.is_running:
            logger.warning("데이터베이스 업데이트 서비스가 이미 실행 중입니다")
            return False
            
        try:
            logger.info(f"실시간 데이터베이스 업데이트 서비스 시작 (간격: {self.update_interval}초)")
            self.is_running = True
            
            # 데이터베이스 연결 테스트
            if not self._test_database_connection():
                logger.error("데이터베이스 연결 실패")
                self.is_running = False
                return False
            
            # 아두이노 연결 시도 (실패해도 시뮬레이션 모드로 진행)
            try:
                self.arduino_comm.connect()
                if self.arduino_comm.is_connected():
                    logger.info("아두이노 연결 성공 - 실제 센서 데이터 사용")
                    self.simulation_mode = False
                else:
                    logger.warning("아두이노 연결 실패 - 시뮬레이션 모드 사용")
                    self.simulation_mode = True
            except Exception as e:
                logger.warning(f"아두이노 연결 중 오류 (시뮬레이션 모드로 진행): {e}")
                self.simulation_mode = True
            
            # 업데이트 스레드 시작
            self.update_thread = threading.Thread(
                target=self._update_loop,
                daemon=True,
                name="DatabaseUpdateThread"
            )
            self.update_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"데이터베이스 업데이트 서비스 시작 중 오류: {e}")
            self.is_running = False
            return False
    
    def stop_updating(self):
        """데이터베이스 업데이트 서비스 중단"""
        logger.info("실시간 데이터베이스 업데이트 서비스 중단 중...")
        self.is_running = False
        
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=5)
            
        # 아두이노 연결 해제
        self.arduino_comm.disconnect()
        logger.info("데이터베이스 업데이트 서비스 중단 완료")
    
    def _test_database_connection(self) -> bool:
        """데이터베이스 연결 테스트"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    return result is not None
        except Exception as e:
            logger.error(f"데이터베이스 연결 테스트 실패: {e}")
            return False
    
    def _update_loop(self):
        """메인 업데이트 루프"""
        while self.is_running:
            try:
                # 1. 센서 데이터 수집
                reading = self._collect_sensor_data()
                
                if reading:
                    # 2. 데이터베이스에 저장
                    success = self._save_to_database(reading)
                    
                    if success:
                        self.last_reading = reading
                        self.readings_count += 1
                        logger.info(f"데이터 저장 성공 #{self.readings_count}: "
                                  f"가곡={reading.gagok_level:.1f}cm, "
                                  f"해룡={reading.haeryong_level:.1f}cm, "
                                  f"상사={reading.sangsa_level:.1f}cm")
                    else:
                        logger.error("데이터베이스 저장 실패")
                else:
                    logger.warning("센서 데이터 수집 실패")
                    
            except Exception as e:
                logger.error(f"업데이트 루프 오류: {e}")
                
            # 다음 업데이트까지 대기
            time.sleep(self.update_interval)
    
    def _collect_sensor_data(self) -> Optional[WaterLevelReading]:
        """센서에서 수위 데이터 수집"""
        try:
            if self.simulation_mode:
                # 시뮬레이션 모드 - 가상 데이터 생성
                return self._generate_simulation_data()
            else:
                # 실제 센서 모드 - 아두이노에서 데이터 가져오기
                return self._collect_arduino_data()
                
        except Exception as e:
            logger.error(f"센서 데이터 수집 중 오류: {e}")
            return None
    
    def _collect_arduino_data(self) -> Optional[WaterLevelReading]:
        """아두이노에서 실제 센서 데이터 수집"""
        try:
            # 아두이노에서 센서 값 읽기
            sensor_result = self.arduino_comm.read_water_level()
            
            if not sensor_result.get('success'):
                logger.error(f"아두이노 센서 읽기 실패: {sensor_result.get('error')}")
                return None
            
            # 펌프 상태 읽기
            pump_result = self.arduino_comm.read_pump_status()
            pump_status = pump_result.get('pump_status', {}) if pump_result.get('success') else {}
            
            # 센서 값을 배수지별로 매핑 (실제 센서 연결에 따라 조정 필요)
            sensor_data = sensor_result.get('sensor_data', {})
            
            return WaterLevelReading(
                timestamp=datetime.now(),
                gagok_level=float(sensor_data.get('channel_0', 0)),
                haeryong_level=float(sensor_data.get('channel_1', 0)),
                sangsa_level=float(sensor_data.get('channel_2', 0)),
                gagok_pump_a=pump_status.get('pump1', False),
                gagok_pump_b=pump_status.get('pump2', False),
                haeryong_pump_a=False,  # 아두이노가 2개 펌프만 제어할 수 있다고 가정
                haeryong_pump_b=False,
                sangsa_pump_a=False,
                sangsa_pump_b=False,
                sangsa_pump_c=False
            )
            
        except Exception as e:
            logger.error(f"아두이노 데이터 수집 중 오류: {e}")
            return None
    
    def _generate_simulation_data(self) -> WaterLevelReading:
        """시뮬레이션용 가상 데이터 생성"""
        now = datetime.now()
        
        # 시간에 따른 변화 시뮬레이션
        time_factor = (now.hour * 3600 + now.minute * 60 + now.second) / 86400.0
        
        # 각 배수지별 시뮬레이션 수위 (정현파 + 노이즈)
        gagok_level = (self.simulation_base_levels['gagok'] + 
                      15 * np.sin(time_factor * 2 * np.pi + 0) +
                      random.normalvariate(0, 2))
        
        haeryong_level = (self.simulation_base_levels['haeryong'] + 
                         20 * np.sin(time_factor * 2 * np.pi + np.pi/3) +
                         random.normalvariate(0, 1.5))
        
        sangsa_level = (self.simulation_base_levels['sangsa'] + 
                       25 * np.sin(time_factor * 2 * np.pi + 2*np.pi/3) +
                       random.normalvariate(0, 3))
        
        # 수위 범위 제한
        gagok_level = max(30, min(120, gagok_level))
        haeryong_level = max(30, min(120, haeryong_level))
        sangsa_level = max(30, min(120, sangsa_level))
        
        # 펌프 상태 (수위에 따른 자동 제어 시뮬레이션)
        gagok_pump_a = gagok_level > 85
        gagok_pump_b = gagok_level > 95
        haeryong_pump_a = haeryong_level > 80
        haeryong_pump_b = haeryong_level > 90
        sangsa_pump_a = sangsa_level > 90
        sangsa_pump_b = sangsa_level > 100
        sangsa_pump_c = sangsa_level > 110
        
        return WaterLevelReading(
            timestamp=now,
            gagok_level=round(gagok_level, 1),
            haeryong_level=round(haeryong_level, 1),
            sangsa_level=round(sangsa_level, 1),
            gagok_pump_a=gagok_pump_a,
            gagok_pump_b=gagok_pump_b,
            haeryong_pump_a=haeryong_pump_a,
            haeryong_pump_b=haeryong_pump_b,
            sangsa_pump_a=sangsa_pump_a,
            sangsa_pump_b=sangsa_pump_b,
            sangsa_pump_c=sangsa_pump_c
        )
    
    def _save_to_database(self, reading: WaterLevelReading) -> bool:
        """수위 데이터를 PostgreSQL water 테이블에 저장"""
        try:
            with psycopg2.connect(**self.db_config) as conn:
                with conn.cursor() as cur:
                    insert_query = """
                        INSERT INTO water 
                        (measured_at, 
                         gagok_water_level, gagok_pump_a, gagok_pump_b,
                         haeryong_water_level, haeryong_pump_a, haeryong_pump_b,
                         sangsa_water_level, sangsa_pump_a, sangsa_pump_b, sangsa_pump_c)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    # boolean 값을 double precision (1.0/0.0)으로 변환
                    cur.execute(insert_query, (
                        reading.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        reading.gagok_level, 
                        1.0 if reading.gagok_pump_a else 0.0, 
                        1.0 if reading.gagok_pump_b else 0.0,
                        reading.haeryong_level, 
                        1.0 if reading.haeryong_pump_a else 0.0, 
                        1.0 if reading.haeryong_pump_b else 0.0,
                        reading.sangsa_level, 
                        1.0 if reading.sangsa_pump_a else 0.0, 
                        1.0 if reading.sangsa_pump_b else 0.0, 
                        1.0 if reading.sangsa_pump_c else 0.0
                    ))
                    
                    conn.commit()
                    return True
                    
        except Exception as e:
            logger.error(f"데이터베이스 저장 중 오류: {e}")
            return False
    
    def get_service_status(self) -> Dict[str, Any]:
        """서비스 상태 정보 반환"""
        return {
            "is_running": self.is_running,
            "update_interval": self.update_interval,
            "simulation_mode": self.simulation_mode,
            "arduino_connected": self.arduino_comm.is_connected() if not self.simulation_mode else None,
            "readings_count": self.readings_count,
            "last_reading": {
                "timestamp": self.last_reading.timestamp.isoformat() if self.last_reading else None,
                "gagok_level": self.last_reading.gagok_level if self.last_reading else None,
                "haeryong_level": self.last_reading.haeryong_level if self.last_reading else None,
                "sangsa_level": self.last_reading.sangsa_level if self.last_reading else None
            } if self.last_reading else None
        }
    
    def manual_data_collection(self) -> Optional[Dict[str, Any]]:
        """수동 데이터 수집 및 저장"""
        try:
            reading = self._collect_sensor_data()
            if reading:
                success = self._save_to_database(reading)
                return {
                    "success": success,
                    "reading": {
                        "timestamp": reading.timestamp.isoformat(),
                        "gagok_level": reading.gagok_level,
                        "haeryong_level": reading.haeryong_level,
                        "sangsa_level": reading.sangsa_level,
                        "pump_status": {
                            "gagok_pump_a": reading.gagok_pump_a,
                            "gagok_pump_b": reading.gagok_pump_b,
                            "haeryong_pump_a": reading.haeryong_pump_a,
                            "haeryong_pump_b": reading.haeryong_pump_b,
                            "sangsa_pump_a": reading.sangsa_pump_a,
                            "sangsa_pump_b": reading.sangsa_pump_b,
                            "sangsa_pump_c": reading.sangsa_pump_c
                        }
                    },
                    "message": "수동 데이터 수집 및 저장 완료"
                }
            else:
                return {
                    "success": False,
                    "error": "센서 데이터 수집 실패"
                }
                
        except Exception as e:
            logger.error(f"수동 데이터 수집 중 오류: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# 전역 업데이터 인스턴스
_global_updater = None

def get_database_updater() -> RealTimeDatabaseUpdater:
    """전역 데이터베이스 업데이터 인스턴스 반환"""
    global _global_updater
    if _global_updater is None:
        _global_updater = RealTimeDatabaseUpdater()
    return _global_updater

def start_database_update_service(update_interval: int = 60) -> bool:
    """데이터베이스 업데이트 서비스 시작"""
    updater = get_database_updater()
    updater.update_interval = update_interval
    return updater.start_updating()

def stop_database_update_service():
    """데이터베이스 업데이트 서비스 중단"""
    updater = get_database_updater()
    updater.stop_updating()

def get_database_update_status() -> Dict[str, Any]:
    """데이터베이스 업데이트 서비스 상태 조회"""
    updater = get_database_updater()
    return updater.get_service_status()