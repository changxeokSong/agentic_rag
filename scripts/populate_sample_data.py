# scripts/populate_sample_data.py

import psycopg2
import numpy as np
from datetime import datetime, timedelta
import os
import sys

# Add project root to path to allow imports from other modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PG_DB_HOST, PG_DB_PORT, PG_DB_NAME, PG_DB_USER, PG_DB_PASSWORD
from utils.logger import setup_logger

logger = setup_logger(__name__)

def add_sample_data(base_time=None):
    """테스트용 샘플 데이터를 데이터베이스에 추가합니다."""
    db_config = {
        'host': PG_DB_HOST,
        'port': PG_DB_PORT,
        'database': PG_DB_NAME,
        'user': PG_DB_USER,
        'password': PG_DB_PASSWORD
    }
    try:
        with psycopg2.connect(**db_config) as conn:
            with conn.cursor() as cur:
                if base_time is None:
                    days_back = np.random.randint(1, 11)
                    base_time = datetime.now() - timedelta(days=days_back, hours=np.random.randint(0, 24))
                
                logger.info("기존 water 테이블 데이터 삭제...")
                cur.execute("DELETE FROM water")
                
                logger.info(f"{base_time}부터 24시간 동안의 샘플 데이터 생성 시작...")
                for i in range(48):
                    timestamp = base_time + timedelta(minutes=30 * i)
                    timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    
                    gagok_level = 70 + np.sin(i * 0.1) * 15 + np.random.normal(0, 3)
                    haeryong_level = 65 + np.sin(i * 0.15 + 1) * 20 + np.random.normal(0, 2)
                    sangsa_level = 80 + np.sin(i * 0.12 + 2) * 25 + np.random.normal(0, 4)
                    
                    gagok_pump_a = 1.0 if gagok_level > 85 else 0.0
                    haeryong_pump_a = 1.0 if haeryong_level > 80 else 0.0
                    
                    cur.execute("""
                        INSERT INTO water (measured_at, gagok_water_level, haeryong_water_level, sangsa_water_level, gagok_pump_a, haeryong_pump_a)
                        VALUES (%s, %s, %s, %s, %s, %s);
                    """, (timestamp_str, round(gagok_level, 2), round(haeryong_level, 2), round(sangsa_level, 2), gagok_pump_a, haeryong_pump_a))
                
                conn.commit()
                logger.info("샘플 데이터 추가 완료: 48개 데이터 포인트가 추가되었습니다.")
                print("샘플 데이터가 성공적으로 추가되었습니다.")

    except Exception as e:
        logger.error(f"샘플 데이터 추가 오류: {str(e)}")
        print(f"오류가 발생했습니다: {e}")

if __name__ == "__main__":
    add_sample_data()
