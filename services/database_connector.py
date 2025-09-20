# services/database_connector.py - 실시간 데이터베이스 연동 서비스

import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor

from config import PG_DB_HOST, PG_DB_PORT, PG_DB_NAME, PG_DB_USER, PG_DB_PASSWORD
from services.logging_system import get_automation_logger, EventType, LogLevel
from utils.logger import setup_logger

logger = setup_logger(__name__)

class DatabaseConnector:
    """실시간 데이터베이스 연동 클래스"""
    
    def __init__(self):
        self.db_config = {
            'host': PG_DB_HOST,
            'port': PG_DB_PORT,
            'database': PG_DB_NAME,
            'user': PG_DB_USER,
            'password': PG_DB_PASSWORD
        }
        
        # 배수지 정보 (water 테이블 기반)
        self.reservoirs = {
            'gagok': {
                'name': '가곡 배수지',
                'level_col': 'gagok_water_level',
                'pumps': ['gagok_pump_a', 'gagok_pump_b'],
                'alert_threshold': 90.0
            },
            'haeryong': {
                'name': '해룡 배수지',
                'level_col': 'haeryong_water_level',
                'pumps': ['haeryong_pump_a', 'haeryong_pump_b'],
                'alert_threshold': 85.0
            },
            'sangsa': {
                'name': '상사 배수지',
                'level_col': 'sangsa_water_level',
                'pumps': ['sangsa_pump_a', 'sangsa_pump_b', 'sangsa_pump_c'],
                'alert_threshold': 95.0
            }
        }
        
        self.automation_logger = get_automation_logger()
        self._lock = threading.Lock()
        self._cached_data = {}
        self._last_update = None
        
        logger.info("데이터베이스 커넥터 초기화 완료")
    
    def get_connection(self):
        """데이터베이스 연결 반환"""
        try:
            return psycopg2.connect(**self.db_config, cursor_factory=RealDictCursor)
        except Exception as e:
            logger.error(f"데이터베이스 연결 오류: {e}")
            raise
    
    def get_latest_water_data(self, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """최신 수위 데이터 조회"""
        try:
            # 캐시 확인 (10초 이내는 캐시 사용)
            if use_cache and self._cached_data and self._last_update:
                if datetime.now() - self._last_update < timedelta(seconds=10):
                    return self._cached_data
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # 최신 데이터 조회
                    cur.execute("""
                        SELECT * FROM water 
                        ORDER BY measured_at DESC 
                        LIMIT 1;
                    """)
                    
                    result = cur.fetchone()
                    
                    if not result:
                        logger.warning("water 테이블에 데이터가 없습니다")
                        return None
                    
                    # 데이터 변환
                    water_data = self._convert_to_reservoir_format(result)
                    
                    # 캐시 업데이트
                    with self._lock:
                        self._cached_data = water_data
                        self._last_update = datetime.now()
                    
                    return water_data
                    
        except Exception as e:
            logger.error(f"수위 데이터 조회 오류: {e}")
            return None
    
    def _convert_to_reservoir_format(self, db_result: Dict[str, Any]) -> Dict[str, Any]:
        """데이터베이스 결과를 배수지 형식으로 변환"""
        reservoir_data = {}
        measured_at = db_result.get('measured_at', datetime.now())
        
        for reservoir_id, config in self.reservoirs.items():
            # 수위 데이터
            water_level = float(db_result.get(config['level_col'], 0.0))
            
            # 펌프 상태 확인
            pump_status = "OFF"
            active_pumps = 0
            pump_details = {}
            
            for pump_col in config['pumps']:
                # double precision 값을 boolean으로 변환 (1.0이면 True, 0.0이면 False)
                pump_value = float(db_result.get(pump_col, 0.0))
                pump_active = pump_value >= 1.0
                pump_name = pump_col.replace(f'{reservoir_id}_', '')
                pump_details[pump_name] = pump_active
                if pump_active:
                    active_pumps += 1
            
            # 펌프 상태 결정
            if active_pumps == 0:
                pump_status = "OFF"
            elif active_pumps == len(config['pumps']):
                pump_status = "ON"
            else:
                pump_status = "AUTO"
            
            reservoir_data[reservoir_id] = {
                'water_level': round(water_level, 2),
                'pump_status': pump_status,
                'alert_level': config['alert_threshold'],
                'active_pumps': active_pumps,
                'total_pumps': len(config['pumps']),
                'pump_details': pump_details,
                'measured_at': measured_at.isoformat() if hasattr(measured_at, 'isoformat') else str(measured_at),
                'reservoir_name': config['name']
            }
        
        return reservoir_data
    
    def update_pump_status(self, reservoir_id: str, pump_action: str) -> bool:
        """펌프 상태 업데이트 (실제 데이터베이스에 반영)"""
        try:
            if reservoir_id not in self.reservoirs:
                logger.error(f"잘못된 배수지 ID: {reservoir_id}")
                return False
            
            config = self.reservoirs[reservoir_id]
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # 현재 시간으로 새 레코드 삽입
                    current_time = datetime.now()
                    
                    # 기존 최신 데이터 조회
                    cur.execute("""
                        SELECT * FROM water 
                        ORDER BY measured_at DESC 
                        LIMIT 1;
                    """)
                    latest_data = cur.fetchone()
                    
                    if not latest_data:
                        logger.error("기존 데이터를 찾을 수 없어 펌프 상태를 업데이트할 수 없습니다")
                        return False
                    
                    # 새 레코드 데이터 준비
                    new_data = dict(latest_data)
                    new_data['measured_at'] = current_time
                    
                    # 펌프 상태 업데이트 (double precision 컬럼에 맞게 1.0/0.0 사용)
                    if pump_action.upper() == "ON":
                        for pump_col in config['pumps']:
                            new_data[pump_col] = 1.0
                    elif pump_action.upper() == "OFF":
                        for pump_col in config['pumps']:
                            new_data[pump_col] = 0.0
                    elif pump_action.upper() == "AUTO":
                        # AUTO 모드는 일부만 켬 (임계치 기반)
                        water_level = new_data.get(config['level_col'], 0.0)
                        for i, pump_col in enumerate(config['pumps']):
                            # 수위가 높을수록 더 많은 펌프 가동
                            new_data[pump_col] = 1.0 if i < (water_level / 30) else 0.0
                    
                    # 새 레코드 삽입
                    columns = list(new_data.keys())
                    values = list(new_data.values())
                    placeholders = ', '.join(['%s'] * len(values))
                    
                    insert_sql = f"""
                        INSERT INTO water ({', '.join(columns)})
                        VALUES ({placeholders})
                    """
                    
                    cur.execute(insert_sql, values)
                    conn.commit()
                    
                    # 로그 기록
                    self.automation_logger.info(
                        EventType.ACTION,
                        reservoir_id,
                        f"펌프 상태 업데이트: {pump_action}",
                        {
                            "pump_action": pump_action,
                            "water_level": new_data.get(config['level_col'], 0.0),
                            "timestamp": current_time.isoformat()
                        }
                    )
                    
                    # 캐시 무효화
                    with self._lock:
                        self._cached_data = {}
                        self._last_update = None
                    
                    logger.info(f"펌프 상태 업데이트 성공: {reservoir_id} -> {pump_action}")
                    return True
                    
        except Exception as e:
            logger.error(f"펌프 상태 업데이트 오류: {e}")
            self.automation_logger.error(
                EventType.ERROR,
                reservoir_id,
                f"펌프 상태 업데이트 실패: {str(e)}"
            )
            return False
    
    def get_historical_data(self, hours: int = 24) -> List[Dict[str, Any]]:
        """과거 데이터 조회"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM water 
                        WHERE measured_at >= %s
                        ORDER BY measured_at DESC;
                    """, (datetime.now() - timedelta(hours=hours),))
                    
                    results = cur.fetchall()
                    
                    historical_data = []
                    for row in results:
                        historical_data.append(self._convert_to_reservoir_format(row))
                    
                    return historical_data
                    
        except Exception as e:
            logger.error(f"과거 데이터 조회 오류: {e}")
            return []
    
    def get_system_health(self) -> Dict[str, Any]:
        """시스템 건강 상태 분석"""
        try:
            latest_data = self.get_latest_water_data()
            if not latest_data:
                return {"status": "ERROR", "message": "데이터를 조회할 수 없습니다"}
            
            critical_reservoirs = []
            warning_reservoirs = []
            normal_reservoirs = []
            
            for reservoir_id, data in latest_data.items():
                water_level = data['water_level']
                alert_level = data['alert_level']
                
                if water_level >= alert_level:
                    critical_reservoirs.append({
                        'id': reservoir_id,
                        'name': data['reservoir_name'],
                        'level': water_level,
                        'threshold': alert_level
                    })
                elif water_level >= alert_level * 0.8:
                    warning_reservoirs.append({
                        'id': reservoir_id,
                        'name': data['reservoir_name'],
                        'level': water_level,
                        'threshold': alert_level
                    })
                else:
                    normal_reservoirs.append({
                        'id': reservoir_id,
                        'name': data['reservoir_name'],
                        'level': water_level,
                        'threshold': alert_level
                    })
            
            # 전체 상태 결정
            if critical_reservoirs:
                overall_status = "CRITICAL"
            elif warning_reservoirs:
                overall_status = "WARNING"
            else:
                overall_status = "NORMAL"
            
            return {
                "status": overall_status,
                "critical_reservoirs": critical_reservoirs,
                "warning_reservoirs": warning_reservoirs,
                "normal_reservoirs": normal_reservoirs,
                "total_reservoirs": len(latest_data),
                "last_update": self._last_update.isoformat() if self._last_update else None
            }
            
        except Exception as e:
            logger.error(f"시스템 건강 상태 분석 오류: {e}")
            return {"status": "ERROR", "message": str(e)}

# 전역 커넥터 인스턴스
_global_db_connector = None

def get_database_connector() -> DatabaseConnector:
    """전역 데이터베이스 커넥터 인스턴스 반환"""
    global _global_db_connector
    if _global_db_connector is None:
        _global_db_connector = DatabaseConnector()
    return _global_db_connector