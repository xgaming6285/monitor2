import React, { useState, useCallback } from "react";
import {
  Search,
  Filter,
  Calendar,
  Monitor,
  Keyboard,
  Clipboard,
  FolderOpen,
  Cpu,
  Globe,
  X,
  Download,
} from "lucide-react";
import { format } from "date-fns";

function SearchPanel() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    computer_id: "",
    event_type: "",
    category: "",
    start: "",
    end: "",
  });
  const [totalResults, setTotalResults] = useState(0);

  // Helper to convert local datetime-local value to UTC ISO string
  const localToUTC = (localDateTimeStr) => {
    if (!localDateTimeStr) return null;
    // datetime-local gives us "YYYY-MM-DDTHH:mm" in local time
    // Convert to UTC for the API
    const localDate = new Date(localDateTimeStr);
    return localDate.toISOString();
  };

  const performSearch = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.computer_id)
        params.append("computer_id", filters.computer_id);
      if (filters.event_type) params.append("event_type", filters.event_type);
      if (filters.category) params.append("category", filters.category);
      // Convert local times to UTC for API query
      if (filters.start) params.append("start", localToUTC(filters.start));
      if (filters.end) params.append("end", localToUTC(filters.end));
      params.append("limit", "100");

      const response = await fetch(`/api/events?${params.toString()}`);
      const data = await response.json();

      // Client-side search in results if query provided
      let filteredResults = data.events || [];
      if (query) {
        const lowerQuery = query.toLowerCase();
        filteredResults = filteredResults.filter((event) => {
          const dataStr = JSON.stringify(event.data || {}).toLowerCase();
          return (
            dataStr.includes(lowerQuery) ||
            event.event_type.includes(lowerQuery) ||
            (event.computer_name || "").toLowerCase().includes(lowerQuery)
          );
        });
      }

      setResults(filteredResults);
      setTotalResults(data.total);
    } catch (error) {
      console.error("Search failed:", error);
    } finally {
      setLoading(false);
    }
  }, [query, filters]);

  const handleSubmit = (e) => {
    e.preventDefault();
    performSearch();
  };

  const clearFilters = () => {
    setFilters({
      computer_id: "",
      event_type: "",
      category: "",
      start: "",
      end: "",
    });
    setQuery("");
    setResults([]);
  };

  const eventTypes = [
    { value: "", label: "All Types" },
    { value: "keystroke", label: "Keystrokes" },
    { value: "window_focus", label: "Window Focus" },
    { value: "clipboard_copy", label: "Clipboard" },
    { value: "file_created", label: "File Created" },
    { value: "file_modified", label: "File Modified" },
    { value: "file_deleted", label: "File Deleted" },
    { value: "process_start", label: "Process Start" },
    { value: "process_end", label: "Process End" },
  ];

  const categories = [
    { value: "", label: "All Categories" },
    { value: "input", label: "Input" },
    { value: "application", label: "Application" },
    { value: "clipboard", label: "Clipboard" },
    { value: "file", label: "File" },
    { value: "browser", label: "Browser" },
  ];

  return (
    <div className="h-full flex flex-col">
      {/* Search Header */}
      <div className="p-6 border-b border-[#30363d] bg-[#161b22]/50">
        <h1 className="font-display text-2xl font-bold mb-4">Search Events</h1>

        <form onSubmit={handleSubmit}>
          {/* Main Search */}
          <div className="relative mb-4">
            <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for keystrokes, file names, clipboard content..."
              className="w-full pl-12 pr-4 py-3 bg-[#21262d] border border-[#30363d] rounded-xl text-gray-200 placeholder-gray-500 focus:outline-none focus:border-cyan-500 transition-colors"
            />
          </div>

          {/* Filters Row */}
          <div className="flex flex-wrap gap-3">
            <select
              value={filters.event_type}
              onChange={(e) =>
                setFilters((f) => ({ ...f, event_type: e.target.value }))
              }
              className="bg-[#21262d] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-cyan-500"
            >
              {eventTypes.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            <select
              value={filters.category}
              onChange={(e) =>
                setFilters((f) => ({ ...f, category: e.target.value }))
              }
              className="bg-[#21262d] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-cyan-500"
            >
              {categories.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            <input
              type="datetime-local"
              value={filters.start}
              onChange={(e) =>
                setFilters((f) => ({ ...f, start: e.target.value }))
              }
              className="bg-[#21262d] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-cyan-500"
              placeholder="Start date"
            />

            <input
              type="datetime-local"
              value={filters.end}
              onChange={(e) =>
                setFilters((f) => ({ ...f, end: e.target.value }))
              }
              className="bg-[#21262d] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-cyan-500"
              placeholder="End date"
            />

            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 rounded-lg text-white font-medium transition-colors disabled:opacity-50"
            >
              {loading ? "Searching..." : "Search"}
            </button>

            <button
              type="button"
              onClick={clearFilters}
              className="px-4 py-2 bg-[#21262d] hover:bg-[#30363d] border border-[#30363d] rounded-lg text-gray-400 transition-colors flex items-center gap-2"
            >
              <X className="w-4 h-4" />
              Clear
            </button>
          </div>
        </form>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto p-6">
        {results.length > 0 ? (
          <>
            <div className="flex items-center justify-between mb-4">
              <p className="text-gray-500">
                Showing {results.length} of {totalResults} results
              </p>
            </div>

            <div className="space-y-2">
              {results.map((event, index) => (
                <div
                  key={event.id || index}
                  className="bg-[#161b22] border border-[#30363d] rounded-lg p-4 hover:border-[#484f58] transition-colors"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <span className="text-cyan-400 font-medium">
                        {event.computer_name}
                      </span>
                      <span className="text-xs px-2 py-1 bg-[#21262d] rounded text-gray-400">
                        {event.event_type}
                      </span>
                      <span className="text-xs text-gray-500">
                        {event.category}
                      </span>
                    </div>
                    <span className="text-xs text-gray-500">
                      {event.timestamp &&
                        format(
                          new Date(
                            event.timestamp.endsWith("Z")
                              ? event.timestamp
                              : event.timestamp + "Z"
                          ),
                          "MMM d, yyyy HH:mm:ss"
                        )}
                    </span>
                  </div>

                  <div className="text-sm text-gray-300 font-mono bg-[#0d1117] rounded p-3 overflow-x-auto">
                    {/* For keystrokes, show reconstructed text prominently */}
                    {event.event_type === "keystroke" && event.data?.text && (
                      <div className="mb-3 pb-3 border-b border-[#30363d]">
                        <span className="text-gray-500 text-xs block mb-1">
                          Final text:
                        </span>
                        <span className="text-cyan-300 text-base">
                          {event.data.text}
                        </span>
                      </div>
                    )}
                    <pre className="whitespace-pre-wrap">
                      {JSON.stringify(event.data, null, 2)}
                    </pre>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <Search className="w-16 h-16 mb-4 opacity-30" />
            <p className="text-lg">Search for events</p>
            <p className="text-sm mt-1">
              Use the search bar and filters above to find specific events
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default SearchPanel;
