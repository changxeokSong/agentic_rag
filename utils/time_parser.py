# utils/time_parser.py

from datetime import datetime, timedelta
import re
from typing import Optional, Tuple

class TimeParser:
    """자연어 시간 표현을 파싱하는 클래스"""
    
    @staticmethod
    def parse_time_expression(expression: str) -> Optional[datetime]:
        """자연어 시간 표현을 datetime으로 변환"""
        now = datetime.now()
        expression = expression.lower().strip()
        
        relative_patterns = {
            r'어제': now - timedelta(days=1),
            r'오늘': now,
            r'내일': now + timedelta(days=1),
            r'이번주': now - timedelta(days=now.weekday()),
            r'지난주': now - timedelta(days=now.weekday() + 7),
            r'점심|12시': now.replace(hour=12, minute=0, second=0, microsecond=0),
            r'오전|아침': now.replace(hour=9, minute=0, second=0, microsecond=0),
            r'오후': now.replace(hour=15, minute=0, second=0, microsecond=0),
            r'저녁': now.replace(hour=18, minute=0, second=0, microsecond=0),
            r'새벽': now.replace(hour=3, minute=0, second=0, microsecond=0),
        }
        
        for pattern, target_time in relative_patterns.items():
            if re.search(pattern, expression):
                return target_time
        
        time_match = re.search(r'(\d{1,2})시', expression)
        if time_match:
            hour = int(time_match.group(1))
            base_date = now
            
            if '어제' in expression:
                base_date = now - timedelta(days=1)
            elif '내일' in expression:
                base_date = now + timedelta(days=1)
            
            return base_date.replace(hour=hour, minute=0, second=0, microsecond=0)
        
        return None
    
    @staticmethod
    def parse_time_range(expression: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """시간 범위 표현을 파싱"""
        now = datetime.now()
        expression = expression.lower().strip()
        
        if '오전' in expression:
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = now.replace(hour=12, minute=0, second=0, microsecond=0)
            return start_time, end_time
        elif '오후' in expression:
            start_time = now.replace(hour=12, minute=0, second=0, microsecond=0)
            end_time = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start_time, end_time
        
        duration_match = re.search(r'지난\s*(\d+)\s*(시간|일)', expression)
        if duration_match:
            amount = int(duration_match.group(1))
            unit = duration_match.group(2)
            
            if unit == '시간':
                start_time = now - timedelta(hours=amount)
            else:
                start_time = now - timedelta(days=amount)
            
            return start_time, now
        
        return None, None
