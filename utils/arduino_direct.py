# pages/arduino_direct.py - 대시보드 전용 직접 아두이노 통신

import serial
import serial.tools.list_ports
import time
import re
import glob
import subprocess
import os
import stat
from typing import Dict, Any, Optional, List
from utils.logger import setup_logger

logger = setup_logger(__name__)

class DirectArduinoComm:
    """대시보드 전용 직접 아두이노 통신 클래스 (LLM 우회)"""
    
    def __init__(self):
        self.serial_connection = None
        self.arduino_port = None
        self.baud_rate = 115200
        self.timeout = 3
        
    def _find_arduino_port(self) -> Optional[str]:
        """아두이노 시리얼 포트 자동 감지"""
        logger.info("아두이노 포트 검색 중...")
        
        import platform
        # 0) 환경변수 우선
        env_port = os.getenv('ARDUINO_SERIAL_PORT') or os.getenv('ARDUINO_PORT')
        if env_port:
            logger.info(f"환경변수에서 포트 감지: {env_port}")
            return env_port
        
        # WSL2 환경 감지
        is_wsl = os.path.exists('/proc/version') and 'microsoft' in open('/proc/version').read().lower()
        if is_wsl:
            logger.info("WSL2 환경이 감지되었습니다!")
            
            # WSL2에서 이미 포워딩된 USB 포트가 있는지 확인
            linux_usb_ports = self._check_wsl_usb_ports()
            if linux_usb_ports:
                logger.info(f"🎉 usbipd-win으로 포워딩된 USB 포트 발견: {linux_usb_ports}")
                
                # 각 포트에 대해 연결 시도
                for port in linux_usb_ports:
                    try:
                        logger.info(f"포트 {port} 연결 시도 중...")
                        test_serial = serial.Serial(port, 115200, timeout=0.5)
                        test_serial.close()
                        logger.info(f"✅ 아두이노 포트 연결 성공: {port}")
                        return port
                    except serial.SerialException as e:
                        logger.warning(f"포트 {port} 연결 실패: {e}")
                        continue
                
                # 연결 실패 시 첫 번째 포트 반환
                return linux_usb_ports[0]
            
            # 포트가 없는 경우 시뮬레이션 모드
            logger.warning("WSL2에서 USB 포트가 감지되지 않았습니다.")
            return "SIMULATION"
        
        # Linux 환경에서 USB 시리얼 포트 검색
        if platform.system() == "Linux":
            usb_ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
            
            if usb_ports:
                logger.info(f"Linux USB 시리얼 포트 발견: {usb_ports}")
                for port in usb_ports:
                    try:
                        test_serial = serial.Serial(port, 115200, timeout=0.5)
                        test_serial.close()
                        logger.info(f"Linux 포트 연결 성공: {port}")
                        return port
                    except Exception:
                        continue
        
        # Windows 환경에서는 실제 아두이노 통신 테스트 수행
        if platform.system() == "Windows":
            for i in range(1, 21):
                com_port = f"COM{i}"
                try:
                    test_serial = serial.Serial(com_port, 115200, timeout=0.5)
                    test_serial.close()
                    # 포트 연결만 확인하고 PING 테스트는 실제 연결 시에 1회만 수행
                    logger.info(f"Windows COM{i} 포트 연결 가능")
                    return com_port
                except Exception as e:
                    logger.debug(f"COM{i} 연결 실패: {e}")
                    continue
        
        # pyserial 포트 스캔 (연결만 확인)
        ports = serial.tools.list_ports.comports()
        for port in ports:
            try:
                test_serial = serial.Serial(port.device, 115200, timeout=0.5)
                test_serial.close()
                # 아두이노 디스크립션 확인 (선택적)
                if 'Arduino' in port.description or 'USB' in port.description:
                    logger.info(f"포트 {port.device} 아두이노 장치로 추정됨: {port.description}")
                    return port.device
                else:
                    logger.info(f"포트 {port.device} 연결 가능: {port.description}")
                    return port.device
            except Exception as e:
                logger.debug(f"포트 {port.device} 연결 실패: {e}")
                continue
        
        return None
    
    def _check_wsl_usb_ports(self) -> List[str]:
        """WSL2에서 USB 포트 확인"""
        usb_ports = []
        
        # /dev/ttyACM* (Arduino Uno, Mega 등)
        acm_ports = glob.glob('/dev/ttyACM*')
        usb_ports.extend(acm_ports)
        
        # /dev/ttyUSB* (USB-Serial 변환기)
        usb_serial_ports = glob.glob('/dev/ttyUSB*')
        usb_ports.extend(usb_serial_ports)
        
        if usb_ports:
            accessible_ports = []
            for port in usb_ports:
                try:
                    port_stat = os.stat(port)
                    if stat.S_ISCHR(port_stat.st_mode):
                        if port.startswith('/dev/ttyACM'):
                            accessible_ports.insert(0, port)  # ACM 포트를 맨 앞에
                        else:
                            accessible_ports.append(port)
                except Exception:
                    # 권한 문제가 있어도 포트는 반환
                    if port.startswith('/dev/ttyACM'):
                        accessible_ports.insert(0, port)
                    else:
                        accessible_ports.append(port)
            
            return accessible_ports
        
        return []
    
    def connect(self, port: Optional[str] = None) -> bool:
        """아두이노 연결"""
        if self.serial_connection and self.serial_connection.is_open:
            return True
        
        try:
            if not port:
                port = self._find_arduino_port()
                if not port:
                    logger.error("아두이노 포트를 찾을 수 없습니다")
                    return False
            
            # 시뮬레이션 모드
            if port == "SIMULATION":
                logger.info("시뮬레이션 모드로 연결됩니다")
                self.arduino_port = port
                return True
            
            logger.info(f"Arduino 연결 시도: {port} @ {self.baud_rate} baud")
            
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
            
            # 연결 안정화 대기
            time.sleep(2)
            
            # 연결 성공 시 1회만 PING 테스트 수행
            try:
                self.serial_connection.write(b"PING\n")
                self.serial_connection.flush()
                time.sleep(0.3)
                
                if self.serial_connection.in_waiting > 0:
                    response = self.serial_connection.read(self.serial_connection.in_waiting)
                    logger.info(f"아두이노 응답 확인: {response.decode('utf-8', errors='ignore').strip()}")
                else:
                    logger.info("아두이노 PING 응답 없음 (정상적일 수 있음)")
            except Exception as e:
                logger.warning(f"PING 테스트 실패 (연결은 유지됨): {e}")
            
            self.arduino_port = port
            logger.info(f"아두이노 연결 성공: {port}")
            return True
                
        except Exception as e:
            logger.error(f"아두이노 연결 실패: {str(e)}")
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
            return False
    
    def disconnect(self) -> bool:
        """아두이노 연결 해제"""
        try:
            if self.serial_connection and hasattr(self.serial_connection, 'is_open') and self.serial_connection.is_open:
                self.serial_connection.close()
                logger.info("아두이노 연결 해제 완료")
            
            # 연결 정보 초기화
            self.serial_connection = None
            self.arduino_port = None
            return True
        except Exception as e:
            logger.error(f"아두이노 연결 해제 실패: {str(e)}")
            # 에러가 발생해도 연결 정보는 초기화
            self.serial_connection = None
            self.arduino_port = None
            return False
    
    def read_water_level(self, channel: Optional[int] = None) -> Dict[str, Any]:
        """수위 센서 값 직접 읽기"""
        if self.arduino_port == "SIMULATION":
            # 시뮬레이션 데이터 반환
            import random
            if channel is not None:
                level = random.randint(20, 95)
                return {
                    "success": True,
                    "channel_levels": {channel: level},
                    "current_water_level": level,
                    "average_water_level": level,
                    "simulation": True
                }
            else:
                ch1_level = random.randint(20, 95)
                ch2_level = random.randint(20, 95)
                return {
                    "success": True,
                    "channel_levels": {1: ch1_level, 2: ch2_level},
                    "current_water_level": ch2_level,
                    "average_water_level": (ch1_level + ch2_level) / 2,
                    "simulation": True
                }
        
        if not self.serial_connection or not self.serial_connection.is_open:
            return {"success": False, "error": "아두이노에 연결되지 않았습니다"}
        
        try:
            # 버퍼 비우기
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()
            
            # 명령어 생성
            if channel is not None:
                command = f"read_water_level_{channel}"
            else:
                command = "read_water_level"
            
            # 명령어 전송
            self.serial_connection.write(f"{command}\n".encode('utf-8'))
            self.serial_connection.flush()
            logger.info(f"아두이노 명령 전송: {command}")
            
            time.sleep(0.5)
            
            # 응답 읽기
            water_levels = []
            start_time = time.time()
            
            # 일부 보드에서 라인당 한 번만 출력하는 경우가 있어 단일 리딩도 허용
            min_samples = 1 if channel is not None else 2
            max_wait = 12  # 초
            while len(water_levels) < min_samples and (time.time() - start_time) < max_wait:
                if self.serial_connection.in_waiting > 0:
                    try:
                        raw_data = self.serial_connection.read(self.serial_connection.in_waiting)
                        decoded_data = raw_data.decode('utf-8', errors='replace')
                        
                        lines = decoded_data.split('\n')
                        for line in lines:
                            line = line.strip()
                            if line:
                                # 새 펌웨어 형식: "Channel[X] water level = Y%"
                                if 'channel[' in line.lower() and 'water level' in line.lower() and '%' in line.lower():
                                    match = re.search(r'channel\[(\d+)\]\s*water level\s*=\s*(\d+)\s*%', line.lower())
                                    if match:
                                        channel_num = int(match.group(1))
                                        water_level = int(match.group(2))
                                        water_levels.append({'channel': channel_num, 'level': water_level})
                                        logger.info(f"수위 데이터: 채널 {channel_num} = {water_level}%")
                                
                                # 기존 형식 호환
                                elif 'water level' in line.lower() and '%' in line.lower() and 'channel[' not in line.lower():
                                    match = re.search(r'water level.*?(\d+)\s*%', line.lower())
                                    if match:
                                        water_level = int(match.group(1))
                                        water_levels.append({'channel': 0, 'level': water_level})
                                        logger.info(f"수위 데이터: {water_level}%")
                                # 더 느슨한 패턴: level: XX%, XX%, 또는 숫자만
                                elif '%' in line and any(ch.isdigit() for ch in line):
                                    nums = re.findall(r'(\d+)\s*%', line)
                                    if nums:
                                        water_level = int(nums[0])
                                        water_levels.append({'channel': channel or 0, 'level': water_level})
                                        logger.info(f"수위 데이터(느슨): {water_level}%")
                                elif line.isdigit():
                                    val = int(line)
                                    if 0 <= val <= 100:
                                        water_levels.append({'channel': channel or 0, 'level': val})
                                        logger.info(f"수위 데이터(숫자): {val}%")
                    except Exception as e:
                        logger.warning(f"데이터 읽기 중 오류: {e}")
                        continue
                
                time.sleep(0.05)
            
            if water_levels:
                # 다중 채널 데이터 처리
                if channel is not None:
                    # 특정 채널 요청
                    channel_data = [reading for reading in water_levels if reading.get('channel') == channel]
                    if channel_data:
                        current_level = channel_data[-1]['level']
                        return {
                            "success": True,
                            "channel_levels": {channel: current_level},
                            "current_water_level": current_level,
                            "average_water_level": current_level
                        }
                    else:
                        # 수신은 되었으나 해당 채널 라벨이 없을 때 마지막값을 사용
                        last_level = water_levels[-1]['level']
                        return {
                            "success": True,
                            "channel_levels": {channel: last_level},
                            "current_water_level": last_level,
                            "average_water_level": last_level
                        }
                else:
                    # 전체 채널 요청
                    channel_levels = {}
                    for reading in water_levels:
                        ch = reading.get('channel', 0)
                        level = reading.get('level')
                        channel_levels[ch] = level
                    
                    all_levels = [reading.get('level', reading) if isinstance(reading, dict) else reading for reading in water_levels]
                    current_level = all_levels[-1] if all_levels else 0
                    average_level = sum(all_levels) / len(all_levels) if all_levels else 0
                    
                    return {
                        "success": True,
                        "channel_levels": channel_levels,
                        "current_water_level": current_level,
                        "average_water_level": round(average_level, 1)
                    }
            
            return {"success": False, "error": "수위 데이터를 읽을 수 없습니다"}
            
        except Exception as e:
            logger.error(f"수위 읽기 실패: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def control_pump(self, pump_id: int, state: str, duration: Optional[int] = None) -> Dict[str, Any]:
        """펌프 직접 제어"""
        if self.arduino_port == "SIMULATION":
            # 시뮬레이션 응답
            return {
                "success": True,
                "message": f"펌프{pump_id} {state} (시뮬레이션)",
                "pump_id": pump_id,
                "new_state": state,
                "simulation": True
            }
        
        if not self.serial_connection or not self.serial_connection.is_open:
            return {"success": False, "error": "아두이노에 연결되지 않았습니다"}
        
        try:
            # 명령어 생성
            if state == "ON":
                command = f"PUMP{pump_id}_ON"
                if duration:
                    command += f"_{duration}"
            else:
                command = f"PUMP{pump_id}_OFF"
            
            # 명령어 전송
            self.serial_connection.write(f"{command}\n".encode('utf-8'))
            self.serial_connection.flush()
            logger.info(f"펌프 명령 전송: {command}")
            
            # 응답 대기
            time.sleep(0.5)
            
            response_lines = []
            start_time = time.time()
            while (time.time() - start_time) < 3:
                if self.serial_connection.in_waiting > 0:
                    try:
                        line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            response_lines.append(line)
                            logger.info(f"아두이노 응답: {line}")
                            if "ACK:" in line:
                                break
                    except Exception as e:
                        logger.warning(f"응답 읽기 중 오류: {e}")
                        break
                time.sleep(0.1)
            
            ack_received = any("ACK:" in line for line in response_lines)
            
            return {
                "success": True,
                "message": f"펌프{pump_id} {state} 제어 완료",
                "command": command,
                "response": " | ".join(response_lines),
                "ack_received": ack_received,
                "pump_id": pump_id,
                "new_state": state
            }
            
        except Exception as e:
            logger.error(f"펌프 제어 실패: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_pump_status(self) -> Dict[str, Any]:
        """펌프 상태 직접 확인"""
        if self.arduino_port == "SIMULATION":
            # 시뮬레이션 응답
            import random
            return {
                "success": True,
                "pump_status": {
                    "pump1": random.choice(["ON", "OFF"]),
                    "pump2": random.choice(["ON", "OFF"])
                },
                "simulation": True
            }
        
        if not self.serial_connection or not self.serial_connection.is_open:
            return {"success": False, "error": "아두이노에 연결되지 않았습니다"}
        
        try:
            # 버퍼 비우기
            self.serial_connection.reset_input_buffer()
            
            # 펌프 상태 요청
            self.serial_connection.write(b"PUMP_STATUS\n")
            self.serial_connection.flush()
            logger.info("펌프 상태 요청 전송")
            
            # 응답 읽기
            response_lines = []
            start_time = time.time()
            while (time.time() - start_time) < 3:
                if self.serial_connection.in_waiting > 0:
                    try:
                        line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            response_lines.append(line)
                            logger.info(f"펌프 상태 응답: {line}")
                            if "PUMP1_STATUS:" in line or "PUMP2_STATUS:" in line:
                                break
                    except Exception as e:
                        logger.warning(f"상태 응답 읽기 중 오류: {e}")
                        break
                time.sleep(0.1)
            
            if response_lines:
                pump_status = {}
                for line in response_lines:
                    if "PUMP1_STATUS:" in line:
                        parts = line.split(',')
                        for part in parts:
                            if "PUMP1_STATUS:" in part:
                                pump_status["pump1"] = part.split(':')[1].strip()
                            elif "PUMP2_STATUS:" in part:
                                pump_status["pump2"] = part.split(':')[1].strip()
                
                return {
                    "success": True,
                    "pump_status": pump_status,
                    "raw_response": " | ".join(response_lines)
                }
            else:
                return {"success": False, "error": "펌프 상태 응답을 받지 못했습니다"}
                
        except Exception as e:
            logger.error(f"펌프 상태 확인 실패: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def is_connected(self) -> bool:
        """연결 상태 확인 (실제 통신 테스트 포함)"""
        if self.arduino_port == "SIMULATION":
            return True
        
        # 시리얼 연결 객체가 없으면 연결되지 않음
        if not self.serial_connection:
            self.arduino_port = None
            return False
            
        # 시리얼 연결 객체가 올바르지 않으면 연결되지 않음
        if not hasattr(self.serial_connection, 'is_open'):
            self.serial_connection = None
            self.arduino_port = None
            return False
            
        try:
            # 시리얼 포트가 열려있는지 확인
            if not self.serial_connection.is_open:
                self.serial_connection = None
                self.arduino_port = None
                return False
            
            # 실제 통신 테스트 (아두이노 응답 확인)
            try:
                # 실제 아두이노 통신 테스트
                self.serial_connection.reset_input_buffer()
                self.serial_connection.write(b"PING\n")
                self.serial_connection.flush()
                time.sleep(0.3)
                
                # 아두이노 응답 확인
                has_response = self.serial_connection.in_waiting > 0
                if has_response:
                    response = self.serial_connection.read(self.serial_connection.in_waiting)
                    logger.debug(f"아두이노 핑 응답: {response}")
                
                # 포트가 실제로 존재하는지 OS 레벨에서도 확인
                import os
                if self.arduino_port and self.arduino_port != "SIMULATION":
                    # Windows COM 포트 체크
                    if self.arduino_port.startswith("COM"):
                        try:
                            # 다른 시리얼 연결로 포트 존재 여부 재확인
                            test_serial = serial.Serial(self.arduino_port, 115200, timeout=0.1)
                            test_serial.close()
                        except serial.SerialException:
                            # COM 포트가 실제로 존재하지 않음
                            logger.warning(f"COM 포트 {self.arduino_port}가 더 이상 존재하지 않습니다")
                            self.disconnect()
                            return False
                    # Linux/Unix 시리얼 포트 체크  
                    elif self.arduino_port.startswith("/dev/"):
                        if not os.path.exists(self.arduino_port):
                            logger.warning(f"시리얼 포트 {self.arduino_port}가 더 이상 존재하지 않습니다")
                            self.disconnect()
                            return False
                
                # 응답이 없으면 실제 아두이노가 아닐 가능성이 높음
                if not has_response:
                    logger.warning(f"포트 {self.arduino_port}에서 아두이노 응답이 없습니다 (실제 아두이노가 아님)")
                    self.disconnect()
                    return False
                
                return True
                
            except (serial.SerialException, OSError, AttributeError) as e:
                logger.warning(f"아두이노 연결이 끊어짐: {e}")
                # 연결이 끊어진 경우 정리
                self.disconnect()
                return False
                
        except Exception as e:
            logger.error(f"연결 상태 확인 중 오류: {e}")
            # 연결 객체가 손상된 경우 정리
            self.disconnect()
            return False