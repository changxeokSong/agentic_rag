# tools/smart_water_prediction_tool.py - DB 연동 스마트 수위 예측 도구

import numpy as np
import tensorflow as tf
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from config import PG_DB_HOST, PG_DB_PORT, PG_DB_NAME, PG_DB_USER, PG_DB_PASSWORD
from utils.logger import setup_logger
import psycopg2
import psycopg2.extras
import os

logger = setup_logger(__name__)

class SmartWaterPredictionTool:
    """데이터베이스 연동 스마트 수위 예측 도구

    사용자가 "가곡 배수지 30분 후 수위 예측해줘" 같은 질문을 하면
    자동으로 DB에서 최근 데이터를 가져와서 예측합니다.
    """

    def __init__(self):
        self.name = "smart_water_prediction"
        self.description = "데이터베이스에서 자동으로 수위 데이터를 가져와서 LSTM 모델로 미래 수위를 예측합니다. 가곡/해룡 배수지별로 1분, 5분, 30분, 1시간, 6시간 후 수위를 예측할 수 있습니다."

        self.db_config = {
            'host': PG_DB_HOST,
            'port': PG_DB_PORT,
            'database': PG_DB_NAME,
            'user': PG_DB_USER,
            'password': PG_DB_PASSWORD
        }

        # 배수지 매핑
        self.reservoirs = {
            'gagok': {'name': '가곡', 'col': 'gagok_water_level'},
            'haeryong': {'name': '해룡', 'col': 'haeryong_water_level'}
        }

        # LSTM 모델 설정
        self.model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'lstm_model', 'lstm_water_level_model.h5')
        self.lstm_model = None
        self.lstm_available = False
        self._load_lstm_model()

    def _load_lstm_model(self):
        """LSTM 모델 로드"""
        try:
            if os.path.exists(self.model_path):
                self.lstm_model = tf.keras.models.load_model(self.model_path)
                self.lstm_available = True
                logger.info(f"LSTM 모델 로드 완료: {self.model_path}")
            else:
                logger.warning(f"LSTM 모델 파일을 찾을 수 없습니다: {self.model_path}")
                self.lstm_available = False
        except Exception as e:
            logger.error(f"LSTM 모델 로드 실패: {str(e)}")
            self.lstm_available = False

    def get_tool_config(self) -> Dict[str, Any]:
        """LLM 도구 설정 반환"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reservoir": {
                            "type": "string",
                            "enum": ["gagok", "haeryong", "가곡", "해룡"],
                            "description": "예측할 배수지 (가곡 또는 해룡)"
                        },
                        "time_minutes": {
                            "type": "integer",
                            "description": "예측 시간 (분 단위). 예: 1, 5, 30, 60, 360. target_level이 설정되지 않은 경우 필수"
                        },
                        "target_level": {
                            "type": "number",
                            "description": "목표 수위 (m 단위). 예: 100m 도달 시간을 알고 싶으면 100 입력. 설정 시 time_minutes는 무시됨"
                        },
                        "lookback_hours": {
                            "type": "integer",
                            "description": "과거 데이터 조회 시간 (시간 단위). 기본값: 4시간 (권장: 2-6시간)",
                            "default": 4
                        },
                        "time_expression": {
                            "type": "string",
                            "description": "시간 표현 (예: '점심', '30분 후', '1시간 후', '오후 3시', '저녁'). 설정 시 time_minutes는 자동 계산됨"
                        }
                    },
                    "required": ["reservoir"]
                }
            }
        }

    def _get_reservoir_key(self, reservoir: str) -> Optional[str]:
        """배수지 이름을 키로 변환"""
        reservoir_lower = reservoir.lower()

        if reservoir_lower in ['gagok', '가곡']:
            return 'gagok'
        elif reservoir_lower in ['haeryong', '해룡']:
            return 'haeryong'

        return None

    def _fetch_historical_data(self, reservoir_key: str, lookback_hours: int = 4) -> List[Dict[str, Any]]:
        """데이터베이스에서 과거 수위 데이터 조회"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            reservoir_info = self.reservoirs[reservoir_key]
            column_name = reservoir_info['col']

            # 최근 N시간 데이터 조회 (이상치 제거)
            query = f"""
                SELECT {column_name} as water_level, measured_at
                FROM water
                WHERE measured_at >= NOW() - INTERVAL '{lookback_hours} hours'
                  AND {column_name} IS NOT NULL
                  AND {column_name} > 0
                  AND {column_name} < 200
                ORDER BY measured_at ASC
            """

            cursor.execute(query)
            rows = cursor.fetchall()

            cursor.close()
            conn.close()

            if not rows:
                logger.warning(f"{reservoir_info['name']} 배수지의 최근 {lookback_hours}시간 데이터가 없습니다")
                return []

            logger.info(f"{reservoir_info['name']} 배수지 과거 데이터 {len(rows)}개 조회 완료")

            return rows

        except Exception as e:
            logger.error(f"데이터베이스 조회 오류: {e}")
            return []

    def _simple_linear_prediction(self, data: List[float], future_steps: int) -> List[float]:
        """간단한 선형 예측 (추세 기반)"""
        if len(data) < 2:
            # 데이터가 부족하면 마지막 값 유지
            return [data[-1]] * future_steps if data else [0.0] * future_steps

        # 최근 데이터의 추세 계산
        recent_window = min(30, len(data))  # 최근 30개 데이터
        recent_data = data[-recent_window:]

        x = np.arange(len(recent_data))
        y = np.array(recent_data)

        # 선형 회귀
        if len(x) > 1:
            coeffs = np.polyfit(x, y, 1)  # y = ax + b
            slope, intercept = coeffs
        else:
            slope = 0
            intercept = recent_data[-1]

        # 미래 예측
        predictions = []
        last_x = len(data) - 1

        for step in range(1, future_steps + 1):
            future_x = last_x + step
            pred_value = slope * future_x + intercept
            predictions.append(float(pred_value))

        return predictions

    def _moving_average_prediction(self, data: List[float], future_steps: int, window: int = 10) -> List[float]:
        """이동 평균 기반 예측"""
        if len(data) < window:
            window = max(1, len(data))

        predictions = []
        current_data = list(data)

        for _ in range(future_steps):
            # 최근 window 개의 평균 계산
            recent = current_data[-window:]
            avg = np.mean(recent)
            predictions.append(float(avg))
            current_data.append(avg)

        return predictions

    def _lstm_prediction(self, data: List[float], future_steps: int) -> List[float]:
        """LSTM 모델을 사용한 예측"""
        if not self.lstm_available or self.lstm_model is None:
            logger.warning("LSTM 모델을 사용할 수 없습니다. 기존 알고리즘으로 폴백합니다.")
            return self._simple_linear_prediction(data, future_steps)

        try:
            # 데이터 전처리 (LSTM 모델 요구사항에 맞춤)
            water_array = np.array(data, dtype=np.float64)
            
            # 모델 입력 크기 확인 (60개 시계열 데이터 필요)
            expected_length = 60
            if len(water_array) < expected_length:
                # 패딩 또는 반복으로 60개 맞추기
                if len(water_array) >= expected_length // 2:
                    # 데이터가 충분히 많으면 마지막 값들을 반복
                    pad_length = expected_length - len(water_array)
                    last_values = np.repeat(water_array[-1], pad_length)
                    water_array = np.concatenate([water_array, last_values])
                else:
                    # 데이터가 적으면 전체를 반복
                    repeat_times = expected_length // len(water_array) + 1
                    water_array = np.tile(water_array, repeat_times)[:expected_length]
            elif len(water_array) > expected_length:
                # 데이터가 많으면 스마트 샘플링 사용
                # 전체 데이터의 마지막 1/3 부분에서 60개 샘플링
                start_idx = max(0, len(water_array) - len(water_array) // 3)
                end_idx = len(water_array)
                
                # 마지막 1/3 부분에서 60개 균등 샘플링
                if end_idx - start_idx >= expected_length:
                    indices = np.linspace(start_idx, end_idx - 1, expected_length, dtype=int)
                    water_array = water_array[indices]
                else:
                    # 마지막 60개만 사용
                    water_array = water_array[-expected_length:]
            
            # 데이터 정규화 (실제 수위 범위 기준으로 개선)
            data_min = np.min(water_array)
            data_max = np.max(water_array)
            data_range = data_max - data_min
            
            # 수위 데이터의 합리적인 범위 (0~100m)를 기준으로 정규화
            if data_range > 50:  # 범위가 너무 크면 고정 범위 사용
                # 고정 범위로 정규화 (0~100m 기준)
                fixed_min, fixed_max = 0.0, 100.0
                normalized_data = (water_array - fixed_min) / (fixed_max - fixed_min)
                # 역정규화를 위한 실제 범위 저장
                data_min, data_max = fixed_min, fixed_max
                data_range = fixed_max - fixed_min
            elif data_range > 0:
                normalized_data = (water_array - data_min) / data_range
            else:
                normalized_data = water_array
            
            input_data = normalized_data.reshape(1, -1, 1)
            
            # 예측 실행
            predictions = []
            current_input = input_data
            
            for step in range(future_steps):
                # 한 스텝 예측
                pred = self.lstm_model.predict(current_input, verbose=0)
                # 정규화된 결과를 원래 범위로 역정규화
                pred_normalized = float(pred[0, 0])
                
                if data_range > 0:
                    pred_value = pred_normalized * data_range + data_min
                else:
                    pred_value = pred_normalized
                
                predictions.append(pred_value)
                
                # 다음 예측을 위해 입력 업데이트 (슬라이딩 윈도우)
                if current_input.shape[1] > 1:
                    current_input = np.concatenate([
                        current_input[:, 1:, :],
                        pred.reshape(1, 1, 1)
                    ], axis=1)
                else:
                    current_input = pred.reshape(1, 1, 1)
            
            logger.info(f"LSTM 모델 예측 완료: {len(predictions)}개 예측값")
            return predictions
            
        except Exception as e:
            logger.error(f"LSTM 예측 중 오류: {str(e)}")
            logger.info("기존 알고리즘으로 폴백합니다.")
            return self._simple_linear_prediction(data, future_steps)

    def _hybrid_prediction(self, data: List[float], future_steps: int) -> Dict[str, Any]:
        """LSTM 기반 예측 (단순화된 버전)"""
        # LSTM 모델 사용 가능 여부에 따라 예측 방법 선택
        if self.lstm_available:
            # LSTM 모델 사용 (100%)
            predictions = self._lstm_prediction(data, future_steps)
            model_used = "LSTM"
        else:
            # LSTM 사용 불가시: 선형 + 이동평균 폴백
            linear_preds = self._simple_linear_prediction(data, future_steps)
            ma_preds = self._moving_average_prediction(data, future_steps)
            predictions = []
            for i in range(future_steps):
                hybrid = 0.7 * linear_preds[i] + 0.3 * ma_preds[i]
                predictions.append(float(hybrid))
            model_used = "Linear + Moving Average (LSTM unavailable)"

        # 추세 분석
        if len(data) >= 2:
            recent_trend = data[-1] - data[max(0, len(data) - 10)]
            if recent_trend > 5:
                trend = "상승"
            elif recent_trend < -5:
                trend = "하강"
            else:
                trend = "안정"
        else:
            trend = "알 수 없음"

        result = {
            'predictions': predictions,
            'trend': trend,
            'current_level': float(data[-1]) if data else None,
            'model_used': model_used,
            'lstm_available': self.lstm_available
        }
        
        # LSTM 모델이 사용된 경우 LSTM 예측값도 포함
        if self.lstm_available:
            result['lstm_predictions'] = predictions
            
        return result

    def _calculate_target_arrival(
        self,
        historical_data: List[float],
        timestamps: List[datetime],
        current_level: float,
        target_level: float,
        reservoir_name: str,
        reservoir_key: str,
        lookback_hours: int,
        avg_interval: float
    ) -> Dict[str, Any]:
        """목표 수위 도달 시간 계산

        Args:
            historical_data: 과거 수위 데이터
            timestamps: 측정 시간 목록
            current_level: 현재 수위
            target_level: 목표 수위
            reservoir_name: 배수지 이름
            reservoir_key: 배수지 키
            lookback_hours: 조회한 과거 데이터 시간
            avg_interval: 데이터 평균 간격 (분)

        Returns:
            도달 시간 예측 결과
        """
        # 추세 분석
        if len(historical_data) >= 2:
            recent_window = min(30, len(historical_data))
            recent_data = historical_data[-recent_window:]
            x = np.arange(len(recent_data))
            y = np.array(recent_data)

            # 선형 회귀로 추세 계산
            coeffs = np.polyfit(x, y, 1)
            slope, intercept = coeffs  # slope는 데이터 포인트당 변화량

            # 분당 변화율 계산
            rate_per_minute = slope / avg_interval if avg_interval > 0 else 0
        else:
            slope = 0
            rate_per_minute = 0

        # 신뢰도 계산
        data_variance = np.var(historical_data[-30:]) if len(historical_data) >= 30 else np.var(historical_data)
        confidence = min(0.95, max(0.5, 1.0 - (data_variance / 100)))

        # 추세 판단
        if abs(rate_per_minute) < 0.01:  # 거의 변화 없음
            trend = "안정"
        elif rate_per_minute > 0:
            trend = "상승"
        else:
            trend = "하강"

        # 도달 가능성 계산
        level_diff = target_level - current_level

        result = {
            "success": True,
            "reservoir": reservoir_name,
            "reservoir_key": reservoir_key,
            "current_level": round(current_level, 2),
            "target_level": target_level,
            "level_difference": round(level_diff, 2),
            "trend": trend,
            "rate_per_minute": round(rate_per_minute, 4),
            "rate_per_hour": round(rate_per_minute * 60, 2),
            "confidence": round(confidence, 2),
            "data_points_used": len(historical_data),
            "lookback_hours": lookback_hours
        }

        # 도달 시간 계산
        if abs(rate_per_minute) < 0.001:  # 거의 변화 없음 (임계값 낮춤)
            result["reachable"] = False
            result["prediction_summary"] = (
                f"{reservoir_name} 배수지 {target_level}m 도달 불가능\n"
                f"📊 현재 수위: {current_level:.2f}m\n"
                f"📈 추세: {trend} (변화율 거의 없음)\n"
                f"⚠️ 현재 추세로는 목표 수위에 도달할 수 없습니다"
            )
            result["reason"] = "수위 변화가 거의 없어 도달 시간 예측 불가능"
        elif (level_diff > 0 and rate_per_minute <= 0) or (level_diff < 0 and rate_per_minute >= 0):
            # 목표가 위인데 하강 중이거나, 목표가 아래인데 상승 중인 경우
            result["reachable"] = False
            direction = "상승" if rate_per_minute > 0 else "하강"
            needed_direction = "상승" if level_diff > 0 else "하강"
            result["prediction_summary"] = (
                f"{reservoir_name} 배수지 {target_level}m 도달 불가능\n"
                f"📊 현재 수위: {current_level:.2f}m (목표까지 {abs(level_diff):.2f}m)\n"
                f"📈 현재 추세: {direction} ({rate_per_minute*60:.2f}m/시간)\n"
                f"⚠️ 목표 도달을 위해서는 {needed_direction} 필요하지만 현재는 {direction} 중입니다"
            )
            result["reason"] = f"추세 방향 불일치 (현재: {direction}, 필요: {needed_direction})"
        else:
            # 도달 가능한 경우
            minutes_to_target = abs(level_diff / rate_per_minute)
            arrival_time = datetime.now() + timedelta(minutes=minutes_to_target)

            result["reachable"] = True
            result["minutes_to_target"] = round(minutes_to_target, 1)
            result["hours_to_target"] = round(minutes_to_target / 60, 1)
            result["days_to_target"] = round(minutes_to_target / (60 * 24), 1)
            result["arrival_time"] = arrival_time.strftime("%Y-%m-%d %H:%M:%S")
            result["arrival_date_kr"] = arrival_time.strftime("%Y년 %m월 %d일 %H시 %M분")

            # 시간 표현을 사용자 친화적으로
            if minutes_to_target < 60:
                time_str = f"약 {int(minutes_to_target)}분"
            elif minutes_to_target < 60 * 24:
                hours = minutes_to_target / 60
                time_str = f"약 {hours:.1f}시간"
            else:
                days = minutes_to_target / (60 * 24)
                time_str = f"약 {days:.1f}일"

            result["time_str"] = time_str
            result["prediction_summary"] = (
                f"{reservoir_name} 배수지 {target_level}m 도달 예측\n"
                f"📊 현재 수위: {current_level:.2f}m\n"
                f"🎯 목표 수위: {target_level}m ({abs(level_diff):.2f}m {'상승' if level_diff > 0 else '하강'} 필요)\n"
                f"📈 현재 추세: {trend} ({rate_per_minute*60:.2f}m/시간)\n"
                f"⏰ 예상 도달 시간: {time_str} 후 ({result['arrival_date_kr']})\n"
                f"📉 신뢰도: {confidence*100:.0f}%"
            )

        return result

    def _parse_time_expression(self, expression: str) -> Optional[int]:
        """자연어 시간 표현을 분 단위로 변환

        Args:
            expression: 시간 표현 (예: "점심", "30분 후", "1시간 후", "오후 3시")

        Returns:
            변환된 시간 (분 단위) 또는 None
        """
        import re

        if not expression:
            return None

        expression = expression.lower().strip()
        now = datetime.now()

        # "N분 후", "N시간 후" 패턴
        minutes_match = re.search(r'(\d+)\s*분\s*(후|뒤)', expression)
        if minutes_match:
            return int(minutes_match.group(1))

        hours_match = re.search(r'(\d+)\s*시간\s*(후|뒤)', expression)
        if hours_match:
            return int(hours_match.group(1)) * 60

        # 특정 시각 표현
        time_targets = {
            '점심': now.replace(hour=12, minute=0),
            '점심때': now.replace(hour=12, minute=0),
            '점심시간': now.replace(hour=12, minute=0),
            '저녁': now.replace(hour=18, minute=0),
            '저녁때': now.replace(hour=18, minute=0),
            '아침': now.replace(hour=9, minute=0),
            '오전': now.replace(hour=9, minute=0),
            '오후': now.replace(hour=15, minute=0),
        }

        for key, target_time in time_targets.items():
            if key in expression:
                # 과거 시간이면 다음 날로 설정
                if target_time < now:
                    target_time += timedelta(days=1)
                diff_minutes = int((target_time - now).total_seconds() / 60)
                return diff_minutes

        # "오후 3시", "오전 9시" 패턴
        time_match = re.search(r'(오전|오후)\s*(\d+)\s*시', expression)
        if time_match:
            period = time_match.group(1)
            hour = int(time_match.group(2))

            if period == '오후' and hour < 12:
                hour += 12
            elif period == '오전' and hour == 12:
                hour = 0

            target_time = now.replace(hour=hour, minute=0)
            if target_time < now:
                target_time += timedelta(days=1)
            diff_minutes = int((target_time - now).total_seconds() / 60)
            return diff_minutes

        # "N시" 패턴 (24시간 형식)
        hour_match = re.search(r'(\d+)\s*시', expression)
        if hour_match:
            hour = int(hour_match.group(1))
            target_time = now.replace(hour=hour, minute=0)
            if target_time < now:
                target_time += timedelta(days=1)
            diff_minutes = int((target_time - now).total_seconds() / 60)
            return diff_minutes

        return None

    def execute(self, reservoir: str, time_minutes: int = None, target_level: float = None, lookback_hours: int = 4, time_expression: str = None, **kwargs) -> Dict[str, Any]:
        """수위 예측 실행

        Args:
            reservoir: 배수지 이름 (gagok, haeryong, 가곡, 해룡)
            time_minutes: 예측 시간 (분 단위). target_level이 없으면 필수
            target_level: 목표 수위 (m 단위). 설정 시 도달 시간 계산
            lookback_hours: 과거 데이터 조회 시간 (시간 단위)
            time_expression: 시간 표현 (예: "점심", "30분 후", "1시간 후")

        Returns:
            예측 결과 딕셔너리
        """
        try:
            # time_expression이 있으면 time_minutes로 변환
            if time_expression and time_minutes is None:
                parsed_minutes = self._parse_time_expression(time_expression)
                if parsed_minutes is not None:
                    time_minutes = parsed_minutes
                    logger.info(f"time_expression '{time_expression}' → {time_minutes}분으로 변환")
                else:
                    logger.warning(f"time_expression '{time_expression}' 파싱 실패")

            # target_level과 time_minutes 중 하나는 반드시 필요
            if target_level is None and time_minutes is None:
                return {
                    "success": False,
                    "error": "time_minutes, target_level 또는 time_expression 중 하나는 반드시 설정해야 합니다"
                }
            # 배수지 검증
            reservoir_key = self._get_reservoir_key(reservoir)
            if not reservoir_key:
                return {
                    "success": False,
                    "error": f"알 수 없는 배수지: {reservoir}. 가곡 또는 해룡을 선택하세요."
                }

            reservoir_info = self.reservoirs[reservoir_key]
            reservoir_name = reservoir_info['name']

            # 시간 검증 (target_level이 없는 경우만)
            if target_level is None and time_minutes <= 0:
                return {
                    "success": False,
                    "error": "예측 시간은 0보다 커야 합니다"
                }

            # 과거 데이터 조회
            if target_level is not None:
                logger.info(f"{reservoir_name} 배수지 {target_level}m 도달 시간 예측 시작")
            else:
                logger.info(f"{reservoir_name} 배수지 {time_minutes}분 후 수위 예측 시작")
            historical_rows = self._fetch_historical_data(reservoir_key, lookback_hours)

            if not historical_rows:
                return {
                    "success": False,
                    "error": f"{reservoir_name} 배수지의 과거 데이터가 없습니다. 데이터베이스를 확인하세요.",
                    "reservoir": reservoir_name
                }
            
            historical_data = [float(row['water_level']) for row in historical_rows]
            timestamps = [row['measured_at'] for row in historical_rows]

            # 데이터 간격 기반으로 예측 스텝 계산
            if len(timestamps) > 1:
                intervals = [(timestamps[i] - timestamps[i-1]).total_seconds() / 60.0 for i in range(1, len(timestamps))]
                avg_interval = np.mean(intervals)
                if avg_interval <= 0: avg_interval = 1 # 0으로 나누기 방지
            else:
                avg_interval = 1.0 # 데이터 포인트가 하나면 1분으로 가정

            # time_minutes이 있는 경우에만 future_steps 계산
            if time_minutes is not None:
                future_steps = int(round(time_minutes / avg_interval))
                if future_steps == 0: future_steps = 1
                logger.info(f"데이터 평균 간격: {avg_interval:.2f}분, 예측 스텝: {future_steps}")
            else:
                future_steps = 1 # target_level 계산 시에는 기본 스텝 사용


            # 현재 수위
            current_level = float(historical_data[-1]) if historical_data else None

            # target_level이 설정된 경우: 도달 시간 계산
            if target_level is not None:
                return self._calculate_target_arrival(
                    historical_data, timestamps, current_level, target_level,
                    reservoir_name, reservoir_key, lookback_hours, avg_interval
                )

            # time_minutes이 설정된 경우: 일반 예측
            # 하이브리드 예측 수행
            prediction_result = self._hybrid_prediction(historical_data, future_steps)

            # 최종 예측값 (time_minutes 시점의 값)
            final_prediction = prediction_result['predictions'][-1]

            # 변화량 계산
            change = final_prediction - current_level if current_level is not None else None

            # 시간 정보
            prediction_time = datetime.now() + timedelta(minutes=time_minutes)

            # 신뢰도 계산 (데이터 양과 변동성 기반)
            data_variance = np.var(historical_data[-30:]) if len(historical_data) >= 30 else np.var(historical_data)
            confidence = min(0.95, max(0.5, 1.0 - (data_variance / 100)))

            result = {
                "success": True,
                "reservoir": reservoir_name,
                "reservoir_key": reservoir_key,
                "current_level": current_level,
                "predicted_level": final_prediction,
                "change": change,
                "prediction_time": prediction_time.strftime("%Y-%m-%d %H:%M:%S"),
                "time_minutes": time_minutes,
                "trend": prediction_result['trend'],
                "confidence": round(confidence, 2),
                "data_points_used": len(historical_data),
                "lookback_hours": lookback_hours,
                "prediction_summary": f"{reservoir_name} 배수지 {time_minutes}분 후 예상 수위: {final_prediction:.2f}m",
                "model_used": prediction_result.get('model_used', 'Unknown'),
                "lstm_available": prediction_result.get('lstm_available', False)
            }

            # 경고 메시지
            warnings = []
            if final_prediction > 90:
                warnings.append(f"⚠️ 높은 수위 예상 ({final_prediction:.2f}m) - 배수 필요")
            elif final_prediction < 20:
                warnings.append(f"⚠️ 낮은 수위 예상 ({final_prediction:.2f}m) - 급수 필요")

            if warnings:
                result["warnings"] = warnings

            logger.info(f"{reservoir_name} 배수지 예측 완료: {final_prediction:.2f}m")
            return result

        except Exception as e:
            logger.error(f"수위 예측 오류: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"수위 예측 중 오류 발생: {str(e)}"
            }

    def get_info(self) -> Dict[str, str]:
        """도구 정보 반환"""
        return {
            "name": self.name,
            "description": self.description,
            "lstm_model_available": str(self.lstm_available),
            "lstm_model_path": self.model_path
        }
