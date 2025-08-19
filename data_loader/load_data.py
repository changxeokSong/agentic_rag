import pandas as pd
from sqlalchemy import create_engine
import sys

# ------------------- 설정 (사용자 환경에 맞게 수정) ------------------- #

# 1. 데이터베이스 연결 정보
DB_USER = "synergy"
DB_PASS = "synergy"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "synergy" 

# 2. 파일 및 테이블 정보
# ◀◀◀ 여기에 실제 엑셀 파일의 전체 경로를 정확하게 입력하세요.
EXCEL_FILE_PATH = "C:/Users/mmlab/Downloads/WATERDATA.xlsx"
TABLE_NAME = "water"

# -------------------------------------------------------------------- #

def load_water_data():
    """엑셀 데이터를 읽어 PostgreSQL 데이터베이스의 water 테이블에 적재합니다."""
    
    try:
        # --- 1. 데이터베이스 연결 ---
        engine_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        engine = create_engine(engine_url)
        print("데이터베이스에 연결되었습니다.")

        # --- 2. 엑셀 파일 읽기 (모든 시트 통합 및 #N/A 처리) ---
        print(f"'{EXCEL_FILE_PATH}' 파일을 읽는 중입니다...")
        # na_values='#N/A' : '#N/A' 텍스트를 결측치(NaN)로 인식하도록 설정
        excel_sheets = pd.read_excel(EXCEL_FILE_PATH, sheet_name=None, engine="openpyxl", na_values='#N/A')
        
        # 모든 시트(월별 데이터)를 하나의 데이터프레임으로 합칩니다.
        df = pd.concat(excel_sheets.values(), ignore_index=True)
        print(f"엑셀 파일의 모든 시트에서 총 {len(df)}개의 행을 읽었습니다.")

        # --- 3. 데이터 정제 ---
        # Time 컬럼에 값이 없는 행 (결측치)을 제거합니다.
        df.dropna(subset=['Time'], inplace=True)
        print(f"유효하지 않은 데이터를 제거한 후, 총 {len(df)}개의 유효한 행을 처리합니다.")

        # --- 4. 컬럼 이름 매핑 ---
        column_mapping = {
            'Time': 'measured_at',
            'Gagok_WaterLevel': 'gagok_water_level',
            'Gagok_PumpA': 'gagok_pump_a',
            'Gagok_PumpB': 'gagok_pump_b',
            '해룡수위': 'haeryong_water_level',
            '해룡펌프A': 'haeryong_pump_a',
            '해룡펌프B': 'haeryong_pump_b',
            '상사수위': 'sangsa_water_level',
            '상사펌프A': 'sangsa_pump_a',
            '상사펌프B': 'sangsa_pump_b',
            '상사펌프C': 'sangsa_pump_c'
        }
        df.rename(columns=column_mapping, inplace=True)
        print("데이터베이스 스키마에 맞게 컬럼 이름을 변경했습니다.")
        
        # --- 5. 데이터 타입 변환 ---
        # 'measured_at' 컬럼을 pandas의 datetime 형식으로 변환합니다.
        df['measured_at'] = pd.to_datetime(df['measured_at'])
        print("'measured_at' 컬럼을 TIMESTAMP로 저장할 수 있도록 변환했습니다.")
        
        # --- 6. 데이터베이스에 적재 ---
        print(f"'{TABLE_NAME}' 테이블에 데이터 적재를 시작합니다...")
        
        # to_sql은 일부 sqlalchemy 버전에서 삽입된 행의 수를 반환합니다.
        # None이 반환될 경우를 대비하여 df의 길이를 사용합니다.
        inserted_rows = df.to_sql(
            name=TABLE_NAME, 
            con=engine, 
            if_exists='replace', 
            index=False,
            method='multi',
            chunksize=1000
        )
        
        final_count = inserted_rows if inserted_rows is not None else len(df)
        
        print(f"✅ 데이터 적재를 성공적으로 완료했습니다! 총 {final_count}개의 행이 '{TABLE_NAME}' 테이블에 저장되었습니다.")

    except FileNotFoundError:
        print(f"오류: '{EXCEL_FILE_PATH}' 파일을 찾을 수 없습니다. 경로를 확인해주세요.", file=sys.stderr)
    except KeyError as e:
        print(f"오류: 엑셀 파일에서 필요한 컬럼을 찾을 수 없습니다: {e}", file=sys.stderr)
        print("엑셀 파일의 컬럼명이 코드의 'column_mapping'과 일치하는지 확인해주세요.", file=sys.stderr)
    except Exception as e:
        print(f"작업 중 오류가 발생했습니다: {e}", file=sys.stderr)

if __name__ == "__main__":
    load_water_data()
