# models/lm_studio.py

import json
import os
import sys
import re
from openai import OpenAI

# cv2 패키지와의 config.py 충돌 방지 - 프로젝트 루트를 우선 검색
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import (
    LM_STUDIO_BASE_URL,
    LM_STUDIO_API_KEY,
    LM_STUDIO_MODEL_NAME,
    TOOL_SELECTION_TEMPERATURE,
    RESPONSE_TEMPERATURE,
    MAX_TOKENS,
    REQUEST_TIMEOUT
)
from utils.logger import setup_logger
from utils.helpers import retry

logger = setup_logger(__name__)

class LMStudioClient:
    """LM Studio API와 상호작용하는 클라이언트 (스트리밍 지원)"""

    def __init__(self, base_url=None, api_key=None, model_name=None):
        """
        LM Studio 클라이언트를 초기화합니다.

        Args:
            base_url (str, optional): API 기본 URL. 기본값은 환경변수에서 가져옵니다.
            api_key (str, optional): API 키. 기본값은 환경변수에서 가져옵니다.
            model_name (str, optional): 모델 이름. 기본값은 환경변수에서 가져옵니다.
        """
        self.base_url = base_url or LM_STUDIO_BASE_URL
        self.api_key = api_key or LM_STUDIO_API_KEY
        self.model = model_name or LM_STUDIO_MODEL_NAME

        # API 클라이언트 초기화 (타임아웃 설정)
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=REQUEST_TIMEOUT
        )

        logger.info(f"LM Studio 클라이언트 초기화: {self.model}, URL: {self.base_url}")
    
    @retry(max_retries=3)
    def generate_response(self, prompt, temperature=None, stream=True):
        """
        LM Studio 모델을 사용하여 응답을 생성합니다.

        Args:
            prompt (str): 모델에 전달할 프롬프트
            temperature (float, optional): 응답의 온도(창의성). 기본값은 환경변수에서 가져옵니다.
            stream (bool, optional): 스트리밍 사용 여부. 기본값은 True (성능 개선).

        Returns:
            Generator or str: 스트리밍 모드면 generator, 아니면 문자열
        """
        if temperature is None:
            temperature = RESPONSE_TEMPERATURE

        logger.info(f"LM Studio 응답 생성, 온도: {temperature}, 스트리밍: {stream}")
        try:
            if stream:
                # 스트리밍 모드: generator 반환
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=MAX_TOKENS,
                    timeout=REQUEST_TIMEOUT,
                    stream=True
                )

                # generator로 반환
                def response_generator():
                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content

                return response_generator()
            else:
                # 기존 방식
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=MAX_TOKENS,
                    timeout=REQUEST_TIMEOUT
                )
                return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LM Studio 응답 생성 오류: {str(e)}")
            raise
    
    @retry(max_retries=3)
    def function_call(self, prompt, functions, temperature=None):
        """
        LM Studio 모델을 사용하여 함수 호출을 실행합니다.
        텍스트 기반 도구 선택 방식을 사용합니다.

        Args:
            prompt (str): 모델에 전달할 프롬프트
            functions (list): 사용 가능한 함수 정의 목록
            temperature (float, optional): 응답의 온도(창의성). 기본값은 환경변수에서 가져옵니다.

        Returns:
            dict or None: 함수 호출 정보 (이름과 인자) 또는 함수 호출이 없는 경우 None
        """
        if temperature is None:
            temperature = TOOL_SELECTION_TEMPERATURE

        # 도구 선택은 짧은 JSON만 필요하므로 토큰 제한을 최소화
        tool_selection_max_tokens = 128

        logger.info(f"LM Studio 텍스트 기반 도구 선택, 온도: {temperature}, max_tokens: {tool_selection_max_tokens}")
        try:
            # 기존 OpenAI functions API 시도
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    functions=functions,
                    function_call="auto",
                    temperature=temperature,
                    max_tokens=tool_selection_max_tokens,
                    timeout=REQUEST_TIMEOUT
                )
                
                message = response.choices[0].message
                
                # 함수 호출 정보 추출 (기존 방식)
                if hasattr(message, 'function_call') and message.function_call is not None:
                    function_name = message.function_call.name
                    try:
                        function_args = json.loads(message.function_call.arguments)
                    except json.JSONDecodeError:
                        logger.error(f"함수 인자 파싱 오류: {message.function_call.arguments}")
                        function_args = {}
                    
                    return {
                        "name": function_name,
                        "arguments": function_args
                    }
                
                # 함수 호출이 없는 경우: content에 JSON 문자열이 있을 수 있음
                content = getattr(message, 'content', None)
                if content:
                    return self._parse_text_response(content)
                    
            except Exception as api_error:
                logger.warning(f"OpenAI functions API 실패, 텍스트 모드로 전환: {api_error}")
                
                # 텍스트 기반 방식으로 폴백
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=tool_selection_max_tokens,
                    timeout=REQUEST_TIMEOUT
                )
                
                content = response.choices[0].message.content
                if content:
                    return self._parse_text_response(content)
            
            return None
            
        except Exception as e:
            logger.error(f"LM Studio 도구 선택 오류: {str(e)}")
            raise
    
    def _parse_text_response(self, content):
        """텍스트 응답에서 JSON을 파싱합니다."""
        try:
            # Markdown 코드 블록 제거
            if content.strip().startswith('```json'):
                content = content.strip()[len('```json'):].strip()
                if content.endswith('```'):
                    content = content[:-len('```')].strip()
            elif content.strip().startswith('```'):
                # 일반적인 코드 블록 제거
                lines = content.strip().split('\n')
                if len(lines) > 2 and lines[0].startswith('```') and lines[-1].strip() == '```':
                    content = '\n'.join(lines[1:-1])

            # JSON 파싱 시도
            try:
                result = json.loads(content)
                # dict(단일 도구) 또는 list(여러 도구) 모두 허용
                if (isinstance(result, dict) and 'name' in result and 'arguments' in result) or isinstance(result, list):
                    logger.info(f"JSON 파싱 성공: {result}")
                    return result
            except json.JSONDecodeError:
                # JSON이 아닌 경우 정규식으로 파싱 시도
                return self._parse_with_regex(content)
                
        except Exception as e:
            logger.error(f"텍스트 응답 파싱 오류: {e}, content: {content}")
        
        return None
    
    def _parse_with_regex(self, content):
        """정규식을 사용하여 도구 호출 정보를 추출합니다."""
        try:
            # 배열 형태 파싱 시도
            array_match = re.search(r'\[([^\]]+)\]', content)
            if array_match:
                array_content = '[' + array_match.group(1) + ']'
                try:
                    result = json.loads(array_content)
                    if isinstance(result, list):
                        logger.info(f"배열 정규식 파싱 성공: {result}")
                        return result
                except:
                    pass
            
            # 단일 객체 파싱
            name_match = re.search(r'"name":\s*"([^"]+)"', content)
            args_match = re.search(r'"arguments":\s*({[^}]*})', content)
            
            if name_match:
                tool_name = name_match.group(1)
                
                # arguments 파싱
                arguments = {}
                if args_match:
                    try:
                        arguments = json.loads(args_match.group(1))
                    except:
                        # 간단한 key-value 파싱
                        arg_matches = re.findall(r'"([^"]+)":\s*"([^"]*)"', args_match.group(1))
                        arguments = dict(arg_matches)
                
                # 간단한 인자 파싱 (expression, query, location 등)
                if not arguments:
                    for arg_name in ['expression', 'query', 'location', 'action', 'pump_id']:
                        arg_match = re.search(f'"{arg_name}":\\s*"([^"]*)"', content)
                        if arg_match:
                            arguments[arg_name] = arg_match.group(1)
                
                logger.info(f"단일 객체 정규식 파싱 성공: {tool_name}, {arguments}")
                return [{
                    "name": tool_name,
                    "arguments": arguments
                }]
                
        except Exception as e:
            logger.error(f"정규식 파싱 오류: {e}")
        
        return None
            
    def get_model_info(self):
        """모델 정보 반환"""
        return {
            "model": self.model,
            "base_url": self.base_url,
            "api_available": self._check_api_available()
        }
    
    def _check_api_available(self):
        """API 사용 가능 여부 확인"""
        try:
            self.client.models.list()
            return True
        except Exception:
            return False