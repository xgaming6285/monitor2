import React, { useState, useEffect, useRef, useCallback } from "react";
import { io } from "socket.io-client";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  FastForward,
  Rewind,
  Calendar,
  Clock,
  Monitor,
  Terminal,
  FileText,
  Globe,
  Keyboard,
  Volume2,
  VolumeX,
  Settings,
  Maximize2,
  Radio,
  Wifi,
  X,
  Layers,
} from "lucide-react";
import { format, parseISO, differenceInMilliseconds } from "date-fns";

// Process icons mapping
const PROCESS_ICONS = {
  "chrome.exe": Globe,
  "firefox.exe": Globe,
  "msedge.exe": Globe,
  "code.exe": Terminal,
  "cursor.exe": Terminal,
  "notepad.exe": FileText,
  "notepad++.exe": FileText,
  "word.exe": FileText,
  "excel.exe": FileText,
  default: Monitor,
};

function getProcessIcon(processName) {
  const lower = (processName || "").toLowerCase();
  for (const [key, Icon] of Object.entries(PROCESS_ICONS)) {
    if (lower.includes(key.replace(".exe", ""))) {
      return Icon;
    }
  }
  return PROCESS_ICONS.default;
}

function KeystrokeReplay() {
  // Time range state
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [selectedComputer, setSelectedComputer] = useState("");
  const [computers, setComputers] = useState([]);

  // Keystroke data
  const [keystrokeEvents, setKeystrokeEvents] = useState([]);
  const [loading, setLoading] = useState(false);

  // Playback state
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // Display state
  const [displayText, setDisplayText] = useState("");
  const [currentWindow, setCurrentWindow] = useState("");
  const [currentProcess, setCurrentProcess] = useState("");
  const [cursorVisible, setCursorVisible] = useState(true);
  const [soundEnabled, setSoundEnabled] = useState(false);

  // Timeline data - processed events with timing
  const [timelineEvents, setTimelineEvents] = useState([]);
  const [currentEventIndex, setCurrentEventIndex] = useState(-1);

  // Live mode state
  const [isLiveMode, setIsLiveMode] = useState(false);
  const [liveEvents, setLiveEvents] = useState([]);
  const [isLiveConnected, setIsLiveConnected] = useState(false);

  // Multi-window live text state - each window gets its own panel
  // Key: "process|window_title", Value: { text, process, window, lastActivity, computerName }
  const [liveWindows, setLiveWindows] = useState({});

  // Refs
  const playbackRef = useRef(null);
  const audioContextRef = useRef(null);
  const displayRef = useRef(null);
  const socketRef = useRef(null);

  // Fetch computers on mount
  useEffect(() => {
    fetch("/api/computers")
      .then((res) => res.json())
      .then((data) => setComputers(data.computers || []))
      .catch(console.error);

    // Set default time range (last 4 hours for more data)
    const now = new Date();
    const fourHoursAgo = new Date(now.getTime() - 4 * 60 * 60 * 1000);
    setEndTime(format(now, "yyyy-MM-dd'T'HH:mm"));
    setStartTime(format(fourHoursAgo, "yyyy-MM-dd'T'HH:mm"));
  }, []);

  // Cursor blink effect
  useEffect(() => {
    const interval = setInterval(() => {
      setCursorVisible((v) => !v);
    }, 530);
    return () => clearInterval(interval);
  }, []);

  // Live mode socket connection
  useEffect(() => {
    if (isLiveMode) {
      // Connect to socket for live updates
      socketRef.current = io("http://localhost:5000/live", {
        transports: ["websocket", "polling"],
      });

      socketRef.current.on("connect", () => {
        setIsLiveConnected(true);
        console.log("Live replay connected");

        // Subscribe to live keystrokes based on selected computer
        if (selectedComputer) {
          socketRef.current.emit("subscribe_live_keystrokes", {
            computer_id: selectedComputer,
          });
        } else {
          socketRef.current.emit("subscribe_live_keystrokes", {});
        }
      });

      socketRef.current.on("disconnect", () => {
        setIsLiveConnected(false);
        console.log("Live replay disconnected");
      });

      // Handle real-time individual keystrokes (truly live!)
      socketRef.current.on("live_keystroke", (event) => {
        // Filter by selected computer if any
        if (selectedComputer && event.computer_id !== selectedComputer) return;

        const key = event.data?.key || "";
        const windowTitle = event.data?.target_window || "Unknown Window";
        const processName = event.data?.target_process || "unknown";
        const computerName = event.computer_name || "Unknown";

        // Create a unique key for this window
        const windowKey = `${processName}|${windowTitle}`;

        setCurrentWindow(windowTitle);
        setCurrentProcess(processName);

        // Add to live events list (for sidebar)
        setLiveEvents((prev) =>
          [
            {
              ...event,
              id: Date.now(),
              data: { ...event.data, text: key },
            },
            ...prev,
          ].slice(0, 100)
        ); // Keep last 100 events, newest first

        // Update the specific window's text
        setLiveWindows((prev) => {
          const existing = prev[windowKey] || {
            text: "",
            process: processName,
            window: windowTitle,
            computerName: computerName,
            lastActivity: Date.now(),
          };

          let newText = existing.text;

          // Handle special keys
          if (key.startsWith("[")) {
            if (key === "[BACKSPACE]") {
              newText = newText.slice(0, -1);
            } else if (key === "[CTRL+BACKSPACE]") {
              // Delete previous word
              while (
                newText.length > 0 &&
                newText[newText.length - 1] === " "
              ) {
                newText = newText.slice(0, -1);
              }
              while (
                newText.length > 0 &&
                newText[newText.length - 1] !== " "
              ) {
                newText = newText.slice(0, -1);
              }
            } else if (key === "[ENTER]") {
              newText += "\n";
            } else if (key === "[TAB]") {
              newText += "    ";
            }
            // Ignore other special keys like [UP], [DOWN], [CTRL+C], etc.
          } else {
            // Regular character
            newText += key;
          }

          return {
            ...prev,
            [windowKey]: {
              ...existing,
              text: newText,
              lastActivity: Date.now(),
            },
          };
        });
      });

      // Also handle batched keystroke events (fallback for history)
      socketRef.current.on("new_event", (event) => {
        // Only process keystroke events (not live_keystroke)
        if (event.event_type !== "keystroke") return;

        // Filter by selected computer if any
        if (selectedComputer && event.computer_id !== selectedComputer) return;

        // This is a batched event - we can use it for the sidebar
        // but don't update live text since live_keystroke handles that
      });

      return () => {
        if (socketRef.current) {
          socketRef.current.disconnect();
          socketRef.current = null;
        }
      };
    } else {
      // Disconnect when leaving live mode
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
        setIsLiveConnected(false);
      }
    }
  }, [isLiveMode, selectedComputer]);

  // Toggle live mode
  const toggleLiveMode = () => {
    if (!isLiveMode) {
      // Entering live mode - clear replay data
      setIsPlaying(false);
      setLiveWindows({});
      setLiveEvents([]);
      setIsLiveMode(true);
    } else {
      // Exiting live mode
      setIsLiveMode(false);
    }
  };

  // Handle computer selection change while in live mode
  useEffect(() => {
    if (isLiveMode && socketRef.current && isLiveConnected) {
      // Resubscribe with new computer selection
      if (selectedComputer) {
        socketRef.current.emit("subscribe_live_keystrokes", {
          computer_id: selectedComputer,
        });
        console.log(
          `Subscribed to live keystrokes from computer ${selectedComputer}`
        );
      } else {
        socketRef.current.emit("subscribe_live_keystrokes", {});
        console.log("Subscribed to live keystrokes from all computers");
      }
      // Clear previous windows when switching computers
      setLiveWindows({});
      setLiveEvents([]);
    }
  }, [selectedComputer, isLiveMode, isLiveConnected]);

  // Clear all live windows
  const clearLiveText = () => {
    setLiveWindows({});
    setLiveEvents([]);
  };

  // Close a specific window panel
  const closeWindowPanel = (windowKey) => {
    setLiveWindows((prev) => {
      const newWindows = { ...prev };
      delete newWindows[windowKey];
      return newWindows;
    });
  };

  // Get sorted window entries (most recent activity first)
  const sortedWindowEntries = Object.entries(liveWindows).sort(
    ([, a], [, b]) => b.lastActivity - a.lastActivity
  );

  // Calculate grid layout based on number of windows
  const getGridClass = (count) => {
    if (count === 1) return "grid-cols-1";
    if (count === 2) return "grid-cols-2";
    if (count <= 4) return "grid-cols-2";
    if (count <= 6) return "grid-cols-3";
    return "grid-cols-3";
  };

  // Load keystroke events
  const loadEvents = useCallback(async () => {
    if (!startTime || !endTime) return;

    setLoading(true);
    try {
      const params = new URLSearchParams({
        event_type: "keystroke",
        start: startTime,
        end: endTime,
        limit: "1000",
      });

      if (selectedComputer) {
        params.append("computer_id", selectedComputer);
      }

      const response = await fetch(`/api/events?${params.toString()}`);
      const data = await response.json();

      // Sort by timestamp ascending
      const events = (data.events || []).sort(
        (a, b) => new Date(a.timestamp) - new Date(b.timestamp)
      );

      setKeystrokeEvents(events);

      // Process events into timeline
      if (events.length > 0) {
        const firstTime = new Date(events[0].timestamp).getTime();
        const lastTime = new Date(
          events[events.length - 1].timestamp
        ).getTime();
        setDuration(lastTime - firstTime);

        // Create timeline events with character-by-character timing
        const timeline = [];
        events.forEach((event, eventIndex) => {
          const eventTime = new Date(event.timestamp).getTime() - firstTime;
          const text = event.data?.text || event.data?.keys || "";
          const rawKeys = event.data?.keys || "";

          // Estimate timing per character (spread across a reasonable typing speed)
          const charsPerSecond = 5; // Average typing speed
          const charDuration = 1000 / charsPerSecond;

          // Parse raw keys to simulate typing with backspaces
          let charIndex = 0;
          let i = 0;
          while (i < rawKeys.length) {
            const charTime = eventTime + charIndex * charDuration;

            if (rawKeys[i] === "[") {
              const end = rawKeys.indexOf("]", i);
              if (end !== -1) {
                const special = rawKeys.substring(i, end + 1);
                timeline.push({
                  time: charTime,
                  type: "special",
                  key: special,
                  window: event.data?.target_window,
                  process: event.data?.target_process,
                  eventIndex,
                });
                i = end + 1;
                // Skip newline after [ENTER]
                if (
                  special === "[ENTER]" &&
                  i < rawKeys.length &&
                  rawKeys[i] === "\n"
                ) {
                  i++;
                }
                charIndex++;
                continue;
              }
            }

            timeline.push({
              time: charTime,
              type: "char",
              key: rawKeys[i],
              window: event.data?.target_window,
              process: event.data?.target_process,
              eventIndex,
            });
            i++;
            charIndex++;
          }
        });

        setTimelineEvents(timeline);
        setCurrentTime(0);
        setDisplayText("");
        setCurrentEventIndex(-1);
      }
    } catch (error) {
      console.error("Failed to load events:", error);
    } finally {
      setLoading(false);
    }
  }, [startTime, endTime, selectedComputer]);

  // Play key sound
  const playKeySound = useCallback(() => {
    if (!soundEnabled) return;

    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext ||
        window.webkitAudioContext)();
    }

    const ctx = audioContextRef.current;
    const oscillator = ctx.createOscillator();
    const gainNode = ctx.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(ctx.destination);

    oscillator.frequency.value = 800 + Math.random() * 200;
    oscillator.type = "sine";

    gainNode.gain.setValueAtTime(0.05, ctx.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);

    oscillator.start(ctx.currentTime);
    oscillator.stop(ctx.currentTime + 0.05);
  }, [soundEnabled]);

  // Playback logic
  useEffect(() => {
    if (!isPlaying || timelineEvents.length === 0) return;

    const interval = setInterval(() => {
      setCurrentTime((prev) => {
        const newTime = prev + 16 * playbackSpeed; // ~60fps
        if (newTime >= duration) {
          setIsPlaying(false);
          return duration;
        }
        return newTime;
      });
    }, 16);

    playbackRef.current = interval;
    return () => clearInterval(interval);
  }, [isPlaying, playbackSpeed, duration, timelineEvents.length]);

  // Update display based on current time
  useEffect(() => {
    if (timelineEvents.length === 0) return;

    let text = "";
    let lastWindow = "";
    let lastProcess = "";
    let lastEventIndex = -1;

    for (const event of timelineEvents) {
      if (event.time > currentTime) break;

      lastWindow = event.window || lastWindow;
      lastProcess = event.process || lastProcess;
      lastEventIndex = event.eventIndex;

      if (event.type === "char") {
        text += event.key;
        if (event.time > currentTime - 50) playKeySound();
      } else if (event.type === "special") {
        switch (event.key) {
          case "[BACKSPACE]":
            text = text.slice(0, -1);
            break;
          case "[CTRL+BACKSPACE]":
            // Delete previous word (back to last space or start)
            // First remove trailing spaces
            while (text.length > 0 && text[text.length - 1] === " ") {
              text = text.slice(0, -1);
            }
            // Then remove until we hit a space or start
            while (text.length > 0 && text[text.length - 1] !== " ") {
              text = text.slice(0, -1);
            }
            break;
          case "[ENTER]":
            text += "\n";
            break;
          case "[TAB]":
            text += "    ";
            break;
          case "[DELETE]":
          case "[CTRL+DELETE]":
            // DELETE at cursor position - simplified
            break;
          default:
            // Other special keys (arrows, etc.) - visual only
            break;
        }
      }
    }

    setDisplayText(text);
    setCurrentWindow(lastWindow);
    setCurrentProcess(lastProcess);
    setCurrentEventIndex(lastEventIndex);
  }, [currentTime, timelineEvents, playKeySound]);

  // Format time display
  const formatPlaybackTime = (ms) => {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
  };

  // Seek to position
  const handleSeek = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percent = x / rect.width;
    setCurrentTime(percent * duration);
  };

  // Skip to event
  const skipToEvent = (direction) => {
    const currentIdx = timelineEvents.findIndex((e) => e.time > currentTime);
    if (direction === "forward") {
      const nextEvent = timelineEvents.find(
        (e, i) =>
          i > currentIdx &&
          e.eventIndex !== timelineEvents[currentIdx]?.eventIndex
      );
      if (nextEvent) setCurrentTime(nextEvent.time);
    } else {
      const prevEvents = timelineEvents.filter(
        (e, i) =>
          i < currentIdx - 1 &&
          e.eventIndex !== timelineEvents[currentIdx - 1]?.eventIndex
      );
      if (prevEvents.length > 0) {
        const lastPrevEvent = prevEvents[prevEvents.length - 1];
        const eventStart = timelineEvents.find(
          (e) => e.eventIndex === lastPrevEvent.eventIndex
        );
        if (eventStart) setCurrentTime(eventStart.time);
      } else {
        setCurrentTime(0);
      }
    }
  };

  const ProcessIcon = getProcessIcon(currentProcess);

  return (
    <div className="h-full flex flex-col bg-[#0d1117]">
      {/* Compact Header */}
      <div className="p-4 border-b border-[#30363d] bg-[#161b22]/80">
        {/* Time Range Selector - All in one row */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <div
              className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                isLiveMode
                  ? "bg-gradient-to-br from-green-500 to-emerald-600"
                  : "bg-gradient-to-br from-orange-500 to-red-600"
              }`}
            >
              {isLiveMode ? (
                <Radio className="w-4 h-4 text-white animate-pulse" />
              ) : (
                <Keyboard className="w-4 h-4 text-white" />
              )}
            </div>
            <span className="font-display font-bold text-lg">
              {isLiveMode ? "Live Keystrokes" : "Keystroke Replay"}
            </span>
            {isLiveMode && isLiveConnected && (
              <span className="flex items-center gap-2 text-xs text-green-400">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  Connected
                </span>
                {sortedWindowEntries.length > 0 && (
                  <span className="flex items-center gap-1 text-gray-400">
                    <Layers className="w-3 h-3" />
                    {sortedWindowEntries.length} window
                    {sortedWindowEntries.length !== 1 ? "s" : ""}
                  </span>
                )}
              </span>
            )}
          </div>

          <div className="h-6 w-px bg-[#30363d]" />

          {/* Live Mode Toggle */}
          <button
            onClick={toggleLiveMode}
            className={`px-3 py-1.5 rounded-lg font-medium text-sm transition-all flex items-center gap-2 ${
              isLiveMode
                ? "bg-green-500/20 text-green-400 border border-green-500/30 hover:bg-green-500/30"
                : "bg-[#21262d] text-gray-400 border border-[#30363d] hover:text-green-400 hover:border-green-500/30"
            }`}
          >
            <Radio className={`w-4 h-4 ${isLiveMode ? "animate-pulse" : ""}`} />
            {isLiveMode ? "Live Mode ON" : "Go Live"}
          </button>

          <div className="h-6 w-px bg-[#30363d]" />

          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Computer:</span>
            <select
              value={selectedComputer}
              onChange={(e) => setSelectedComputer(e.target.value)}
              className="bg-[#21262d] border border-[#30363d] rounded-lg px-2 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-cyan-500"
            >
              <option value="">All</option>
              {computers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.computer_name}
                </option>
              ))}
            </select>
          </div>

          {/* Time range controls - only show in replay mode */}
          {!isLiveMode && (
            <>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">From:</span>
                <input
                  type="datetime-local"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  className="bg-[#21262d] border border-[#30363d] rounded-lg px-2 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">To:</span>
                <input
                  type="datetime-local"
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  className="bg-[#21262d] border border-[#30363d] rounded-lg px-2 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <button
                onClick={loadEvents}
                disabled={loading}
                className="px-4 py-1.5 bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-400 hover:to-red-500 rounded-lg text-white font-medium text-sm transition-all disabled:opacity-50 flex items-center gap-2"
              >
                {loading ? (
                  <>
                    <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Loading...
                  </>
                ) : (
                  <>
                    <Play className="w-3 h-3" />
                    Load
                  </>
                )}
              </button>
            </>
          )}

          {/* Clear button for live mode */}
          {isLiveMode && sortedWindowEntries.length > 0 && (
            <button
              onClick={clearLiveText}
              className="px-3 py-1.5 bg-[#21262d] text-gray-400 border border-[#30363d] rounded-lg font-medium text-sm transition-all hover:text-red-400 hover:border-red-500/30 flex items-center gap-2"
            >
              <X className="w-3 h-3" />
              Clear All
            </button>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Visual Display Area */}
        <div className="flex-1 flex flex-col p-4 min-h-0">
          {/* Simulated Window */}
          <div className="flex-1 flex flex-col rounded-xl overflow-hidden border border-[#30363d] bg-[#161b22] shadow-2xl min-h-[200px]">
            {/* Window Title Bar */}
            <div className="flex items-center gap-3 px-4 py-2 bg-[#21262d] border-b border-[#30363d]">
              <div className="flex gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <div className="w-3 h-3 rounded-full bg-yellow-500" />
                <div className="w-3 h-3 rounded-full bg-green-500" />
              </div>
              <div className="flex-1 flex items-center justify-center gap-2">
                <ProcessIcon className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-300 truncate max-w-md">
                  {currentWindow || "No window selected"}
                </span>
              </div>
              <div className="text-xs text-gray-500">
                {currentProcess || "—"}
              </div>
            </div>

            {/* Text Display Area */}
            <div ref={displayRef} className="flex-1 overflow-auto bg-[#0d1117]">
              {isLiveMode ? (
                // Live mode display - multiple window panels
                sortedWindowEntries.length > 0 ? (
                  <div
                    className={`grid ${getGridClass(
                      sortedWindowEntries.length
                    )} gap-3 p-4 h-full`}
                  >
                    {sortedWindowEntries.map(
                      ([windowKey, windowData], index) => {
                        const WindowIcon = getProcessIcon(windowData.process);
                        const isActive = index === 0; // Most recent is active

                        return (
                          <div
                            key={windowKey}
                            className={`flex flex-col rounded-lg border overflow-hidden transition-all ${
                              isActive
                                ? "border-green-500/50 bg-[#161b22] ring-1 ring-green-500/30"
                                : "border-[#30363d] bg-[#161b22]/50"
                            }`}
                          >
                            {/* Window Title Bar */}
                            <div
                              className={`flex items-center gap-2 px-3 py-2 border-b ${
                                isActive
                                  ? "border-green-500/30 bg-green-500/10"
                                  : "border-[#30363d] bg-[#21262d]"
                              }`}
                            >
                              <div className="flex gap-1.5">
                                <button
                                  onClick={() => closeWindowPanel(windowKey)}
                                  className="w-3 h-3 rounded-full bg-red-500 hover:bg-red-400 transition-colors"
                                  title="Close panel"
                                />
                                <div className="w-3 h-3 rounded-full bg-yellow-500" />
                                <div className="w-3 h-3 rounded-full bg-green-500" />
                              </div>
                              <WindowIcon
                                className={`w-4 h-4 ml-2 ${
                                  isActive ? "text-green-400" : "text-gray-400"
                                }`}
                              />
                              <span
                                className={`text-xs truncate flex-1 ${
                                  isActive ? "text-green-300" : "text-gray-400"
                                }`}
                              >
                                {windowData.window}
                              </span>
                              {isActive && (
                                <span className="flex items-center gap-1 text-xs text-green-400">
                                  <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                                  Active
                                </span>
                              )}
                            </div>

                            {/* Window Content */}
                            <div className="flex-1 p-3 font-mono text-sm text-gray-200 overflow-auto min-h-[100px] max-h-[300px]">
                              <div className="whitespace-pre-wrap break-words">
                                {windowData.text}
                                {isActive && (
                                  <span
                                    className={`inline-block w-[2px] h-[1em] bg-green-400 ml-[1px] align-middle transition-opacity ${
                                      cursorVisible
                                        ? "opacity-100"
                                        : "opacity-0"
                                    }`}
                                  />
                                )}
                              </div>
                            </div>

                            {/* Window Footer */}
                            <div className="px-3 py-1.5 border-t border-[#30363d] bg-[#0d1117]/50">
                              <div className="flex items-center justify-between text-xs text-gray-500">
                                <span>{windowData.process}</span>
                                <span>{windowData.computerName}</span>
                              </div>
                            </div>
                          </div>
                        );
                      }
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-gray-500 p-6">
                    <Radio className="w-16 h-16 mb-4 opacity-30 animate-pulse" />
                    <p className="text-lg text-green-400">Live Mode Active</p>
                    <p className="text-sm mt-1">Waiting for keystrokes...</p>
                    <p className="text-xs mt-3 text-gray-600">
                      Type something on a monitored device to see it here
                    </p>
                    <p className="text-xs mt-1 text-gray-600">
                      Each window will appear as a separate panel
                    </p>
                  </div>
                )
              ) : // Replay mode display
              timelineEvents.length > 0 ? (
                <div className="p-6 font-mono text-lg text-gray-200 leading-relaxed whitespace-pre-wrap">
                  {displayText}
                  <span
                    className={`inline-block w-[2px] h-[1.2em] bg-orange-400 ml-[1px] align-middle transition-opacity ${
                      cursorVisible ? "opacity-100" : "opacity-0"
                    }`}
                  />
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-gray-500 p-6">
                  <Keyboard className="w-16 h-16 mb-4 opacity-30" />
                  <p className="text-lg">No replay loaded</p>
                  <p className="text-sm mt-1">
                    Select a time range and click "Load"
                  </p>
                  <p className="text-xs mt-3 text-gray-600">
                    Or click "Go Live" to see real-time keystrokes
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Playback Controls - Only show in replay mode with data */}
          {!isLiveMode && timelineEvents.length > 0 && (
            <div className="mt-3 bg-[#161b22] rounded-xl border border-[#30363d] p-3 flex-shrink-0">
              {/* Timeline */}
              <div
                className="h-2 bg-[#21262d] rounded-full cursor-pointer mb-4 relative overflow-hidden group"
                onClick={handleSeek}
              >
                {/* Progress */}
                <div
                  className="h-full bg-gradient-to-r from-orange-500 to-red-500 rounded-full transition-all"
                  style={{ width: `${(currentTime / duration) * 100}%` }}
                />

                {/* Event markers */}
                {keystrokeEvents.map((event, i) => {
                  const eventTime =
                    new Date(event.timestamp).getTime() -
                    new Date(keystrokeEvents[0].timestamp).getTime();
                  const position = (eventTime / duration) * 100;
                  return (
                    <div
                      key={i}
                      className={`absolute top-0 w-1 h-full ${
                        i === currentEventIndex
                          ? "bg-yellow-400"
                          : "bg-gray-600"
                      }`}
                      style={{ left: `${position}%` }}
                    />
                  );
                })}

                {/* Hover indicator */}
                <div className="absolute inset-0 bg-white/5 opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>

              {/* Controls Row */}
              <div className="flex items-center justify-between">
                {/* Left - Time */}
                <div className="text-sm font-mono text-gray-400 min-w-[100px]">
                  {formatPlaybackTime(currentTime)} /{" "}
                  {formatPlaybackTime(duration)}
                </div>

                {/* Center - Controls */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setCurrentTime(0)}
                    className="p-2 text-gray-400 hover:text-white transition-colors"
                    title="Restart"
                  >
                    <SkipBack className="w-5 h-5" />
                  </button>

                  <button
                    onClick={() => skipToEvent("backward")}
                    className="p-2 text-gray-400 hover:text-white transition-colors"
                    title="Previous Event"
                  >
                    <Rewind className="w-5 h-5" />
                  </button>

                  <button
                    onClick={() => setIsPlaying(!isPlaying)}
                    className="p-4 bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-400 hover:to-red-500 rounded-full text-white transition-all"
                  >
                    {isPlaying ? (
                      <Pause className="w-6 h-6" />
                    ) : (
                      <Play className="w-6 h-6 ml-0.5" />
                    )}
                  </button>

                  <button
                    onClick={() => skipToEvent("forward")}
                    className="p-2 text-gray-400 hover:text-white transition-colors"
                    title="Next Event"
                  >
                    <FastForward className="w-5 h-5" />
                  </button>

                  <button
                    onClick={() => setCurrentTime(duration)}
                    className="p-2 text-gray-400 hover:text-white transition-colors"
                    title="End"
                  >
                    <SkipForward className="w-5 h-5" />
                  </button>
                </div>

                {/* Right - Speed & Sound */}
                <div className="flex items-center gap-3 min-w-[100px] justify-end">
                  <button
                    onClick={() => setSoundEnabled(!soundEnabled)}
                    className={`p-2 rounded-lg transition-colors ${
                      soundEnabled
                        ? "text-orange-400 bg-orange-500/20"
                        : "text-gray-500 hover:text-gray-300"
                    }`}
                    title="Toggle Sound"
                  >
                    {soundEnabled ? (
                      <Volume2 className="w-4 h-4" />
                    ) : (
                      <VolumeX className="w-4 h-4" />
                    )}
                  </button>

                  <select
                    value={playbackSpeed}
                    onChange={(e) => setPlaybackSpeed(Number(e.target.value))}
                    className="bg-[#21262d] border border-[#30363d] rounded-lg px-2 py-1 text-sm text-gray-300 focus:outline-none focus:border-orange-500"
                  >
                    <option value={0.25}>0.25x</option>
                    <option value={0.5}>0.5x</option>
                    <option value={1}>1x</option>
                    <option value={2}>2x</option>
                    <option value={4}>4x</option>
                    <option value={8}>8x</option>
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Event List Sidebar */}
        <div className="w-80 border-l border-[#30363d] bg-[#161b22]/50 flex flex-col">
          <div className="p-4 border-b border-[#30363d]">
            <h2 className="font-semibold text-gray-200">
              {isLiveMode ? "Live Events" : "Events Timeline"}
            </h2>
            <p className="text-xs text-gray-500 mt-1">
              {isLiveMode
                ? `${liveEvents.length} live events`
                : `${keystrokeEvents.length} keystroke events`}
            </p>
          </div>

          <div className="flex-1 overflow-y-auto p-2">
            {isLiveMode ? (
              // Live mode events list
              <>
                {liveEvents
                  .slice()
                  .reverse()
                  .map((event, i) => {
                    const Icon = getProcessIcon(event.data?.target_process);
                    return (
                      <div
                        key={event.id || i}
                        className={`w-full text-left p-3 rounded-lg mb-1 transition-all ${
                          i === 0
                            ? "bg-green-500/20 border border-green-500/30 animate-pulse"
                            : "bg-[#21262d]/30"
                        }`}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <Icon className="w-4 h-4 text-gray-400" />
                          <span className="text-xs text-gray-500">
                            {event.timestamp &&
                              format(new Date(event.timestamp), "HH:mm:ss")}
                          </span>
                          {i === 0 && (
                            <span className="text-xs text-green-400 font-medium">
                              NEW
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-300 truncate font-mono">
                          {event.data?.text ||
                            event.data?.keys?.substring(0, 30) ||
                            "..."}
                        </p>
                        <p className="text-xs text-gray-500 truncate mt-1">
                          {event.data?.target_process} • {event.computer_name}
                        </p>
                      </div>
                    );
                  })}

                {liveEvents.length === 0 && (
                  <div className="text-center text-gray-500 py-8">
                    <Radio className="w-8 h-8 mx-auto mb-2 opacity-30 animate-pulse" />
                    <p className="text-sm text-green-400">
                      Listening for events...
                    </p>
                    <p className="text-xs mt-1 text-gray-600">
                      Events will appear here in real-time
                    </p>
                  </div>
                )}
              </>
            ) : (
              // Replay mode events list
              <>
                {keystrokeEvents.map((event, i) => {
                  const Icon = getProcessIcon(event.data?.target_process);
                  return (
                    <button
                      key={event.id || i}
                      onClick={() => {
                        const eventTime =
                          new Date(event.timestamp).getTime() -
                          new Date(keystrokeEvents[0].timestamp).getTime();
                        setCurrentTime(eventTime);
                      }}
                      className={`w-full text-left p-3 rounded-lg mb-1 transition-all ${
                        currentEventIndex === i
                          ? "bg-orange-500/20 border border-orange-500/30"
                          : "hover:bg-[#21262d]/50"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <Icon className="w-4 h-4 text-gray-400" />
                        <span className="text-xs text-gray-500">
                          {event.timestamp &&
                            format(new Date(event.timestamp), "HH:mm:ss")}
                        </span>
                      </div>
                      <p className="text-sm text-gray-300 truncate font-mono">
                        {event.data?.text ||
                          event.data?.keys?.substring(0, 30) ||
                          "..."}
                      </p>
                      <p className="text-xs text-gray-500 truncate mt-1">
                        {event.data?.target_process}
                      </p>
                    </button>
                  );
                })}

                {keystrokeEvents.length === 0 && (
                  <div className="text-center text-gray-500 py-8">
                    <Clock className="w-8 h-8 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">No events loaded</p>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default KeystrokeReplay;
