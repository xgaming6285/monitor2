import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { io } from 'socket.io-client';
import { 
  Monitor, Activity, Search, Settings, Bell, 
  Layout, Keyboard, Clipboard, FolderOpen, Cpu,
  Globe, ChevronRight, Wifi, WifiOff
} from 'lucide-react';

import ComputerList from './components/ComputerList';
import LiveFeed from './components/LiveFeed';
import Dashboard from './components/Dashboard';
import SearchPanel from './components/SearchPanel';

// Socket connection
const socket = io('http://localhost:5000/live', {
  transports: ['websocket', 'polling']
});

function Sidebar({ computers, selectedComputer, onSelectComputer }) {
  const location = useLocation();
  
  const navItems = [
    { path: '/', icon: Layout, label: 'Dashboard' },
    { path: '/live', icon: Activity, label: 'Live Feed' },
    { path: '/search', icon: Search, label: 'Search' },
    { path: '/settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <div className="w-64 bg-[#161b22] border-r border-[#30363d] flex flex-col h-screen">
      {/* Logo */}
      <div className="p-4 border-b border-[#30363d]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-teal-600 flex items-center justify-center">
            <Monitor className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="font-display font-bold text-lg">Monitor</h1>
            <p className="text-xs text-gray-500">Control Center</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="p-3 space-y-1">
        {navItems.map(({ path, icon: Icon, label }) => (
          <Link
            key={path}
            to={path}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${
              location.pathname === path
                ? 'bg-[#21262d] text-cyan-400 border border-[#30363d]'
                : 'text-gray-400 hover:text-gray-200 hover:bg-[#21262d]/50'
            }`}
          >
            <Icon className="w-5 h-5" />
            <span className="font-medium">{label}</span>
          </Link>
        ))}
      </nav>

      {/* Computers List */}
      <div className="flex-1 overflow-y-auto border-t border-[#30363d] mt-3">
        <div className="p-3">
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 px-3">
            Computers ({computers.length})
          </h2>
          <div className="space-y-1">
            {computers.map((computer) => (
              <button
                key={computer.id}
                onClick={() => onSelectComputer(computer)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left ${
                  selectedComputer?.id === computer.id
                    ? 'bg-cyan-500/10 border border-cyan-500/30 text-cyan-400'
                    : 'text-gray-400 hover:bg-[#21262d]/50 hover:text-gray-200'
                }`}
              >
                <div className={`w-2 h-2 rounded-full ${
                  computer.is_online ? 'status-online' : 'status-offline'
                }`} />
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate text-sm">{computer.computer_name}</p>
                  <p className="text-xs text-gray-500 truncate">{computer.username}</p>
                </div>
                {computer.is_online && (
                  <Wifi className="w-4 h-4 text-green-500" />
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Status */}
      <div className="p-3 border-t border-[#30363d]">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <div className="w-2 h-2 rounded-full status-online" />
          <span>Connected to server</span>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [computers, setComputers] = useState([]);
  const [selectedComputer, setSelectedComputer] = useState(null);
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);

  // Fetch computers on mount
  useEffect(() => {
    fetch('/api/computers')
      .then(res => res.json())
      .then(data => {
        setComputers(data.computers || []);
      })
      .catch(console.error);
  }, []);

  // Socket connection
  useEffect(() => {
    socket.on('connect', () => {
      console.log('Connected to server');
      setConnected(true);
    });

    socket.on('disconnect', () => {
      console.log('Disconnected from server');
      setConnected(false);
    });

    socket.on('new_event', (event) => {
      setEvents(prev => [event, ...prev].slice(0, 500));
    });

    socket.on('computer_registered', (computer) => {
      setComputers(prev => [computer, ...prev]);
    });

    socket.on('computer_status', (data) => {
      setComputers(prev => prev.map(c => 
        c.id === data.computer_id 
          ? { ...c, is_online: data.is_online, last_seen: data.last_seen }
          : c
      ));
    });

    return () => {
      socket.off('connect');
      socket.off('disconnect');
      socket.off('new_event');
      socket.off('computer_registered');
      socket.off('computer_status');
    };
  }, []);

  return (
    <Router>
      <div className="flex h-screen gradient-mesh">
        <Sidebar 
          computers={computers}
          selectedComputer={selectedComputer}
          onSelectComputer={setSelectedComputer}
        />
        
        <main className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={
              <Dashboard 
                computers={computers}
                events={events}
              />
            } />
            <Route path="/live" element={
              <LiveFeed 
                events={events}
                selectedComputer={selectedComputer}
              />
            } />
            <Route path="/search" element={
              <SearchPanel />
            } />
            <Route path="/settings" element={
              <div className="p-8">
                <h1 className="font-display text-2xl font-bold">Settings</h1>
                <p className="text-gray-500 mt-2">Configuration options coming soon...</p>
              </div>
            } />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;

