"""
Clipboard Monitor Module
Tracks clipboard content changes including text, files, and images
"""
import threading
import time
import io
import base64
from datetime import datetime

try:
    import win32clipboard
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

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
        """Get current clipboard content including images"""
        if not HAS_WIN32:
            return None, None, None
        
        try:
            win32clipboard.OpenClipboard()
            
            content = None
            content_type = None
            image_data = None
            
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
                try:
                    # Try to get file paths using shell32
                import ctypes
                from ctypes import wintypes
                
                    shell32 = ctypes.windll.shell32
                    h_drop = win32clipboard.GetClipboardData(win32con.CF_HDROP)
                    
                    # Get number of files
                    num_files = shell32.DragQueryFileW(h_drop, 0xFFFFFFFF, None, 0)
                    
                    if num_files > 0:
                        file_paths = []
                        for i in range(min(num_files, 10)):  # Limit to 10 files
                            buffer_size = shell32.DragQueryFileW(h_drop, i, None, 0) + 1
                            buffer = ctypes.create_unicode_buffer(buffer_size)
                            shell32.DragQueryFileW(h_drop, i, buffer, buffer_size)
                            file_paths.append(buffer.value)
                        
                        if num_files > 10:
                            content = '\n'.join(file_paths) + f'\n... and {num_files - 10} more files'
                        else:
                            content = '\n'.join(file_paths)
                        content_type = 'files'
                    else:
                    content = "[Files copied]"
                    content_type = 'files'
                except Exception as e:
                    if DEBUG_MODE:
                        print(f"File path extraction error: {e}")
                    content = "[Files copied]"
                    content_type = 'files'
            
            # Check for image (DIB format - Device Independent Bitmap)
            elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
                try:
                    if HAS_PIL:
                        # Get the DIB data
                        dib_data = win32clipboard.GetClipboardData(win32con.CF_DIB)
                        
                        # Convert DIB to image using PIL
                        # DIB starts with BITMAPINFOHEADER, we need to prepend file header
                        import struct
                        
                        # Parse BITMAPINFOHEADER
                        header_size = struct.unpack('<I', dib_data[0:4])[0]
                        width = struct.unpack('<i', dib_data[4:8])[0]
                        height = struct.unpack('<i', dib_data[8:12])[0]
                        bit_count = struct.unpack('<H', dib_data[14:16])[0]
                        
                        # Create BMP file header
                        file_size = 14 + len(dib_data)
                        bmp_header = struct.pack('<2sIHHI', b'BM', file_size, 0, 0, 14 + header_size)
                        
                        # Combine headers and data
                        bmp_data = bmp_header + dib_data
                        
                        # Open with PIL and convert to PNG for smaller size
                        img = Image.open(io.BytesIO(bmp_data))
                        
                        # Resize if too large (max 800px on longest side)
                        max_size = 800
                        if img.width > max_size or img.height > max_size:
                            ratio = min(max_size / img.width, max_size / img.height)
                            new_size = (int(img.width * ratio), int(img.height * ratio))
                            img = img.resize(new_size, Image.LANCZOS)
                        
                        # Convert to PNG base64
                        buffer = io.BytesIO()
                        img.save(buffer, format='PNG', optimize=True)
                        image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                        
                        content = f"[Image: {img.width}x{img.height}]"
                        content_type = 'image'
                    else:
                        content = "[Image copied - PIL not installed for capture]"
                        content_type = 'image'
                except Exception as e:
                    if DEBUG_MODE:
                        print(f"Image capture error: {e}")
                        import traceback
                        traceback.print_exc()
                    content = "[Image copied - capture failed]"
                    content_type = 'image'
            
            # Check for bitmap format as fallback
            elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_BITMAP):
                content = "[Bitmap copied]"
                content_type = 'image'
            
            # Check for HTML
            html_format = win32clipboard.RegisterClipboardFormat("HTML Format")
            if content is None and win32clipboard.IsClipboardFormatAvailable(html_format):
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
            return content, content_type, image_data
            
        except Exception as e:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
            if DEBUG_MODE:
                print(f"Clipboard error: {e}")
            return None, None, None
    
    def _monitor_clipboard(self):
        """Background thread to monitor clipboard changes"""
        while self.running:
            try:
                content, content_type, image_data = self._get_clipboard_content()
                
                if content:
                    # Check if content changed
                    # For images, include image_data in hash if available
                    hash_content = str(content)[:1000]
                    if image_data:
                        hash_content += image_data[:100]  # Include part of image data in hash
                    content_hash = hash(hash_content)
                    
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
                        if content_type != 'image' and len(content) > 500:
                            display_content = content[:500] + '...[truncated]'
                        
                        event_data = {
                            'content': display_content,
                            'content_type': content_type,
                            'content_length': len(content) if content_type != 'image' else (len(image_data) if image_data else 0),
                            'source_window': source_window,
                            'source_process': source_process
                        }
                        
                        # Include image data if available
                        if image_data:
                            event_data['image_base64'] = image_data
                        
                        self.event_callback({
                            'timestamp': datetime.now().isoformat(),
                            'event_type': 'clipboard_copy',
                            'category': 'clipboard',
                            'data': event_data
                        })
                        
                        if DEBUG_MODE:
                            if content_type == 'image' and image_data:
                                print(f"Clipboard: {content_type} - {len(image_data)} bytes base64")
                            else:
                            print(f"Clipboard: {content_type} - {display_content[:50]}...")
                
            except Exception as e:
                if DEBUG_MODE:
                    print(f"Clipboard monitoring error: {e}")
                    import traceback
                    traceback.print_exc()
            
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

