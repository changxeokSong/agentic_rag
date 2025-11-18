# models/lm_studio.py

import json
import os
import sys
import re
from openai import OpenAI

from config import (
    LM_STUDIO_BASE_URL,
    LM_STUDIO_API_KEY,
    LM_STUDIO_MODEL_NAME,
    TOOL_SELECTION_TEMPERATURE,
    RESPONSE_TEMPERATURE,
    MAX_TOKENS,
    REQUEST_TIMEOUT,
)
from utils.logger import setup_logger
from utils.helpers import retry

# 프로젝트 루트를 우선 탐색하도록 sys.path 조정
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logger = setup_logger(__name__)


class LMStudioClient:
    """LM Studio API 클라이언트 (스트리밍 지원)"""

    def __init__(self, base_url=None, api_key=None, model_name=None):
        self.base_url = base_url or LM_STUDIO_BASE_URL
        self.api_key = api_key or LM_STUDIO_API_KEY
        self.model = model_name or LM_STUDIO_MODEL_NAME

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=REQUEST_TIMEOUT,
        )

        logger.info(f"LM Studio 클라이언트 초기화: {self.model}, URL: {self.base_url}")

    @retry(max_retries=3)
    def generate_response(self, prompt, temperature=None, stream=True):
        """일반 응답 생성 (스트리밍 지원)"""
        if temperature is None:
            temperature = RESPONSE_TEMPERATURE

        logger.info(f"LM Studio 응답 생성, 온도: {temperature}, 스트리밍: {stream}")
        try:
            if stream:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=MAX_TOKENS,
                    timeout=REQUEST_TIMEOUT,
                    stream=True,
                )

                def response_generator():
                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content

                return response_generator()
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=MAX_TOKENS,
                    timeout=REQUEST_TIMEOUT,
                )
                return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LM Studio 응답 생성 오류: {str(e)}")
            raise

    @retry(max_retries=3)
    def function_call(self, prompt, functions, temperature=None):
        """
        도구/함수 호출 생성:
        1) tools + tool_choice=auto (Qwen 등 신형)
        2) 실패 시 functions + function_call=auto
        3) 그래도 없으면 텍스트(JSON) 파싱
        """
        if temperature is None:
            temperature = TOOL_SELECTION_TEMPERATURE

        tool_selection_max_tokens = 128  # 도구 선택 결과만 필요

        logger.info(f"LM Studio 도구 선택, 온도: {temperature}, max_tokens: {tool_selection_max_tokens}")
        try:
            # 1) 신형 tools API
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    tools=[{"type": "function", "function": f} for f in functions],
                    tool_choice="auto",
                    temperature=temperature,
                    max_tokens=tool_selection_max_tokens,
                    timeout=REQUEST_TIMEOUT,
                )

                message = response.choices[0].message

                if getattr(message, "tool_calls", None):
                    call = message.tool_calls[0]
                    function_name = call.function.name
                    try:
                        function_args = json.loads(call.function.arguments)
                    except json.JSONDecodeError:
                        logger.error(f"도구 인자 파싱 실패: {call.function.arguments}")
                        function_args = {}
                    return {"name": function_name, "arguments": function_args}

                content = getattr(message, "content", None)
                if content:
                    return self._parse_text_response(content)

            except Exception as tools_error:
                logger.warning(f"tools API 실패, functions로 폴백: {tools_error}")

                # 2) 구 functions API 폴백
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    functions=functions,
                    function_call="auto",
                    temperature=temperature,
                    max_tokens=tool_selection_max_tokens,
                    timeout=REQUEST_TIMEOUT,
                )

                message = response.choices[0].message

                if getattr(message, "function_call", None):
                    function_name = message.function_call.name
                    try:
                        function_args = json.loads(message.function_call.arguments)
                    except json.JSONDecodeError:
                        logger.error(f"함수 인자 파싱 실패: {message.function_call.arguments}")
                        function_args = {}

                    return {"name": function_name, "arguments": function_args}

                content = getattr(message, "content", None)
                if content:
                    return self._parse_text_response(content)

            return None

        except Exception as e:
            logger.error(f"LM Studio 도구 선택 오류: {str(e)}", exc_info=True)
            raise

    def _parse_text_response(self, content):
        """텍스트 응답에서 JSON을 파싱한다."""
        try:
            # Markdown 코드 블록 제거
            if content.strip().startswith("```json"):
                content = content.strip()[len("```json") :].strip()
                if content.endswith("```"):
                    content = content[: -len("```")].strip()
            elif content.strip().startswith("```"):
                lines = content.strip().split("\n")
                if len(lines) > 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
                    content = "\n".join(lines[1:-1])

            try:
                result = json.loads(content)
                if (isinstance(result, dict) and "name" in result and "arguments" in result) or isinstance(
                    result, list
                ):
                    logger.info(f"JSON 파싱 성공: {result}")
                    return result
            except json.JSONDecodeError:
                return self._parse_with_regex(content)

        except Exception as e:
            logger.error(f"텍스트 응답 파싱 오류: {e}, content: {content}")

        return None

    def _parse_with_regex(self, content):
        """정규표현식으로 함수 호출 정보 추출"""
        try:
            array_match = re.search(r"\[([^\]]+)\]", content)
            if array_match:
                array_content = "[" + array_match.group(1) + "]"
                try:
                    result = json.loads(array_content)
                    if isinstance(result, list):
                        logger.info(f"배열 정규식 파싱 성공: {result}")
                        return result
                except Exception:
                    pass

            name_match = re.search(r'"name":\s*"([^"]+)"', content)
            args_match = re.search(r'"arguments":\s*({[^}]*})', content)

            if name_match:
                tool_name = name_match.group(1)
                arguments = {}
                if args_match:
                    try:
                        arguments = json.loads(args_match.group(1))
                    except Exception:
                        arg_matches = re.findall(r'"([^"]+)":\s*"([^"]*)"', args_match.group(1))
                        arguments = dict(arg_matches)

                if not arguments:
                    for arg_name in ["expression", "query", "location", "action", "pump_id"]:
                        arg_match = re.search(f'"{arg_name}":\\s*"([^"]*)"', content)
                        if arg_match:
                            arguments[arg_name] = arg_match.group(1)

                logger.info(f"단일 객체 정규식 파싱 성공: {tool_name}, {arguments}")
                return [{"name": tool_name, "arguments": arguments}]

        except Exception as e:
            logger.error(f"정규식 파싱 오류: {e}")

        return None

    def get_model_info(self):
        """모델 정보 반환"""
        return {
            "model": self.model,
            "base_url": self.base_url,
            "api_available": self._check_api_available(),
        }

    def _check_api_available(self):
        """API 연결 가능 여부 확인"""
        try:
            self.client.models.list()
            return True
        except Exception:
            return False
