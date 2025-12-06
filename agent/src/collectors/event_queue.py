"""
Event Queue Module
Local queue for events with persistence
"""
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Callable
from collections import deque

from ..config import CACHE_DIR, CACHE_MAX_SIZE, BATCH_SIZE, BATCH_INTERVAL, DEBUG_MODE


class EventQueue:
    """Thread-safe event queue with local persistence"""
    
    def __init__(self, send_callback: Callable[[List[dict]], bool]):
        """
        Initialize event queue
        
        Args:
            send_callback: Function to send events to server
                          Returns True if successful
        """
        self.send_callback = send_callback
        self.queue = deque(maxlen=CACHE_MAX_SIZE)
        self.lock = threading.Lock()
        
        self.cache_file = CACHE_DIR / 'events_cache.json'
        self.running = False
        self.sender_thread = None
        
        # Load cached events
        self._load_cache()
    
    def _load_cache(self):
        """Load cached events from disk"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    cached = json.load(f)
                    for event in cached:
                        self.queue.append(event)
                if DEBUG_MODE:
                    print(f"Loaded {len(cached)} cached events")
        except Exception as e:
            if DEBUG_MODE:
                print(f"Failed to load cache: {e}")
    
    def _save_cache(self):
        """Save queue to disk for persistence"""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with self.lock:
                events = list(self.queue)
            with open(self.cache_file, 'w') as f:
                json.dump(events, f)
        except Exception as e:
            if DEBUG_MODE:
                print(f"Failed to save cache: {e}")
    
    def add_event(self, event: dict):
        """Add an event to the queue"""
        with self.lock:
            self.queue.append(event)
    
    def _get_batch(self) -> List[dict]:
        """Get a batch of events from the queue"""
        with self.lock:
            batch = []
            for _ in range(min(BATCH_SIZE, len(self.queue))):
                if self.queue:
                    batch.append(self.queue.popleft())
            return batch
    
    def _return_batch(self, batch: List[dict]):
        """Return failed batch to front of queue"""
        with self.lock:
            for event in reversed(batch):
                self.queue.appendleft(event)
    
    def _sender_loop(self):
        """Background thread to send events"""
        last_save = time.time()
        
        while self.running:
            try:
                # Get and send batch
                if len(self.queue) >= BATCH_SIZE or \
                   (len(self.queue) > 0 and time.time() % BATCH_INTERVAL < 1):
                    
                    batch = self._get_batch()
                    if batch:
                        success = self.send_callback(batch)
                        
                        if not success:
                            # Put events back in queue
                            self._return_batch(batch)
                            if DEBUG_MODE:
                                print(f"Failed to send batch, returned {len(batch)} events")
                        else:
                            if DEBUG_MODE:
                                print(f"Sent {len(batch)} events")
                
                # Periodically save cache
                if time.time() - last_save > 30:
                    self._save_cache()
                    last_save = time.time()
                    
            except Exception as e:
                if DEBUG_MODE:
                    print(f"Sender error: {e}")
            
            time.sleep(1)
        
        # Final cache save
        self._save_cache()
    
    def start(self):
        """Start the sender thread"""
        if self.running:
            return
        
        self.running = True
        self.sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self.sender_thread.start()
        
        if DEBUG_MODE:
            print("Event queue started")
    
    def stop(self):
        """Stop the sender thread"""
        self.running = False
        self._save_cache()
        
        if DEBUG_MODE:
            print("Event queue stopped")
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        return len(self.queue)

