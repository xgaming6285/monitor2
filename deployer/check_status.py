"""
Monitor Agent Status Checker
Run to verify installation and check agent status.
"""
import os
import sys
import json
import winreg
import subprocess
import socket
from pathlib import Path


APP_NAME = "WindowsUpdateService"
INSTALL_DIR = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))) / 'WindowsUpdate'
CONFIG_FILE = INSTALL_DIR / 'config.json'
REG_RUN_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
REG_SERVICE_KEY = r"SOFTWARE\WindowsUpdateService"


def check_files():
    """Check if installation files exist"""
    print("\n[Files]")
    
    checks = [
        (INSTALL_DIR, "Installation directory"),
        (INSTALL_DIR / 'agent', "Agent source"),
        (INSTALL_DIR / 'extension', "Chrome extension"),
        (INSTALL_DIR / 'monitor_service.pyw', "Service script"),
        (CONFIG_FILE, "Configuration file"),
    ]
    
    all_ok = True
    for path, name in checks:
        exists = path.exists()
        status = "✓" if exists else "✗"
        print(f"  {status} {name}: {path}")
        if not exists:
            all_ok = False
    
    return all_ok


def check_config():
    """Check configuration"""
    print("\n[Configuration]")
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        print(f"  Dashboard IP: {config.get('dashboard_ip', 'N/A')}")
        print(f"  Server URL: {config.get('server_url', 'N/A')}")
        print(f"  Computer Name: {config.get('computer_name', 'N/A')}")
        print(f"  Username: {config.get('username', 'N/A')}")
        print(f"  Installed: {config.get('installed_at', 'N/A')}")
        
        return config.get('server_url')
    except Exception as e:
        print(f"  ✗ Could not read config: {e}")
        return None


def check_registry():
    """Check registry entries"""
    print("\n[Registry]")
    
    all_ok = True
    
    # Check Run key
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        print(f"  ✓ Startup entry: {value}")
    except:
        print(f"  ✗ Startup entry not found")
        all_ok = False
    
    # Check service key
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_SERVICE_KEY, 0, winreg.KEY_READ)
        install_path, _ = winreg.QueryValueEx(key, "InstallPath")
        dashboard_ip, _ = winreg.QueryValueEx(key, "DashboardIP")
        winreg.CloseKey(key)
        print(f"  ✓ Service key: InstallPath={install_path}")
        print(f"  ✓ Service key: DashboardIP={dashboard_ip}")
    except:
        print(f"  ✗ Service registry key not found")
        all_ok = False
    
    return all_ok


def check_scheduled_task():
    """Check scheduled task"""
    print("\n[Scheduled Task]")
    
    result = subprocess.run(
        ['schtasks', '/query', '/tn', APP_NAME],
        capture_output=True, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    
    if result.returncode == 0:
        print(f"  ✓ Task exists")
        # Parse task info
        for line in result.stdout.split('\n'):
            if 'Status' in line or 'Next Run' in line:
                print(f"    {line.strip()}")
        return True
    else:
        print(f"  ✗ Task not found")
        return False


def check_process():
    """Check if agent process is running"""
    print("\n[Process]")
    
    # Check for pythonw processes
    result = subprocess.run(
        ['tasklist', '/fi', 'imagename eq pythonw.exe'],
        capture_output=True, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    
    if 'pythonw.exe' in result.stdout:
        # Count processes
        count = result.stdout.count('pythonw.exe')
        print(f"  ✓ Agent running (pythonw.exe instances: {count})")
        return True
    else:
        print(f"  ✗ Agent not running")
        return False


def check_connection(server_url):
    """Check connection to dashboard"""
    print("\n[Network]")
    
    if not server_url:
        print("  ✗ No server URL configured")
        return False
    
    # Extract host and port
    try:
        from urllib.parse import urlparse
        parsed = urlparse(server_url)
        host = parsed.hostname
        port = parsed.port or 5000
    except:
        print(f"  ✗ Invalid server URL: {server_url}")
        return False
    
    # Test connection
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"  ✓ Dashboard reachable at {host}:{port}")
            return True
        else:
            print(f"  ✗ Dashboard not reachable at {host}:{port}")
            return False
    except Exception as e:
        print(f"  ✗ Connection test failed: {e}")
        return False


def check_firewall():
    """Check firewall rules"""
    print("\n[Firewall]")
    
    result = subprocess.run(
        ['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=all'],
        capture_output=True, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    
    found_rules = []
    for port in [5000, 5001]:
        if f"Windows Update Helper Port {port}" in result.stdout:
            found_rules.append(port)
    
    if found_rules:
        print(f"  ✓ Firewall rules exist for ports: {found_rules}")
        return True
    else:
        print(f"  ✗ Firewall rules not found")
        return False


def check_logs():
    """Check recent log entries"""
    print("\n[Logs]")
    
    log_files = [
        (INSTALL_DIR / 'update.log', "Installation log"),
        (INSTALL_DIR / 'service.log', "Service log"),
    ]
    
    for log_file, name in log_files:
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    last_lines = lines[-5:] if len(lines) >= 5 else lines
                    
                print(f"\n  {name} (last {len(last_lines)} entries):")
                for line in last_lines:
                    print(f"    {line.strip()}")
            except:
                print(f"  Could not read {name}")
        else:
            print(f"  {name}: Not found")


def main():
    print("=" * 60)
    print("  Monitor Agent Status Check")
    print("=" * 60)
    
    files_ok = check_files()
    server_url = check_config()
    registry_ok = check_registry()
    task_ok = check_scheduled_task()
    process_ok = check_process()
    connection_ok = check_connection(server_url)
    firewall_ok = check_firewall()
    check_logs()
    
    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    
    all_ok = all([files_ok, registry_ok, task_ok, process_ok, connection_ok, firewall_ok])
    
    if all_ok:
        print("\n  ✓ All checks passed. Agent is running correctly.")
    else:
        print("\n  ✗ Some checks failed. Review the output above.")
        print("\n  Troubleshooting:")
        if not files_ok:
            print("    - Run the installer again")
        if not registry_ok:
            print("    - Run installer as administrator")
        if not task_ok:
            print("    - Run installer as administrator")
        if not process_ok:
            print("    - Check service.log for errors")
            print("    - Try: python monitor_service.pyw (in install dir)")
        if not connection_ok:
            print("    - Verify dashboard is running")
            print("    - Check dashboard IP in config.json")
        if not firewall_ok:
            print("    - Run installer as administrator")
    
    print()
    input("Press Enter to exit...")


if __name__ == '__main__':
    main()
