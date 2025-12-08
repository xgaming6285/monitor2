with open(r'E:\GitProjects\monitor2\simple_output.txt', 'w') as f:
    f.write("Python works!\n")
    
    import sys
    sys.path.insert(0, r'C:\Users\EVLSV69\AppData\Local\WindowsUpdate\agent')
    
    try:
        from src.monitors.keystroke_logger import KeystrokeLogger
        f.write("KeystrokeLogger import: OK\n")
    except Exception as e:
        f.write(f"KeystrokeLogger import ERROR: {e}\n")
    
    try:
        from src.monitors.clipboard_monitor import ClipboardMonitor
        f.write("ClipboardMonitor import: OK\n")
    except Exception as e:
        f.write(f"ClipboardMonitor import ERROR: {e}\n")
    
    try:
        from src.main import MonitoringAgent
        f.write("MonitoringAgent import: OK\n")
    except Exception as e:
        f.write(f"MonitoringAgent import ERROR: {e}\n")
        import traceback
        f.write(traceback.format_exc())

print("Test complete")
