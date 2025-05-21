# utils/logger.py

import logging
import sys
from config import LOG_LEVEL, DEBUG_MODE

# 로그 레벨 매핑
log_levels = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

# 로거 설정
def setup_logger(name):
    """애플리케이션 로거를 설정합니다."""
    logger = logging.getLogger(name)
    level = log_levels.get(LOG_LEVEL, logging.INFO)
    logger.setLevel(level)
    
    # 핸들러가 이미 설정되어 있지 않은 경우에만 추가
    if not logger.handlers:
        # 콘솔 핸들러 추가
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger