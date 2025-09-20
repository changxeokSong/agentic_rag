# services/decision_engine.py - AI 기반 의사결정 엔진

from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from tools.water_level_monitoring_tool import WaterLevelMonitor
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ActionType(Enum):
    PUMP_ON = "PUMP_ON"
    PUMP_OFF = "PUMP_OFF"
    MAINTAIN = "MAINTAIN"
    EMERGENCY_ALL_ON = "EMERGENCY_ALL_ON"
    ALERT_ONLY = "ALERT_ONLY"

class UrgencyLevel(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5

@dataclass
class Decision:
    reservoir_id: str
    action: ActionType
    target_pumps: List[str]
    confidence: float  # 0-1
    urgency: UrgencyLevel
    reasoning: str
    predicted_outcome: Dict[str, Any]
    estimated_time_to_effect: int  # seconds

@dataclass
class PredictionData:
    current_trend: str  # "rising", "falling", "stable"
    predicted_level_30min: float
    predicted_level_1hour: float
    confidence: float

class IntelligentDecisionEngine:
    """AI 기반 지능형 의사결정 엔진"""
    
    def __init__(self):
        self.water_monitor = WaterLevelMonitor()
        
        # 학습 데이터 저장소
        self.historical_patterns = {}
        self.pump_efficiency_data = {}
        
        # 고급 규칙 설정
        self.advanced_rules = {
            # 시간대별 기준값 조정
            "time_based_thresholds": {
                "peak_hours": {  # 오전 7-9시, 오후 6-8시
                    "times": [(7, 9), (18, 20)],
                    "threshold_multiplier": 1.2  # 20% 더 엄격
                },
                "low_usage": {  # 밤 12-5시
                    "times": [(0, 5)],
                    "threshold_multiplier": 0.8  # 20% 더 관대
                }
            },
            # 날씨 기반 조정 (확장 가능)
            "weather_adjustments": {
                "rainy_day_multiplier": 1.3,
                "hot_day_multiplier": 1.1
            },
            # 펌프 효율성 고려
            "pump_performance": {
                "min_operation_time": 300,  # 5분 최소 가동
                "max_continuous_time": 3600,  # 1시간 최대 연속 가동
                "cooldown_between_cycles": 180  # 3분 쿨다운
            }
        }

    def make_decision(self, reservoir_data: Dict[str, Any], historical_context: List[Dict] = None) -> Decision:
        """종합적인 의사결정 수행"""
        try:
            reservoir_id = reservoir_data.get('reservoir_id', '')
            current_level = reservoir_data.get('current_level', 0)
            pump_statuses = reservoir_data.get('pump_statuses', {})
            
            # 1. 현재 상황 분석
            situation_analysis = self._analyze_situation(reservoir_data, historical_context)
            
            # 2. 미래 예측
            prediction = self._predict_water_level(reservoir_id, current_level, historical_context)
            
            # 3. 최적 행동 결정
            decision = self._determine_optimal_action(
                reservoir_data, situation_analysis, prediction
            )
            
            logger.info(f"[{reservoir_id}] 의사결정 완료: {decision.action.value} "
                       f"(신뢰도: {decision.confidence:.2f}, 긴급도: {decision.urgency.name})")
            
            return decision
            
        except Exception as e:
            logger.error(f"의사결정 중 오류: {e}")
            # 안전한 기본 결정 반환
            return Decision(
                reservoir_id=reservoir_data.get('reservoir_id', 'unknown'),
                action=ActionType.MAINTAIN,
                target_pumps=[],
                confidence=0.5,
                urgency=UrgencyLevel.LOW,
                reasoning="오류로 인한 기본 결정",
                predicted_outcome={},
                estimated_time_to_effect=0
            )

    def _analyze_situation(self, reservoir_data: Dict[str, Any], historical_context: List[Dict] = None) -> Dict[str, Any]:
        """현재 상황 종합 분석"""
        reservoir_id = reservoir_data.get('reservoir_id', '')
        current_level = reservoir_data.get('current_level', 0)
        pump_statuses = reservoir_data.get('pump_statuses', {})
        
        analysis = {
            "current_risk_level": self._calculate_risk_level(current_level),
            "time_adjusted_threshold": self._get_time_adjusted_threshold(current_level),
            "pump_status_analysis": self._analyze_pump_status(pump_statuses),
            "trend_analysis": self._analyze_trend(reservoir_id, historical_context),
            "efficiency_score": self._calculate_system_efficiency(reservoir_id)
        }
        
        return analysis

    def _calculate_risk_level(self, water_level: float) -> Dict[str, Any]:
        """위험도 계산"""
        if water_level >= 120:
            risk_level = "EMERGENCY"
            risk_score = 1.0
        elif water_level >= 100:
            risk_level = "CRITICAL" 
            risk_score = 0.8
        elif water_level >= 80:
            risk_level = "HIGH"
            risk_score = 0.6
        elif water_level >= 60:
            risk_level = "MEDIUM"
            risk_score = 0.4
        else:
            risk_level = "LOW"
            risk_score = 0.2
            
        return {
            "level": risk_level,
            "score": risk_score,
            "description": f"수위 {water_level}cm - {risk_level} 위험도"
        }

    def _get_time_adjusted_threshold(self, current_level: float) -> Dict[str, float]:
        """시간대별 임계값 조정"""
        current_hour = datetime.now().hour
        base_thresholds = {
            "emergency": 120,
            "critical": 100,
            "warning": 80,
            "normal": 60
        }
        
        multiplier = 1.0
        
        # 피크 시간대 조정
        for start_hour, end_hour in self.advanced_rules["time_based_thresholds"]["peak_hours"]["times"]:
            if start_hour <= current_hour <= end_hour:
                multiplier = self.advanced_rules["time_based_thresholds"]["peak_hours"]["threshold_multiplier"]
                break
        
        # 사용량 적은 시간대 조정
        for start_hour, end_hour in self.advanced_rules["time_based_thresholds"]["low_usage"]["times"]:
            if start_hour <= current_hour <= end_hour:
                multiplier = self.advanced_rules["time_based_thresholds"]["low_usage"]["threshold_multiplier"]
                break
        
        adjusted_thresholds = {
            key: value * multiplier 
            for key, value in base_thresholds.items()
        }
        
        return adjusted_thresholds

    def _analyze_pump_status(self, pump_statuses: Dict[str, bool]) -> Dict[str, Any]:
        """펌프 상태 분석"""
        active_pumps = [name for name, active in pump_statuses.items() if active]
        total_pumps = len(pump_statuses)
        active_count = len(active_pumps)
        
        utilization_rate = active_count / total_pumps if total_pumps > 0 else 0
        
        return {
            "active_pumps": active_pumps,
            "active_count": active_count,
            "total_count": total_pumps,
            "utilization_rate": utilization_rate,
            "can_increase": active_count < total_pumps,
            "can_decrease": active_count > 0
        }

    def _analyze_trend(self, reservoir_id: str, historical_context: List[Dict] = None) -> Dict[str, Any]:
        """수위 변화 트렌드 분석"""
        if not historical_context or len(historical_context) < 2:
            return {
                "trend": "unknown",
                "rate_of_change": 0,
                "confidence": 0.0
            }
        
        # 최근 데이터 포인트들의 수위 변화 분석
        recent_levels = [point.get('current_level', 0) for point in historical_context[-5:]]
        
        if len(recent_levels) >= 2:
            # 간단한 차이 기반 트렌드 계산
            first_level = recent_levels[0]
            last_level = recent_levels[-1]
            diff = last_level - first_level
            rate_of_change = diff / len(recent_levels)
                
            if abs(rate_of_change) < 0.5:
                trend = "stable"
            elif rate_of_change > 0:
                trend = "rising"
            else:
                trend = "falling"
            
            confidence = min(1.0, abs(rate_of_change) / 10.0)  # 기울기에 따른 신뢰도
            
            return {
                "trend": trend,
                "rate_of_change": rate_of_change,
                "confidence": confidence
            }
        
        return {
            "trend": "unknown",
            "rate_of_change": 0,
            "confidence": 0.0
        }

    def _calculate_system_efficiency(self, reservoir_id: str) -> float:
        """시스템 효율성 점수"""
        # 여기서는 간단한 기본 점수 반환
        # 실제로는 과거 펌프 가동 이력과 수위 변화 데이터를 분석하여 계산
        return 0.8  # 임시 값

    def _predict_water_level(self, reservoir_id: str, current_level: float, historical_context: List[Dict] = None) -> PredictionData:
        """수위 변화 예측"""
        if not historical_context:
            # 기본 예측 (변화 없음)
            return PredictionData(
                current_trend="stable",
                predicted_level_30min=current_level,
                predicted_level_1hour=current_level,
                confidence=0.5
            )
        
        trend_analysis = self._analyze_trend(reservoir_id, historical_context)
        rate_of_change = trend_analysis.get("rate_of_change", 0)
        
        # 30분, 1시간 후 예측 (단순 선형 외삽)
        predicted_30min = current_level + (rate_of_change * 6)  # 5분 간격 * 6 = 30분
        predicted_1hour = current_level + (rate_of_change * 12)  # 5분 간격 * 12 = 1시간
        
        return PredictionData(
            current_trend=trend_analysis.get("trend", "unknown"),
            predicted_level_30min=max(0, predicted_30min),
            predicted_level_1hour=max(0, predicted_1hour),
            confidence=trend_analysis.get("confidence", 0.5)
        )

    def _determine_optimal_action(self, reservoir_data: Dict[str, Any], situation_analysis: Dict, prediction: PredictionData) -> Decision:
        """최적 행동 결정"""
        reservoir_id = reservoir_data.get('reservoir_id', '')
        current_level = reservoir_data.get('current_level', 0)
        pump_statuses = reservoir_data.get('pump_statuses', {})
        
        risk_info = situation_analysis["current_risk_level"]
        thresholds = situation_analysis["time_adjusted_threshold"]
        pump_analysis = situation_analysis["pump_status_analysis"]
        
        # 펌프 목록
        available_pumps = list(pump_statuses.keys())
        active_pumps = pump_analysis["active_pumps"]
        
        # 긴급 상황 처리
        if current_level >= thresholds["emergency"] or prediction.predicted_level_30min >= thresholds["emergency"]:
            return Decision(
                reservoir_id=reservoir_id,
                action=ActionType.EMERGENCY_ALL_ON,
                target_pumps=available_pumps,
                confidence=0.95,
                urgency=UrgencyLevel.EMERGENCY,
                reasoning=f"긴급 상황: 현재 {current_level}cm, 30분 후 예상 {prediction.predicted_level_30min:.1f}cm",
                predicted_outcome={"expected_level_reduction": 15, "time_to_safe_level": 900},
                estimated_time_to_effect=60
            )
        
        # 위험 상황
        if current_level >= thresholds["critical"]:
            confidence = 0.85
            if prediction.current_trend == "rising":
                # 상승 중이면 더 많은 펌프 가동
                target_pumps = available_pumps[:min(2, len(available_pumps))]
                reasoning = f"위험 상황에서 수위 상승 중: {current_level}cm → {prediction.predicted_level_30min:.1f}cm"
            else:
                # 안정/하강이면 1-2개 펌프로 충분
                needed_pumps = 1 if len(active_pumps) == 0 else min(2, len(available_pumps))
                target_pumps = available_pumps[:needed_pumps]
                reasoning = f"위험 상황이지만 수위 안정화 중: {current_level}cm"
            
            return Decision(
                reservoir_id=reservoir_id,
                action=ActionType.PUMP_ON,
                target_pumps=target_pumps,
                confidence=confidence,
                urgency=UrgencyLevel.CRITICAL,
                reasoning=reasoning,
                predicted_outcome={"expected_level_reduction": 10, "time_to_safe_level": 1200},
                estimated_time_to_effect=120
            )
        
        # 주의 상황
        if current_level >= thresholds["warning"]:
            # 예측을 고려한 정교한 제어
            if prediction.current_trend == "rising" and prediction.predicted_level_30min >= thresholds["critical"]:
                # 곧 위험해질 것으로 예상되면 선제적 대응
                return Decision(
                    reservoir_id=reservoir_id,
                    action=ActionType.PUMP_ON,
                    target_pumps=available_pumps[:2],
                    confidence=0.8,
                    urgency=UrgencyLevel.HIGH,
                    reasoning=f"선제적 대응: 30분 후 위험 수위 예상 ({prediction.predicted_level_30min:.1f}cm)",
                    predicted_outcome={"expected_level_reduction": 8, "time_to_safe_level": 1500},
                    estimated_time_to_effect=180
                )
            elif prediction.current_trend == "stable" or prediction.current_trend == "falling":
                # 안정적이면 최소한의 펌프만 가동
                target_pump = available_pumps[:1]
                return Decision(
                    reservoir_id=reservoir_id,
                    action=ActionType.PUMP_ON,
                    target_pumps=target_pump,
                    confidence=0.7,
                    urgency=UrgencyLevel.MEDIUM,
                    reasoning=f"주의 수위에서 안정화 제어: {current_level}cm",
                    predicted_outcome={"expected_level_reduction": 5, "time_to_safe_level": 1800},
                    estimated_time_to_effect=240
                )
        
        # 정상 범위
        if current_level < thresholds["normal"]:
            if len(active_pumps) > 0:
                # 불필요한 펌프 중단
                return Decision(
                    reservoir_id=reservoir_id,
                    action=ActionType.PUMP_OFF,
                    target_pumps=active_pumps,
                    confidence=0.9,
                    urgency=UrgencyLevel.LOW,
                    reasoning=f"정상 수위로 펌프 중단: {current_level}cm < {thresholds['normal']}cm",
                    predicted_outcome={"energy_saved": True, "maintained_safe_level": True},
                    estimated_time_to_effect=30
                )
            else:
                # 현상 유지
                return Decision(
                    reservoir_id=reservoir_id,
                    action=ActionType.MAINTAIN,
                    target_pumps=[],
                    confidence=0.95,
                    urgency=UrgencyLevel.LOW,
                    reasoning=f"정상 수위 유지: {current_level}cm",
                    predicted_outcome={"status": "optimal"},
                    estimated_time_to_effect=0
                )
        
        # 기본 현상 유지
        return Decision(
            reservoir_id=reservoir_id,
            action=ActionType.MAINTAIN,
            target_pumps=[],
            confidence=0.6,
            urgency=UrgencyLevel.LOW,
            reasoning="현상 유지",
            predicted_outcome={"status": "maintain"},
            estimated_time_to_effect=0
        )

    def evaluate_decision_outcome(self, decision: Decision, actual_outcome: Dict[str, Any]) -> Dict[str, Any]:
        """의사결정 결과 평가 및 학습"""
        try:
            # 예측과 실제 결과 비교
            predicted = decision.predicted_outcome
            actual = actual_outcome
            
            evaluation = {
                "decision_id": f"{decision.reservoir_id}_{decision.action.value}_{int(decision.estimated_time_to_effect)}",
                "accuracy_score": self._calculate_accuracy(predicted, actual),
                "effectiveness_score": self._calculate_effectiveness(decision, actual),
                "lessons_learned": []
            }
            
            # 학습 데이터 업데이트
            self._update_learning_data(decision, actual_outcome, evaluation)
            
            return evaluation
            
        except Exception as e:
            logger.error(f"의사결정 평가 중 오류: {e}")
            return {"error": str(e)}

    def _calculate_accuracy(self, predicted: Dict, actual: Dict) -> float:
        """예측 정확도 계산"""
        # 간단한 정확도 계산 로직
        return 0.8  # 임시값

    def _calculate_effectiveness(self, decision: Decision, actual_outcome: Dict) -> float:
        """의사결정 효과성 계산"""
        # 효과성 평가 로직
        return 0.85  # 임시값

    def _update_learning_data(self, decision: Decision, actual_outcome: Dict, evaluation: Dict):
        """학습 데이터 업데이트"""
        reservoir_id = decision.reservoir_id
        
        if reservoir_id not in self.historical_patterns:
            self.historical_patterns[reservoir_id] = []
        
        learning_record = {
            "timestamp": datetime.now().isoformat(),
            "decision": {
                "action": decision.action.value,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning
            },
            "outcome": actual_outcome,
            "evaluation": evaluation
        }
        
        self.historical_patterns[reservoir_id].append(learning_record)
        
        # 최근 100개 기록만 유지
        if len(self.historical_patterns[reservoir_id]) > 100:
            self.historical_patterns[reservoir_id] = self.historical_patterns[reservoir_id][-100:]

    def get_learning_summary(self, reservoir_id: str = None) -> Dict[str, Any]:
        """학습 현황 요약"""
        if reservoir_id:
            patterns = self.historical_patterns.get(reservoir_id, [])
        else:
            patterns = []
            for reservoir_patterns in self.historical_patterns.values():
                patterns.extend(reservoir_patterns)
        
        if not patterns:
            return {"message": "학습 데이터 없음"}
        
        # 기본 통계
        total_decisions = len(patterns)
        successful_decisions = len([p for p in patterns if p.get("evaluation", {}).get("effectiveness_score", 0) > 0.7])
        success_rate = successful_decisions / total_decisions if total_decisions > 0 else 0
        
        return {
            "total_decisions": total_decisions,
            "successful_decisions": successful_decisions,
            "success_rate": success_rate,
            "learning_period": f"{len(self.historical_patterns)} 배수지",
            "latest_update": patterns[-1]["timestamp"] if patterns else "없음"
        }