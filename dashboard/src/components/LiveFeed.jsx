import React, { useRef, useEffect, useState } from "react";
import {
  Keyboard,
  Monitor,
  Clipboard,
  FolderOpen,
  Cpu,
  Globe,
  Pause,
  Play,
  Filter,
  Download,
  Trash2,
} from "lucide-react";
import { format } from "date-fns";

const EVENT_ICONS = {
  keystroke: {
    icon: Keyboard,
    color: "text-orange-400",
    bg: "bg-orange-500/20",
  },
  window_focus: { icon: Monitor, color: "text-blue-400", bg: "bg-blue-500/20" },
  clipboard_copy: {
    icon: Clipboard,
    color: "text-purple-400",
    bg: "bg-purple-500/20",
  },
  file_created: {
    icon: FolderOpen,
    color: "text-green-400",
    bg: "bg-green-500/20",
  },
  file_modified: {
    icon: FolderOpen,
    color: "text-yellow-400",
    bg: "bg-yellow-500/20",
  },
  file_deleted: {
    icon: FolderOpen,
    color: "text-red-400",
    bg: "bg-red-500/20",
  },
  file_moved: {
    icon: FolderOpen,
    color: "text-cyan-400",
    bg: "bg-cyan-500/20",
  },
  process_start: { icon: Cpu, color: "text-pink-400", bg: "bg-pink-500/20" },
  process_end: { icon: Cpu, color: "text-gray-400", bg: "bg-gray-500/20" },
  page_load: { icon: Globe, color: "text-cyan-400", bg: "bg-cyan-500/20" },
  click: { icon: Globe, color: "text-cyan-400", bg: "bg-cyan-500/20" },
  form_input: { icon: Globe, color: "text-cyan-400", bg: "bg-cyan-500/20" },
};

function EventItem({ event }) {
  const config = EVENT_ICONS[event.event_type] || EVENT_ICONS.keystroke;
  const Icon = config.icon;

  const getEventDescription = () => {
    const data = event.data || {};

    switch (event.event_type) {
      case "keystroke":
        // Show reconstructed text if available (final typed text), otherwise raw keys
        const displayText = data.text || data.keys;
        return (
          <span className="font-mono text-sm">
            Typed:{" "}
            <span className="text-orange-300">
              "{displayText?.substring(0, 100)}"
            </span>
            {data.target_process && (
              <span className="text-gray-500"> in {data.target_process}</span>
            )}
            {data.text && data.keys !== data.text && (
              <span className="text-gray-600 text-xs ml-2">(edited)</span>
            )}
          </span>
        );
      case "window_focus":
        return (
          <span>
            {data.action === "gained_focus" ? "Focused: " : "Left: "}
            <span className="text-blue-300">
              {data.window_title?.substring(0, 60)}
            </span>
            {data.duration_seconds && (
              <span className="text-gray-500 ml-2">
                ({data.duration_seconds}s)
              </span>
            )}
          </span>
        );
      case "clipboard_copy":
        return (
          <span>
            Copied:{" "}
            <span className="text-purple-300 font-mono text-sm">
              "{data.content?.substring(0, 80)}"
            </span>
            {data.source_process && (
              <span className="text-gray-500"> from {data.source_process}</span>
            )}
          </span>
        );
      case "file_created":
        return (
          <span>
            Created: <span className="text-green-300">{data.file_path}</span>
          </span>
        );
      case "file_modified":
        return (
          <span>
            Modified: <span className="text-yellow-300">{data.file_path}</span>
          </span>
        );
      case "file_deleted":
        return (
          <span>
            Deleted: <span className="text-red-300">{data.file_path}</span>
          </span>
        );
      case "file_moved":
        return (
          <span>
            Moved: <span className="text-cyan-300">{data.file_name}</span>
            <span className="text-gray-500"> → {data.destination_path}</span>
          </span>
        );
      case "process_start":
        return (
          <span>
            Started: <span className="text-pink-300">{data.process_name}</span>
          </span>
        );
      case "process_end":
        return (
          <span>
            Ended: <span className="text-gray-300">{data.process_name}</span>
            {data.duration_seconds && (
              <span className="text-gray-500">
                {" "}
                ({Math.round(data.duration_seconds)}s)
              </span>
            )}
          </span>
        );
      default:
        return (
          <span className="text-gray-400">
            {JSON.stringify(data).substring(0, 100)}
          </span>
        );
    }
  };

  return (
    <div className="flex items-start gap-3 p-3 hover:bg-[#21262d]/50 rounded-lg transition-colors animate-slide-in">
      {/* Icon */}
      <div
        className={`w-8 h-8 rounded-lg ${config.bg} flex items-center justify-center flex-shrink-0`}
      >
        <Icon className={`w-4 h-4 ${config.color}`} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold text-cyan-400">
            {event.computer_name}
          </span>
          <span className="text-xs text-gray-500">
            {event.timestamp &&
              format(
                new Date(
                  event.timestamp.endsWith("Z")
                    ? event.timestamp
                    : event.timestamp + "Z"
                ),
                "HH:mm:ss"
              )}
          </span>
          <span
            className={`text-xs px-1.5 py-0.5 rounded ${config.bg} ${config.color}`}
          >
            {event.event_type.replace("_", " ")}
          </span>
        </div>
        <div className="text-sm text-gray-300 break-words">
          {getEventDescription()}
        </div>
      </div>
    </div>
  );
}

function LiveFeed({ events, selectedComputer }) {
  const [isPaused, setIsPaused] = useState(false);
  const [filter, setFilter] = useState("all");
  const containerRef = useRef(null);
  const [displayEvents, setDisplayEvents] = useState([]);

  // Filter events
  useEffect(() => {
    let filtered = events;

    if (selectedComputer) {
      filtered = filtered.filter((e) => e.computer_id === selectedComputer.id);
    }

    if (filter !== "all") {
      filtered = filtered.filter(
        (e) => e.category === filter || e.event_type === filter
      );
    }

    setDisplayEvents(filtered.slice(0, 200));
  }, [events, selectedComputer, filter]);

  const filterOptions = [
    { value: "all", label: "All Events" },
    { value: "keystroke", label: "Keystrokes" },
    { value: "application", label: "Applications" },
    { value: "clipboard", label: "Clipboard" },
    { value: "file", label: "Files" },
  ];

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-[#30363d] bg-[#161b22]/50">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display text-xl font-bold flex items-center gap-3">
              Live Activity Feed
              {!isPaused && (
                <span className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  <span className="text-sm font-normal text-gray-500">
                    Live
                  </span>
                </span>
              )}
            </h1>
            {selectedComputer && (
              <p className="text-sm text-gray-500 mt-1">
                Filtering: {selectedComputer.computer_name}
              </p>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* Filter */}
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="bg-[#21262d] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-cyan-500"
            >
              {filterOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            {/* Pause/Play */}
            <button
              onClick={() => setIsPaused(!isPaused)}
              className={`p-2 rounded-lg transition-colors ${
                isPaused
                  ? "bg-yellow-500/20 text-yellow-400"
                  : "bg-[#21262d] text-gray-400 hover:text-gray-200"
              }`}
            >
              {isPaused ? (
                <Play className="w-5 h-5" />
              ) : (
                <Pause className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Events List */}
      <div ref={containerRef} className="flex-1 overflow-y-auto p-2">
        {displayEvents.length > 0 ? (
          displayEvents.map((event, index) => (
            <EventItem key={event.id || index} event={event} />
          ))
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <Monitor className="w-12 h-12 mb-4 text-gray-600" />
            <p>Waiting for events...</p>
            <p className="text-sm mt-1">Events will appear here in real-time</p>
          </div>
        )}
      </div>

      {/* Footer Stats */}
      <div className="p-3 border-t border-[#30363d] bg-[#161b22]/50">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{displayEvents.length} events displayed</span>
          <span>{events.length} total in buffer</span>
        </div>
      </div>
    </div>
  );
}

export default LiveFeed;
