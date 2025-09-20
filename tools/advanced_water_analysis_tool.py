# tools/advanced_water_analysis_tool.py - 고급 수위 분석 및 예측 도구

import psycopg2
import psycopg2.extras
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
import re
from statistics import stdev, mean

from config import PG_DB_HOST, PG_DB_PORT, PG_DB_NAME, PG_DB_USER, PG_DB_PASSWORD
from utils.logger import setup_logger
from tools.water_level_prediction_tool import WaterLevelPredictionTool

logger = setup_logger(__name__)

class TimeParser:
    """자연어 시간 표현을 파싱하는 클래스"""
    
    @staticmethod
    def parse_time_expression(expression: str) -> Optional[datetime]:
        """자연어 시간 표현을 datetime으로 변환"""
        now = datetime.now()
        expression = expression.lower().strip()
        
        # 상대적 시간 표현
        relative_patterns = {
            r'어제': now - timedelta(days=1),
            r'오늘': now,
            r'내일': now + timedelta(days=1),
            r'이번주': now - timedelta(days=now.weekday()),
            r'지난주': now - timedelta(days=now.weekday() + 7),
            r'점심|12시': now.replace(hour=12, minute=0, second=0, microsecond=0),
            r'오전|아침': now.replace(hour=9, minute=0, second=0, microsecond=0),
            r'오후': now.replace(hour=15, minute=0, second=0, microsecond=0),
            r'저녁': now.replace(hour=18, minute=0, second=0, microsecond=0),
            r'새벽': now.replace(hour=3, minute=0, second=0, microsecond=0),
        }
        
        for pattern, target_time in relative_patterns.items():
            if re.search(pattern, expression):
                return target_time
        
        # 구체적인 시간 패턴 (예: "오늘 9시", "내일 오후 3시")
        time_match = re.search(r'(\d{1,2})시', expression)
        if time_match:
            hour = int(time_match.group(1))
            base_date = now
            
            if '어제' in expression:
                base_date = now - timedelta(days=1)
            elif '내일' in expression:
                base_date = now + timedelta(days=1)
            
            return base_date.replace(hour=hour, minute=0, second=0, microsecond=0)
        
        return None
    
    @staticmethod
    def parse_time_range(expression: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """시간 범위 표현을 파싱"""
        now = datetime.now()
        expression = expression.lower().strip()
        
        # 오전/오후 구분
        if '오전' in expression:
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = now.replace(hour=12, minute=0, second=0, microsecond=0)
            return start_time, end_time
        elif '오후' in expression:
            start_time = now.replace(hour=12, minute=0, second=0, microsecond=0)
            end_time = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start_time, end_time
        
        # 지난 N시간/일
        duration_match = re.search(r'지난\s*(\d+)\s*(시간|일)', expression)
        if duration_match:
            amount = int(duration_match.group(1))
            unit = duration_match.group(2)
            
            if unit == '시간':
                start_time = now - timedelta(hours=amount)
            else:  # 일
                start_time = now - timedelta(days=amount)
            
            return start_time, now
        
        return None, None

class AdvancedWaterAnalyzer:
    """고급 수위 분석 클래스"""
    
    def __init__(self):
        self.db_config = {
            'host': PG_DB_HOST,
            'port': PG_DB_PORT,
            'database': PG_DB_NAME,
            'user': PG_DB_USER,
            'password': PG_DB_PASSWORD
        }
        
        self.reservoirs = {
            'gagok': {'name': '가곡 배수지', 'level_col': 'gagok_water_level', 'pumps': ['gagok_pump_a', 'gagok_pump_b']},
            'haeryong': {'name': '해룡 배수지', 'level_col': 'haeryong_water_level', 'pumps': ['haeryong_pump_a', 'haeryong_pump_b']},
            'sangsa': {'name': '상사 배수지', 'level_col': 'sangsa_water_level', 'pumps': ['sangsa_pump_a', 'sangsa_pump_b', 'sangsa_pump_c']}
        }
        
        self.time_parser = TimeParser()
        self.prediction_tool = WaterLevelPredictionTool()
        
    def get_connection(self):
        """PostgreSQL 연결"""
        try:
            return psycopg2.connect(**self.db_config)
        except Exception as e:
            logger.error(f"DB 연결 오류: {str(e)}")
            raise
    
    def get_current_trend(self, reservoir_id: str, hours: int = 1) -> Dict[str, Any]:
        """현재 수위 상승/하강 추세 계산"""
        try:
            if reservoir_id not in self.reservoirs:
                return {'success': False, 'error': f'존재하지 않는 배수지: {reservoir_id}'}
            
            config = self.reservoirs[reservoir_id]
            
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    # 최근 N시간 데이터 조회
                    cur.execute(f"""
                        SELECT measured_at, {config['level_col']} as water_level
                        FROM water 
                        WHERE measured_at >= NOW() - INTERVAL '{hours} hours'
                        ORDER BY measured_at ASC;
                    """)
                    
                    results = cur.fetchall()
                    
                    if len(results) < 2:
                        return {
                            'success': False,
                            'error': '추세 계산을 위한 충분한 데이터가 없습니다'
                        }
                    
                    # 선형 회귀로 추세 계산
                    timestamps = []
                    levels = []
                    
                    for row in results:
                        if row['water_level'] is not None:
                            timestamps.append(row['measured_at'].timestamp())
                            levels.append(float(row['water_level']))
                    
                    if len(levels) < 2:
                        return {'success': False, 'error': '유효한 수위 데이터가 부족합니다'}
                    
                    # 최소제곱법으로 기울기 계산
                    n = len(timestamps)
                    x_mean = mean(timestamps)
                    y_mean = mean(levels)
                    
                    numerator = sum((timestamps[i] - x_mean) * (levels[i] - y_mean) for i in range(n))
                    denominator = sum((timestamps[i] - x_mean) ** 2 for i in range(n))
                    
                    if denominator == 0:
                        slope = 0
                    else:
                        slope = numerator / denominator
                    
                    # 기울기를 시간당 변화량으로 변환 (cm/hour)
                    trend_per_hour = slope * 3600
                    
                    # 추세 분류
                    if abs(trend_per_hour) < 0.1:
                        trend_type = "stable"
                        trend_description = "안정"
                    elif trend_per_hour > 0:
                        trend_type = "rising"
                        trend_description = "상승"
                    else:
                        trend_type = "falling"  
                        trend_description = "하강"
                    
                    return {
                        'success': True,
                        'reservoir_id': reservoir_id,
                        'reservoir_name': config['name'],
                        'trend_per_hour': round(trend_per_hour, 2),
                        'trend_type': trend_type,
                        'trend_description': trend_description,
                        'current_level': levels[-1],
                        'data_points': len(levels),
                        'time_range_hours': hours
                    }
                    
        except Exception as e:
            logger.error(f"추세 계산 오류: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def predict_alert_time(self, reservoir_id: str, alert_threshold: float = 100.0) -> Dict[str, Any]:
        """경보 수위 도달 시점 예측"""
        try:
            # 현재 추세 계산
            trend_result = self.get_current_trend(reservoir_id, hours=1)
            
            if not trend_result['success']:
                return trend_result
            
            current_level = trend_result['current_level']
            trend_per_hour = trend_result['trend_per_hour']
            
            if trend_per_hour <= 0:
                return {
                    'success': True,
                    'message': '현재 수위가 하강 중이거나 안정적이어서 경보 수위에 도달하지 않을 것으로 예상됩니다.',
                    'current_level': current_level,
                    'alert_threshold': alert_threshold,
                    'trend_per_hour': trend_per_hour
                }
            
            # 경보 수위까지의 거리와 시간 계산
            level_difference = alert_threshold - current_level
            
            if level_difference <= 0:
                return {
                    'success': True,
                    'message': '이미 경보 수위를 초과했습니다.',
                    'current_level': current_level,
                    'alert_threshold': alert_threshold,
                    'exceeded': True
                }
            
            hours_to_alert = level_difference / trend_per_hour
            alert_time = datetime.now() + timedelta(hours=hours_to_alert)
            
            return {
                'success': True,
                'current_level': current_level,
                'alert_threshold': alert_threshold,
                'trend_per_hour': trend_per_hour,
                'hours_to_alert': round(hours_to_alert, 1),
                'minutes_to_alert': round(hours_to_alert * 60, 0),
                'alert_time': alert_time.strftime('%Y-%m-%d %H:%M:%S'),
                'message': f'현재 속도라면 약 {round(hours_to_alert * 60, 0)}분 후 경보 수위 도달 예상'
            }
            
        except Exception as e:
            logger.error(f"경보 시점 예측 오류: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def simulate_pump_effect(self, reservoir_id: str, pump_flow_rate: float = 10.0) -> Dict[str, Any]:
        """펌프 가동 시 수위 감소 시뮬레이션"""
        try:
            # 현재 수위와 추세 계산
            trend_result = self.get_current_trend(reservoir_id, hours=1)
            
            if not trend_result['success']:
                return trend_result
            
            current_level = trend_result['current_level']
            inflow_rate = trend_result['trend_per_hour']  # 현재 상승률
            
            config = self.reservoirs[reservoir_id]
            total_pumps = len(config['pumps'])
            
            # 펌프 가동 시 순 감소율 계산 (유입량 - 펌프 배출량)
            # 펌프 1개당 flow_rate cm/hour 감소 효과 가정
            net_change_rate = inflow_rate - (pump_flow_rate * total_pumps)
            
            # 정상 수위(예: 60cm)까지 복귀 시간 계산
            normal_level = 60.0
            
            if current_level <= normal_level:
                return {
                    'success': True,
                    'message': '이미 정상 수위입니다.',
                    'current_level': current_level,
                    'normal_level': normal_level
                }
            
            level_to_reduce = current_level - normal_level
            
            if net_change_rate >= 0:
                return {
                    'success': True,
                    'message': f'펌프 가동 중이지만 유입량({inflow_rate:.1f} cm/h)이 많아 수위가 계속 상승할 것으로 예상됩니다.',
                    'current_level': current_level,
                    'inflow_rate': inflow_rate,
                    'pump_capacity': pump_flow_rate * total_pumps,
                    'net_change_rate': net_change_rate
                }
            
            hours_to_normal = level_to_reduce / abs(net_change_rate)
            recovery_time = datetime.now() + timedelta(hours=hours_to_normal)
            
            return {
                'success': True,
                'current_level': current_level,
                'normal_level': normal_level,
                'inflow_rate': inflow_rate,
                'pump_capacity': pump_flow_rate * total_pumps,
                'net_reduction_rate': abs(net_change_rate),
                'hours_to_recovery': round(hours_to_normal, 1),
                'minutes_to_recovery': round(hours_to_normal * 60, 0),
                'recovery_time': recovery_time.strftime('%Y-%m-%d %H:%M:%S'),
                'message': f'펌프 자동 가동 시 약 {round(hours_to_normal * 60, 0)}분 내 정상 수위 복귀 예상'
            }
            
        except Exception as e:
            logger.error(f"펌프 효과 시뮬레이션 오류: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def compare_periods(self, reservoir_id: str, period1_start: datetime, period1_end: datetime,
                       period2_start: datetime, period2_end: datetime) -> Dict[str, Any]:
        """두 기간의 수위 데이터 비교"""
        try:
            if reservoir_id not in self.reservoirs:
                return {'success': False, 'error': f'존재하지 않는 배수지: {reservoir_id}'}
            
            config = self.reservoirs[reservoir_id]
            
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    # 첫 번째 기간 데이터
                    cur.execute(f"""
                        SELECT {config['level_col']} as water_level
                        FROM water 
                        WHERE measured_at BETWEEN %s AND %s
                        AND {config['level_col']} IS NOT NULL
                        ORDER BY measured_at;
                    """, (period1_start, period1_end))
                    
                    period1_data = [float(row['water_level']) for row in cur.fetchall()]
                    
                    # 두 번째 기간 데이터
                    cur.execute(f"""
                        SELECT {config['level_col']} as water_level
                        FROM water 
                        WHERE measured_at BETWEEN %s AND %s
                        AND {config['level_col']} IS NOT NULL
                        ORDER BY measured_at;
                    """, (period2_start, period2_end))
                    
                    period2_data = [float(row['water_level']) for row in cur.fetchall()]
                    
                    if not period1_data or not period2_data:
                        return {
                            'success': False,
                            'error': '비교할 데이터가 충분하지 않습니다',
                            'period1_points': len(period1_data),
                            'period2_points': len(period2_data)
                        }
                    
                    # 통계 계산
                    period1_stats = {
                        'average': round(mean(period1_data), 2),
                        'min': round(min(period1_data), 2),
                        'max': round(max(period1_data), 2),
                        'std_dev': round(stdev(period1_data) if len(period1_data) > 1 else 0, 2),
                        'range': round(max(period1_data) - min(period1_data), 2),
                        'data_points': len(period1_data)
                    }
                    
                    period2_stats = {
                        'average': round(mean(period2_data), 2),
                        'min': round(min(period2_data), 2),
                        'max': round(max(period2_data), 2),
                        'std_dev': round(stdev(period2_data) if len(period2_data) > 1 else 0, 2),
                        'range': round(max(period2_data) - min(period2_data), 2),
                        'data_points': len(period2_data)
                    }
                    
                    # 안정성 비교 (표준편차 기준)
                    if period1_stats['std_dev'] < period2_stats['std_dev']:
                        more_stable = 'period1'
                        stability_diff = period2_stats['std_dev'] - period1_stats['std_dev']
                    elif period2_stats['std_dev'] < period1_stats['std_dev']:
                        more_stable = 'period2'
                        stability_diff = period1_stats['std_dev'] - period2_stats['std_dev']
                    else:
                        more_stable = 'equal'
                        stability_diff = 0
                    
                    return {
                        'success': True,
                        'reservoir_id': reservoir_id,
                        'reservoir_name': config['name'],
                        'period1': {
                            'start': period1_start.strftime('%Y-%m-%d %H:%M:%S'),
                            'end': period1_end.strftime('%Y-%m-%d %H:%M:%S'),
                            'stats': period1_stats
                        },
                        'period2': {
                            'start': period2_start.strftime('%Y-%m-%d %H:%M:%S'),
                            'end': period2_end.strftime('%Y-%m-%d %H:%M:%S'),
                            'stats': period2_stats
                        },
                        'comparison': {
                            'more_stable_period': more_stable,
                            'stability_difference': round(stability_diff, 2),
                            'average_difference': round(period2_stats['average'] - period1_stats['average'], 2),
                            'range_difference': round(period2_stats['range'] - period1_stats['range'], 2)
                        }
                    }
                    
        except Exception as e:
            logger.error(f"기간 비교 오류: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_pump_history(self, reservoir_id: str, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """특정 기간의 펌프 가동 이력 조회"""
        try:
            if reservoir_id not in self.reservoirs:
                return {'success': False, 'error': f'존재하지 않는 배수지: {reservoir_id}'}
            
            config = self.reservoirs[reservoir_id]
            
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    # 펌프 상태 변화 이력 조회
                    pump_columns = ', '.join(config['pumps'])
                    
                    cur.execute(f"""
                        SELECT measured_at, {pump_columns}
                        FROM water 
                        WHERE measured_at BETWEEN %s AND %s
                        ORDER BY measured_at;
                    """, (start_time, end_time))
                    
                    results = cur.fetchall()
                    
                    if not results:
                        return {
                            'success': False,
                            'error': '해당 기간의 펌프 데이터가 없습니다'
                        }
                    
                    # 펌프 가동 구간 분석
                    pump_sessions = []
                    current_session = None
                    
                    for row in results:
                        # 현재 가동 중인 펌프 확인
                        active_pumps = []
                        for pump_col in config['pumps']:
                            pump_value = float(row[pump_col]) if row[pump_col] is not None else 0.0
                            if pump_value >= 1.0:
                                pump_name = pump_col.replace(f'{reservoir_id}_', '').replace('_', ' ').title()
                                active_pumps.append(pump_name)
                        
                        if active_pumps:
                            if current_session is None:
                                current_session = {
                                    'start_time': row['measured_at'],
                                    'active_pumps': active_pumps
                                }
                            elif current_session['active_pumps'] != active_pumps:
                                # 펌프 상태가 변경됨 - 이전 세션 종료
                                current_session['end_time'] = row['measured_at']
                                duration = (current_session['end_time'] - current_session['start_time']).total_seconds() / 60
                                current_session['duration_minutes'] = round(duration, 1)
                                pump_sessions.append(current_session)
                                
                                # 새 세션 시작
                                current_session = {
                                    'start_time': row['measured_at'],
                                    'active_pumps': active_pumps
                                }
                        else:
                            if current_session is not None:
                                # 펌프 중단 - 세션 종료
                                current_session['end_time'] = row['measured_at']
                                duration = (current_session['end_time'] - current_session['start_time']).total_seconds() / 60
                                current_session['duration_minutes'] = round(duration, 1)
                                pump_sessions.append(current_session)
                                current_session = None
                    
                    # 마지막 세션 처리
                    if current_session is not None:
                        current_session['end_time'] = results[-1]['measured_at']
                        duration = (current_session['end_time'] - current_session['start_time']).total_seconds() / 60
                        current_session['duration_minutes'] = round(duration, 1)
                        pump_sessions.append(current_session)
                    
                    # 통계 계산
                    total_sessions = len(pump_sessions)
                    total_duration = sum(session['duration_minutes'] for session in pump_sessions)
                    
                    return {
                        'success': True,
                        'reservoir_id': reservoir_id,
                        'reservoir_name': config['name'],
                        'period': {
                            'start': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'end': end_time.strftime('%Y-%m-%d %H:%M:%S')
                        },
                        'pump_sessions': [
                            {
                                'start_time': session['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
                                'end_time': session['end_time'].strftime('%Y-%m-%d %H:%M:%S'),
                                'duration_minutes': session['duration_minutes'],
                                'active_pumps': session['active_pumps']
                            }
                            for session in pump_sessions
                        ],
                        'summary': {
                            'total_sessions': total_sessions,
                            'total_duration_minutes': round(total_duration, 1),
                            'total_duration_hours': round(total_duration / 60, 1),
                            'average_session_duration': round(total_duration / total_sessions, 1) if total_sessions > 0 else 0
                        }
                    }
                    
        except Exception as e:
            logger.error(f"펌프 이력 조회 오류: {str(e)}")
            return {'success': False, 'error': str(e)}

def advanced_water_analysis_tool(**kwargs) -> Dict[str, Any]:
    """고급 수위 분석 도구 메인 함수"""
    analyzer = AdvancedWaterAnalyzer()
    action = kwargs.get('action', 'current_trend')
    
    try:
        if action == 'current_trend':
            # 현재 수위 추세 분석
            reservoir_id = kwargs.get('reservoir_id', 'gagok')
            hours = kwargs.get('hours', 1)
            return analyzer.get_current_trend(reservoir_id, hours)
        
        elif action == 'predict_alert':
            # 경보 수위 도달 시점 예측
            reservoir_id = kwargs.get('reservoir_id', 'gagok')
            alert_threshold = kwargs.get('alert_threshold', 100.0)
            return analyzer.predict_alert_time(reservoir_id, alert_threshold)
        
        elif action == 'simulate_pump':
            # 펌프 효과 시뮬레이션
            reservoir_id = kwargs.get('reservoir_id', 'gagok')
            pump_flow_rate = kwargs.get('pump_flow_rate', 10.0)
            return analyzer.simulate_pump_effect(reservoir_id, pump_flow_rate)
        
        elif action == 'compare_periods':
            # 기간별 수위 비교
            reservoir_id = kwargs.get('reservoir_id', 'gagok')
            period1_start = kwargs.get('period1_start')
            period1_end = kwargs.get('period1_end')
            period2_start = kwargs.get('period2_start')
            period2_end = kwargs.get('period2_end')
            
            if not all([period1_start, period1_end, period2_start, period2_end]):
                return {'success': False, 'error': '비교할 기간을 모두 지정해야 합니다'}
            
            return analyzer.compare_periods(reservoir_id, period1_start, period1_end, period2_start, period2_end)
        
        elif action == 'pump_history':
            # 펌프 가동 이력 조회
            reservoir_id = kwargs.get('reservoir_id', 'gagok')
            start_time = kwargs.get('start_time')
            end_time = kwargs.get('end_time')
            
            if not start_time or not end_time:
                # 기본값: 어제 전체
                end_time = datetime.now()
                start_time = end_time - timedelta(days=1)
            
            return analyzer.get_pump_history(reservoir_id, start_time, end_time)
        
        elif action == 'parse_time':
            # 시간 표현 파싱
            expression = kwargs.get('expression', '')
            parsed_time = analyzer.time_parser.parse_time_expression(expression)
            
            if parsed_time:
                return {
                    'success': True,
                    'expression': expression,
                    'parsed_time': parsed_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp': parsed_time.timestamp()
                }
            else:
                return {
                    'success': False,
                    'error': f'시간 표현 "{expression}"을 해석할 수 없습니다'
                }
        
        else:
            return {
                'success': False,
                'error': f'알 수 없는 액션: {action}',
                'available_actions': [
                    'current_trend', 'predict_alert', 'simulate_pump',
                    'compare_periods', 'pump_history', 'parse_time'
                ]
            }
            
    except Exception as e:
        logger.error(f"고급 수위 분석 도구 오류: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'message': '고급 수위 분석 중 오류 발생'
        }