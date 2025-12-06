"""
Process Monitor Module
Tracks application launches and closures
"""
import threading
import time
from datetime import datetime
from typing import Dict, Set

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from ..config import DEBUG_MODE


class ProcessMonitor:
    """Monitors process starts and stops"""
    
    # Processes to ignore (system processes)
    IGNORED_PROCESSES = {
        'system', 'idle', 'registry', 'smss.exe', 'csrss.exe',
        'wininit.exe', 'services.exe', 'lsass.exe', 'svchost.exe',
        'fontdrvhost.exe', 'dwm.exe', 'sihost.exe', 'taskhostw.exe',
        'ctfmon.exe', 'runtimebroker.exe', 'shellexperiencehost.exe',
        'searchindexer.exe', 'searchprotocolhost.exe', 'searchfilterhost.exe',
        'wmiprvse.exe', 'spoolsv.exe', 'audiodg.exe', 'conhost.exe',
        'dllhost.exe', 'msdtc.exe', 'sppsvc.exe', 'vds.exe', 'vssvc.exe'
    }
    
    def __init__(self, event_callback):
        """
        Initialize process monitor
        
        Args:
            event_callback: Function to call with process events
        """
        self.event_callback = event_callback
        
        self.known_processes: Dict[int, dict] = {}
        self.running = False
        self.thread = None
        self.poll_interval = 2  # Check every 2 seconds
    
    def _get_process_info(self, proc) -> dict:
        """Get information about a process"""
        try:
            return {
                'pid': proc.pid,
                'name': proc.name(),
                'exe': proc.exe() if proc.exe() else '',
                'cmdline': ' '.join(proc.cmdline()) if proc.cmdline() else '',
                'create_time': proc.create_time(),
                'username': proc.username() if proc.username() else ''
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
    
    def _should_ignore(self, process_name: str) -> bool:
        """Check if process should be ignored"""
        return process_name.lower() in self.IGNORED_PROCESSES
    
    def _scan_processes(self):
        """Scan current processes and detect changes"""
        current_pids: Set[int] = set()
        
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pid = proc.pid
                name = proc.name()
                current_pids.add(pid)
                
                # Skip ignored processes
                if self._should_ignore(name):
                    continue
                
                # Check if new process
                if pid not in self.known_processes:
                    info = self._get_process_info(proc)
                    if info:
                        self.known_processes[pid] = info
                        
                        # Skip if process is older than 5 seconds (was already running)
                        if time.time() - info['create_time'] < 5:
                            self.event_callback({
                                'timestamp': datetime.utcnow().isoformat(),
                                'event_type': 'process_start',
                                'category': 'application',
                                'data': {
                                    'process_name': info['name'],
                                    'exe_path': info['exe'],
                                    'command_line': info['cmdline'][:500],  # Truncate
                                    'pid': pid,
                                    'username': info['username']
                                }
                            })
                            
                            if DEBUG_MODE:
                                print(f"Process started: {info['name']} (PID: {pid})")
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Check for terminated processes
        terminated = set(self.known_processes.keys()) - current_pids
        for pid in terminated:
            info = self.known_processes.pop(pid, None)
            if info and not self._should_ignore(info['name']):
                duration = time.time() - info['create_time']
                
                self.event_callback({
                    'timestamp': datetime.utcnow().isoformat(),
                    'event_type': 'process_end',
                    'category': 'application',
                    'data': {
                        'process_name': info['name'],
                        'exe_path': info['exe'],
                        'pid': pid,
                        'duration_seconds': round(duration, 2)
                    }
                })
                
                if DEBUG_MODE:
                    print(f"Process ended: {info['name']} (PID: {pid})")
    
    def _monitor_processes(self):
        """Background thread to monitor process changes"""
        # Initial scan to populate known processes
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                info = self._get_process_info(proc)
                if info:
                    self.known_processes[proc.pid] = info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        while self.running:
            try:
                self._scan_processes()
            except Exception as e:
                if DEBUG_MODE:
                    print(f"Process monitoring error: {e}")
            
            time.sleep(self.poll_interval)
    
    def start(self):
        """Start the process monitor"""
        if self.running:
            return
        
        if not HAS_PSUTIL:
            if DEBUG_MODE:
                print("Process monitoring requires psutil")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_processes, daemon=True)
        self.thread.start()
        
        if DEBUG_MODE:
            print("Process monitor started")
    
    def stop(self):
        """Stop the process monitor"""
        self.running = False
        
        if DEBUG_MODE:
            print("Process monitor stopped")

