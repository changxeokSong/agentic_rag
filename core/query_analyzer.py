# core/query_analyzer.py

from config import FUNCTION_SELECTION_PROMPT, AVAILABLE_FUNCTIONS
from utils.logger import setup_logger
import json

logger = setup_logger(__name__)

class QueryAnalyzer:
    """사용자 질의를 분석하고 적절한 도구를 선택하는 분석기"""
    
    def __init__(self, lm_studio_client):
        """질의 분석기 초기화"""
        self.lm_studio_client = lm_studio_client
        logger.info("질의 분석기 초기화")
    
    def analyze(self, query):
        """하이브리드 방식: 규칙 기반 + LLM 분석으로 도구 선택"""
        logger.info(f"하이브리드 질의 분석: {query}")

        # 0. 스몰토크/자기소개/인사 등은 도구 미사용으로 강제 처리
        if self._is_small_talk(query):
            logger.info("스몰토크로 판단됨 → 도구 미사용")
            return None
        
        # 1. 규칙 기반 빠른 판단 시도
        rule_based_result = self._rule_based_analysis(query)
        if rule_based_result:
            logger.info(f"규칙 기반 매칭 성공: {[tool['name'] for tool in rule_based_result]}")
            return rule_based_result
        
        # 2. 규칙으로 해결되지 않는 경우 LLM 사용
        logger.info("규칙 기반 매칭 실패, LLM 분석 시도")
        return self._llm_based_analysis(query)
    
    def _rule_based_analysis(self, query):
        """규칙 기반 도구 선택 - 복합 요청 지원"""
        query_lower = query.lower()
        selected_tools = []
        matched_patterns = []
        
        logger.info(f"규칙 기반 분석 시작: '{query_lower}'")
        
        # 더 정교한 키워드 패턴 매칭 - 복합 질문 특화
        rule_patterns = {
            # 파일 관련 - 다양한 표현 추가
            "파일_목록": {
                "keywords": [
                    "파일 목록", "업로드된 파일", "파일들", "파일 리스트", "업로드 목록", 
                    "파일 알려", "목록들 알려", "파일목록", "업로드파일", "파일리스트"
                ],
                "tools": [{"name": "list_files_tool", "arguments": {}}]
            },
            
            # 펌프 제어 - 자연스러운 한국어 표현 추가
            "펌프1_켜기": {
                "keywords": ["펌프1 켜", "펌프 1 켜", "pump1 on", "펌프1 가동", "펌프1 시작", "펌프1켜"],
                "tools": [{"name": "arduino_water_sensor", "arguments": {"action": "pump1_on"}}]
            },
            "펌프1_끄기": {
                "keywords": ["펌프1 꺼", "펌프 1 꺼", "pump1 off", "펌프1 정지", "펌프1 중단", "펌프1꺼"],
                "tools": [{"name": "arduino_water_sensor", "arguments": {"action": "pump1_off"}}]
            },
            "펌프2_켜기": {
                "keywords": ["펌프2 켜", "펌프 2 켜", "pump2 on", "펌프2 가동", "펌프2 시작", "펌프2켜"],
                "tools": [{"name": "arduino_water_sensor", "arguments": {"action": "pump2_on"}}]
            },
            "펌프2_끄기": {
                "keywords": [
                    "펌프2 꺼", "펌프 2 꺼", "pump2 off", "펌프2 정지", "펌프2 중단", 
                    "펌프2 꺼주", "펌프2꺼", "펌프2꺼주"
                ],
                "tools": [{"name": "arduino_water_sensor", "arguments": {"action": "pump2_off"}}]
            },
            
            # 수위 측정 - 복합적 표현 추가
            "수위_측정": {
                "keywords": [
                    "현재 수위", "수위 측정", "수위 읽어", "물 높이", "수위 확인", 
                    "수위 레벨", "수위 상태", "레벨 상태", "상태 확인", 
                    "수위레벨", "레벨상태", "상태확인"
                ],
                "tools": [{"name": "arduino_water_sensor", "arguments": {"action": "read_water_level"}}]
            },
            
            # 아두이노 연결
            "아두이노_연결": {
                "keywords": ["아두이노 연결", "아두이노 접속", "arduino connect", "아두이노 상태"],
                "tools": [{"name": "arduino_water_sensor", "arguments": {"action": "connect"}}]
            },
            
            # 수위 예측
            "수위_예측": {
                "keywords": ["수위 예측", "미래 수위", "앞으로 수위", "다음 수위", "시간 후 수위"],
                "tools": [{"name": "water_level_prediction_tool", "arguments": {}}]
            }
        }
        
        # 모든 패턴을 체크하여 매칭되는 것들을 수집
        for pattern_name, pattern_data in rule_patterns.items():
            for keyword in pattern_data["keywords"]:
                if keyword in query_lower:
                    if pattern_name not in matched_patterns:
                        logger.info(f"✓ 규칙 매칭: '{keyword}' → {pattern_name}")
                        matched_patterns.append(pattern_name)
                        selected_tools.extend(pattern_data["tools"])
                        break  # 패턴당 하나의 키워드만 매칭되면 충분
        
        # 매칭된 패턴이 있으면 반환
        if selected_tools:
            # 중복 제거 (같은 도구가 중복으로 선택될 수 있음)
            unique_tools = []
            seen_tools = set()
            
            for tool in selected_tools:
                tool_key = f"{tool['name']}_{str(tool['arguments'])}"
                if tool_key not in seen_tools:
                    unique_tools.append(tool)
                    seen_tools.add(tool_key)
            
            logger.info(f"✓ 규칙 기반 선택 완료: {len(unique_tools)}개 도구 - {[tool['name'] for tool in unique_tools]}")
            logger.info(f"✓ 매칭된 패턴들: {matched_patterns}")
            return unique_tools
        
        logger.info("✗ 규칙 기반 매칭 실패 - 매칭된 패턴 없음")
        return None
    
    def _check_complex_patterns(self, query_lower):
        """복합 패턴 체크 (여러 도구 조합) - 사용되지 않음, 메인 로직에서 처리"""
        # 이 메서드는 더 이상 사용되지 않습니다.
        # 모든 복합 패턴은 _rule_based_analysis에서 처리됩니다.
        return None
    
    def _llm_based_analysis(self, query):
        """LLM 기반 도구 선택 (복잡하거나 애매한 경우) - 복합 질문 지원"""
        logger.info(f"LLM 기반 질의 분석: {query}")
        
        # 복합 질문임을 강조하는 개선된 프롬프트
        enhanced_prompt = f"""
{FUNCTION_SELECTION_PROMPT}

**중요**: 사용자 질문에서 여러 개의 요청이 포함된 경우, 모든 요청에 대해 필요한 도구들을 배열로 반환하세요.
또한 다음과 같은 스몰토크/일반 대화/자기소개/감사/인사에는 반드시 빈 배열([])을 반환하세요.
- 예: "너는 누구니", "너 뭐야", "자기소개", "너 뭐하는 역할이야?", "안녕", "반가워", "고마워", "잘가", "어떻게 지내"

예시:
- "펌프2 꺼주고 수위 확인하고 파일 목록 알려줘" 
  → [
      {{"name": "arduino_water_sensor", "arguments": {{"action": "pump2_off"}}}},
      {{"name": "arduino_water_sensor", "arguments": {{"action": "read_water_level"}}}},
      {{"name": "list_files_tool", "arguments": {{}}}}
    ]

사용자 질문: {query}
"""
        
        logger.info(f"개선된 도구 선택 프롬프트 사용")
        
        # 함수 호출 요청
        try:
            result = self.lm_studio_client.function_call(enhanced_prompt, AVAILABLE_FUNCTIONS)
            logger.info(f"LLM 모델 원본 반환값: {result}")

            # result가 문자열(즉, JSON 문자열)일 경우 파싱 시도
            if isinstance(result, str):
                logger.info(f"LLM 문자열 결과 파싱 시도: {result}")
                try:
                    result = json.loads(result)
                    logger.info(f"LLM JSON 파싱 성공: {result}")
                except Exception as e:
                    logger.error(f"LLM 모델 반환값 JSON 파싱 오류: {e}, result: {result}")
                    return None

            # 결과 검증 및 정규화
            if isinstance(result, list):
                # 빈 배열인 경우 (도구가 필요하지 않음)
                if len(result) == 0:
                    logger.info("LLM: 도구가 필요하지 않은 일반 대화로 판단됨")
                    return None
                
                # 배열인 경우 각 항목 검증
                validated_results = []
                for item in result:
                    if isinstance(item, dict) and "name" in item and "arguments" in item:
                        validated_results.append(item)
                    else:
                        logger.warning(f"LLM 잘못된 도구 항목: {item}")
                
                if validated_results:
                    # 스몰토크로 재판단되면 방어적으로 도구 사용 취소
                    if self._is_small_talk(query):
                        logger.info("스몰토크로 재판단됨 → 도구 반환 무시")
                        return None
                    logger.info(f"✓ LLM 선택된 도구들: {[r['name'] for r in validated_results]} (총 {len(validated_results)}개)")
                    return validated_results
                else:
                    logger.warning("LLM: 유효한 도구가 없음")
                    return None
            
            elif isinstance(result, dict) and "name" in result and "arguments" in result:
                # 단일 객체인 경우 배열로 변환
                if self._is_small_talk(query):
                    logger.info("스몰토크로 재판단됨(단일 도구) → 도구 미사용")
                    return None
                logger.info(f"✓ LLM 선택된 단일 도구: {result['name']}")
                return [result]
            
            else:
                # 잘못된 형태인 경우
                logger.warning(f"LLM 모델이 올바른 도구를 반환하지 않음: {result}")
                return None
            
        except Exception as e:
            logger.error(f"LLM 도구 선택 오류: {str(e)}", exc_info=True)
            # 오류 발생 시 도구 없음으로 반환
            return None

    def _is_small_talk(self, query: str) -> bool:
        """인사/자기소개/감사 등 스몰토크 판별"""
        q = (query or "").strip().lower()
        small_talk_keywords = [
            "누구니", "누구야", "너 뭐", "자기소개", "소개해", "안녕", "반가워", "고마워", "감사", "잘가", "뭐해",
            "who are you", "introduce", "hello", "hi", "thanks", "thank you", "bye"
        ]
        return any(k in q for k in small_talk_keywords)