"""
Event Sender Module
Sends events to central server
"""
import requests
import threading
import time
from typing import List
from datetime import datetime

from ..config import AgentConfig, HEARTBEAT_INTERVAL, DEBUG_MODE, COMPUTER_NAME, USERNAME
import platform


class EventSender:
    """Sends events to the central monitoring server"""
    
    def __init__(self):
        self.config = AgentConfig()
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'MonitorAgent/1.0'
        })
        
        self.heartbeat_thread = None
        self.running = False
    
    def _get_api_url(self, endpoint: str) -> str:
        """Build API URL"""
        return f"{self.config.server_url}/api{endpoint}"
    
    def register(self) -> bool:
        """Register this computer with the server"""
        if self.config.api_key:
            if DEBUG_MODE:
                print("Already registered")
            return True
        
        try:
            response = self.session.post(
                self._get_api_url('/register'),
                json={
                    'computer_name': COMPUTER_NAME,
                    'username': USERNAME,
                    'os_version': f"{platform.system()} {platform.release()}",
                    'agent_version': '1.0.0'
                },
                timeout=10
            )
            
            if response.status_code == 201:
                data = response.json()
                self.config.update_credentials(
                    api_key=data['api_key'],
                    computer_id=data['computer_id']
                )
                
                # Update session headers
                self.session.headers['X-API-Key'] = data['api_key']
                
                if DEBUG_MODE:
                    print(f"Registered: {data['computer_id']}")
                return True
            else:
                if DEBUG_MODE:
                    print(f"Registration failed: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            if DEBUG_MODE:
                print(f"Registration error: {e}")
            return False
    
    def send_events(self, events: List[dict]) -> bool:
        """
        Send a batch of events to the server
        
        Returns True if successful
        """
        if not self.config.api_key:
            if not self.register():
                return False
        
        try:
            self.session.headers['X-API-Key'] = self.config.api_key
            
            response = self.session.post(
                self._get_api_url('/events'),
                json={'events': events},
                timeout=15
            )
            
            if response.status_code == 200:
                return True
            elif response.status_code == 401:
                # API key invalid, try to re-register
                self.config.api_key = None
                return self.register() and self.send_events(events)
            else:
                if DEBUG_MODE:
                    print(f"Send failed: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            if DEBUG_MODE:
                print(f"Send error: {e}")
            return False
    
    def _heartbeat_loop(self):
        """Background thread for heartbeat"""
        while self.running:
            try:
                if self.config.api_key:
                    self.session.headers['X-API-Key'] = self.config.api_key
                    
                    response = self.session.post(
                        self._get_api_url('/heartbeat'),
                        json={'agent_version': '1.0.0'},
                        timeout=10
                    )
                    
                    if DEBUG_MODE and response.status_code == 200:
                        print("Heartbeat sent")
                        
            except requests.RequestException as e:
                if DEBUG_MODE:
                    print(f"Heartbeat error: {e}")
            
            time.sleep(HEARTBEAT_INTERVAL)
    
    def start_heartbeat(self):
        """Start the heartbeat thread"""
        if self.running:
            return
        
        self.running = True
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        
        if DEBUG_MODE:
            print("Heartbeat started")
    
    def stop_heartbeat(self):
        """Stop the heartbeat thread"""
        self.running = False
        
        if DEBUG_MODE:
            print("Heartbeat stopped")

