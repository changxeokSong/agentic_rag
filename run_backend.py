import os
import signal
import sys
import time
from utils.logger import setup_logger

logger = setup_logger(__name__)

# 글로벌 변수로 서비스 관리
water_logger_service = None

def signal_handler(sig, frame):
    """시그널 핸들러 - 서비스 종료"""
    global water_logger_service
    logger.info("\n[Backend] 종료 시그널 수신...")

    if water_logger_service:
        water_logger_service.stop()

    logger.info("[Backend] 서비스 종료 완료")
    sys.exit(0)

def main():
    global water_logger_service

    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # LM Studio 설정 출력
    base_url = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
    logger.info(f"[Backend] Using LM Studio at: {base_url}")

    # 수위 로거 서비스 시작
    try:
        from services.water_level_logger import WaterLevelLogger

        # 수집 주기 설정 (환경 변수로 조정 가능, 기본 60초)
        interval = int(os.getenv("WATER_LEVEL_LOG_INTERVAL", "60"))

        logger.info(f"[Backend] 수위 로거 서비스 초기화 중... (주기: {interval}초)")
        water_logger_service = WaterLevelLogger(interval=interval)
        water_logger_service.start()

        logger.info("[Backend] ✅ 수위 로거 서비스 시작 완료")

    except Exception as e:
        logger.error(f"[Backend] ❌ 수위 로거 서비스 시작 실패: {e}", exc_info=True)
        logger.info("[Backend] 수위 로거 없이 계속 실행...")

    # 백엔드 서비스 유지
    logger.info("[Backend] Ready. 수위 로거 서비스 실행 중...")

    try:
        while True:
            time.sleep(60)
            # 서비스 상태 주기적 출력
            if water_logger_service:
                status = water_logger_service.get_status()
                logger.info(f"[Backend] 서비스 상태: {status}")
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)


if __name__ == "__main__":
    main()


