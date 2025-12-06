"""
File System Watcher Module
Monitors file operations in specified directories
"""
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import List

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from ..config import WATCHED_DIRECTORIES, DEBUG_MODE


class FileEventHandler(FileSystemEventHandler):
    """Handles file system events"""
    
    # File extensions to ignore
    IGNORED_EXTENSIONS = {
        '.tmp', '.temp', '.log', '.bak', '.swp', '.lock',
        '.db-journal', '.db-wal', '.db-shm'
    }
    
    # Directories to ignore
    IGNORED_DIRS = {
        '__pycache__', '.git', '.svn', 'node_modules',
        '.vscode', '.idea', 'venv', '.env'
    }
    
    def __init__(self, event_callback, window_tracker=None):
        super().__init__()
        self.event_callback = event_callback
        self.window_tracker = window_tracker
    
    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored"""
        path_obj = Path(path)
        
        # Check extension
        if path_obj.suffix.lower() in self.IGNORED_EXTENSIONS:
            return True
        
        # Check parent directories
        for parent in path_obj.parents:
            if parent.name in self.IGNORED_DIRS:
                return True
        
        return False
    
    def _get_file_info(self, path: str) -> dict:
        """Get file information"""
        try:
            stat = os.stat(path)
            return {
                'size_bytes': stat.st_size,
                'extension': Path(path).suffix.lower(),
                'is_hidden': Path(path).name.startswith('.')
            }
        except (OSError, FileNotFoundError):
            return {
                'size_bytes': 0,
                'extension': Path(path).suffix.lower(),
                'is_hidden': Path(path).name.startswith('.')
            }
    
    def _create_event(self, event_type: str, event: FileSystemEvent, extra_data: dict = None):
        """Create and send a file event"""
        if self._should_ignore(event.src_path):
            return
        
        # Get source application context
        source_process = None
        if self.window_tracker:
            window_info = self.window_tracker.get_current_window()
            source_process = window_info.get('process_name')
        
        file_info = self._get_file_info(event.src_path)
        
        data = {
            'file_path': event.src_path,
            'file_name': Path(event.src_path).name,
            'is_directory': event.is_directory,
            'source_process': source_process,
            **file_info
        }
        
        if extra_data:
            data.update(extra_data)
        
        self.event_callback({
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': f'file_{event_type}',
            'category': 'file',
            'data': data
        })
        
        if DEBUG_MODE:
            print(f"File {event_type}: {event.src_path}")
    
    def on_created(self, event: FileSystemEvent):
        """Handle file/directory creation"""
        self._create_event('created', event)
    
    def on_deleted(self, event: FileSystemEvent):
        """Handle file/directory deletion"""
        self._create_event('deleted', event)
    
    def on_modified(self, event: FileSystemEvent):
        """Handle file modification"""
        if not event.is_directory:  # Ignore directory modification events
            self._create_event('modified', event)
    
    def on_moved(self, event: FileSystemEvent):
        """Handle file/directory move/rename"""
        self._create_event('moved', event, {
            'destination_path': event.dest_path,
            'destination_name': Path(event.dest_path).name
        })


class FileWatcher:
    """Watches directories for file changes"""
    
    def __init__(self, event_callback, window_tracker=None, 
                 directories: List[str] = None):
        """
        Initialize file watcher
        
        Args:
            event_callback: Function to call with file events
            window_tracker: Optional WindowTracker for context
            directories: List of directories to watch (defaults to config)
        """
        self.event_callback = event_callback
        self.window_tracker = window_tracker
        self.directories = directories or WATCHED_DIRECTORIES
        
        self.observer = None
        self.running = False
    
    def _check_usb_drives(self):
        """Check for USB drives (Windows)"""
        try:
            import win32api
            import win32file
            
            drives = win32api.GetLogicalDriveStrings().split('\000')[:-1]
            usb_drives = []
            
            for drive in drives:
                try:
                    drive_type = win32file.GetDriveType(drive)
                    if drive_type == win32file.DRIVE_REMOVABLE:
                        usb_drives.append(drive)
                except Exception:
                    continue
            
            return usb_drives
            
        except ImportError:
            return []
    
    def start(self):
        """Start watching directories"""
        if self.running:
            return
        
        self.running = True
        self.observer = Observer()
        
        handler = FileEventHandler(self.event_callback, self.window_tracker)
        
        # Add configured directories
        for directory in self.directories:
            if os.path.exists(directory):
                try:
                    self.observer.schedule(handler, directory, recursive=True)
                    if DEBUG_MODE:
                        print(f"Watching: {directory}")
                except Exception as e:
                    if DEBUG_MODE:
                        print(f"Failed to watch {directory}: {e}")
        
        # Also watch USB drives
        for usb_drive in self._check_usb_drives():
            try:
                self.observer.schedule(handler, usb_drive, recursive=True)
                if DEBUG_MODE:
                    print(f"Watching USB: {usb_drive}")
            except Exception as e:
                if DEBUG_MODE:
                    print(f"Failed to watch USB {usb_drive}: {e}")
        
        self.observer.start()
        
        if DEBUG_MODE:
            print("File watcher started")
    
    def stop(self):
        """Stop watching directories"""
        self.running = False
        
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2)
            self.observer = None
        
        if DEBUG_MODE:
            print("File watcher stopped")
    
    def add_directory(self, directory: str):
        """Add a directory to watch"""
        if os.path.exists(directory) and self.observer:
            handler = FileEventHandler(self.event_callback, self.window_tracker)
            self.observer.schedule(handler, directory, recursive=True)
            if DEBUG_MODE:
                print(f"Added watch: {directory}")

