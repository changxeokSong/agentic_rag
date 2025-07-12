# tools/weather_tool.py

import os
import requests
from typing import Dict, Any
from config import WEATHER_API_KEY
from utils.logger import setup_logger

logger = setup_logger(__name__)

class WeatherTool:
    """날씨 정보 도구"""
    
    def __init__(self, api_key=None):
        """
        날씨 도구 초기화
        
        Args:
            api_key (str, optional): 날씨 API 키. 기본값은 환경변수에서 가져옵니다.
        """
        self.name = "weather_tool"
        self.description = "특정 위치의 현재 날씨 정보를 가져옵니다."
        self.api_key = api_key or WEATHER_API_KEY
        logger.info("날씨 도구 초기화")
    
    def execute(self, location):
        """
        위치에 대한 날씨 정보 가져오기
        
        Args:
            location (str): 날씨를 확인할 위치(도시 이름)
            
        Returns:
            dict: 형식화된 날씨 정보 (모든 주요 필드 포함)
        """
        logger.info(f"날씨 조회: {location}")
        
        try:
            # API 키가 존재하면 실제 API 호출
            if self.api_key:
                weather_data = self._get_real_weather(location)
            else:
                # API 키가 없으면 모의 데이터 사용
                weather_data = self._get_mock_weather(location)
            
            return weather_data
        except Exception as e:
            logger.error(f"날씨 조회 오류: {str(e)}")
            return {"error": f"날씨 정보를 가져오는 중 오류가 발생했습니다: {str(e)}"}
    
    def _get_real_weather(self, location):
        """OpenWeather Current Weather Data API 사용 (무료, 모든 주요 필드 포함)"""
        logger.info(f"OpenWeather Geocoding API 호출: {location}")
        geo_url = f"https://api.openweathermap.org/geo/1.0/direct?q={location}&limit=1&appid={self.api_key}"
        geo_resp = requests.get(geo_url)
        if geo_resp.status_code != 200:
            raise Exception(f"Geocoding API 오류 (코드: {geo_resp.status_code}): {geo_resp.text}")
        geo_data = geo_resp.json()
        if not geo_data:
            raise Exception("도시명을 위도/경도로 변환할 수 없습니다.")
        lat = geo_data[0]['lat']
        lon = geo_data[0]['lon']

        logger.info(f"OpenWeather Current Weather API 호출: lat={lat}, lon={lon}")
        weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&appid={self.api_key}&lang=kr"
        weather_resp = requests.get(weather_url)
        if weather_resp.status_code != 200:
            raise Exception(f"Current Weather API 오류 (코드: {weather_resp.status_code}): {weather_resp.text}")
        data = weather_resp.json()

        main = data.get('main', {})
        wind = data.get('wind', {})
        clouds = data.get('clouds', {})
        rain = data.get('rain', {})
        snow = data.get('snow', {})
        weather = data.get('weather', [{}])[0]
        sys = data.get('sys', {})

        temp_c = main.get('temp', 0)
        temp_f = round(temp_c * 9/5 + 32, 1)
        feels_like = main.get('feels_like', '')
        pressure = main.get('pressure', '')
        humidity = main.get('humidity', '')
        temp_min = main.get('temp_min', '')
        temp_max = main.get('temp_max', '')
        sea_level = main.get('sea_level', '')
        grnd_level = main.get('grnd_level', '')
        dew_point = ''  # 무료 API에는 없음
        cloudiness = clouds.get('all', '')
        visibility = data.get('visibility', '')
        wind_speed = wind.get('speed', '')
        wind_deg = wind.get('deg', '')
        wind_gust = wind.get('gust', '')
        rain_1h = rain.get('1h', 0)
        rain_3h = rain.get('3h', 0)
        snow_1h = snow.get('1h', 0)
        snow_3h = snow.get('3h', 0)
        sunrise = sys.get('sunrise', '')
        sunset = sys.get('sunset', '')
        country = sys.get('country', '')
        timezone = data.get('timezone', '')
        dt = data.get('dt', '')
        icon = weather.get('icon', '')
        weather_id = weather.get('id', '')
        weather_main = weather.get('main', '')
        weather_desc = weather.get('description', '')

        return {
            "location": location,
            "lat": lat,
            "lon": lon,
            "country": country,
            "timezone": timezone,
            "datetime_utc": dt,
            "temperature_c": temp_c,
            "temperature_f": temp_f,
            "temperature_min": temp_min,
            "temperature_max": temp_max,
            "feels_like": feels_like,
            "pressure": pressure,
            "humidity": humidity,
            "cloudiness": cloudiness,
            "visibility": visibility,
            "wind_speed": wind_speed,
            "wind_deg": wind_deg,
            "wind_gust": wind_gust,
            "rain_1h": rain_1h,
            "rain_3h": rain_3h,
            "snow_1h": snow_1h,
            "snow_3h": snow_3h,
            "weather_main": weather_main,
            "weather_desc": weather_desc,
            "icon": icon,
            "sunrise": sunrise,
            "sunset": sunset
        }
    
    def _get_mock_weather(self, location):
        """모의 날씨 데이터 반환 (API 키가 없을 때)"""
        import random
        
        # 모의 데이터 생성
        temp_c = round(random.uniform(-10, 35), 1)
        temp_f = round(temp_c * 9/5 + 32, 1)
        
        return {
            "location": location,
            "temperature_c": temp_c,
            "temperature_f": temp_f,
            "feels_like": round(temp_c + random.uniform(-3, 3), 1),
            "humidity": random.randint(30, 90),
            "pressure": random.randint(1000, 1030),
            "weather_desc": random.choice(["맑음", "구름 조금", "흐림", "비", "눈"]),
            "wind_speed": round(random.uniform(0, 15), 1),
            "message": "모의 데이터입니다. 정확한 날씨 정보를 위해 WEATHER_API_KEY를 설정하세요."
        }
    
    def get_info(self) -> Dict[str, str]:
        """도구 정보 반환"""
        return {
            "name": self.name,
            "description": self.description
        }