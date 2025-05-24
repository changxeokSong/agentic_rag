# tools/calculator_tool.py

import math
import re
from tools.base_tool import BaseTool
from utils.logger import setup_logger

logger = setup_logger(__name__)

class CalculatorTool(BaseTool):
    """계산 도구"""
    
    def __init__(self):
        """계산 도구 초기화"""
        super().__init__(
            name="calculator_tool",
            description="수학 계산, 단위 변환, 공식 계산 등 수치 연산이 필요할 때 사용합니다."
        )
    
    def execute(self, expression):
        """수학 표현식 계산"""
        logger.info(f"계산 실행: {expression}")
        try:
            # 안전한 표현식 검증 (안전하지 않은 함수 호출 방지)
            if not self._is_safe_expression(expression):
                return {"error": "안전하지 않은 표현식입니다. 기본 수학 연산, sqrt, sin, cos, tan, log, pi, e 등만 허용됩니다."}
            
            # 계산 실행
            result = self._safe_eval(expression)
            if isinstance(result, float):
                result = round(result, 6)
            return {"expression": expression, "result": result}
        except Exception as e:
            logger.error(f"계산 오류: {str(e)}")
            return {"error": f"계산 중 오류가 발생했습니다: {str(e)}"}
    
    def _is_safe_expression(self, expression):
        """표현식이 안전한지 확인 (코드 실행 방지)"""
        # 허용되는 문자 및 함수만 포함하는지 확인
        if not re.match(r'^[\d\s\+\-\*\/\(\)\.,\^%√πeE]+|sqrt|sin|cos|tan|log|abs|max|min|round|math|pi|e', expression):
            return False
        
        # 금지된 키워드 확인
        forbidden = ['import', 'exec', 'eval', 'compile', 'open', '__']
        for word in forbidden:
            if word in expression:
                return False
        
        return True
    
    def _safe_eval(self, expression):
        """안전한 계산 수행"""
        # 연산자 및 함수 치환
        expression = expression.replace('^', '**')  # 제곱
        expression = expression.replace('√', 'math.sqrt')  # 제곱근
        expression = expression.replace('π', 'math.pi')  # 파이
        expression = expression.replace('PI', 'math.pi')
        expression = expression.replace('E', 'math.e')
        # sqrt, sin, cos, tan, log 등 함수 지원
        safe_dict = {
            'abs': abs,
            'max': max,
            'min': min,
            'round': round,
            'math': math,
            'sqrt': math.sqrt,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'log': math.log,
            'pi': math.pi,
            'e': math.e
        }
        return eval(expression, {"__builtins__": {}}, safe_dict)