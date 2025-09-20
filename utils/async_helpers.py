# utils/async_helpers.py - 비동기 처리 헬퍼 함수들

import asyncio
import time
import threading
from typing import Dict, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor
import streamlit as st

class AsyncStateManager:
    """비동기 상태 관리자"""
    
    def __init__(self):
        self._cache = {}
        self._cache_timestamps = {}
        self._cache_duration = 30  # 30초 캐시
        self._executor = ThreadPoolExecutor(max_workers=3)
        
    def get_cached_data(self, key: str, fetch_func: Callable, force_refresh: bool = False) -> Any:
        """캐시된 데이터 가져오기 또는 새로 패치"""
        current_time = time.time()
        
        # 캐시 확인
        if not force_refresh and key in self._cache:
            cached_time = self._cache_timestamps.get(key, 0)
            if current_time - cached_time < self._cache_duration:
                return self._cache[key]
        
        # 새 데이터 패치
        try:
            data = fetch_func()
            self._cache[key] = data
            self._cache_timestamps[key] = current_time
            return data
        except Exception as e:
            # 패치 실패 시 기존 캐시 반환
            return self._cache.get(key, None)
    
    def async_fetch(self, key: str, fetch_func: Callable) -> Any:
        """비동기로 데이터 패치"""
        future = self._executor.submit(fetch_func)
        try:
            data = future.result(timeout=5)  # 5초 타임아웃
            self._cache[key] = data
            self._cache_timestamps[key] = time.time()
            return data
        except Exception as e:
            return self._cache.get(key, None)
    
    def clear_cache(self, key: Optional[str] = None):
        """캐시 클리어"""
        if key:
            self._cache.pop(key, None)
            self._cache_timestamps.pop(key, None)
        else:
            self._cache.clear()
            self._cache_timestamps.clear()

class StreamlitStateSync:
    """Streamlit 상태 동기화 유틸리티"""
    
    @staticmethod
    def update_state_without_rerun(updates: Dict[str, Any]):
        """페이지 새로고침 없이 상태 업데이트"""
        for key, value in updates.items():
            if hasattr(st.session_state, key):
                setattr(st.session_state, key, value)
    
    @staticmethod
    def get_state_safe(key: str, default: Any = None) -> Any:
        """안전하게 세션 상태 가져오기"""
        try:
            return getattr(st.session_state, key, default)
        except AttributeError:
            return default
    
    @staticmethod
    def batch_update_state(updates: Dict[str, Any], rerun: bool = False):
        """배치로 상태 업데이트"""
        updated = False
        for key, value in updates.items():
            current_value = StreamlitStateSync.get_state_safe(key)
            if current_value != value:
                setattr(st.session_state, key, value)
                updated = True
        
        if updated and rerun:
            st.rerun()
        
        return updated

class NonBlockingUpdater:
    """논블로킹 업데이트 매니저"""
    
    def __init__(self):
        self._update_queue = []
        self._is_updating = False
        
    def queue_update(self, update_func: Callable, *args, **kwargs):
        """업데이트를 큐에 추가"""
        self._update_queue.append((update_func, args, kwargs))
        
        if not self._is_updating:
            self._process_queue()
    
    def _process_queue(self):
        """큐 처리"""
        if not self._update_queue:
            return
            
        self._is_updating = True
        
        def process():
            while self._update_queue:
                update_func, args, kwargs = self._update_queue.pop(0)
                try:
                    update_func(*args, **kwargs)
                except Exception as e:
                    print(f"Update error: {e}")
            self._is_updating = False
        
        thread = threading.Thread(target=process, daemon=True)
        thread.start()

# 전역 인스턴스들
async_state_manager = AsyncStateManager()
streamlit_state_sync = StreamlitStateSync()
non_blocking_updater = NonBlockingUpdater()

def get_async_state_manager() -> AsyncStateManager:
    """비동기 상태 관리자 가져오기"""
    return async_state_manager

def get_streamlit_state_sync() -> StreamlitStateSync:
    """Streamlit 상태 동기화 유틸리티 가져오기"""
    return streamlit_state_sync

def get_non_blocking_updater() -> NonBlockingUpdater:
    """논블로킹 업데이터 가져오기"""
    return non_blocking_updater

def debounce_update(func: Callable, delay: float = 1.0):
    """디바운스된 업데이트 함수"""
    def wrapper(*args, **kwargs):
        if hasattr(wrapper, '_timer'):
            wrapper._timer.cancel()
        
        wrapper._timer = threading.Timer(delay, func, args, kwargs)
        wrapper._timer.start()
    
    return wrapper

def throttle_update(func: Callable, interval: float = 2.0):
    """스로틀된 업데이트 함수"""
    last_called = [0]
    
    def wrapper(*args, **kwargs):
        current_time = time.time()
        if current_time - last_called[0] >= interval:
            last_called[0] = current_time
            return func(*args, **kwargs)
    
    return wrapper