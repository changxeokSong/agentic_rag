# tools/weather_tool.py

import os
import requests
from tools.base_tool import BaseTool
from config import WEATHER_API_KEY
from utils.logger import setup_logger

logger = setup_logger(__name__)

class WeatherTool(BaseTool):
    """날씨 정보 도구"""
    
    def __init__(self, api_key=None):
        """
        날씨 도구 초기화
        
        Args:
            api_key (str, optional): 날씨 API 키. 기본값은 환경변수에서 가져옵니다.
        """
        super().__init__(
            name="weather_tool",
            description="특정 위치의 현재 날씨 정보를 가져옵니다."
        )
        self.api_key = api_key or WEATHER_API_KEY
        logger.info("날씨 도구 초기화")
    
    def execute(self, location):
        """
        위치에 대한 날씨 정보 가져오기
        
        Args:
            location (str): 날씨를 확인할 위치(도시 이름)
            
        Returns:
            str: 형식화된 날씨 정보 (모든 주요 필드 포함)
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
            return f"날씨 정보를 가져오는 중 오류가 발생했습니다: {str(e)}"
    
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

        lines = [
            f"위치: {location} (위도: {lat}, 경도: {lon}, 국가: {country})",
            f"시간대: {timezone}, 데이터 시각(UTC): {dt}",
            f"[현재 날씨]",
            f"- 온도: {temp_c}°C / {temp_f}°F (최저: {temp_min}°C, 최고: {temp_max}°C)",
            f"- 체감온도: {feels_like}°C",
            f"- 기압: {pressure} hPa",
            f"- 습도: {humidity}%",
            f"- 구름: {cloudiness}%",
            f"- 가시거리: {visibility} m",
            f"- 바람: {wind_speed} m/s, 풍향: {wind_deg}°" + (f", 돌풍: {wind_gust} m/s" if wind_gust else ""),
            f"- 강수량(1시간): {rain_1h} mm, (3시간): {rain_3h} mm",
            f"- 적설량(1시간): {snow_1h} mm, (3시간): {snow_3h} mm",
            f"- 상태: {weather_main} ({weather_desc})",
            f"- 날씨 아이콘: {icon}",
            f"- 일출: {sunrise}, 일몰: {sunset}"
        ]
        return '\n'.join(lines)