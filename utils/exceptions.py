"""커스텀 예외 클래스 정의

이 모듈은 프로젝트 전체에서 사용되는 커스텀 예외 클래스들을 정의합니다.
"""

from typing import Optional, Any, Dict


class AgenticRAGException(Exception):
    """AgenticRAG 시스템의 기본 예외 클래스"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (상세: {self.details})"
        return self.message


class ConfigurationError(AgenticRAGException):
    """설정 관련 오류"""
    pass


class DatabaseError(AgenticRAGException):
    """데이터베이스 관련 오류"""
    pass


class ConnectionError(AgenticRAGException):
    """연결 관련 오류"""
    pass


class EmbeddingError(AgenticRAGException):
    """임베딩 생성 관련 오류"""
    pass


class ToolExecutionError(AgenticRAGException):
    """도구 실행 관련 오류"""
    pass


class ArduinoConnectionError(ConnectionError):
    """Arduino 연결 오류"""
    pass


class WaterLevelError(AgenticRAGException):
    """수위 관련 오류"""
    pass


class ValidationError(AgenticRAGException):
    """데이터 검증 오류"""
    pass


class FileProcessingError(AgenticRAGException):
    """파일 처리 관련 오류"""
    pass


class AutomationError(AgenticRAGException):
    """자동화 시스템 오류"""
    pass


class LLMError(AgenticRAGException):
    """LLM 관련 오류"""
    pass


class TimeoutError(AgenticRAGException):
    """타임아웃 오류"""
    pass
