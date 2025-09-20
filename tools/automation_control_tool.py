# tools/automation_control_tool.py - 자동화 시스템 제어 도구

import time
from typing import Dict, Any, Optional
from services.autonomous_agent import get_autonomous_agent
from services.logging_system import get_automation_logger, EventType, LogLevel
from utils.logger import setup_logger
from utils.helpers import get_current_timestamp, create_error_response, create_success_response, get_lm_studio_client
import streamlit as st

logger = setup_logger(__name__)

def automation_control_tool(**kwargs) -> Dict[str, Any]:
    """자동화 시스템 제어 도구
    
    Actions:
    - start: 자동화 시작
    - stop: 자동화 중단
    - status: 현재 상태 조회
    - debug_arduino: Arduino 연결 상태 및 디버깅 정보
    - test_arduino_connection: Arduino 연결 테스트
    - get_logs: 로그 조회
    - get_history: 의사결정 이력 조회
    - manual_control: 수동 펌프 제어
    - update_config: 설정 변경
    """
    
    # LM Studio 클라이언트 가져오기
    lm_client = get_lm_studio_client()
    if not lm_client:
        return {
            'success': False,
            'error': '시스템이 초기화되지 않았습니다. 먼저 시스템 초기화를 실행해주세요.'
        }
    
    automation_agent = get_autonomous_agent(lm_client)
    automation_logger = get_automation_logger()
    
    action = kwargs.get('action', 'status')
    
    try:
        if action == 'start':
            return _start_automation(automation_agent, automation_logger)
        
        elif action == 'stop':
            return _stop_automation(automation_agent, automation_logger)
        
        elif action == 'status':
            return _get_status(automation_agent, automation_logger)
        
        elif action == 'get_logs':
            limit = kwargs.get('limit', 50)
            level = kwargs.get('level', 'INFO')
            reservoir_id = kwargs.get('reservoir_id')
            
            return _get_logs(automation_logger, limit, level, reservoir_id)
        
        elif action == 'debug_arduino':
            return _debug_arduino_connection(automation_logger)
        
        elif action == 'test_arduino_connection':
            return _test_arduino_connection(automation_logger)
        
        else:
            return {
                'success': False,
                'error': f'알 수 없는 액션: {action}',
                'available_actions': ['start', 'stop', 'status', 'debug_arduino', 'test_arduino_connection', 'get_logs']
            }
            
    except Exception as e:
        logger.error(f"자동화 제어 도구 오류: {e}")
        return {
            'success': False,
            'error': str(e),
            'message': '자동화 시스템 제어 중 오류 발생'
        }

def _start_automation(automation_agent, automation_logger) -> Dict[str, Any]:
    """AI 자동화 에이전트 시작"""
    try:
        automation_logger.info(
            EventType.SYSTEM, 
            "system", 
            "AI 자동화 에이전트 시작 요청"
        )
        
        if not automation_agent:
            return {
                'success': False,
                'error': 'AI 에이전트를 초기화할 수 없습니다'
            }
        
        success = automation_agent.start_monitoring()
        
        if success:
            # === 전체 상태 동기화 ===
            # 1. 세션 상태 업데이트
            st.session_state.automation_status = True
            st.session_state.autonomous_monitoring = True
            
            # 2. 글로벌 상태 동기화
            try:
                from utils.state_manager import sync_automation_status
                sync_automation_status(True, True)
            except Exception as sync_error:
                automation_logger.warning(EventType.SYSTEM, "system", f"글로벌 상태 동기화 오류: {sync_error}")
            
            automation_logger.info(
                EventType.SYSTEM,
                "system", 
                "AI 자동화 에이전트 시작 완료 - 모든 상태 동기화됨"
            )
            
            return {
                'success': True,
                'message': '🤖 EXAONE AI 자동화 에이전트가 시작되었습니다! 30초마다 시스템을 분석하고 자동으로 조치합니다.',
                'status': automation_agent.get_status(),
                'details': {
                    'agent_type': 'EXAONE 4.0.1.2B',
                    'decision_interval': '30초',
                    'monitoring': '실시간'
                }
            }
        else:
            automation_logger.error(
                EventType.ERROR,
                "system",
                "AI 자동화 에이전트 시작 실패"
            )
            
            return {
                'success': False,
                'error': 'AI 자동화 에이전트 시작에 실패했습니다'
            }
            
    except Exception as e:
        automation_logger.error(
            EventType.ERROR,
            "system",
            f"AI 자동화 시작 중 오류: {str(e)}"
        )
        raise

def _stop_automation(automation_agent, automation_logger) -> Dict[str, Any]:
    """AI 자동화 에이전트 중단"""
    try:
        automation_logger.warning(
            EventType.SYSTEM,
            "system",
            "AI 자동화 에이전트 중단 요청"
        )
        
        if automation_agent:
            success = automation_agent.stop_monitoring()
        else:
            success = True
        
        # === 전체 상태 동기화 ===
        # 1. 세션 상태 업데이트
        st.session_state.automation_status = False
        st.session_state.autonomous_monitoring = False
        
        # 2. 글로벌 상태 동기화
        try:
            from utils.state_manager import sync_automation_status
            sync_automation_status(False, False)
        except Exception as sync_error:
            automation_logger.warning(EventType.SYSTEM, "system", f"글로벌 상태 동기화 오류: {sync_error}")
        
        automation_logger.info(
            EventType.SYSTEM,
            "system",
            "AI 자동화 에이전트 중단 완료 - 모든 상태 동기화됨"
        )
        
        return {
            'success': True,
            'message': '🛑 AI 자동화 에이전트가 중단되었습니다',
            'final_status': automation_agent.get_status() if automation_agent else {'is_running': False}
        }
        
    except Exception as e:
        automation_logger.error(
            EventType.ERROR,
            "system",
            f"AI 자동화 중단 중 오류: {str(e)}"
        )
        raise

def _get_status(automation_agent, automation_logger) -> Dict[str, Any]:
    """AI 에이전트 상태 조회 - 실제 실행 상태 확인"""
    try:
        # 실제 에이전트 실행 상태 확인
        agent_status = automation_agent.get_status() if automation_agent else {'is_running': False}
        agent_running = agent_status.get('is_running', False) if agent_status else False
        
        # 세션 상태의 automation_status와 비교
        session_automation = getattr(st.session_state, 'automation_status', False)
        
        # 실제 실행 상태를 우선으로 함
        actual_running = agent_running
        
        # 글로벌 상태 관리자에서 확인
        try:
            from utils.state_manager import get_automation_status
            global_automation, global_monitoring = get_automation_status()
        except:
            global_automation, global_monitoring = session_automation, False
        
        recent_logs = automation_logger.get_recent_logs(limit=10, level=LogLevel.INFO)
        
        # 시스템 상태 수집
        reservoir_status = getattr(st.session_state, 'reservoir_data', {})
        simulation_mode = getattr(st.session_state, 'simulation_mode', True)
        
        # 위험 상황 분석
        critical_reservoirs = []
        warning_reservoirs = []
        
        for res_id, data in reservoir_status.items():
            water_level = data.get('water_level', 0)
            alert_level = data.get('alert_level', 100)
            
            if water_level >= alert_level:
                critical_reservoirs.append(res_id)
            elif water_level >= alert_level * 0.8:
                warning_reservoirs.append(res_id)
        
        # 상태 불일치 로깅
        if actual_running != global_automation:
            automation_logger.warning(
                EventType.SYSTEM,
                "status_check",
                f"상태 불일치 감지 - 실제: {actual_running}, 글로벌: {global_automation}, 세션: {session_automation}"
            )
        
        # 사용자 친화적인 메시지 생성
        status_icon = "🟢" if actual_running else "🔴"
        status_text = "활성" if actual_running else "비활성"
        consistency_text = "일관됨" if actual_running == global_automation == session_automation else "불일치"
        
        # 배수지 상태 요약
        health_summary = []
        if critical_reservoirs:
            health_summary.append(f"🚨 위험: {len(critical_reservoirs)}개 배수지")
        if warning_reservoirs:
            health_summary.append(f"⚠️ 경고: {len(warning_reservoirs)}개 배수지")
        if not critical_reservoirs and not warning_reservoirs:
            health_summary.append("✅ 모든 배수지 정상")
        
        # 최근 로그 요약
        log_summary = []
        if recent_logs:
            error_logs = [log for log in recent_logs if log['level'] in ['ERROR', 'CRITICAL']]
            if error_logs:
                log_summary.append(f"❌ 최근 오류: {len(error_logs)}건")
            else:
                log_summary.append("✅ 최근 오류 없음")
        
        return {
            'success': True,
            'is_running': actual_running,
            'automation_active': session_automation,
            'global_automation': global_automation,
            'simulation_mode': simulation_mode,
            'system_health': {
                'critical_reservoirs': critical_reservoirs,
                'warning_reservoirs': warning_reservoirs,
                'total_reservoirs': len(reservoir_status)
            },
            'status_summary': {
                'agent_running': actual_running,
                'session_status': session_automation,
                'global_status': global_automation,
                'consistent': actual_running == global_automation == session_automation
            },
            'formatted_status': {
                'main_status': f'{status_icon} AI 자동화 에이전트: {status_text}',
                'consistency': f'상태 동기화: {consistency_text}',
                'system_health': ' | '.join(health_summary) if health_summary else '시스템 정상',
                'recent_logs': ' | '.join(log_summary) if log_summary else '로그 없음',
                'simulation_mode': '🔄 시뮬레이션 모드' if simulation_mode else '⚡ 실제 모드'
            },
            'message': f'AI 자동화 에이전트 상태: {status_icon} {status_text} (상태 동기화: {consistency_text})',
            'detailed_report': f"""
## 🤖 AI 자동화 시스템 상태

**메인 상태:** {status_icon} {status_text}  
**상태 동기화:** {consistency_text}  
**운영 모드:** {'🔄 시뮬레이션' if simulation_mode else '⚡ 실제'}  

### 📊 시스템 건강도
{' | '.join(health_summary)}

### 📝 최근 활동
{' | '.join(log_summary)}

### 🔧 상세 정보
- 실제 에이전트 실행: {'예' if actual_running else '아니오'}
- 세션 상태: {'활성' if session_automation else '비활성'}
- 글로벌 상태: {'활성' if global_automation else '비활성'}
- 총 배수지 수: {len(reservoir_status)}개
            """.strip()
        }
        
    except Exception as e:
        logger.error(f"상태 조회 중 오류: {e}")
        raise


def _get_logs(automation_logger, limit: int, level: str, reservoir_id: Optional[str]) -> Dict[str, Any]:
    """로그 조회"""
    try:
        level_enum = getattr(LogLevel, level.upper(), LogLevel.INFO)
        
        if reservoir_id:
            logs = automation_logger.get_logs_by_reservoir(reservoir_id, limit)
            message = f"{reservoir_id} 배수지 로그 {len(logs)}개 조회"
        else:
            logs = automation_logger.get_recent_logs(limit, level_enum)
            message = f"전체 로그 {len(logs)}개 조회"
        
        return {
            'success': True,
            'logs': logs,
            'total_count': len(logs),
            'level_filter': level,
            'reservoir_filter': reservoir_id,
            'message': message
        }
        
    except Exception as e:
        logger.error(f"로그 조회 중 오류: {e}")
        raise


def _debug_arduino_connection(automation_logger) -> Dict[str, Any]:
    """Arduino 연결 상태 및 디버깅 정보 제공"""
    try:
        from utils.helpers import get_arduino_tool
        import platform
        import os
        import subprocess
        
        debug_info = {
            "success": True,
            "timestamp": get_current_timestamp(),
            "system_info": {},
            "arduino_status": {},
            "connection_diagnosis": {},
            "recommendations": []
        }
        
        # === 시스템 정보 수집 ===
        debug_info["system_info"] = {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "is_wsl": os.path.exists('/proc/version') and 'microsoft' in open('/proc/version').read().lower() if os.path.exists('/proc/version') else False,
            "python_version": platform.python_version(),
            "working_directory": os.getcwd()
        }
        
        # === Arduino 도구 상태 확인 ===
        try:
            arduino_tool = get_arduino_tool()
            
            if arduino_tool is not None:
                debug_info["arduino_status"] = {
                    "tool_imported": True,
                    "current_port": getattr(arduino_tool, 'arduino_port', None),
                    "serial_connection_exists": arduino_tool.serial_connection is not None,
                    "is_connected": arduino_tool._is_connected(),
                    "baud_rate": arduino_tool.baud_rate,
                    "timeout": arduino_tool.timeout
                }
            else:
                debug_info["arduino_status"] = {
                    "tool_imported": False,
                    "initialization_error": "Arduino 도구 생성 실패"
                }
            
            if arduino_tool and arduino_tool.serial_connection:
                try:
                    debug_info["arduino_status"]["serial_is_open"] = arduino_tool.serial_connection.is_open
                    debug_info["arduino_status"]["serial_port"] = arduino_tool.serial_connection.port
                except:
                    debug_info["arduino_status"]["serial_is_open"] = False
            
        except ImportError as e:
            debug_info["arduino_status"] = {
                "tool_imported": False,
                "import_error": str(e)
            }
        except Exception as e:
            debug_info["arduino_status"] = {
                "tool_imported": True,
                "initialization_error": str(e)
            }
        
        # === 연결 진단 ===
        diagnosis = debug_info["connection_diagnosis"]
        
        # WSL 환경 체크
        if debug_info["system_info"]["is_wsl"]:
            diagnosis["environment"] = "WSL2 환경"
            diagnosis["usb_requirements"] = "usbipd-win 필요"
            
            # WSL USB 포트 확인
            try:
                import glob
                usb_ports = glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyUSB*')
                diagnosis["available_usb_ports"] = usb_ports
                diagnosis["usb_ports_found"] = len(usb_ports) > 0
                
                if usb_ports:
                    # 포트 권한 확인
                    port_permissions = {}
                    for port in usb_ports:
                        try:
                            import stat
                            port_stat = os.stat(port)
                            port_permissions[port] = {
                                "readable": os.access(port, os.R_OK),
                                "writable": os.access(port, os.W_OK),
                                "mode": oct(stat.S_IMODE(port_stat.st_mode))
                            }
                        except Exception as e:
                            port_permissions[port] = {"error": str(e)}
                    
                    diagnosis["port_permissions"] = port_permissions
                
            except Exception as e:
                diagnosis["usb_port_check_error"] = str(e)
                
            # lsusb로 Arduino 장치 확인
            try:
                result = subprocess.run(['lsusb'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    arduino_devices = [line for line in result.stdout.split('\n') 
                                     if 'arduino' in line.lower() or '2341:' in line]
                    diagnosis["lsusb_arduino_devices"] = arduino_devices
                    diagnosis["arduino_device_detected"] = len(arduino_devices) > 0
                else:
                    diagnosis["lsusb_error"] = "lsusb 명령 실행 실패"
            except Exception as e:
                diagnosis["lsusb_error"] = str(e)
                
        elif debug_info["system_info"]["platform"] == "Windows":
            diagnosis["environment"] = "Windows 환경"
            # Windows COM 포트 스캔은 Arduino 도구에서 처리
            
        elif debug_info["system_info"]["platform"] == "Linux":
            diagnosis["environment"] = "Linux 환경"
            
        # === 권장사항 생성 ===
        recommendations = debug_info["recommendations"]
        
        if not debug_info["arduino_status"].get("is_connected", False):
            if debug_info["system_info"]["is_wsl"]:
                recommendations.extend([
                    "WSL2 환경에서 Arduino 연결 문제 해결 방법:",
                    "1. Windows PowerShell(관리자)에서: usbipd wsl list",
                    "2. Arduino 장치의 BUSID 확인",
                    "3. Windows PowerShell(관리자)에서: usbipd wsl attach --busid <BUSID>",
                    "4. WSL2에서: ls /dev/ttyACM* /dev/ttyUSB* 로 포트 확인",
                    "5. 권한 문제 시: sudo chmod 666 /dev/ttyACM0"
                ])
                
                if not diagnosis.get("usb_ports_found", False):
                    recommendations.append("⚠️ USB 포트가 감지되지 않았습니다. usbipd-win 설정을 확인하세요.")
                
                elif diagnosis.get("port_permissions"):
                    for port, perm in diagnosis["port_permissions"].items():
                        if not perm.get("writable", False):
                            recommendations.append(f"⚠️ {port} 포트 쓰기 권한 없음: sudo chmod 666 {port}")
                            
            else:
                recommendations.extend([
                    "Arduino 연결 확인사항:",
                    "1. Arduino가 USB로 연결되어 있는지 확인",
                    "2. Arduino 드라이버가 설치되어 있는지 확인", 
                    "3. 다른 프로그램에서 포트를 사용하고 있지 않은지 확인",
                    "4. Arduino IDE Serial Monitor가 닫혀있는지 확인"
                ])
        
        if not debug_info["arduino_status"].get("tool_imported", True):
            recommendations.append("❌ Arduino 도구 임포트 실패. 모듈 경로를 확인하세요.")
        
        # 자동화 로거에 디버깅 정보 기록
        automation_logger.info(
            "SYSTEM",
            "arduino_debug",
            "Arduino 연결 디버깅 실행",
            {
                "connected": debug_info["arduino_status"].get("is_connected", False),
                "port": debug_info["arduino_status"].get("current_port"),
                "environment": diagnosis.get("environment", "Unknown")
            }
        )
        
        # 사용자 친화적 메시지 생성
        connection_status = debug_info["arduino_status"].get("is_connected", False)
        current_port = debug_info["arduino_status"].get("current_port", "None")
        environment = diagnosis.get("environment", "Unknown")
        
        status_icon = "✅" if connection_status else "❌"
        
        debug_info["message"] = f"{status_icon} **Arduino 연결 디버깅 결과**"
        debug_info["detailed_report"] = f"""
## 🔧 Arduino 연결 디버깅 보고서

**연결 상태:** {status_icon} {'연결됨' if connection_status else '연결 안됨'}  
**현재 포트:** {current_port}  
**환경:** {environment}  

### 📊 시스템 정보
- **플랫폼:** {debug_info['system_info']['platform']}
- **WSL2 환경:** {'예' if debug_info['system_info']['is_wsl'] else '아니오'}
- **Python 버전:** {debug_info['system_info']['python_version']}

### 🔌 Arduino 상태
- **도구 임포트:** {'성공' if debug_info['arduino_status'].get('tool_imported', False) else '실패'}
- **연결 상태:** {'연결됨' if connection_status else '연결 안됨'}
- **현재 포트:** {current_port}
- **보드레이트:** {debug_info['arduino_status'].get('baud_rate', 'N/A')}

### 💡 권장사항
{chr(10).join('- ' + rec for rec in recommendations) if recommendations else '- 현재 특별한 조치가 필요하지 않습니다.'}
        """.strip()
        
        return debug_info
        
    except Exception as e:
        logger.error(f"Arduino 디버깅 중 오류: {e}")
        automation_logger.error(
            "ERROR",
            "arduino_debug", 
            f"Arduino 디버깅 중 오류: {str(e)}"
        )
        return create_error_response(str(e), "Arduino 디버깅 오류")


def _test_arduino_connection(automation_logger) -> Dict[str, Any]:
    """Arduino 연결 테스트 및 자동 연결 시도"""
    try:
        from utils.helpers import get_arduino_tool
        
        # Arduino 도구 생성
        arduino_tool = get_arduino_tool()
        
        if arduino_tool is None:
            return create_error_response("Arduino 도구를 생성할 수 없습니다", "Arduino 도구 초기화 실패")
        
        test_result = {
            "success": False,
            "timestamp": get_current_timestamp(),
            "connection_attempts": [],
            "final_status": {}
        }
        
        # 현재 연결 상태 확인
        initial_connected = arduino_tool._is_connected()
        test_result["initial_connection_status"] = initial_connected
        
        if initial_connected:
            # 이미 연결된 경우 통신 테스트
            automation_logger.info(
                "SYSTEM",
                "arduino_test",
                "Arduino 이미 연결됨 - 통신 테스트 실행"
            )
            
            comm_test = arduino_tool._test_communication()
            test_result["communication_test"] = comm_test
            
            if comm_test.get("success", False):
                test_result["success"] = True
                test_result["message"] = "✅ **Arduino 연결 및 통신 정상**"
                test_result["detailed_report"] = f"""
## ✅ Arduino 연결 테스트 성공

**현재 상태:** 연결됨 및 통신 정상  
**포트:** {arduino_tool.arduino_port}  
**통신 상태:** {comm_test.get('communication_status', '정상')}  

### 📊 통신 테스트 결과
- **총 데이터 청크:** {comm_test.get('total_data_chunks', 0)}개
- **총 수신 바이트:** {comm_test.get('total_bytes_received', 0)}
- **테스트 시간:** {comm_test.get('test_duration', 0)}초

### 💡 상태
Arduino가 정상적으로 연결되어 있고 통신이 가능합니다.
                """.strip()
        else:
            # 연결 시도
            automation_logger.info(
                "SYSTEM",
                "arduino_test", 
                "Arduino 연결되지 않음 - 자동 연결 시도"
            )
            
            # 자동 포트 검색 및 연결 시도
            attempt_count = 0
            max_attempts = 3
            
            while attempt_count < max_attempts and not arduino_tool._is_connected():
                attempt_count += 1
                attempt_info = {
                    "attempt": attempt_count,
                    "timestamp": get_current_timestamp("%H:%M:%S")
                }
                
                try:
                    # 연결 시도
                    connection_success = arduino_tool._connect_to_arduino()
                    attempt_info["connection_result"] = connection_success
                    attempt_info["port_found"] = arduino_tool.arduino_port
                    
                    if connection_success:
                        attempt_info["status"] = "성공"
                        # 연결 성공 후 간단한 통신 테스트
                        if arduino_tool.arduino_port != "SIMULATION":
                            comm_test = arduino_tool._test_communication()
                            attempt_info["communication_test"] = comm_test.get("success", False)
                        else:
                            attempt_info["communication_test"] = True  # 시뮬레이션 모드
                        break
                    else:
                        attempt_info["status"] = "실패"
                        
                except Exception as e:
                    attempt_info["status"] = "오류"
                    attempt_info["error"] = str(e)
                
                test_result["connection_attempts"].append(attempt_info)
                
                if attempt_count < max_attempts:
                    time.sleep(1)  # 다음 시도 전 대기
            
            # 최종 결과 확인
            final_connected = arduino_tool._is_connected()
            test_result["final_status"] = {
                "connected": final_connected,
                "port": arduino_tool.arduino_port,
                "attempts_made": attempt_count
            }
            
            if final_connected:
                test_result["success"] = True
                simulation_mode = arduino_tool.arduino_port == "SIMULATION"
                
                test_result["message"] = f"✅ **Arduino 연결 테스트 성공**"
                test_result["detailed_report"] = f"""
## ✅ Arduino 연결 테스트 성공

**최종 상태:** 연결됨  
**포트:** {arduino_tool.arduino_port}  
**시도 횟수:** {attempt_count}회  
**모드:** {'시뮬레이션' if simulation_mode else '실제 하드웨어'}  

### 📊 연결 과정
{chr(10).join(f"- 시도 {att['attempt']}: {att['status']} ({'포트: ' + str(att.get('port_found', 'None')) if att.get('port_found') else ''})" for att in test_result['connection_attempts'])}

### 💡 상태
Arduino가 성공적으로 연결되었습니다. {'시뮬레이션 모드에서' if simulation_mode else ''} 펌프 제어가 가능합니다.
                """.strip()
                
                automation_logger.info(
                    "SYSTEM",
                    "arduino_test",
                    f"Arduino 연결 테스트 성공 - {arduino_tool.arduino_port}",
                    {"port": arduino_tool.arduino_port, "attempts": attempt_count}
                )
            else:
                test_result["success"] = False
                test_result["message"] = f"❌ **Arduino 연결 테스트 실패**"
                test_result["detailed_report"] = f"""
## ❌ Arduino 연결 테스트 실패

**최종 상태:** 연결 실패  
**시도 횟수:** {attempt_count}회  

### 📊 연결 시도 내역
{chr(10).join(f"- 시도 {att['attempt']}: {att['status']} {('- ' + att.get('error', '')) if att.get('error') else ''}" for att in test_result['connection_attempts'])}

### 💡 권장사항
- Arduino가 USB로 제대로 연결되어 있는지 확인하세요
- Arduino 드라이버가 설치되어 있는지 확인하세요
- WSL2 환경인 경우 usbipd-win 설정을 확인하세요
- 다른 프로그램에서 시리얼 포트를 사용하고 있지 않은지 확인하세요

자세한 디버깅 정보는 'debug_arduino' 액션을 사용하세요.
                """.strip()
                
                automation_logger.error(
                    "ERROR", 
                    "arduino_test",
                    f"Arduino 연결 테스트 실패 - {attempt_count}회 시도",
                    {"attempts": test_result["connection_attempts"]}
                )
        
        return test_result
        
    except Exception as e:
        logger.error(f"Arduino 연결 테스트 중 오류: {e}")
        automation_logger.error(
            "ERROR",
            "arduino_test",
            f"Arduino 연결 테스트 중 오류: {str(e)}"
        )
        return create_error_response(str(e), "Arduino 연결 테스트 오류")


# 편의 함수들
def start_automation() -> Dict[str, Any]:
    """AI 자동화 에이전트 시작 (편의 함수)"""
    return automation_control_tool(action='start')

def stop_automation() -> Dict[str, Any]:
    """AI 자동화 에이전트 중단 (편의 함수)"""
    return automation_control_tool(action='stop')

def get_automation_status() -> Dict[str, Any]:
    """AI 자동화 에이전트 상태 조회 (편의 함수)"""
    return automation_control_tool(action='status')