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
    
    def __init__(self, event_callback, keystroke_logger=None, live_window_callback=None):
        """
        Initialize window tracker
        
        Args:
            event_callback: Function to call with window events
            keystroke_logger: Optional KeystrokeLogger to update context
            live_window_callback: Optional callback for real-time window state changes
        """
        self.event_callback = event_callback
        self.keystroke_logger = keystroke_logger
        self.live_window_callback = live_window_callback
        
        self.current_window = None
        self.current_process = None
        self.current_exe = None
        self.window_start_time = None
        
        # Track all open windows
        self.known_windows = {}  # hwnd -> {title, process, exe}
        
        self.running = False
        self.thread = None
        self.poll_interval = 0.5  # Check every 500ms
    
    def set_live_callback(self, callback):
        """Set or update the live window callback"""
        self.live_window_callback = callback
    
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
    
    def _get_all_windows(self):
        """Get all visible windows with titles"""
        if not HAS_WIN32:
            return {}
        
        windows = {}
        
        def enum_callback(hwnd, _):
            try:
                # Check if window is visible and has a title
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title and len(title.strip()) > 0:
                        # Get process info
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        try:
                            process = psutil.Process(pid)
                            process_name = process.name()
                            exe_path = process.exe()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            process_name = 'unknown'
                            exe_path = ''
                        
                        # Skip certain system windows
                        if process_name.lower() not in ['applicationframehost.exe', 'textinputhost.exe', 'searchhost.exe']:
                            windows[hwnd] = {
                                'title': title,
                                'process': process_name,
                                'exe': exe_path,
                                'hwnd': hwnd
                            }
            except Exception:
                pass
            return True
        
        try:
            win32gui.EnumWindows(enum_callback, None)
        except Exception as e:
            if DEBUG_MODE:
                print(f"Error enumerating windows: {e}")
        
        return windows
    
    def _send_live_window_event(self, event_type, window_data):
        """Send a live window event"""
        if not self.live_window_callback:
            return
        
        try:
            self.live_window_callback({
                'timestamp': datetime.utcnow().isoformat(),
                'event_type': event_type,
                'category': 'window',
                'data': window_data
            })
        except Exception as e:
            if DEBUG_MODE:
                print(f"Live window event error: {e}")
    
    def _track_windows(self):
        """Background thread to track window changes"""
        # Initial scan of all windows
        self.known_windows = self._get_all_windows()
        
        # Send initial window list
        for hwnd, win_data in self.known_windows.items():
            self._send_live_window_event('window_opened', {
                'window_title': win_data['title'],
                'process_name': win_data['process'],
                'exe_path': win_data['exe'],
                'hwnd': hwnd
            })
        
        while self.running:
            try:
                # Track active window changes (existing logic)
                window_title, process_name, exe_path = self._get_active_window_info()
                
                # Check if active window changed
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
                    
                    # Send live focus change event
                    self._send_live_window_event('window_focused', {
                        'window_title': window_title,
                        'process_name': process_name,
                        'exe_path': exe_path
                    })
                    
                    if DEBUG_MODE:
                        print(f"Window changed: {process_name} - {window_title[:50]}")
                
                # Track all windows for open/close detection
                current_windows = self._get_all_windows()
                current_hwnds = set(current_windows.keys())
                known_hwnds = set(self.known_windows.keys())
                
                # Detect newly opened windows
                for hwnd in current_hwnds - known_hwnds:
                    win_data = current_windows[hwnd]
                    self._send_live_window_event('window_opened', {
                        'window_title': win_data['title'],
                        'process_name': win_data['process'],
                        'exe_path': win_data['exe'],
                        'hwnd': hwnd
                    })
                    if DEBUG_MODE:
                        print(f"Window opened: {win_data['process']} - {win_data['title'][:50]}")
                
                # Detect closed windows
                closed_processes = set()
                for hwnd in known_hwnds - current_hwnds:
                    win_data = self.known_windows[hwnd]
                    closed_processes.add(win_data['process'])
                    self._send_live_window_event('window_closed', {
                        'window_title': win_data['title'],
                        'process_name': win_data['process'],
                        'exe_path': win_data['exe'],
                        'hwnd': hwnd
                    })
                    if DEBUG_MODE:
                        print(f"Window closed: {win_data['process']} - {win_data['title'][:50]}")
                
                # Check if any closed process has completely exited (no more windows)
                # If so, send a process_closed event to close ALL windows for that process
                for process_name in closed_processes:
                    # Check if this process still has any open windows
                    process_still_running = any(
                        w['process'] == process_name for w in current_windows.values()
                    )
                    if not process_still_running:
                        self._send_live_window_event('process_closed', {
                            'process_name': process_name
                        })
                        if DEBUG_MODE:
                            print(f"Process completely closed: {process_name}")
                
                # Update known windows
                self.known_windows = current_windows
                
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

