# services/water_level_logger.py - 아두이노 수위 데이터 실시간 로깅 서비스

import time
import threading
from datetime import datetime
from typing import Optional
from utils.logger import setup_logger
from utils.arduino_direct import DirectArduinoComm

logger = setup_logger(__name__)

class WaterLevelLogger:
    """아두이노 수위 센서 데이터를 주기적으로 읽어서 데이터베이스에 저장하는 서비스"""

    def __init__(self, interval: int = 60):
        """
        Args:
            interval: 데이터 수집 주기 (초), 기본값 60초
        """
        self.interval = interval
        self.arduino = DirectArduinoComm()
        self.running = False
        self.thread: Optional[threading.Thread] = None

        # DB 설정 (직접 연결)
        from config import PG_DB_HOST, PG_DB_PORT, PG_DB_NAME, PG_DB_USER, PG_DB_PASSWORD
        self.db_config = {
            'host': PG_DB_HOST,
            'port': PG_DB_PORT,
            'database': PG_DB_NAME,
            'user': PG_DB_USER,
            'password': PG_DB_PASSWORD
        }

        # 채널 매핑 설정
        self.CHANNEL_GAGOK = 2  # 가곡 배수지
        self.CHANNEL_HAERYONG = 8  # 해룡 배수지

    def start(self):
        """서비스 시작"""
        if self.running:
            logger.warning("수위 로거가 이미 실행 중입니다")
            return

        logger.info("=== 수위 로거 서비스 시작 ===")

        # PostgreSQL 연결 테스트
        try:
            import psycopg2
            test_conn = psycopg2.connect(**self.db_config)
            test_conn.close()
            logger.info("✅ PostgreSQL 연결 테스트 성공")
        except Exception as e:
            logger.error(f"❌ PostgreSQL 연결 실패: {e}")
            return

        # 아두이노 연결
        if not self.arduino.connect():
            logger.warning("⚠️ 아두이노 연결 실패 - 시뮬레이션 모드로 계속 진행")

        # 백그라운드 스레드 시작
        self.running = True
        self.thread = threading.Thread(target=self._logging_loop, daemon=True)
        self.thread.start()
        logger.info(f"✅ 수위 로거 스레드 시작 (수집 주기: {self.interval}초)")

    def stop(self):
        """서비스 중지"""
        logger.info("수위 로거 서비스 중지 중...")
        self.running = False

        if self.thread:
            self.thread.join(timeout=5)

        if self.arduino:
            self.arduino.disconnect()

        logger.info("✅ 수위 로거 서비스 중지 완료")

    def _logging_loop(self):
        """주기적으로 수위 및 펌프 데이터를 읽고 저장하는 루프"""
        logger.info("수위 로거 루프 시작")

        while self.running:
            try:
                # 현재 시간
                measured_at = datetime.now()

                # 채널 1 (가곡) 수위 읽기
                gagok_data = self.arduino.read_water_level(channel=self.CHANNEL_GAGOK)
                gagok_level = None

                if gagok_data.get("success"):
                    gagok_level = gagok_data.get("current_water_level")
                    logger.info(f"📊 가곡 수위: {gagok_level}m")
                else:
                    logger.warning(f"⚠️ 가곡 수위 읽기 실패: {gagok_data.get('error', 'Unknown')}")

                time.sleep(1)  # 센서 간 대기

                # 채널 2 (해룡) 수위 읽기
                haeryong_data = self.arduino.read_water_level(channel=self.CHANNEL_HAERYONG)
                haeryong_level = None

                if haeryong_data.get("success"):
                    haeryong_level = haeryong_data.get("current_water_level")
                    logger.info(f"📊 해룡 수위: {haeryong_level}m")
                else:
                    logger.warning(f"⚠️ 해룡 수위 읽기 실패: {haeryong_data.get('error', 'Unknown')}")

                time.sleep(1)  # 펌프 상태 읽기 전 대기

                # 펌프 상태 읽기
                pump_status = self.arduino.get_pump_status()
                pump1_status = None
                pump2_status = None

                if pump_status.get("success"):
                    status_dict = pump_status.get("pump_status", {})
                    pump1_raw = status_dict.get("pump1", "OFF")
                    pump2_raw = status_dict.get("pump2", "OFF")

                    # ON=1, OFF=0으로 변환
                    pump1_status = 1.0 if pump1_raw == "ON" else 0.0
                    pump2_status = 1.0 if pump2_raw == "ON" else 0.0

                    logger.info(f"⚙️ 펌프1: {pump1_raw}, 펌프2: {pump2_raw}")
                else:
                    logger.warning(f"⚠️ 펌프 상태 읽기 실패: {pump_status.get('error', 'Unknown')}")

                # 데이터베이스에 저장 (최소 하나의 데이터라도 있으면 저장)
                if gagok_level is not None or haeryong_level is not None:
                    self._save_to_database(
                        measured_at,
                        gagok_level, pump1_status,
                        haeryong_level, pump2_status
                    )
                else:
                    logger.warning("⚠️ 유효한 수위 데이터가 없어서 저장하지 않습니다")

            except Exception as e:
                logger.error(f"❌ 수위 로깅 중 오류: {e}", exc_info=True)

            # 다음 수집까지 대기
            logger.info(f"⏰ 다음 수집까지 {self.interval}초 대기...")
            time.sleep(self.interval)

    def _save_to_database(
        self,
        measured_at: datetime,
        gagok_level: Optional[float],
        gagok_pump: Optional[float],
        haeryong_level: Optional[float],
        haeryong_pump: Optional[float]
    ):
        """수위 및 펌프 데이터를 데이터베이스에 저장

        Args:
            measured_at: 측정 시간
            gagok_level: 가곡 수위 (m)
            gagok_pump: 가곡 펌프 상태 (1.0=ON, 0.0=OFF)
            haeryong_level: 해룡 수위 (m)
            haeryong_pump: 해룡 펌프 상태 (1.0=ON, 0.0=OFF)
        """
        conn = None
        try:
            import psycopg2

            # 새 연결 생성
            conn = psycopg2.connect(**self.db_config)

            # SQL INSERT 쿼리 실행
            # gagok_pump_a, haeryong_pump_a에 펌프 상태 저장
            query = """
                INSERT INTO water (
                    measured_at,
                    gagok_water_level, gagok_pump_a,
                    haeryong_water_level, haeryong_pump_a
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (measured_at) DO UPDATE
                SET gagok_water_level = COALESCE(EXCLUDED.gagok_water_level, water.gagok_water_level),
                    gagok_pump_a = COALESCE(EXCLUDED.gagok_pump_a, water.gagok_pump_a),
                    haeryong_water_level = COALESCE(EXCLUDED.haeryong_water_level, water.haeryong_water_level),
                    haeryong_pump_a = COALESCE(EXCLUDED.haeryong_pump_a, water.haeryong_pump_a)
            """

            params = (measured_at, gagok_level, gagok_pump, haeryong_level, haeryong_pump)

            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()

            logger.info(
                f"✅ 데이터베이스 저장 완료: {measured_at.strftime('%Y-%m-%d %H:%M:%S')} - "
                f"가곡(수위: {gagok_level}m, 펌프: {gagok_pump}), "
                f"해룡(수위: {haeryong_level}m, 펌프: {haeryong_pump})"
            )

        except Exception as e:
            logger.error(f"❌ 데이터베이스 저장 실패: {e}", exc_info=True)
        finally:
            if conn:
                conn.close()

    def get_status(self) -> dict:
        """현재 서비스 상태 반환"""
        return {
            "running": self.running,
            "interval": self.interval,
            "arduino_connected": self.arduino.is_connected() if self.arduino else False,
            "arduino_port": self.arduino.arduino_port if self.arduino else None,
            "database_configured": self.db_config is not None
        }
