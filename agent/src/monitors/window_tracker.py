"""
Active Window Tracker Module
Monitors which application/window is in focus
"""
import threading
import time
from datetime import datetime

try:
    import win32gui
    import win32process
    import psutil
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

from ..config import DEBUG_MODE


class WindowTracker:
    """Tracks active window changes and focus duration"""
    
    def __init__(self, event_callback, keystroke_logger=None):
        """
        Initialize window tracker
        
        Args:
            event_callback: Function to call with window events
            keystroke_logger: Optional KeystrokeLogger to update context
        """
        self.event_callback = event_callback
        self.keystroke_logger = keystroke_logger
        
        self.current_window = None
        self.current_process = None
        self.current_exe = None
        self.window_start_time = None
        
        self.running = False
        self.thread = None
        self.poll_interval = 0.5  # Check every 500ms
    
    def _get_active_window_info(self):
        """Get information about the currently active window"""
        if not HAS_WIN32:
            return None, None, None
        
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None, None, None
            
            # Get window title
            window_title = win32gui.GetWindowText(hwnd)
            
            # Get process info
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                process = psutil.Process(pid)
                process_name = process.name()
                exe_path = process.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                process_name = 'unknown'
                exe_path = ''
            
            return window_title, process_name, exe_path
            
        except Exception as e:
            if DEBUG_MODE:
                print(f"Window tracking error: {e}")
            return None, None, None
    
    def _track_windows(self):
        """Background thread to track window changes"""
        while self.running:
            try:
                window_title, process_name, exe_path = self._get_active_window_info()
                
                # Check if window changed
                if window_title and (window_title != self.current_window or 
                                    process_name != self.current_process):
                    
                    now = datetime.utcnow()
                    
                    # Log previous window duration
                    if self.current_window and self.window_start_time:
                        duration = (now - self.window_start_time).total_seconds()
                        
                        self.event_callback({
                            'timestamp': self.window_start_time.isoformat(),
                            'event_type': 'window_focus',
                            'category': 'application',
                            'data': {
                                'window_title': self.current_window,
                                'process_name': self.current_process,
                                'exe_path': self.current_exe,
                                'duration_seconds': round(duration, 2),
                                'action': 'lost_focus'
                            }
                        })
                    
                    # Update current window
                    self.current_window = window_title
                    self.current_process = process_name
                    self.current_exe = exe_path
                    self.window_start_time = now
                    
                    # Update keystroke logger context
                    if self.keystroke_logger:
                        self.keystroke_logger.set_active_window(window_title, process_name)
                    
                    # Log new window focus
                    self.event_callback({
                        'timestamp': now.isoformat(),
                        'event_type': 'window_focus',
                        'category': 'application',
                        'data': {
                            'window_title': window_title,
                            'process_name': process_name,
                            'exe_path': exe_path,
                            'action': 'gained_focus'
                        }
                    })
                    
                    if DEBUG_MODE:
                        print(f"Window changed: {process_name} - {window_title[:50]}")
                
            except Exception as e:
                if DEBUG_MODE:
                    print(f"Window tracking error: {e}")
            
            time.sleep(self.poll_interval)
    
    def start(self):
        """Start the window tracker"""
        if self.running:
            return
        
        if not HAS_WIN32:
            if DEBUG_MODE:
                print("Window tracking requires pywin32 (Windows only)")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._track_windows, daemon=True)
        self.thread.start()
        
        if DEBUG_MODE:
            print("Window tracker started")
    
    def stop(self):
        """Stop the window tracker"""
        self.running = False
        
        # Log final window duration
        if self.current_window and self.window_start_time:
            duration = (datetime.utcnow() - self.window_start_time).total_seconds()
            self.event_callback({
                'timestamp': self.window_start_time.isoformat(),
                'event_type': 'window_focus',
                'category': 'application',
                'data': {
                    'window_title': self.current_window,
                    'process_name': self.current_process,
                    'exe_path': self.current_exe,
                    'duration_seconds': round(duration, 2),
                    'action': 'tracking_stopped'
                }
            })
        
        if DEBUG_MODE:
            print("Window tracker stopped")
    
    def get_current_window(self):
        """Get current active window info"""
        return {
            'window_title': self.current_window,
            'process_name': self.current_process,
            'exe_path': self.current_exe
        }

