# tools/real_time_database_control_tool.py

from services.real_time_database_updater import (
    get_database_updater, 
    start_database_update_service, 
    stop_database_update_service, 
    get_database_update_status
)
from utils.logger import setup_logger

logger = setup_logger(__name__)

def real_time_database_control_tool(**kwargs):
    """실시간 데이터베이스 업데이트 서비스 제어 도구"""
    
    action = kwargs.get('action', 'status')
    
    try:
        if action == 'start':
            # 서비스 시작
            update_interval = kwargs.get('update_interval', 60)
            success = start_database_update_service(update_interval)
            
            if success:
                status = get_database_update_status()
                return {
                    'success': True,
                    'message': f'실시간 데이터베이스 업데이트 서비스가 시작되었습니다 (간격: {update_interval}초)',
                    'service_status': status
                }
            else:
                return {
                    'success': False,
                    'error': '서비스 시작 실패',
                    'message': '데이터베이스 연결 또는 서비스 초기화에 문제가 있습니다'
                }
        
        elif action == 'stop':
            # 서비스 중단
            stop_database_update_service()
            return {
                'success': True,
                'message': '실시간 데이터베이스 업데이트 서비스가 중단되었습니다'
            }
        
        elif action == 'status':
            # 서비스 상태 조회
            status = get_database_update_status()
            return {
                'success': True,
                'service_status': status,
                'message': '서비스가 실행 중입니다' if status['is_running'] else '서비스가 중단되었습니다'
            }
        
        elif action == 'manual_collect':
            # 수동 데이터 수집
            updater = get_database_updater()
            result = updater.manual_data_collection()
            
            if result and result.get('success'):
                return {
                    'success': True,
                    'message': '수동 데이터 수집 및 저장이 완료되었습니다',
                    'data': result.get('reading'),
                    'timestamp': result['reading']['timestamp'] if result.get('reading') else None
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', '알 수 없는 오류') if result else '데이터 수집 실패',
                    'message': '수동 데이터 수집에 실패했습니다'
                }
        
        elif action == 'restart':
            # 서비스 재시작
            stop_database_update_service()
            import time
            time.sleep(2)  # 완전 정지 대기
            
            update_interval = kwargs.get('update_interval', 60)
            success = start_database_update_service(update_interval)
            
            if success:
                status = get_database_update_status()
                return {
                    'success': True,
                    'message': f'실시간 데이터베이스 업데이트 서비스가 재시작되었습니다 (간격: {update_interval}초)',
                    'service_status': status
                }
            else:
                return {
                    'success': False,
                    'error': '서비스 재시작 실패',
                    'message': '서비스를 재시작할 수 없습니다'
                }
        
        else:
            return {
                'success': False,
                'error': f'알 수 없는 액션: {action}',
                'available_actions': ['start', 'stop', 'status', 'manual_collect', 'restart'],
                'message': '사용 가능한 액션: start, stop, status, manual_collect, restart'
            }
            
    except Exception as e:
        logger.error(f"실시간 데이터베이스 제어 도구 오류: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'message': '실시간 데이터베이스 제어 중 오류 발생'
        }