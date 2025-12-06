"""
Clipboard Monitor Module
Tracks clipboard content changes
"""
import threading
import time
from datetime import datetime

try:
    import win32clipboard
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

from ..config import DEBUG_MODE


class ClipboardMonitor:
    """Monitors clipboard for copy operations"""
    
    def __init__(self, event_callback, window_tracker=None):
        """
        Initialize clipboard monitor
        
        Args:
            event_callback: Function to call with clipboard events
            window_tracker: Optional WindowTracker to get source app context
        """
        self.event_callback = event_callback
        self.window_tracker = window_tracker
        
        self.last_content = None
        self.last_content_hash = None
        
        self.running = False
        self.thread = None
        self.poll_interval = 0.5  # Check every 500ms
    
    def _get_clipboard_content(self):
        """Get current clipboard content"""
        if not HAS_WIN32:
            return None, None
        
        try:
            win32clipboard.OpenClipboard()
            
            content = None
            content_type = None
            
            # Try text first
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                content = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                content_type = 'text'
            elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                content = win32clipboard.GetClipboardData(win32con.CF_TEXT)
                if isinstance(content, bytes):
                    content = content.decode('utf-8', errors='ignore')
                content_type = 'text'
            
            # Check for files
            elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                import ctypes
                from ctypes import wintypes
                
                # Get file paths from clipboard
                try:
                    h_drop = win32clipboard.GetClipboardData(win32con.CF_HDROP)
                    # This is complex, so we'll just note that files were copied
                    content = "[Files copied]"
                    content_type = 'files'
                except Exception:
                    content = "[Files copied]"
                    content_type = 'files'
            
            # Check for image
            elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
                content = "[Image copied]"
                content_type = 'image'
            
            # Check for HTML
            html_format = win32clipboard.RegisterClipboardFormat("HTML Format")
            if win32clipboard.IsClipboardFormatAvailable(html_format):
                try:
                    html_content = win32clipboard.GetClipboardData(html_format)
                    if isinstance(html_content, bytes):
                        html_content = html_content.decode('utf-8', errors='ignore')
                    # Extract just the fragment
                    if 'StartFragment' in html_content:
                        content = html_content
                        content_type = 'html'
                except Exception:
                    pass
            
            win32clipboard.CloseClipboard()
            return content, content_type
            
        except Exception as e:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
            if DEBUG_MODE:
                print(f"Clipboard error: {e}")
            return None, None
    
    def _monitor_clipboard(self):
        """Background thread to monitor clipboard changes"""
        while self.running:
            try:
                content, content_type = self._get_clipboard_content()
                
                if content:
                    # Check if content changed
                    content_hash = hash(str(content)[:1000])  # Hash first 1000 chars
                    
                    if content_hash != self.last_content_hash:
                        self.last_content = content
                        self.last_content_hash = content_hash
                        
                        # Get source application context
                        source_window = None
                        source_process = None
                        if self.window_tracker:
                            window_info = self.window_tracker.get_current_window()
                            source_window = window_info.get('window_title')
                            source_process = window_info.get('process_name')
                        
                        # Truncate content for logging
                        display_content = content
                        if len(content) > 500:
                            display_content = content[:500] + '...[truncated]'
                        
                        self.event_callback({
                            'timestamp': datetime.utcnow().isoformat(),
                            'event_type': 'clipboard_copy',
                            'category': 'clipboard',
                            'data': {
                                'content': display_content,
                                'content_type': content_type,
                                'content_length': len(content),
                                'source_window': source_window,
                                'source_process': source_process
                            }
                        })
                        
                        if DEBUG_MODE:
                            print(f"Clipboard: {content_type} - {display_content[:50]}...")
                
            except Exception as e:
                if DEBUG_MODE:
                    print(f"Clipboard monitoring error: {e}")
            
            time.sleep(self.poll_interval)
    
    def start(self):
        """Start the clipboard monitor"""
        if self.running:
            return
        
        if not HAS_WIN32:
            if DEBUG_MODE:
                print("Clipboard monitoring requires pywin32 (Windows only)")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_clipboard, daemon=True)
        self.thread.start()
        
        if DEBUG_MODE:
            print("Clipboard monitor started")
    
    def stop(self):
        """Stop the clipboard monitor"""
        self.running = False
        
        if DEBUG_MODE:
            print("Clipboard monitor stopped")

