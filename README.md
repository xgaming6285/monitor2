# 🖥️ Desktop Monitor

Enterprise employee monitoring solution with **live user activity tracking** across multiple computers.

## Features

| Feature                  | Description                                        |
| ------------------------ | -------------------------------------------------- |
| **Keystroke Logging**    | Capture all keystrokes with application context    |
| **Application Tracking** | Monitor active windows, process launches/closes    |
| **Clipboard Monitoring** | Track copy/paste operations                        |
| **File Operations**      | Watch file creation, modification, deletion, moves |
| **Browser Activity**     | Track page visits, clicks, form inputs, scrolls    |
| **Live Dashboard**       | Real-time activity feed from all monitored PCs     |
| **Multi-PC Support**     | Central server monitors unlimited computers        |

## Architecture

```
┌─────────────────────────────────────────────┐
│           CENTRAL SERVER (Flask)            │
│  • REST API for agents                      │
│  • WebSocket for live updates               │
│  • PostgreSQL database                      │
│  • React Admin Dashboard                    │
└─────────────────────────────────────────────┘
                    ▲
                    │
        ┌───────────┼───────────┐
        │           │           │
   ┌────▼────┐ ┌────▼────┐ ┌────▼────┐
   │ Agent 1 │ │ Agent 2 │ │ Agent N │
   │ + Ext   │ │ + Ext   │ │ + Ext   │
   └─────────┘ └─────────┘ └─────────┘
```

## Quick Start

### 1. Start the Server (Docker)

```bash
docker-compose up -d
```

Or manually:

```bash
# Start PostgreSQL
docker run -d --name monitor-db \
  -e POSTGRES_USER=monitor \
  -e POSTGRES_PASSWORD=monitor123 \
  -e POSTGRES_DB=monitor_db \
  -p 5432:5432 \
  postgres:15-alpine

# Start Flask server
cd server
pip install -r requirements.txt
python run.py
```

### 2. Start the Dashboard

```bash
cd dashboard
npm install
npm run dev
```

Open http://localhost:3000

### 3. Deploy Agents

On each monitored computer:

```bash
cd agent
pip install -r requirements.txt
python -m src.main --server http://YOUR_SERVER:5000 --debug
```

### 4. Install Browser Extensions

**Chrome/Edge/Brave:**

1. Go to `chrome://extensions`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select `extensions/chromium` folder

**Firefox:**

1. Go to `about:debugging`
2. Click "This Firefox"
3. Click "Load Temporary Add-on"
4. Select `extensions/firefox/manifest.json`

## Project Structure

```
monitor/
├── server/                 # Central Flask server
│   ├── app/
│   │   ├── models.py       # Database models
│   │   ├── routes/
│   │   │   ├── api.py      # REST endpoints
│   │   │   └── websocket.py # Live updates
│   │   └── config.py
│   └── run.py
│
├── agent/                  # Desktop monitoring agent
│   └── src/
│       ├── monitors/       # Monitoring modules
│       │   ├── keystroke_logger.py
│       │   ├── window_tracker.py
│       │   ├── clipboard_monitor.py
│       │   ├── process_monitor.py
│       │   └── file_watcher.py
│       ├── collectors/     # Event handling
│       └── main.py
│
├── dashboard/              # React admin dashboard
│   └── src/
│       └── components/
│           ├── Dashboard.jsx
│           ├── LiveFeed.jsx
│           └── SearchPanel.jsx
│
├── extensions/             # Browser extensions
│   ├── chromium/           # Chrome/Edge/Brave
│   └── firefox/
│
└── docker-compose.yml
```

## API Endpoints

| Endpoint         | Method | Description                |
| ---------------- | ------ | -------------------------- |
| `/api/register`  | POST   | Register new computer      |
| `/api/events`    | POST   | Receive events from agents |
| `/api/events`    | GET    | Query events with filters  |
| `/api/heartbeat` | POST   | Agent health check         |
| `/api/computers` | GET    | List all computers         |
| `/api/stats`     | GET    | Dashboard statistics       |
| `/api/health`    | GET    | Server health check        |

## WebSocket Events

Connect to `ws://SERVER:5000/live`

| Event                 | Direction       | Description           |
| --------------------- | --------------- | --------------------- |
| `new_event`           | Server → Client | New monitoring event  |
| `computer_registered` | Server → Client | New computer added    |
| `computer_status`     | Server → Client | Online/offline status |

## Configuration

### Server Environment Variables

```bash
DATABASE_URL=postgresql://user:pass@host:5432/db
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-key
FLASK_ENV=production
```

### Agent Configuration

```bash
MONITOR_SERVER_URL=http://server:5000
MONITOR_API_KEY=your-api-key  # After registration
MONITOR_DEBUG=true
```

## Event Types

| Category        | Event Types                                                   |
| --------------- | ------------------------------------------------------------- |
| **Input**       | `keystroke`                                                   |
| **Application** | `window_focus`, `process_start`, `process_end`                |
| **Clipboard**   | `clipboard_copy`                                              |
| **File**        | `file_created`, `file_modified`, `file_deleted`, `file_moved` |
| **Browser**     | `page_load`, `click`, `form_input`, `scroll`, `tab_activated` |

## Development

### Running Tests

```bash
# Server tests
cd server
pytest

# Dashboard tests
cd dashboard
npm test
```

### Building Agent Executable

```bash
cd agent
pip install pyinstaller
pyinstaller --onefile --windowed --name MonitorAgent src/main.py
```

## Security Considerations

- All agent-server communication uses HTTPS in production
- API keys are unique per agent
- Passwords in form inputs are masked (`[PASSWORD]`)
- Local event cache is encrypted
- Admin dashboard requires authentication

## License

Proprietary - Internal Use Only
