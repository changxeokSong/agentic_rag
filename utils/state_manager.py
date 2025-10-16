# utils/state_manager.py - 앱 간 상태 동기화를 위한 글로벌 상태 관리자

import json
import os
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from utils.logger import setup_logger

logger = setup_logger(__name__)

class GlobalStateManager:
    """앱 간 공유되는 상태를 관리하는 클래스"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        # 프로젝트 루트 경로를 현재 작업 디렉토리 기준으로 설정
        project_root = Path(os.environ.get('PROJECT_ROOT', os.getcwd()))
        self.state_file = project_root / '.app_state.json'
        self._lock = threading.Lock()
        self._last_update = None
        
        # 무한 루프 방지를 위한 동기화 플래그
        self._syncing_to_streamlit = False
        self._syncing_from_streamlit = False
        self._last_sync_state = {}
        
        # 기본 상태
        self.default_state = {
            'automation_status': False,
            'autonomous_monitoring': False,
            'system_initialized': False,  # 초기화 상태를 False로 설정 (강제 초기화)
            'last_update': None,
            'orchestrator_active': False,
            'arduino_connected': False,
            'simulation_mode': True,
            'model_loaded': False,
            'arduino_port': None,
            'last_successful_data': None,
            'dashboard_data': []
        }
        
        # 상태 초기화
        self._ensure_state_file()
    
    def _ensure_state_file(self):
        """상태 파일이 없으면 생성"""
        if not self.state_file.exists():
            self.save_state(self.default_state)
    
    def load_state(self) -> Dict[str, Any]:
        """상태 파일에서 상태 로드"""
        try:
            with self._lock:
                if self.state_file.exists():
                    with open(self.state_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        
                    # 빈 파일이거나 불완전한 JSON인 경우 처리
                    if not content or not content.startswith('{'):
                        logger.warning("상태 파일이 비어있거나 손상됨, 기본 상태로 초기화")
                        return self.default_state.copy()
                    
                    try:
                        state = json.loads(content)
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON 파싱 오류: {e}")
                        # 백업 파일 생성
                        self._create_backup()
                        return self.default_state.copy()
                    
                    # 유효성 검사
                    if isinstance(state, dict):
                        # 기본 키들이 있는지 확인하고 없으면 추가
                        for key, default_value in self.default_state.items():
                            if key not in state:
                                state[key] = default_value
                        return state
                    
            return self.default_state.copy()
            
        except Exception as e:
            logger.error(f"상태 로드 오류: {e}")
            return self.default_state.copy()
    
    def save_state(self, state: Dict[str, Any]):
        """상태를 파일에 저장"""
        try:
            with self._lock:
                # 현재 시각 추가 (문자열로 변환)
                state['last_update'] = datetime.now().isoformat()
                
                # datetime 객체를 문자열로 변환
                cleaned_state = self._clean_state_for_json(state)
                
                with open(self.state_file, 'w', encoding='utf-8') as f:
                    json.dump(cleaned_state, f, indent=2, ensure_ascii=False)
                
                self._last_update = time.time()
                
        except Exception as e:
            logger.error(f"상태 저장 오류: {e}")
    
    def _clean_state_for_json(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """JSON 직렬화를 위해 상태 정리"""
        cleaned = {}
        for key, value in state.items():
            if isinstance(value, datetime):
                cleaned[key] = value.isoformat()
            elif isinstance(value, dict):
                cleaned[key] = self._clean_state_for_json(value)
            elif isinstance(value, list):
                cleaned[key] = [
                    self._clean_state_for_json(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                cleaned[key] = value
        return cleaned
    
    def _create_backup(self):
        """손상된 상태 파일 백업"""
        try:
            if self.state_file.exists():
                backup_file = self.state_file.with_suffix('.json.backup')
                import shutil
                shutil.copy2(self.state_file, backup_file)
                logger.info(f"상태 파일 백업 생성: {backup_file}")
        except Exception as e:
            logger.error(f"백업 생성 오류: {e}")
    
    def update_automation_status(self, automation_status: bool, autonomous_monitoring: bool = None):
        """자동화 상태 업데이트"""
        state = self.load_state()
        
        # 변경사항 있는지 체크
        changed = False
        if state.get('automation_status') != automation_status:
            state['automation_status'] = automation_status
            changed = True
        
        if autonomous_monitoring is not None and state.get('autonomous_monitoring') != autonomous_monitoring:
            state['autonomous_monitoring'] = autonomous_monitoring
            changed = True
        
        if changed:
            self.save_state(state)
            logger.info(f"자동화 상태 업데이트: automation={automation_status}, monitoring={state.get('autonomous_monitoring', False)}")
        
        # 상태 추적 업데이트
        self._last_sync_state['automation_status'] = automation_status
        if autonomous_monitoring is not None:
            self._last_sync_state['autonomous_monitoring'] = autonomous_monitoring
    
    def update_system_status(self, system_initialized: bool, orchestrator_active: bool = None):
        """시스템 상태 업데이트"""
        state = self.load_state()
        state['system_initialized'] = system_initialized
        
        if orchestrator_active is not None:
            state['orchestrator_active'] = orchestrator_active
        
        self.save_state(state)
    
    def update_arduino_status(self, connected: bool, port: str = None, simulation: bool = None):
        """아두이노 연결 상태 업데이트"""
        state = self.load_state()
        state['arduino_connected'] = connected
        
        if port is not None:
            state['arduino_port'] = port
        
        if simulation is not None:
            state['simulation_mode'] = simulation
        
        self.save_state(state)
    
    def update_model_status(self, loaded: bool):
        """모델 로드 상태 업데이트"""
        state = self.load_state()
        state['model_loaded'] = loaded
        self.save_state(state)
    
    def save_dashboard_data(self, data: dict):
        """대시보드 데이터 저장"""
        state = self.load_state()
        if 'dashboard_data' not in state:
            state['dashboard_data'] = []
        
        # 최대 100개 항목 유지
        state['dashboard_data'].append(data)
        if len(state['dashboard_data']) > 100:
            state['dashboard_data'] = state['dashboard_data'][-100:]
        
        self.save_state(state)
    
    def get_dashboard_data(self) -> list:
        """대시보드 데이터 조회"""
        state = self.load_state()
        return state.get('dashboard_data', [])
    
    def save_last_successful_data(self, data: dict):
        """마지막 성공한 데이터 저장"""
        state = self.load_state()
        state['last_successful_data'] = data
        self.save_state(state)
    
    def get_last_successful_data(self) -> dict:
        """마지막 성공한 데이터 조회"""
        state = self.load_state()
        return state.get('last_successful_data', None)
    
    def is_automation_active(self) -> tuple[bool, bool]:
        """자동화 상태 반환 (automation_status, autonomous_monitoring)"""
        state = self.load_state()
        return state.get('automation_status', False), state.get('autonomous_monitoring', False)
    
    def sync_to_streamlit(self):
        """Streamlit 세션 상태에 동기화 (무한 루프 방지)"""
        # 이미 동기화 중이면 스킵
        if self._syncing_to_streamlit:
            return False
            
        try:
            import streamlit as st
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            
            # 스크립트 컨텍스트가 있는지 확인 (메인 스레드에서만)
            ctx = get_script_run_ctx()
            if ctx is None:
                return False
            
            self._syncing_to_streamlit = True
            
            state = self.load_state()
            
            # 변경사항 체크 - 실제로 변경된 것만 동기화
            changed = False
            for key in ['automation_status', 'autonomous_monitoring', 'system_initialized']:
                if key in state:
                    current_session_value = getattr(st.session_state, key, None)
                    global_value = state[key]
                    last_sync_value = self._last_sync_state.get(key)
                    
                    # 글로벌 상태가 변경되었고, 현재 세션 값과 다르면 업데이트
                    if global_value != last_sync_value and global_value != current_session_value:
                        st.session_state[key] = global_value
                        changed = True
                        self._last_sync_state[key] = global_value
            
            if changed:
                logger.debug("Streamlit 세션에 상태 동기화 완료")
            
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False
        finally:
            self._syncing_to_streamlit = False
    
    def sync_from_streamlit(self):
        """Streamlit 세션 상태로부터 동기화 (무한 루프 방지)"""
        # 이미 동기화 중이면 스킵
        if self._syncing_from_streamlit or self._syncing_to_streamlit:
            return False
            
        try:
            import streamlit as st
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            
            ctx = get_script_run_ctx()
            if ctx is None:
                return False
            
            self._syncing_from_streamlit = True
            
            state = self.load_state()
            
            # 주요 상태들만 동기화
            key_mappings = {
                'automation_status': 'automation_status',
                'autonomous_monitoring': 'autonomous_monitoring', 
                'system_initialized': 'system_initialized',
                'simulation_mode': 'simulation_mode'
            }
            
            updated = False
            for st_key, state_key in key_mappings.items():
                if hasattr(st.session_state, st_key):
                    new_value = getattr(st.session_state, st_key)
                    old_value = state.get(state_key)
                    
                    # 실제로 값이 변경된 경우에만 업데이트
                    if old_value != new_value:
                        state[state_key] = new_value
                        updated = True
                        self._last_sync_state[state_key] = new_value
            
            if updated:
                self.save_state(state)
                logger.debug("글로벌 상태에 Streamlit 세션 동기화 완료")
            
            return True
            
        except Exception as e:
            logger.error(f"Streamlit -> 글로벌 동기화 오류: {e}")
            return False
        finally:
            self._syncing_from_streamlit = False

# 글로벌 인스턴스
_state_manager = None

def get_state_manager() -> GlobalStateManager:
    """상태 관리자 인스턴스 반환"""
    global _state_manager
    if _state_manager is None:
        _state_manager = GlobalStateManager()
    return _state_manager

def sync_automation_status(automation_active: bool, autonomous_monitoring: bool = None):
    """자동화 상태를 모든 앱에 동기화"""
    manager = get_state_manager()
    manager.update_automation_status(automation_active, autonomous_monitoring)

def get_automation_status() -> tuple[bool, bool]:
    """현재 자동화 상태 조회"""
    manager = get_state_manager()
    return manager.is_automation_active()

# 개발 시 테스트용 함수 (프로덕션에서는 사용하지 않음)
def _test_state_manager():
    """상태 관리자 테스트 함수 (개발용)"""
    logger.info("상태 관리자 테스트 시작")
    manager = get_state_manager()
    
    # 테스트 상태 저장
    logger.info("테스트 상태 저장: automation=True, monitoring=True")
    manager.update_automation_status(True, True)
    
    # 저장된 상태 확인
    automation, monitoring = manager.is_automation_active()
    logger.info(f"저장 후 상태 확인: automation={automation}, monitoring={monitoring}")
    
    return automation, monitoring