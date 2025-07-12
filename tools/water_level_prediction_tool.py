# tools/water_level_prediction_tool.py

import numpy as np
import tensorflow as tf
from typing import Dict
from utils.logger import setup_logger
import os

logger = setup_logger(__name__)

class WaterLevelPredictionTool:
    """LSTM 모델을 사용한 수위 예측 도구"""
    
    def __init__(self):
        """수위 예측 도구 초기화"""
        self.name = "water_level_prediction_tool"
        self.description = "LSTM 모델을 사용하여 수위를 예측합니다. 과거 수위 데이터를 입력받아 미래 수위를 예측합니다."
        self.model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'lstm_model', 'lstm_water_level_model.h5')
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """LSTM 모델 로드"""
        try:
            if os.path.exists(self.model_path):
                self.model = tf.keras.models.load_model(self.model_path)
                logger.info(f"LSTM 모델 로드 완료: {self.model_path}")
            else:
                logger.error(f"모델 파일을 찾을 수 없습니다: {self.model_path}")
        except Exception as e:
            logger.error(f"모델 로드 실패: {str(e)}")
    
    def _convert_and_validate_data(self, data):
        """데이터를 수위 리스트로 변환 및 검증"""
        if data is None:
            return None
        
        try:
            # 이미 리스트인 경우
            if isinstance(data, list):
                # 중첩 리스트 평면화
                if any(isinstance(item, (list, tuple)) for item in data):
                    flattened = []
                    for item in data:
                        if isinstance(item, (list, tuple)):
                            flattened.extend(item)
                        else:
                            flattened.append(item)
                    data = flattened
                
                # 숫자 변환
                converted = []
                for item in data:
                    if isinstance(item, (int, float)):
                        converted.append(float(item))
                    elif isinstance(item, str):
                        # 문자열에서 숫자 추출
                        try:
                            converted.append(float(item.strip()))
                        except ValueError:
                            # 문자열에서 숫자만 추출 시도
                            import re
                            numbers = re.findall(r'-?\d+\.?\d*', item)
                            if numbers:
                                converted.append(float(numbers[0]))
                            else:
                                logger.warning(f"숫자로 변환할 수 없는 항목 무시: {item}")
                                continue
                    else:
                        logger.warning(f"지원되지 않는 데이터 타입 무시: {type(item)} - {item}")
                        continue
                
                return converted if converted else None
            
            # 문자열인 경우 (JSON 형태 가능)
            elif isinstance(data, str):
                import json
                import re
                
                try:
                    # JSON 파싱 시도
                    parsed = json.loads(data)
                    if isinstance(parsed, list):
                        return self._convert_and_validate_data(parsed)
                except json.JSONDecodeError:
                    pass
                
                # 대괄호로 감싸진 문자열 처리
                if data.strip().startswith('[') and data.strip().endswith(']'):
                    try:
                        # 안전하게 리스트로 변환
                        list_str = data.strip()[1:-1]  # 대괄호 제거
                        numbers = []
                        for item in list_str.split(','):
                            item = item.strip()
                            if item:
                                numbers.append(float(item))
                        return numbers if numbers else None
                    except ValueError:
                        pass
                
                # 일반 문자열에서 숫자 추출
                numbers = re.findall(r'-?\d+\.?\d*', data)
                if numbers:
                    return [float(num) for num in numbers]
                
                return None
            
            # 단일 숫자인 경우
            elif isinstance(data, (int, float)):
                return [float(data)]
            
            # 다른 반복 가능한 객체인 경우
            elif hasattr(data, '__iter__'):
                return self._convert_and_validate_data(list(data))
            
            else:
                logger.warning(f"지원되지 않는 데이터 타입: {type(data)}")
                return None
                
        except Exception as e:
            logger.error(f"데이터 변환 중 오류: {str(e)}")
            return None
    
    def _clean_data(self, data):
        """데이터 품질 검증 및 정제"""
        if not data:
            return data
        
        cleaned = []
        for item in data:
            # 이상치 제거 (너무 큰 값이나 작은 값)
            if isinstance(item, (int, float)):
                if -10000 <= item <= 10000:  # 수위 범위 제한
                    cleaned.append(item)
                else:
                    logger.warning(f"이상치 제거: {item}")
            else:
                logger.warning(f"숫자가 아닌 데이터 제거: {item}")
        
        # 중복 제거 (연속된 동일한 값 제한)
        if len(cleaned) > 1:
            final_cleaned = [cleaned[0]]
            consecutive_count = 1
            
            for i in range(1, len(cleaned)):
                if cleaned[i] == cleaned[i-1]:
                    consecutive_count += 1
                    if consecutive_count <= 5:  # 연속 5개까지만 허용
                        final_cleaned.append(cleaned[i])
                else:
                    consecutive_count = 1
                    final_cleaned.append(cleaned[i])
            
            cleaned = final_cleaned
        
        logger.info(f"데이터 정제 완료: {len(data)} → {len(cleaned)}개")
        return cleaned
    
    def _extract_data_from_context(self, kwargs):
        """컨텍스트나 환경에서 수위 데이터 추출"""
        # 시스템 컨텍스트에서 사용자 질문 가져오기
        try:
            # 전역 변수나 컨텍스트에서 현재 사용자 질문 가져오기
            import threading
            context = getattr(threading.current_thread(), 'context', None)
            if context and hasattr(context, 'user_query'):
                user_query = context.user_query
            else:
                # 다른 방법으로 사용자 질문 가져오기
                user_query = kwargs.get('user_query') or kwargs.get('query') or kwargs.get('question')
            
            if user_query:
                logger.info(f"사용자 질문에서 데이터 추출 시도: {user_query[:100]}...")
                return self._parse_data_from_text(user_query)
            
        except Exception as e:
            logger.debug(f"컨텍스트에서 데이터 추출 실패: {e}")
        
        return None
    
    def _parse_data_from_text(self, text):
        """텍스트에서 수위 데이터 파싱"""
        if not text:
            return None
        
        import re
        
        # 대괄호 안의 숫자 리스트 찾기
        bracket_pattern = r'\[([^\]]+)\]'
        matches = re.findall(bracket_pattern, text)
        
        for match in matches:
            try:
                # 쉼표로 분리된 숫자들 추출
                numbers = []
                for item in match.split(','):
                    item = item.strip()
                    if item:
                        numbers.append(float(item))
                
                if numbers and len(numbers) > 3:  # 최소 4개 이상의 데이터 포인트
                    logger.info(f"텍스트에서 {len(numbers)}개 데이터 추출 성공")
                    return numbers
            except ValueError:
                continue
        
        # 일반 숫자 패턴으로 추출
        number_pattern = r'-?\d+\.?\d*'
        all_numbers = re.findall(number_pattern, text)
        
        if len(all_numbers) > 10:  # 충분한 숫자가 있는 경우
            try:
                numbers = [float(num) for num in all_numbers if 50 <= float(num) <= 150]  # 수위 범위 필터
                if len(numbers) > 3:
                    logger.info(f"텍스트에서 {len(numbers)}개 수위 데이터 추출 성공")
                    return numbers
            except ValueError:
                pass
        
        logger.warning("텍스트에서 유효한 수위 데이터를 찾을 수 없습니다")
        return None
    
    def get_current_water_level(self):
        """현재 수위 센서 값 반환 (시뮬레이션)"""
        import random
        import time
        
        # 수위 변화 시뮬레이션 (자연스러운 변화)
        change = random.uniform(-2.0, 1.0)  # 수위는 보통 감소하는 경향
        self.current_water_level += change
        
        # 수위 범위 제한 (0~100%)
        if self.current_water_level < 0:
            self.current_water_level = 0
        elif self.current_water_level > 100:
            self.current_water_level = 100
            
        return round(self.current_water_level, 1)
    
    def execute(self, action="READ_SENSOR", water_levels=None, dataPoints=None, data=None, prediction_steps=None, prediction_hours=None, time_horizon=None, **kwargs):
        """수위 센서 및 예측 실행
        
        Args:
            action: 실행할 동작 ("READ_SENSOR": 현재 수위 읽기, "PREDICT": 미래 수위 예측)
            water_levels: 과거 수위 데이터 리스트 (시계열 순서)
            dataPoints: water_levels의 별칭
            data: water_levels의 별칭
            prediction_steps: 예측할 미래 시점 개수 (기본값: 1)
            prediction_hours: 시간 기반 예측 설정
            time_horizon: 시간 범위 설정 (minutes, hours 등)
        
        Returns:
            센서 값 또는 예측 결과 딕셔너리
        """
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        if action == "READ_SENSOR":
            # 현재 수위 센서 값 반환
            current_level = self.get_current_water_level()
            return {
                "success": True,
                "current_water_level": current_level,
                "unit": "percent",
                "timestamp": current_time,
                "sensor_status": "active",
                "message": f"현재 수위: {current_level}%"
            }
        
        elif action == "PREDICT":
            # 기존 예측 로직 실행
            return self._predict_water_level(water_levels, dataPoints, data, prediction_steps, prediction_hours, time_horizon, **kwargs)
        
        else:
            return {
                "success": False,
                "error": f"지원하지 않는 액션입니다: {action}. READ_SENSOR 또는 PREDICT를 사용하세요.",
                "timestamp": current_time
            }
    
    def get_tool_config(self):
        """도구 설정 반환"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["READ_sensor", "READ", "get_level", "current"],
                            "description": "수위 센서 액션 (현재 수위 읽기)"
                        }
                    },
                    "required": []
                }
            }
        }
    
    def _predict_water_level(self, water_levels=None, dataPoints=None, data=None, prediction_steps=None, prediction_hours=None, time_horizon=None, **kwargs):
        """수위 예측 실행 (기존 로직)"""
        # 매개변수 정규화
        if water_levels is None and dataPoints is not None:
            water_levels = dataPoints
        elif water_levels is None and data is not None:
            water_levels = data
        
        # 데이터 자동 변환 및 정제
        water_levels = self._convert_and_validate_data(water_levels)
        
        # 모든 데이터가 None인 경우 사용자 질문에서 추출 시도
        if water_levels is None:
            user_query = kwargs.get('user_query')
            if user_query:
                logger.info(f"사용자 질문에서 데이터 추출 시도: {user_query[:100]}...")
                water_levels = self._parse_data_from_text(user_query)
            else:
                water_levels = self._extract_data_from_context(kwargs)
        
        # 시간 범위 처리
        if prediction_steps is None and time_horizon is not None:
            if isinstance(time_horizon, dict):
                if 'minutes' in time_horizon:
                    # 분 단위를 시간 단위로 변환 (30분 = 0.5시간)
                    prediction_steps = max(1, int(time_horizon['minutes'] / 60) or 1)
                elif 'hours' in time_horizon:
                    prediction_steps = time_horizon['hours']
                else:
                    prediction_steps = 1
            else:
                prediction_steps = 1
        elif prediction_steps is None and prediction_hours is not None:
            # prediction_hours가 딕셔너리 형태인 경우 처리
            if isinstance(prediction_hours, dict) and 'value' in prediction_hours:
                prediction_steps = prediction_hours['value']
            elif isinstance(prediction_hours, (int, float)):
                prediction_steps = int(prediction_hours)
            else:
                prediction_steps = 1
        elif prediction_steps is None:
            prediction_steps = 1
            
        logger.info(f"수위 예측 실행: {len(water_levels) if water_levels else 0}개 데이터, {prediction_steps}개 예측")
        
        try:
            if self.model is None:
                return {"error": "LSTM 모델이 로드되지 않았습니다."}
            
            # 데이터 변환 후 검증
            if water_levels is None or not isinstance(water_levels, list) or len(water_levels) == 0:
                return {"error": "수위 데이터가 유효하지 않습니다. 숫자 데이터를 입력하세요. 지원 형태: 리스트, 문자열, JSON 등"}
            
            # 데이터 품질 검증 및 정제
            water_levels = self._clean_data(water_levels)
            
            # 입력 데이터 전처리 - 고정밀 소수점 지원
            try:
                # numpy array로 변환하여 고정밀 처리
                water_array = np.array(water_levels, dtype=np.float64)
                
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
                    # 데이터가 많으면 최근 60개만 사용
                    water_array = water_array[-expected_length:]
                
                # 데이터 정규화 (입력 범위 기준)
                data_min = np.min(water_array)
                data_max = np.max(water_array)
                data_range = data_max - data_min
                
                if data_range > 0:
                    normalized_data = (water_array - data_min) / data_range
                else:
                    normalized_data = water_array
                
                input_data = normalized_data.reshape(1, -1, 1)
                logger.info(f"입력 데이터 형태: {input_data.shape}, 정규화 범위: {data_min:.6f} ~ {data_max:.6f}")
                
            except (ValueError, TypeError) as e:
                return {"error": f"수위 데이터를 숫자로 변환할 수 없습니다: {str(e)}"}
            
            # 예측 실행
            predictions = []
            current_input = input_data
            
            for step in range(prediction_steps):
                # 한 스텝 예측
                pred = self.model.predict(current_input, verbose=0)
                # 정규화된 결과를 원래 범위로 역정규화
                pred_normalized = float(pred[0, 0])
                
                if data_range > 0:
                    pred_value = pred_normalized * data_range + data_min
                else:
                    pred_value = pred_normalized
                
                predictions.append(pred_value)
                logger.debug(f"예측 스텝 {step+1}: 정규화값={pred_normalized:.6f}, 실제값={pred_value:.6f}")
                
                # 다음 예측을 위해 입력 업데이트 (슬라이딩 윈도우)
                if current_input.shape[1] > 1:
                    current_input = np.concatenate([
                        current_input[:, 1:, :],
                        pred.reshape(1, 1, 1)
                    ], axis=1)
                else:
                    current_input = pred.reshape(1, 1, 1)
            
            # 시간 정보가 포함된 결과 생성
            result = {
                "input_data": water_levels,
                "predictions": predictions,
                "prediction_steps": prediction_steps,
                "model_input_shape": list(input_data.shape),
                "data_preprocessing": {
                    "original_length": len(water_levels),
                    "processed_length": len(water_array),
                    "normalization_range": [float(data_min), float(data_max)],
                    "auto_converted": True
                }
            }
            
            # 시간 기반 예측인 경우 추가 정보 제공
            if time_horizon is not None:
                result["time_horizon"] = time_horizon
                result["time_based_prediction"] = True
                
                # 시간 정보에 따른 요약 메시지
                if isinstance(time_horizon, dict):
                    if 'minutes' in time_horizon:
                        minutes = time_horizon['minutes']
                        if len(predictions) == 1:
                            result["prediction_summary"] = f"{minutes}분 후 예상 수위: {predictions[0]:.6f}"
                        else:
                            result["prediction_summary"] = f"향후 {minutes}분 동안의 예상 수위: {[round(p, 6) for p in predictions]}"
                    elif 'hours' in time_horizon:
                        hours = time_horizon['hours']
                        if len(predictions) == 1:
                            result["prediction_summary"] = f"{hours}시간 후 예상 수위: {predictions[0]:.6f}"
                        else:
                            result["prediction_summary"] = f"향후 {hours}시간 동안의 예상 수위: {[round(p, 6) for p in predictions]}"
            elif prediction_hours is not None:
                if isinstance(prediction_hours, dict) and 'value' in prediction_hours:
                    hours = prediction_hours['value']
                else:
                    hours = prediction_hours
                result["prediction_hours"] = hours
                result["time_based_prediction"] = True
                
                # 예측 결과에 시간 정보 추가 (6자리 정밀도)
                if len(predictions) == 1:
                    result["prediction_summary"] = f"{hours}시간 후 예상 수위: {predictions[0]:.6f}"
                else:
                    result["prediction_summary"] = f"향후 {hours}시간 동안의 예상 수위: {[round(p, 6) for p in predictions]}"
            
            logger.info(f"수위 예측 완료: {predictions}")
            return result
            
        except Exception as e:
            logger.error(f"수위 예측 오류: {str(e)}")
            return {"error": f"수위 예측 중 오류가 발생했습니다: {str(e)}"}
    
    def get_model_info(self):
        """모델 정보 반환"""
        try:
            if self.model is None:
                return {"error": "모델이 로드되지 않았습니다."}
            
            return {
                "model_path": self.model_path,
                "input_shape": self.model.input_shape,
                "output_shape": self.model.output_shape,
                "total_params": self.model.count_params()
            }
        except Exception as e:
            logger.error(f"모델 정보 조회 오류: {str(e)}")
            return {"error": f"모델 정보 조회 중 오류가 발생했습니다: {str(e)}"}
    
    def get_info(self) -> Dict[str, str]:
        """도구 정보 반환"""
        return {
            "name": self.name,
            "description": self.description
        }