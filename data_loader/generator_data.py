from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import time
import random
import sys

# ------------------- 설정 (사용자 환경에 맞게 수정) ------------------- #

# 1. 데이터베이스 연결 정보
import os
DB_USER = os.getenv("PG_DB_USER", "synergy")
DB_PASS = os.getenv("PG_DB_PASSWORD", "synergy")
DB_HOST = os.getenv("PG_DB_HOST", "localhost")  # 도커: "postgres", 로컬: "localhost"
DB_PORT = os.getenv("PG_DB_PORT", "5432")
DB_NAME = os.getenv("PG_DB_NAME", "synergy") 

TABLE_NAME = "water"

# 2. 시뮬레이션 설정
# 데이터 한 줄을 입력하고 다음 줄을 입력하기까지의 대기 시간 (초 단위)
INSERT_INTERVAL_SECONDS = 0.000000001 # 속도를 약간 높였습니다.
# DB가 비어있을 경우, 가상 데이터 생성을 시작할 시점
DEFAULT_START_TIME = datetime(2025, 9, 15, 0, 0, 0)

# -------------------------------------------------------------------- #

def generate_and_save_virtual_data():
    """
    데이터베이스에서 마지막 데이터를 확인한 후, 그 시점부터 현재까지의
    가상 데이터를 생성하여 실시간으로 적재합니다.
    """
    
    # --- 중요: 이 스크립트를 실행하기 전, 아래 SQL을 DB에서 실행했는지 확인하세요 ---
    # ALTER TABLE water ADD PRIMARY KEY (measured_at);
    # -------------------------------------------------------------------------

    try:
        # --- 1. 데이터베이스 연결 ---
        engine_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        engine = create_engine(engine_url)
        print("✅ 데이터베이스에 성공적으로 연결되었습니다.")

        with engine.connect() as connection:
            # --- 2. DB에서 마지막 데이터 시간 확인하여 시작 시간 결정 ---
            query = text(f"SELECT MAX(measured_at) FROM {TABLE_NAME};")
            latest_timestamp = connection.execute(query).scalar_one_or_none()

            if latest_timestamp:
          #       start_time = latest_timestamp + timedelta(minutes=1)
          #       print(f"DB에 저장된 마지막 데이터 시간: {latest_timestamp}")
          #   else:
                start_time = DEFAULT_START_TIME
                print("DB가 비어있어, 기본 시작 시간부터 데이터를 생성합니다.")
            
            print(f"==> 데이터 생성을 시작할 시간: {start_time} <==")

            # --- 3. 데이터 생성 초기값 설정 ---
            current_time = start_time
            levels = {'gagok': 67.0, 'haeryong': 2.48, 'sangsa': 90.0}
            pumps = {'gagok_a': 0, 'gagok_b': 0, 'haeryong_a': 0, 'haeryong_b': 1, 'sangsa_a': 0, 'sangsa_b': 0, 'sangsa_c': 0}
            thresholds = {'gagok': {'low': 60, 'high': 75}, 'haeryong': {'low': 2.0, 'high': 2.8}, 'sangsa': {'low': 85, 'high': 95}}
            
            print(f"\n🚀 {current_time.strftime('%Y-%m-%d %H:%M:%S')}부터 현재 시간까지 가상 데이터 생성을 시작합니다.")
            print(f"(중지하려면 Ctrl+C를 누르세요.)\n")

            # --- 4. 실시간 데이터 생성 및 적재 루프 ---
            while current_time < datetime.now():
                # (가상 데이터 생성 로직은 이전과 동일)
                levels['gagok'] -= random.uniform(0.01, 0.05)
                if pumps['gagok_a'] == 1: levels['gagok'] += random.uniform(0.1, 0.3)
                if levels['gagok'] < thresholds['gagok']['low']: pumps['gagok_a'] = 1
                elif levels['gagok'] > thresholds['gagok']['high']: pumps['gagok_a'] = 0
                
                # 해룡, 상사 배수지 로직 추가 (이전 코드에서 누락된 부분 보완)
                levels['haeryong'] -= random.uniform(0.001, 0.005)
                if pumps['haeryong_b'] == 1: levels['haeryong'] += random.uniform(0.005, 0.01)
                if levels['haeryong'] < thresholds['haeryong']['low']: pumps['haeryong_b'] = 1
                elif levels['haeryong'] > thresholds['haeryong']['high']: pumps['haeryong_b'] = 0

                levels['sangsa'] -= random.uniform(0.01, 0.05)
                if pumps['sangsa_a'] == 1: levels['sangsa'] += random.uniform(0.1, 0.2)
                if levels['sangsa'] < thresholds['sangsa']['low']: pumps['sangsa_a'] = 1
                elif levels['sangsa'] > thresholds['sangsa']['high']: pumps['sangsa_a'] = 0

                new_row = {
                    "measured_at": current_time,
                    "gagok_water_level": round(levels['gagok'], 4), "gagok_pump_a": pumps['gagok_a'], "gagok_pump_b": pumps['gagok_b'],
                    "haeryong_water_level": round(levels['haeryong'], 4), "haeryong_pump_a": pumps['haeryong_a'], "haeryong_pump_b": pumps['haeryong_b'],
                    "sangsa_water_level": round(levels['sangsa'], 4), "sangsa_pump_a": pumps['sangsa_a'], "sangsa_pump_b": pumps['sangsa_b'], "sangsa_pump_c": pumps['sangsa_c']
                }

                insert_query = text("""
                    INSERT INTO water (measured_at, gagok_water_level, gagok_pump_a, gagok_pump_b, haeryong_water_level, haeryong_pump_a, haeryong_pump_b, sangsa_water_level, sangsa_pump_a, sangsa_pump_b, sangsa_pump_c)
                    VALUES (:measured_at, :gagok_water_level, :gagok_pump_a, :gagok_pump_b, :haeryong_water_level, :haeryong_pump_a, :haeryong_pump_b, :sangsa_water_level, :sangsa_pump_a, :sangsa_pump_b, :sangsa_pump_c)
                    ON CONFLICT (measured_at) DO NOTHING;
                """)
                
                # ★★★★★ 수정된 부분 ★★★★★
                # 루프 내에서 트랜잭션을 새로 시작하는 대신, execute 후 바로 commit 합니다.
                result = connection.execute(insert_query, new_row)
                connection.commit()
                
                # 결과 확인 및 출력
                if result.rowcount > 0:
                    print(f"✅ SUCCESS: {current_time.strftime('%Y-%m-%d %H:%M:%S')} 데이터 저장 완료")
                else:
                    print(f"🟡 SKIPPED: {current_time.strftime('%Y-%m-%d %H:%M:%S')} 데이터는 이미 존재합니다.")
                
                current_time += timedelta(minutes=1)
                time.sleep(INSERT_INTERVAL_SECONDS)
                
        print("\n🎉 현재 시간까지의 모든 가상 데이터 생성을 완료했습니다!")

    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 중지되었습니다.", file=sys.stderr)
    except Exception as e:
        print(f"\n작업 중 오류가 발생했습니다: {e}", file=sys.stderr)

if __name__ == "__main__":
    generate_and_save_virtual_data()