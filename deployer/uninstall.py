"""
Monitor Agent Uninstaller
Completely removes the monitoring agent from the system.
"""
import os
import sys
import subprocess
import ctypes
import winreg
import shutil
from pathlib import Path


APP_NAME = "WindowsUpdateService"
APP_DISPLAY_NAME = "Windows Update Helper"
INSTALL_DIR = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))) / 'WindowsUpdate'
REG_RUN_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
REG_SERVICE_KEY = r"SOFTWARE\WindowsUpdateService"


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


def stop_processes():
    """Stop all running agent processes"""
    print("Stopping agent processes...")
    
    subprocess.run(['taskkill', '/f', '/im', 'pythonw.exe'], 
                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    subprocess.run(['taskkill', '/f', '/im', 'python.exe'], 
                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    
    print("  Done")


def remove_scheduled_task():
    """Remove the scheduled task"""
    print("Removing scheduled task...")
    
    subprocess.run(['schtasks', '/delete', '/tn', APP_NAME, '/f'],
                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    
    print("  Done")


def remove_registry_entries():
    """Remove all registry entries"""
    print("Removing registry entries...")
    
    # Remove Run key
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
    except:
        pass
    
    # Remove service key
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_SERVICE_KEY)
    except:
        pass
    
    # Remove Chrome extension policy
    try:
        subprocess.run([
            'reg', 'delete', 
            r'HKCU\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist',
            '/f'
        ], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    except:
        pass
    
    # Remove native messaging host
    try:
        subprocess.run([
            'reg', 'delete',
            r'HKCU\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.monitor.native_host',
            '/f'
        ], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    except:
        pass
    
    print("  Done")


def remove_firewall_rules():
    """Remove firewall rules"""
    print("Removing firewall rules...")
    
    for port in [5000, 5001]:
        subprocess.run([
            'netsh', 'advfirewall', 'firewall', 'delete', 'rule',
            f'name={APP_DISPLAY_NAME} Port {port}'
        ], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        
        subprocess.run([
            'netsh', 'advfirewall', 'firewall', 'delete', 'rule',
            f'name={APP_DISPLAY_NAME} Port {port} Out'
        ], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    
    print("  Done")


def remove_files():
    """Remove installation directory"""
    print("Removing installation files...")
    
    if INSTALL_DIR.exists():
        try:
            shutil.rmtree(INSTALL_DIR)
            print("  Done")
        except Exception as e:
            print(f"  Warning: Some files could not be removed: {e}")
            print(f"  You may need to manually delete: {INSTALL_DIR}")
    else:
        print("  Installation directory not found")


def main():
    print("=" * 50)
    print("  Monitor Agent Uninstaller")
    print("=" * 50)
    print()
    
    # Check for admin privileges
    if not is_admin():
        print("Requesting administrator privileges...")
        run_as_admin()
        return
    
    # Confirm uninstall
    confirm = input("This will completely remove the monitoring agent. Continue? [y/N]: ")
    if confirm.lower() != 'y':
        print("Uninstall cancelled.")
        return
    
    print()
    
    stop_processes()
    remove_scheduled_task()
    remove_registry_entries()
    remove_firewall_rules()
    remove_files()
    
    print()
    print("=" * 50)
    print("  Uninstall Complete!")
    print("=" * 50)
    print()
    
    input("Press Enter to exit...")


if __name__ == '__main__':
    main()
