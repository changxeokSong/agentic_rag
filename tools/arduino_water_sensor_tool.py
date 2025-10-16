# tools/arduino_water_sensor_tool.py - 아두이노 USB 시리얼 통신 수위 센서 도구

import time
import serial
import serial.tools.list_ports
import re
from typing import Dict, Any, Optional, List
from utils.logger import setup_logger
from utils.helpers import get_current_timestamp, create_error_response, create_success_response

logger = setup_logger(__name__)

class ArduinoWaterSensorTool:
    """아두이노 USB 시리얼 통신을 통한 수위 센서 및 펌프 제어 도구"""
    
    def __init__(self):
        self.name = "arduino_water_sensor"
        self.description = "아두이노 USB 시리얼 통신을 통해 수위 센서 값을 읽고 펌프를 제어하는 도구 (WSL2에서는 usbipd-win 필요)"
        self.serial_connection = None
        self.arduino_port = None
        self.baud_rate = 115200
        self.timeout = 3
        
    def get_tool_config(self) -> Dict[str, Any]:
        """도구 설정 반환"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["read_water_level", "read_water_level_channel", "read_current_level", "pump1_on", "pump1_off", "pump2_on", "pump2_off", "connect", "disconnect", "status", "test_communication", "pump_status", "read_pump_status"],
                            "description": "실행할 액션 (read_water_level: 모든 센서 읽기, read_water_level_channel: 특정 채널 읽기, read_current_level: 수위 읽기, pump1_on/off: 펌프1 제어, pump2_on/off: 펌프2 제어, connect: 연결, disconnect: 연결 해제, status: 상태 확인, test_communication: 통신 테스트, pump_status/read_pump_status: 펌프 상태 확인)"
                        },
                        "channel": {
                            "type": "integer",
                            "description": "센서 채널 번호 (read_water_level_channel 액션에서 사용)",
                            "minimum": 0,
                            "maximum": 7
                        },
                        "port": {
                            "type": "string",
                            "description": "아두이노 시리얼 포트 (예: COM3, /dev/ttyUSB0). 자동 감지를 위해 생략 가능"
                        },
                        "duration": {
                            "type": "integer",
                            "description": "펌프 작동 시간 (초). 펌프 제어 시 사용",
                            "minimum": 1,
                            "maximum": 300
                        }
                    },
                    "required": ["action"]
                }
            }
        }
    
    def _find_arduino_port(self) -> Optional[str]:
        """아두이노 시리얼 포트 자동 감지"""
        import platform
        import os
        
        # 0) 환경변수 우선 사용 (프론트/백엔드 간 통일용)
        env_port = os.getenv('ARDUINO_SERIAL_PORT') or os.getenv('ARDUINO_PORT')
        if env_port:
            logger.info(f"환경변수에서 포트 감지: {env_port}")
            return env_port

        # 1) WSL2 환경 감지
        is_wsl = os.path.exists('/proc/version') and 'microsoft' in open('/proc/version').read().lower()
        if is_wsl:
            linux_usb_ports = self._check_wsl_usb_ports()
            if linux_usb_ports:
                # 각 포트에 대해 연결 시도
                for port in linux_usb_ports:
                    try:
                        test_serial = serial.Serial(port, 115200, timeout=0.5)
                        test_serial.close()
                        logger.info(f"아두이노 포트 발견: {port}")
                        return port
                    except serial.SerialException:
                        continue
                return linux_usb_ports[0]  # 첫 번째 포트 반환
            
            logger.info("WSL2에서 USB 포트 미감지 - 시뮬레이션 모드")
            return "SIMULATION"
        
        # 2) Linux 환경에서 USB 시리얼 포트 검색
        if platform.system() == "Linux":
            # /dev/ttyUSB*, /dev/ttyACM* 포트 검색
            import glob
            usb_ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
            
            if usb_ports:
                logger.info(f"Linux USB 시리얼 포트 발견: {usb_ports}")
                for port in usb_ports:
                    try:
                        test_serial = serial.Serial(port, 115200, timeout=0.5)
                        test_serial.close()
                        logger.info(f"Linux 포트 연결 성공: {port}")
                        return port
                    except serial.SerialException as e:
                        logger.debug(f"Linux 포트 {port} 연결 실패: {e}")
                        continue
        
        # 3) Windows 환경 (WSL2가 아닌 경우)
        if platform.system() == "Windows":
            logger.info("Windows COM 포트 검색 중...")
            # COM1~COM20까지 모두 시도
            for i in range(1, 21):
                com_port = f"COM{i}"
                try:
                    test_serial = serial.Serial(com_port, 115200, timeout=0.5)
                    test_serial.close()
                    logger.info(f"Windows COM{i} 연결 성공!")
                    return com_port
                except serial.SerialException:
                    continue
        
        # 4) pyserial 포트 스캔
        ports = serial.tools.list_ports.comports()
        logger.info(f"총 {len(ports)}개의 시리얼 포트 발견")
        
        for port in ports:
            logger.info(f"  포트: {port.device}")
            logger.info(f"  설명: {port.description}")
            logger.info(f"  하드웨어ID: {port.hwid}")
            logger.info("  ---")
        
        # 발견된 모든 포트 시도
        for port in ports:
            try:
                logger.info(f"포트 {port.device} 연결 시도 중...")
                test_serial = serial.Serial(port.device, 115200, timeout=0.5)
                test_serial.close()
                logger.info(f"포트 {port.device} 연결 성공!")
                return port.device
            except serial.SerialException as e:
                logger.debug(f"포트 {port.device} 연결 실패: {e}")
                continue
        
        logger.error("아두이노 포트를 찾을 수 없습니다")
        return None
    
    def _check_wsl_usb_ports(self) -> List[str]:
        """WSL2에서 USB 포트 확인"""
        import glob
        import subprocess
        import os
        import stat
        
        # lsusb로 Arduino 장치 확인
        try:
            result = subprocess.run(['lsusb'], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                arduino_found = False
                for line in lines:
                    if 'arduino' in line.lower() or '2341:' in line or 'mega' in line.lower():
                        logger.info(f"Arduino 장치 발견: {line.strip()}")
                        arduino_found = True
                
                if arduino_found:
                    logger.info("✅ Arduino Mega 2560 R3 (CDC ACM) 감지됨!")
                else:
                    logger.warning("lsusb에서 Arduino 장치를 찾을 수 없습니다")
        except Exception as e:
            logger.warning(f"lsusb 실행 실패: {e}")
        
        # Arduino가 일반적으로 사용하는 포트들
        usb_ports = []
        
        # /dev/ttyACM* (Arduino Uno, Mega 등 - CDC ACM 장치)
        acm_ports = glob.glob('/dev/ttyACM*')
        usb_ports.extend(acm_ports)
        
        # /dev/ttyUSB* (USB-Serial 변환기)
        usb_serial_ports = glob.glob('/dev/ttyUSB*')
        usb_ports.extend(usb_serial_ports)
        
        if usb_ports:
            logger.info(f"🎉 usbipd-win으로 포워딩된 USB 포트 발견: {usb_ports}")
            return usb_ports
        else:
            logger.warning("WSL2에서 USB 포트를 찾을 수 없습니다")
            logger.warning("usbipd-win이 제대로 설정되었는지 확인하세요:")
            logger.warning("  1. Windows: usbipd wsl list")
            logger.warning("  2. Windows: usbipd wsl attach --busid <BUSID>")
            logger.warning("  3. WSL2: ls /dev/ttyACM* /dev/ttyUSB*")
        
        return []
    
    def _connect_to_arduino(self, port: Optional[str] = None) -> bool:
        """아두이노 시리얼 연결"""
        if self.serial_connection and self.serial_connection.is_open:
            logger.info("이미 아두이노에 연결되어 있습니다")
            return True
        
        try:
            if not port:
                port = self._find_arduino_port()
                if not port:
                    logger.error("아두이노 포트를 찾을 수 없습니다")
                    return False
            
            # 시뮬레이션 모드 처리
            if port == "SIMULATION":
                logger.info("시뮬레이션 모드로 연결됩니다")
                self.arduino_port = port
                return True
            
            logger.info(f"Arduino Mega 2560 연결 시도: {port} @ {self.baud_rate} baud")
            
            # Arduino Mega 2560에 최적화된 시리얼 설정
            self.serial_connection = serial.Serial(
                port=port,
                baudrate=self.baud_rate,
                timeout=self.timeout,
                write_timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            
            # Arduino Mega 2560 연결 안정화 대기 (CDC ACM 장치)
            time.sleep(2)
            logger.info("Arduino Mega 2560 연결 안정화 완료")
            
            # 연결 테스트
            if self._test_connection():
                self.arduino_port = port
                logger.info(f"아두이노 연결 성공: {port}")
                return True
            else:
                self.serial_connection.close()
                logger.error("아두이노 연결 테스트 실패")
                return False
                
        except Exception as e:
            logger.error(f"아두이노 연결 실패: {str(e)}")
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
            return False
    
    def _test_connection(self) -> bool:
        """Arduino Mega 2560 연결 테스트"""
        try:
            if not self.serial_connection or not self.serial_connection.is_open:
                return False
            
            # 버퍼 비우기
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()
            
            # Arduino Mega 2560 부팅 완료 대기
            logger.info("Arduino Mega 2560 부팅 완료 대기 중...")
            time.sleep(1)  # 대기 시간 단축
            
            # 핑 테스트 명령 전송 (3회 시도)
            for attempt in range(3):
                try:
                    self.serial_connection.write(b"PING\n")
                    self.serial_connection.flush()
                    logger.info(f"PING 명령 전송됨 (시도 {attempt + 1}/3)")
                    
                    # PONG 응답 대기 (5초)
                    start_time = time.time()
                    while (time.time() - start_time) < 5:
                        if self.serial_connection.in_waiting > 0:
                            try:
                                data = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                                if data:
                                    logger.info(f"Arduino 응답: {data}")
                                    # PONG 응답 확인
                                    if 'PONG' in data.upper():
                                        logger.info("✅ PING-PONG 응답 확인됨!")
                                        return True
                                    # 다른 유효한 데이터도 연결 성공으로 간주
                                    elif any(keyword in data.lower() for keyword in ['water', 'level', 'pump', 'ack', 'ready']):
                                        logger.info("✅ Arduino 응답 확인됨!")
                                        return True
                            except Exception as e:
                                logger.debug(f"데이터 읽기 중 오류: {e}")
                                continue
                        time.sleep(0.1)
                    
                    # 다음 시도 전 잠시 대기
                    if attempt < 2:
                        time.sleep(0.5)
                        
                except Exception as e:
                    logger.error(f"PING 명령 전송 실패 (시도 {attempt + 1}): {e}")
                    if attempt < 2:
                        time.sleep(0.5)
                    continue
            
            # PING 실패 시 일반 데이터 수신 확인
            logger.info("PING 테스트 실패, 일반 데이터 수신 확인 중...")
            start_time = time.time()
            while (time.time() - start_time) < 5:
                if self.serial_connection.in_waiting > 0:
                    try:
                        data = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                        if data:
                            logger.info(f"일반 데이터 수신: {data}")
                            if len(data) > 0:  # 어떤 데이터든 수신되면 연결됨으로 간주
                                logger.info("✅ Arduino 데이터 수신 확인됨!")
                                return True
                    except Exception as e:
                        logger.debug(f"데이터 읽기 중 오류: {e}")
                        continue
                time.sleep(0.1)
            
            logger.warning("Arduino에서 데이터가 수신되지 않았습니다. 연결이 올바르지 않을 수 있습니다.")
            return False
            
        except Exception as e:
            logger.error(f"Arduino Mega 2560 연결 테스트 실패: {e}")
            return False
    
    def _disconnect_from_arduino(self) -> bool:
        """아두이노 연결 해제"""
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
                logger.info("아두이노 연결 해제 완료")
                return True
            return True
        except Exception as e:
            logger.error(f"아두이노 연결 해제 실패: {str(e)}")
            return False
    
    def _is_connected(self) -> bool:
        """현재 아두이노 연결 상태 확인 (재연결 시도 없이)"""
        try:
            # 시뮬레이션 모드인 경우
            if self.arduino_port == "SIMULATION":
                return True
            
            # 시리얼 연결 객체가 없거나 닫혀있는 경우
            if not self.serial_connection or not self.serial_connection.is_open:
                return False
            
            # 간단한 연결 테스트 (빠른 체크)
            try:
                # 시리얼 포트가 여전히 유효한지 확인
                self.serial_connection.write(b"")
                self.serial_connection.flush()
                return True
            except Exception as e:
                logger.warning(f"연결 상태 체크 실패: {e}")
                # 연결이 끊어진 것으로 판단하고 정리
                try:
                    self.serial_connection.close()
                except:
                    pass
                self.serial_connection = None
                self.arduino_port = None
                return False
                
        except Exception as e:
            logger.error(f"연결 상태 확인 중 오류: {e}")
            return False
    
    def _test_communication(self) -> Dict[str, Any]:
        """아두이노와의 기본 통신 테스트"""
        if not self.serial_connection or not self.serial_connection.is_open:
            return {"error": "❌ **연결 오류**  \n• 아두이노에 연결되지 않았습니다", "success": False}
        
        try:
            # 버퍼 비우기
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()
            
            logger.info("아두이노 통신 테스트 시작...")
            
            # 30초 동안 모든 데이터 수신 및 분석
            all_data = []
            raw_bytes = []
            start_time = time.time()
            
            while (time.time() - start_time) < 30:
                try:
                    if self.serial_connection.in_waiting > 0:
                        # 원시 바이트 데이터 읽기
                        raw_data = self.serial_connection.read(self.serial_connection.in_waiting)
                        raw_bytes.append(raw_data)
                        
                        # 문자열로 변환
                        try:
                            decoded = raw_data.decode('utf-8', errors='replace')
                            all_data.append(decoded)
                            logger.info(f"수신 데이터: {repr(decoded)}")
                        except Exception as e:
                            logger.warning(f"디코딩 오류: {e}")
                            all_data.append(f"[디코딩 오류: {raw_data}]")
                    
                    time.sleep(0.1)
                except Exception as e:
                    logger.warning(f"데이터 수신 중 오류: {e}")
                    continue
            
            # 통신 테스트 결과
            total_bytes = sum(len(chunk) for chunk in raw_bytes)
            total_chunks = len(raw_bytes)
            
            result = {
                "success": True,
                "test_duration": 30,
                "total_data_chunks": total_chunks,
                "total_bytes_received": total_bytes,
                "raw_data_sample": all_data[:5],  # 첫 5개 데이터만 표시
                "timestamp": get_current_timestamp(),
                "port": self.arduino_port,
                "baud_rate": self.baud_rate
            }
            
            if total_bytes > 0:
                result["message"] = f"📡 **통신 테스트 성공**  \n• 데이터 청크: {total_chunks}개  \n• 총 수신 바이트: {total_bytes}"
                result["communication_status"] = "데이터 수신 중"
            else:
                result["message"] = "📡 **통신 연결 확인**  \n• 상태: 연결됨  \n• 데이터: 수신되지 않음"
                result["communication_status"] = "연결됨 (데이터 없음)"
                result["suggestions"] = [
                    "아두이노 코드가 실행 중인지 확인하세요",
                    "시리얼 모니터에서 데이터 출력을 확인하세요",
                    "보드레이트 설정을 확인하세요 (현재: 115200)",
                    "아두이노 리셋 후 다시 시도하세요"
                ]
            
            return result
            
        except Exception as e:
            logger.error(f"통신 테스트 실패: {str(e)}")
            return {
                "success": False,
                "error": f"❌ **통신 테스트 오류**\n• {str(e)}",
                "timestamp": get_current_timestamp()
            }
    
    def _read_water_level(self, channel: Optional[int] = None) -> Dict[str, Any]:
        """수위 센서 값 읽기 (전체 또는 특정 채널)"""
        # 시뮬레이션 모드 처리
        if self.arduino_port == "SIMULATION":
            import random
            
            # 시뮬레이션 데이터 생성
            if channel is not None:
                # 특정 채널 요청
                simulated_level = random.randint(20, 80)
                return {
                    "success": True,
                    "current_water_level": simulated_level,
                    "average_water_level": simulated_level,
                    "readings": [{'channel': channel, 'level': simulated_level}],
                    "channel_levels": {channel: simulated_level},
                    "unit": "percent",
                    "timestamp": get_current_timestamp(),
                    "message": f"🔄 **시뮬레이션 모드** - 채널 {channel} 수위  \n• 현재 수위: **{simulated_level}m**",
                    "simulation_mode": True
                }
            else:
                # 전체 채널 요청
                levels = [random.randint(20, 80) for _ in range(3)]
                current_level = levels[0]
                average_level = sum(levels) / len(levels)
                channel_levels = {i: levels[i] for i in range(len(levels))}
                
                return {
                    "success": True,
                    "current_water_level": current_level,
                    "average_water_level": round(average_level, 1),
                    "readings": [{'channel': i, 'level': levels[i]} for i in range(len(levels))],
                    "channel_levels": channel_levels,
                    "unit": "percent",
                    "timestamp": get_current_timestamp(),
                    "message": f"🔄 **시뮬레이션 모드** - 수위 센서  \n• 현재 수위: **{current_level}m**  \n• 평균 수위: **{round(average_level, 1)}m**",
                    "simulation_mode": True
                }
        
        if not self.serial_connection or not self.serial_connection.is_open:
            return {"error": "❌ **연결 오류**  \n• 아두이노에 연결되지 않았습니다", "success": False}
        
        try:
            # 버퍼 비우기
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()
            
            logger.info("아두이노에서 수위 데이터 읽기 시작...")
            logger.info(f"시리얼 포트: {self.arduino_port}, 보드레이트: {self.baud_rate}")
            
            # 아두이노 명령어 생성 (새 펌웨어 프로토콜에 맞춤)
            if channel is not None:
                command = f"read_water_level_{channel}"
                logger.info(f"특정 채널 {channel} 수위 데이터 요청")
            else:
                command = "read_water_level"
                logger.info("모든 센서 채널 수위 데이터 요청")
            
            # 명령어 전송
            try:
                self.serial_connection.write(f"{command}\n".encode('utf-8'))
                self.serial_connection.flush()
                logger.info(f"아두이노에 수위 데이터 요청 신호 전송: '{command}'")
                time.sleep(0.5)  # 아두이노가 응답할 시간 제공
            except Exception as e:
                logger.warning(f"데이터 요청 신호 전송 실패: {e}")
            
            # 수위 데이터 수집 (여러 번 읽어서 안정적인 값 획득)
            water_levels = []
            all_received_data = []
            raw_bytes_data = []
            start_time = time.time()
            
            # 더 긴 타임아웃과 상세한 디버깅
            while len(water_levels) < 3 and (time.time() - start_time) < 20:  # 최대 20초 대기
                try:
                    # 입력 버퍼에 데이터가 있는지 확인
                    bytes_available = self.serial_connection.in_waiting
                    if bytes_available > 0:
                        logger.info(f"버퍼에 {bytes_available} 바이트 대기 중")
                        
                        # 원시 바이트 데이터 읽기
                        raw_data = self.serial_connection.read(bytes_available)
                        raw_bytes_data.append(raw_data)
                        logger.info(f"원시 바이트 데이터: {raw_data}")
                        
                        # 바이트를 문자열로 변환
                        try:
                            decoded_data = raw_data.decode('utf-8', errors='replace')
                            logger.info(f"디코딩된 데이터: {repr(decoded_data)}")
                            
                            # 줄 단위로 분할
                            lines = decoded_data.split('\n')
                            for line in lines:
                                line = line.strip()
                                if line:  # 빈 줄이 아닌 경우
                                    all_received_data.append(line)
                                    logger.info(f"수신된 라인: '{line}' (길이: {len(line)})")
                                    
                                    # 새 펌웨어 수위 데이터 파싱
                                    line_lower = line.lower()
                                    
                                    # 패턴 1: "Channel[X] water level = 85%" 형태 (새 펌웨어)
                                    if 'channel[' in line_lower and 'water level' in line_lower and '%' in line_lower:
                                        match = re.search(r'channel\[(\d+)\]\s*water level\s*=\s*(\d+)\s*%', line_lower)
                                        if match:
                                            channel_num = int(match.group(1))
                                            water_level = int(match.group(2))
                                            water_levels.append({'channel': channel_num, 'level': water_level})
                                            logger.info(f"✅ 수위 데이터 추출 (새 펌웨어): 채널 {channel_num} = {water_level}m")
                                    
                                    # 패턴 2: "water level = 85%" 형태 (기존 호환성)
                                    elif 'water level' in line_lower and '%' in line_lower and 'channel[' not in line_lower:
                                        match = re.search(r'water level.*?(\d+)\s*%', line_lower)
                                        if match:
                                            water_level = int(match.group(1))
                                            water_levels.append({'channel': 0, 'level': water_level})  # 기본 채널 0
                                            logger.info(f"✅ 수위 데이터 추출 (기존호환): {water_level}m")
                                    
                                    # 패턴 3: "level: 85%" 형태 (기존 호환성)
                                    elif 'level' in line_lower and '%' in line_lower and 'channel[' not in line_lower:
                                        match = re.search(r'level.*?(\d+)\s*%', line_lower)
                                        if match:
                                            water_level = int(match.group(1))
                                            water_levels.append({'channel': 0, 'level': water_level})
                                            logger.info(f"✅ 수위 데이터 추출 (레벨): {water_level}m")
                                    
                                    # 패턴 4: 숫자와 % 기호가 포함된 모든 라인 (기존 호환성)
                                    elif '%' in line and any(char.isdigit() for char in line) and 'channel[' not in line_lower:
                                        numbers = re.findall(r'(\d+)\s*%', line)
                                        if numbers:
                                            water_level = int(numbers[0])
                                            water_levels.append({'channel': 0, 'level': water_level})
                                            logger.info(f"✅ 수위 데이터 추출 (일반): {water_level}m")
                                    
                                    # 패턴 5: 단순 숫자만 있는 경우 (수위 값으로 가정)
                                    elif line.isdigit():
                                        water_level = int(line)
                                        if 0 <= water_level <= 100:  # 합리적인 수위 범위
                                            water_levels.append({'channel': 0, 'level': water_level})
                                            logger.info(f"✅ 수위 데이터 추출 (숫자): {water_level}m")
                                        
                        except UnicodeDecodeError as e:
                            logger.warning(f"데이터 디코딩 오류: {e}")
                            logger.warning(f"원시 바이트: {raw_data}")
                    
                    # 더 짧은 대기 시간으로 빠른 응답
                    time.sleep(0.05)
                    
                except Exception as e:
                    logger.warning(f"데이터 읽기 중 오류: {e}")
                    continue
            
            # 디버깅 정보 출력
            logger.info(f"총 수신된 데이터 라인: {len(all_received_data)}")
            logger.info(f"총 수신된 원시 바이트 청크: {len(raw_bytes_data)}")
            
            if all_received_data:
                logger.info(f"수신된 모든 데이터 라인: {all_received_data}")
            else:
                logger.warning("아두이노에서 어떤 데이터도 수신되지 않았습니다")
                logger.warning("아두이노가 켜져 있고 코드가 실행 중인지 확인하세요")
                logger.warning("아두이노 시리얼 모니터에서 데이터 출력을 확인하세요")
            
            if raw_bytes_data:
                logger.info(f"원시 바이트 데이터 샘플: {raw_bytes_data[:3]}")
            
            if water_levels:
                # 다중 채널 데이터 처리
                if channel is not None:
                    # 특정 채널 요청인 경우
                    channel_data = [reading for reading in water_levels if reading.get('channel') == channel]
                    if channel_data:
                        current_level = channel_data[-1]['level']
                        average_level = sum(reading['level'] for reading in channel_data) / len(channel_data)
                        message = f"💧 **채널 {channel} 수위 센서 측정 완료**  \n• 현재 수위: **{current_level}m**"
                    else:
                        return {
                            "success": False,
                            "error": f"❌ **채널 {channel} 데이터 없음**  \n• 해당 채널에서 수위 데이터를 찾을 수 없습니다",
                            "timestamp": get_current_timestamp()
                        }
                else:
                    # 전체 채널 요청인 경우
                    # 최신 데이터에서 각 채널별 최신 값 추출
                    channel_levels = {}
                    for reading in water_levels:
                        ch = reading.get('channel', 0)
                        level = reading.get('level')
                        channel_levels[ch] = level
                    
                    # 평균 계산
                    all_levels = [reading.get('level', reading) if isinstance(reading, dict) else reading for reading in water_levels]
                    current_level = all_levels[-1] if all_levels else 0
                    average_level = sum(all_levels) / len(all_levels) if all_levels else 0
                    
                    # 메시지 생성
                    if len(channel_levels) > 1:
                        channel_info = ", ".join([f"채널{ch}: {lvl}m" for ch, lvl in sorted(channel_levels.items())])
                        message = f"💧 **다중 채널 수위 센서 측정 완료**  \n• {channel_info}  \n• 평균 수위: **{round(average_level, 1)}m**"
                    else:
                        message = f"💧 **수위 센서 측정 완료**  \n• 현재 수위: **{current_level}m**"
                
                result = {
                    "success": True,
                    "current_water_level": current_level,
                    "average_water_level": round(average_level, 1),
                    "readings": water_levels,
                    "channel_levels": channel_levels if channel is None else {channel: current_level},
                    "unit": "percent",
                    "timestamp": get_current_timestamp(),
                    "message": message,
                    "raw_data": all_received_data[:10],
                    "debug_info": {
                        "total_lines": len(all_received_data),
                        "total_bytes_chunks": len(raw_bytes_data),
                        "port": self.arduino_port,
                        "baud_rate": self.baud_rate,
                        "requested_channel": channel
                    }
                }
                
                # 펌프 상태도 함께 확인
                try:
                    time.sleep(0.2)  # 안정화 대기
                    status_result = self._get_pump_status()
                    if status_result.get("success"):
                        pump_status = status_result.get("pump_status", {})
                        result["pump_status"] = pump_status
                        result["detailed_message"] = self._generate_water_level_with_pump_status(result)
                except Exception as e:
                    logger.warning(f"펌프 상태 확인 중 오류: {e}")
                
                return result
            else:
                return {
                    "success": False,
                    "error": f"❌ **수위 데이터 오류**  \n• 수신 라인: {len(all_received_data)}개  \n• 문제: 수위 데이터 형식을 찾을 수 없습니다",
                    "timestamp": get_current_timestamp(),
                    "raw_data": all_received_data[:10],  # 디버깅용 원본 데이터
                    "raw_bytes_sample": [bytes(chunk) for chunk in raw_bytes_data[:3]],
                    "expected_format": "water level = XX% 또는 level: XX% 또는 단순 숫자 형태의 데이터가 필요합니다",
                    "debug_info": {
                        "total_lines": len(all_received_data),
                        "total_bytes_chunks": len(raw_bytes_data),
                        "port": self.arduino_port,
                        "baud_rate": self.baud_rate,
                        "timeout_used": 20
                    }
                }
                
        except Exception as e:
            logger.error(f"수위 읽기 실패: {str(e)}")
            return {
                "success": False,
                "error": f"❌ **수위 읽기 오류**  \n• {str(e)}",
                "timestamp": get_current_timestamp()
            }
    
    def _send_pump_command(self, pump_id: int, state: str, duration: Optional[int] = None, auto_status: bool = False) -> Dict[str, Any]:
        """펌프 제어 명령 전송 (Arduino 코드의 명령어 프로토콜에 맞춤)"""
        # 시뮬레이션 모드 처리
        if self.arduino_port == "SIMULATION":
            result = {
                "success": True,
                "message": f"🔄 **시뮬레이션 모드** - 펌프{pump_id} 제어  \n• 상태: {state}",
                "command": f"PUMP{pump_id}_{state}",
                "response": "SIMULATION_ACK",
                "ack_received": True,
                "pump_id": pump_id,
                "new_state": state,
                "timestamp": get_current_timestamp(),
                "simulation_mode": True
            }
            
            if duration and state == "ON":
                result["auto_off_duration"] = duration
                result["message"] += f" ({duration}초 후 자동 종료)"
            
            return result
        
        if not self.serial_connection or not self.serial_connection.is_open:
            return {"error": "❌ **연결 오류**  \n• 아두이노에 연결되지 않았습니다", "success": False}
        
        try:
            # Arduino 코드에 맞는 펌프 명령 생성
            if state == "ON":
                command = f"PUMP{pump_id}_ON"
                if duration:
                    command += f"_{duration}"
            else:
                command = f"PUMP{pump_id}_OFF"
            
            # 명령 전송
            self.serial_connection.write(f"{command}\n".encode('utf-8'))
            self.serial_connection.flush()
            
            logger.info(f"펌프 명령 전송: {command}")
            
            # 아두이노 응답 대기 (Arduino는 ACK 메시지를 보냄)
            time.sleep(0.5)
            
            # 응답 읽기 - Arduino에서 ACK 메시지 확인
            response_lines = []
            start_time = time.time()
            while (time.time() - start_time) < 3:  # 3초 대기
                if self.serial_connection.in_waiting > 0:
                    try:
                        line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            response_lines.append(line)
                            logger.info(f"아두이노 응답: {line}")
                            # ACK 메시지가 오면 성공으로 간주
                            if "ACK:" in line:
                                break
                    except Exception as e:
                        logger.warning(f"응답 읽기 중 오류: {e}")
                        break
                time.sleep(0.1)
            
            response = " | ".join(response_lines) if response_lines else "응답 없음"
            ack_received = any("ACK:" in line for line in response_lines)
            
            result = {
                "success": True,
                "message": f"⚙️ **펌프{pump_id} 제어 완료**  \n• 상태: {state}",
                "command": command,
                "response": response,
                "ack_received": ack_received,
                "pump_id": pump_id,
                "new_state": state,
                "timestamp": get_current_timestamp()
            }
            
            # duration이 설정된 경우 자동 종료 정보 추가
            if duration and state == "ON":
                result["auto_off_duration"] = duration
                result["message"] += f" ({duration}초 후 자동 종료)"
            
            # 펌프 상태 확인이 요청된 경우 현재 상태 추가
            if auto_status and ack_received:
                try:
                    time.sleep(0.2)  # 명령 처리 대기
                    status_result = self._get_pump_status()
                    if status_result.get("success"):
                        result["current_pump_status"] = status_result.get("pump_status", {})
                        result["detailed_message"] = self._generate_detailed_status_message(result)
                except Exception as e:
                    logger.warning(f"펌프 상태 확인 중 오류: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"펌프 명령 전송 실패: {str(e)}")
            return {
                "success": False,
                "error": f"❌ **펌프 제어 오류**  \n• {str(e)}",
                "timestamp": get_current_timestamp()
            }
    
    def _get_pump_status(self) -> Dict[str, Any]:
        """펌프 상태 확인 (Arduino의 PUMP_STATUS 명령 사용)"""
        if not self.serial_connection or not self.serial_connection.is_open:
            return {"error": "❌ **연결 오류**  \n• 아두이노에 연결되지 않았습니다", "success": False}
        
        try:
            # 버퍼 비우기
            self.serial_connection.reset_input_buffer()
            
            # Arduino에 펌프 상태 요청
            self.serial_connection.write(b"PUMP_STATUS\n")
            self.serial_connection.flush()
            
            logger.info("펌프 상태 요청 전송: 'PUMP_STATUS'")
            
            # 응답 대기 및 읽기
            response_lines = []
            start_time = time.time()
            while (time.time() - start_time) < 3:  # 3초 대기
                if self.serial_connection.in_waiting > 0:
                    try:
                        line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            response_lines.append(line)
                            logger.info(f"펌프 상태 응답: {line}")
                            # 상태 응답이 오면 처리
                            if "PUMP1_STATUS:" in line or "PUMP2_STATUS:" in line:
                                break
                    except Exception as e:
                        logger.warning(f"상태 응답 읽기 중 오류: {e}")
                        break
                time.sleep(0.1)
            
            if response_lines:
                # 상태 파싱
                pump_status = {}
                for line in response_lines:
                    if "PUMP1_STATUS:" in line:
                        # "PUMP1_STATUS:ON,PUMP2_STATUS:OFF" 형태 파싱
                        parts = line.split(',')
                        for part in parts:
                            if "PUMP1_STATUS:" in part:
                                pump_status["pump1"] = part.split(':')[1].strip()
                            elif "PUMP2_STATUS:" in part:
                                pump_status["pump2"] = part.split(':')[1].strip()
                
                return {
                    "success": True,
                    "pump_status": pump_status,
                    "message": self._format_pump_status_message(pump_status),
                    "raw_response": " | ".join(response_lines),
                    "timestamp": get_current_timestamp()
                }
            else:
                return {
                    "success": False,
                    "error": "❌ **펌프 상태 오류**  \n• 상태 응답을 받지 못했습니다",
                    "timestamp": get_current_timestamp()
                }
                
        except Exception as e:
            logger.error(f"펌프 상태 확인 실패: {str(e)}")
            return {
                "success": False,
                "error": f"❌ **펌프 상태 오류**  \n• {str(e)}",
                "timestamp": get_current_timestamp()
            }
    
    def _generate_detailed_status_message(self, pump_result: Dict[str, Any]) -> str:
        """펌프 제어 결과에 대한 상세한 상태 메시지 생성"""
        pump_id = pump_result.get("pump_id")
        new_state = pump_result.get("new_state")
        current_status = pump_result.get("current_pump_status", {})
        
        # 기본 메시지
        action_kr = "켜짐" if new_state == "ON" else "꺼짐"
        message = f"✅ 펌프{pump_id}이(가) 성공적으로 {action_kr}되었습니다.  \n"
        
        # 현재 전체 펌프 상태 추가
        if current_status:
            pump1_status = current_status.get("pump1", "Unknown")
            pump2_status = current_status.get("pump2", "Unknown")
            
            status_kr = {
                "ON": "🟢 작동중",
                "OFF": "🔴 정지",
                "Unknown": "❓ 알 수 없음"
            }
            
            message += f"  \n📊 **현재 펌프 상태**  \n"
            message += f"• 펌프1: {status_kr.get(pump1_status, pump1_status)}  \n"
            message += f"• 펌프2: {status_kr.get(pump2_status, pump2_status)}"
        
        return message
    
    def _format_pump_status_message(self, pump_status: Dict[str, Any]) -> str:
        """펌프 상태를 포맷팅된 메시지로 변환"""
        pump1_status = pump_status.get("pump1", "Unknown")
        pump2_status = pump_status.get("pump2", "Unknown")
        
        status_kr = {
            "ON": "🟢 작동중",
            "OFF": "🔴 정지",
            "Unknown": "❓ 알 수 없음"
        }
        
        message = f"📊 **현재 펌프 상태**  \n"
        message += f"• 펌프1: {status_kr.get(pump1_status, pump1_status)}  \n"
        message += f"• 펌프2: {status_kr.get(pump2_status, pump2_status)}  \n"
        
        return message
    
    def _generate_water_level_with_pump_status(self, water_result: Dict[str, Any]) -> str:
        """수위 데이터와 펌프 상태를 함께 표시하는 메시지 생성"""
        current_level = water_result.get("current_water_level")
        average_level = water_result.get("average_water_level")
        channel_levels = water_result.get("channel_levels", {})
        pump_status = water_result.get("pump_status", {})
        
        # 각 채널별 수위 상태 평가 함수
        def get_level_status(level):
            if level is not None and level <= 10:
                return "🔴 매우 낮음"
            elif level is not None and level <= 30:
                return "🟡 낮음"
            elif level is not None and level <= 70:
                return "🟢 보통"
            elif level is not None and level <= 90:
                return "🔵 높음"
            elif level is not None and level <= 100:
                return "🔵 매우 높음"
            else:
                return "❓ 알 수 없음"
        
        # 전체 상태 평가 (가장 낮은 수위 기준)
        min_level = min(channel_levels.values()) if channel_levels else current_level
        if min_level is not None and min_level <= 10:
            level_recommendation = "⚠️ 즉시 급수가 필요합니다!"
        elif min_level is not None and min_level <= 30:
            level_recommendation = "💧 급수를 고려해주세요."
        elif min_level is not None and min_level <= 70:
            level_recommendation = "✅ 정상 수위입니다."
        elif min_level is not None and min_level <= 90:
            level_recommendation = "⚡ 배수를 고려해주세요."
        elif min_level is not None and min_level <= 100:
            level_recommendation = "⚡ 배수를 고려해주세요."
        else:
            level_recommendation = "❓ 알 수 없음"

        message = f"💧 **수위 센서 측정 결과**  \n"
        
        # 다중 채널 데이터가 있는 경우 각 채널별로 표시
        if channel_levels and len(channel_levels) > 1:
            for channel, level in sorted(channel_levels.items()):
                status = get_level_status(level)
                message += f"• 채널 {channel}: **{level}m** ({status})  \n"
            message += f"• 전체 평균: **{average_level}m**  \n"
        else:
            # 단일 채널이거나 기존 형식인 경우
            status = get_level_status(current_level)
            message += f"• 현재 수위: **{current_level}m** ({status})  \n"
            message += f"• 평균 수위: **{average_level}m**  \n"
        
        message += f"{level_recommendation}  \n"
        
        # 펌프 상태 추가
        if pump_status:
            pump1_status = pump_status.get("pump1", "Unknown")
            pump2_status = pump_status.get("pump2", "Unknown")
            
            status_kr = {
                "ON": "🟢 작동중",
                "OFF": "🔴 정지",
                "Unknown": "❓ 알 수 없음"
            }
            
            message += f"  \n📊 **현재 펌프 상태**  \n"
            message += f"• 펌프1: {status_kr.get(pump1_status, pump1_status)}  \n"
            message += f"• 펌프2: {status_kr.get(pump2_status, pump2_status)}  \n"
            
            # 자동 제어 제안
            if current_level is not None and current_level <= 10:  # 매우 낮음
                if pump1_status == "OFF" and pump2_status == "OFF":
                    message += f"  \n💡 **제안**: 수위가 매우 낮습니다. 펌프를 가동하여 급수하시겠습니까?"
            elif current_level is not None and current_level >= 80:  # 매우 높음
                if pump1_status == "ON" or pump2_status == "ON":
                    message += f"  \n💡 **제안**: 수위가 높습니다. 펌프를 정지하시겠습니까?"
        
        return message
    
    def _should_check_status_automatically(self, action: str) -> bool:
        """특정 액션 후 자동으로 상태를 확인해야 하는지 판단"""
        # 펌프 제어 액션인 경우 자동 상태 확인
        return action in ["pump1_on", "pump1_off", "pump2_on", "pump2_off"]
    
    def execute(self, action: str, port: Optional[str] = None, duration: Optional[int] = None, channel: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """아두이노 제어 실행"""
        try:
            action = action.lower()
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 연결 관리
            if action == "connect":
                if self._connect_to_arduino(port):
                    return {
                        "success": True,
                        "message": f"✅ **아두이노 연결 성공**  \n• 포트: {self.arduino_port}",
                        "port": self.arduino_port,
                        "timestamp": current_time
                    }
                else:
                    return {
                        "success": False,
                        "message": "❌ **아두이노 연결 실패**  \n• USB 연결을 확인하세요",
                        "timestamp": current_time
                    }
            
            elif action == "disconnect":
                if self._disconnect_from_arduino():
                    return {
                        "success": True,
                        "message": "✅ **아두이노 연결 해제 완료**",
                        "timestamp": current_time
                    }
                else:
                    return {
                        "success": False,
                        "message": "❌ **아두이노 연결 해제 실패**",
                        "timestamp": current_time
                    }
            
            elif action == "status":
                is_connected = self.serial_connection and self.serial_connection.is_open
                return {
                    "success": True,
                    "connected": is_connected,
                    "port": self.arduino_port if is_connected else None,
                    "message": f"🔌 **아두이노 상태**  \n• 연결: {'✅ 연결됨' if is_connected else '❌ 연결안됨'}  \n• 포트: {self.arduino_port if is_connected else 'N/A'}",
                    "timestamp": current_time
                }
            
            elif action == "test_communication":
                # 통신 테스트는 연결 상태 확인 후 실행
                if not self._is_connected():
                    return {
                        "success": False,
                        "error": "❌ **연결 필요**  \n• 아두이노가 연결되지 않았습니다. 먼저 connect 액션을 사용하여 연결하세요.",
                        "timestamp": current_time
                    }
                return self._test_communication()
            
            elif action == "pump_status" or action == "read_pump_status":
                # 펌프 상태 확인은 연결 상태 확인 후 실행
                if not self._is_connected():
                    return {
                        "success": False,
                        "error": "❌ **연결 필요**  \n• 아두이노가 연결되지 않았습니다. 먼저 connect 액션을 사용하여 연결하세요.",
                        "timestamp": current_time
                    }
                return self._get_pump_status()
            
            # 데이터 읽기 및 펌프 제어 액션들 - 연결 상태 확인만 하고 자동 연결하지 않음
            elif action in ["read_water_level", "read_current_level", "read_water_level_channel", 
                           "pump1_on", "pump1_off", "pump2_on", "pump2_off"]:
                
                # 연결 상태 확인
                if not self._is_connected():
                    return {
                        "success": False,
                        "error": "❌ **연결 필요**  \n• 아두이노가 연결되지 않았습니다  \n• 먼저 'connect' 액션을 사용하여 연결하거나  \n• 시스템 제어판에서 '시스템 초기화'를 다시 실행하세요",
                        "timestamp": current_time,
                        "suggested_action": "connect"
                    }
                
                # 수위 읽기
                if action == "read_water_level" or action == "read_current_level":
                    return self._read_water_level()
                
                elif action == "read_water_level_channel":
                    channel = kwargs.get('channel')
                    if channel is None:
                        return {
                            "success": False,
                            "error": "❌ **채널 번호 필요**  \n• read_water_level_channel 액션에는 channel 파라미터가 필요합니다",
                            "timestamp": current_time
                        }
                    return self._read_water_level(channel=channel)
                
                # 펌프 제어 (자동 상태 확인 포함)
                elif action == "pump1_on":
                    return self._send_pump_command(1, "ON", duration, auto_status=True)
                
                elif action == "pump1_off":
                    return self._send_pump_command(1, "OFF", auto_status=True)
                
                elif action == "pump2_on":
                    return self._send_pump_command(2, "ON", duration, auto_status=True)
                
                elif action == "pump2_off":
                    return self._send_pump_command(2, "OFF", auto_status=True)
            
            else:
                return {
                    "success": False,
                    "error": f"❌ **액션 오류**  \n• 지원하지 않는 액션: {action}",
                    "timestamp": current_time
                }
                
        except Exception as e:
            error_msg = f"아두이노 제어 실행 중 오류 발생: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "timestamp": get_current_timestamp()
            }
    
    def get_info(self) -> Dict[str, str]:
        """도구 정보 반환"""
        return {
            "name": self.name,
            "description": self.description
        }
    
    def __del__(self):
        """소멸자 - 시리얼 연결 종료"""
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()