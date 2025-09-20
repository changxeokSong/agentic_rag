# tools/water_level_monitoring_tool.py

import psycopg2
import psycopg2.extras
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import base64
import io
import json
from config import PG_DB_HOST, PG_DB_PORT, PG_DB_NAME, PG_DB_USER, PG_DB_PASSWORD
from utils.logger import setup_logger

logger = setup_logger(__name__)

class WaterLevelMonitor:
    """배수지 수위 모니터링 및 그래프 생성 도구"""
    
    def __init__(self):
        self.db_config = {
            'host': PG_DB_HOST,
            'port': PG_DB_PORT,
            'database': PG_DB_NAME,
            'user': PG_DB_USER,
            'password': PG_DB_PASSWORD
        }
        
        # 배수지 정보 정의
        self.reservoirs = {
            'gagok': {'name': '가곡 배수지', 'level_col': 'gagok_water_level', 'pumps': ['gagok_pump_a', 'gagok_pump_b']},
            'haeryong': {'name': '해룡 배수지', 'level_col': 'haeryong_water_level', 'pumps': ['haeryong_pump_a', 'haeryong_pump_b']},
            'sangsa': {'name': '상사 배수지', 'level_col': 'sangsa_water_level', 'pumps': ['sangsa_pump_a', 'sangsa_pump_b', 'sangsa_pump_c']}
        }
        
    def _safe_datetime_convert(self, dt_value):
        """안전한 datetime 변환"""
        if dt_value is None:
            return datetime.now().isoformat()
        
        # 이미 datetime 객체인 경우
        if hasattr(dt_value, 'isoformat'):
            return dt_value.isoformat()
        
        # 문자열인 경우 파싱 시도
        if isinstance(dt_value, str):
            try:
                # ISO 형식 시도
                if 'T' in dt_value:
                    return datetime.fromisoformat(dt_value.replace('Z', '+00:00')).isoformat()
                # 일반 날짜 형식 시도
                return datetime.strptime(dt_value, '%Y-%m-%d %H:%M:%S').isoformat()
            except:
                # 파싱 실패 시 현재 시간 반환
                return datetime.now().isoformat()
        
        # 그 외의 경우 문자열로 변환
        return str(dt_value)
        
    def get_connection(self):
        """PostgreSQL 연결"""
        try:
            conn = psycopg2.connect(**self.db_config)
            return conn
        except Exception as e:
            logger.error(f"DB 연결 오류: {str(e)}")
            raise

    def get_current_status(self):
        """현재 수위 상태 조회 - measured_at 기준 최신 데이터"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    # measured_at 기준 최신 데이터 조회 (TEXT 타입 safe)
                    # 먼저 데이터 존재 여부 확인
                    cur.execute("""
                        SELECT COUNT(*) as count FROM water;
                    """)
                    count_result = cur.fetchone()
                    logger.info(f"water 테이블 데이터 개수: {count_result['count'] if count_result else 0}")
                    
                    cur.execute("""
                        SELECT * FROM water 
                        ORDER BY measured_at DESC 
                        LIMIT 1;
                    """)
                    
                    result = cur.fetchone()
                    
                    if not result:
                        return {
                            'success': False,
                            'error': '데이터가 없습니다',
                            'message': 'water 테이블에 수위 데이터가 존재하지 않습니다. 데이터베이스에 데이터를 추가해주세요.'
                        }
                    
                    status_data = []
                    for reservoir_id, reservoir_info in self.reservoirs.items():
                        level_value = result[reservoir_info['level_col']]
                        
                        # 펌프 상태 확인 (double precision 값을 boolean으로 변환)
                        pump_statuses = {}
                        active_pumps = 0
                        for pump_col in reservoir_info['pumps']:
                            pump_value = float(result[pump_col]) if result[pump_col] is not None else 0.0
                            pump_status = pump_value >= 1.0
                            pump_statuses[pump_col.replace(f'{reservoir_id}_', '')] = pump_status
                            if pump_status:
                                active_pumps += 1
                        
                        # 위험 수준 판단 (간단한 임계값 기준)
                        if level_value is not None:
                            if level_value >= 100:
                                status = 'CRITICAL'
                            elif level_value >= 80:
                                status = 'WARNING'
                            else:
                                status = 'NORMAL'
                        else:
                            status = 'UNKNOWN'
                            level_value = 0
                        
                        status_data.append({
                            'reservoir': reservoir_info['name'],
                            'reservoir_id': reservoir_id,
                            'current_level': float(level_value) if level_value else 0,
                            'pump_statuses': pump_statuses,
                            'active_pumps': active_pumps,
                            'total_pumps': len(reservoir_info['pumps']),
                            'status': status,
                            'last_update': self._safe_datetime_convert(result['measured_at'])
                        })
                    
                    return {
                        'success': True,
                        'timestamp': datetime.now().isoformat(),
                        'reservoirs': status_data,
                        'total_reservoirs': len(status_data)
                    }
                    
        except Exception as e:
            logger.error(f"현재 상태 조회 오류: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': 'DB 연결 오류 또는 데이터 조회 실패'
            }

    def get_historical_data(self, hours=24):
        """과거 수위 데이터 조회 - synergy 데이터베이스 water 테이블 기준"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    # 최신 데이터의 measured_at을 기준으로 24시간 전 데이터까지 조회 (TEXT 타입 호환)
                    cur.execute("""
                        SELECT 
                            MAX(measured_at) as latest_time
                        FROM water;
                    """)
                    
                    latest_result = cur.fetchone()
                    if not latest_result or not latest_result['latest_time']:
                        return {
                            'success': False,
                            'error': 'water 테이블에 데이터가 없습니다',
                            'time_range_hours': hours
                        }
                    
                    # 최신 시간에서 24시간을 빼기 (파이썬에서 계산)
                    try:
                        latest_time_str = latest_result['latest_time']
                        if isinstance(latest_time_str, str):
                            # 문자열인 경우 datetime으로 변환
                            latest_time = datetime.strptime(latest_time_str, '%Y-%m-%d %H:%M:%S')
                        else:
                            # 이미 datetime 객체인 경우
                            latest_time = latest_time_str
                        
                        start_time = latest_time - timedelta(hours=hours)
                        start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception as e:
                        logger.error(f"시간 계산 오류: {str(e)}")
                        return {
                            'success': False,
                            'error': f'시간 계산 중 오류: {str(e)}',
                            'time_range_hours': hours
                        }
                    
                    # 계산된 시간 범위로 데이터 조회
                    cur.execute("""
                        SELECT * FROM water 
                        WHERE measured_at >= %s 
                        ORDER BY measured_at;
                    """, (start_time_str,))
                    
                    results = cur.fetchall()
                    
                    if not results:
                        return {
                            'success': False,
                            'error': '데이터가 없습니다',
                            'time_range_hours': hours
                        }
                    
                    # 배수지별로 데이터 정리
                    data_by_reservoir = {}
                    for reservoir_id, reservoir_info in self.reservoirs.items():
                        data_by_reservoir[reservoir_info['name']] = []
                    
                    for row in results:
                        for reservoir_id, reservoir_info in self.reservoirs.items():
                            level_value = row[reservoir_info['level_col']]
                            
                            # 펌프 상태 (double precision 값을 boolean으로 변환)
                            pump_statuses = {}
                            for pump_col in reservoir_info['pumps']:
                                pump_value = float(row[pump_col]) if row[pump_col] is not None else 0.0
                                pump_statuses[pump_col.replace(f'{reservoir_id}_', '')] = pump_value >= 1.0
                            
                            data_by_reservoir[reservoir_info['name']].append({
                                'timestamp': self._safe_datetime_convert(row['measured_at']),
                                'water_level': float(level_value) if level_value else 0,
                                'pump_statuses': pump_statuses
                            })
                    
                    return {
                        'success': True,
                        'time_range_hours': hours,
                        'data': data_by_reservoir,
                        'data_points': len(results),
                        'actual_start_time': start_time.isoformat(),
                        'actual_end_time': latest_time.isoformat()
                    }
                    
        except Exception as e:
            logger.error(f"과거 데이터 조회 오류: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def generate_level_graph(self, hours=24):
        """수위 그래프 생성"""
        try:
            # 과거 데이터 조회
            data_result = self.get_historical_data(hours)
            if not data_result['success']:
                return data_result
            
            data = data_result['data']
            
            # 한글 폰트 설정
            plt.rcParams['font.family'] = ['DejaVu Sans', 'Malgun Gothic', 'gulim']
            plt.rcParams['axes.unicode_minus'] = False
            
            # 그래프 생성 (3개 배수지)
            fig, axes = plt.subplots(3, 1, figsize=(14, 12), facecolor='white')
            colors = ['#2563eb', '#059669', '#dc2626']  # 파랑, 녹색, 빨강
            
            for i, (reservoir_name, records) in enumerate(data.items()):
                ax = axes[i]
                
                if not records:
                    ax.text(0.5, 0.5, f'{reservoir_name} 데이터 없음', 
                           ha='center', va='center', transform=ax.transAxes)
                    continue
                
                # 데이터 준비
                timestamps = pd.to_datetime([r['timestamp'] for r in records])
                levels = [r['water_level'] for r in records]
                
                # 수위 라인 그래프
                ax.plot(timestamps, levels, color=colors[i], 
                       linewidth=2.5, label='수위', marker='o', markersize=3)
                
                # 경고 수위 라인 (100cm 기준)
                ax.axhline(y=100, color='red', linestyle='--', 
                          alpha=0.7, label='위험 수위 (100cm)')
                ax.axhline(y=80, color='orange', linestyle='--', 
                          alpha=0.5, label='주의 수위 (80cm)')
                
                # 펌프 가동 구간 표시
                for j in range(len(records)):
                    pump_active = any(records[j]['pump_statuses'].values())
                    if pump_active and j < len(timestamps)-1:
                        ax.axvspan(timestamps[j], timestamps[j+1] if j+1 < len(timestamps) else timestamps[j], 
                                  alpha=0.15, color='green')
                
                # 그래프 스타일링
                ax.set_title(f'{reservoir_name} 수위 현황 ({hours}시간)', 
                           fontsize=14, fontweight='bold', pad=15)
                ax.set_xlabel('시간', fontsize=11)
                ax.set_ylabel('수위 (cm)', fontsize=11)
                ax.grid(True, alpha=0.3)
                ax.legend(loc='upper right', fontsize=9)
                
                # 시간축 포맷
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=max(1, hours//6)))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=9)
                
                # Y축 범위 설정
                if levels:
                    min_level = min(levels)
                    max_level = max(levels)
                    margin = max(10, (max_level - min_level) * 0.1)
                    ax.set_ylim(max(0, min_level - margin), max_level + margin)
            
            plt.suptitle('배수지 수위 모니터링', fontsize=16, fontweight='bold', y=0.98)
            plt.tight_layout()
            plt.subplots_adjust(top=0.95)
            
            # 그래프를 이미지로 저장
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            buffer.seek(0)
            
            # Base64 인코딩
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            plt.close()
            buffer.close()
            
            # 파일 정보 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"water_levels_{timestamp}.png"
            file_id = f"graph_{timestamp}"
            
            # 데이터베이스에서 가져온 실제 시간 범위 사용
            actual_start = data_result.get('actual_start_time')
            actual_end = data_result.get('actual_end_time')
            
            if actual_start and actual_end:
                try:
                    start_dt = datetime.fromisoformat(actual_start.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(actual_end.replace('Z', '+00:00'))
                    time_range_display = f"{start_dt.strftime('%Y-%m-%d %H:%M:%S')} ~ {end_dt.strftime('%Y-%m-%d %H:%M:%S')}"
                except:
                    time_range_display = f"{actual_start} ~ {actual_end}"
            else:
                time_range_display = f"데이터베이스 시간 기준 {hours}시간"
            
            return {
                'success': True,
                'graph_file_id': file_id,
                'graph_filename': filename,
                'image_base64': image_base64,
                'time_range_hours': hours,
                'time_range_display': time_range_display,
                'reservoirs_count': 3,
                'data_points': data_result.get('data_points', 0),
                'message': f'3개 배수지의 {hours}시간 수위 그래프 생성 완료\n시간 범위: {time_range_display}'
            }
            
        except Exception as e:
            logger.error(f"그래프 생성 오류: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': '그래프 생성 중 오류 발생'
            }

    def add_sample_data(self, base_time=None):
        """테스트용 샘플 데이터 추가 (프로토타입용 랜덤 시간 지원)"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # 프로토타입용 랜덤 시간 생성
                    if base_time is None:
                        # 랜덤하게 1-10일 전 시점 선택
                        days_back = np.random.randint(1, 11)
                        base_time = datetime.now() - timedelta(days=days_back, hours=np.random.randint(0, 24))
                    
                    # 기존 데이터 삭제 (프로토타입용)
                    cur.execute("DELETE FROM water")
                    
                    # 30분 간격으로 48개 데이터 포인트 생성
                    for i in range(48):
                        timestamp = base_time + timedelta(minutes=30 * i)
                        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                        
                        # 각 배수지별 수위 시뮬레이션
                        gagok_level = 70 + np.sin(i * 0.1) * 15 + np.random.normal(0, 3)
                        haeryong_level = 65 + np.sin(i * 0.15 + 1) * 20 + np.random.normal(0, 2)
                        sangsa_level = 80 + np.sin(i * 0.12 + 2) * 25 + np.random.normal(0, 4)
                        
                        # 펌프 상태 (수위가 높을 때 가동)
                        gagok_pump_a = 1 if gagok_level > 85 else 0
                        gagok_pump_b = 1 if gagok_level > 95 else 0
                        
                        haeryong_pump_a = 1 if haeryong_level > 80 else 0
                        haeryong_pump_b = 1 if haeryong_level > 90 else 0
                        
                        sangsa_pump_a = 1 if sangsa_level > 90 else 0
                        sangsa_pump_b = 1 if sangsa_level > 100 else 0
                        sangsa_pump_c = 1 if sangsa_level > 110 else 0
                        
                        cur.execute("""
                            INSERT INTO water 
                            (measured_at, 
                             gagok_water_level, gagok_pump_a, gagok_pump_b,
                             haeryong_water_level, haeryong_pump_a, haeryong_pump_b,
                             sangsa_water_level, sangsa_pump_a, sangsa_pump_b, sangsa_pump_c)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """, (timestamp_str, 
                              round(gagok_level, 1), 1.0 if gagok_pump_a else 0.0, 1.0 if gagok_pump_b else 0.0,
                              round(haeryong_level, 1), 1.0 if haeryong_pump_a else 0.0, 1.0 if haeryong_pump_b else 0.0,
                              round(sangsa_level, 1), 1.0 if sangsa_pump_a else 0.0, 1.0 if sangsa_pump_b else 0.0, 1.0 if sangsa_pump_c else 0.0))
                    
                    conn.commit()
                    
                    # 시간 범위 정보 반환
                    end_time = base_time + timedelta(hours=24)
                    
                    return {
                        'success': True,
                        'message': '샘플 데이터 추가 완료',
                        'reservoirs': ['가곡 배수지', '해룡 배수지', '상사 배수지'],
                        'data_points': 48,
                        'time_range': '24시간 (30분 간격)',
                        'start_time': base_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'end_time': end_time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
        except Exception as e:
            logger.error(f"샘플 데이터 추가 오류: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

def water_level_monitoring_tool(**kwargs):
    """수위 모니터링 도구 메인 함수 - synergy 데이터베이스의 water 테이블만 사용"""
    monitor = WaterLevelMonitor()
    
    action = kwargs.get('action', 'current_status')
    
    try:
        if action == 'current_status':
            return monitor.get_current_status()
        
        elif action == 'historical_data':
            hours = kwargs.get('hours', 24)
            return monitor.get_historical_data(hours)
        
        elif action == 'generate_graph':
            hours = kwargs.get('hours', 24)
            return monitor.generate_level_graph(hours)
        
        elif action == 'add_sample_data':
            # 테스트/개발용 샘플 데이터 생성
            return monitor.add_sample_data()
        
        else:
            return {
                'success': False,
                'error': f'알 수 없는 액션: {action}',
                'available_actions': ['current_status', 'historical_data', 'generate_graph', 'add_sample_data'],
                'message': 'synergy 데이터베이스의 water 테이블에서 데이터를 조회합니다.'
            }
            
    except Exception as e:
        logger.error(f"수위 모니터링 도구 오류: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'message': 'synergy 데이터베이스 water 테이블 조회 중 오류 발생'
        }