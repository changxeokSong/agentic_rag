# tools/base_tool.py

from abc import ABC, abstractmethod
from utils.logger import setup_logger

logger = setup_logger(__name__)

class BaseTool(ABC):
    """모든 도구의 기본 클래스"""
    
    def __init__(self, name, description):
        """기본 도구 초기화"""
        self.name = name
        self.description = description
        logger.info(f"도구 초기화: {name}")
    
    @abstractmethod
    def execute(self, **kwargs):
        """도구 실행 (하위 클래스에서 구현)"""
        pass
    
    def to_dict(self):
        """도구를 사전으로 변환"""
        return {
            "name": self.name,
            "description": self.description
        }
    
    def __str__(self):
        return f"{self.name}: {self.description}"