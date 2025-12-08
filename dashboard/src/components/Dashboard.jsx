import React, { useState, useEffect } from "react";
import {
  Monitor,
  Activity,
  Keyboard,
  Clipboard,
  FolderOpen,
  Cpu,
  TrendingUp,
  Users,
  Clock,
  AlertTriangle,
} from "lucide-react";

function StatCard({ title, value, icon: Icon, trend, color = "cyan" }) {
  const colors = {
    cyan: "from-cyan-500 to-teal-500",
    green: "from-green-500 to-emerald-500",
    orange: "from-orange-500 to-amber-500",
    purple: "from-purple-500 to-pink-500",
  };

  return (
    <div className="bg-[#161b22] rounded-xl border border-[#30363d] p-5 card-hover">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-gray-500 text-sm">{title}</p>
          <p className="text-3xl font-bold mt-2 font-display">{value}</p>
          {trend && (
            <div className="flex items-center gap-1 mt-2 text-green-400 text-sm">
              <TrendingUp className="w-4 h-4" />
              <span>{trend}</span>
            </div>
          )}
        </div>
        <div
          className={`w-12 h-12 rounded-xl bg-gradient-to-br ${colors[color]} flex items-center justify-center`}
        >
          <Icon className="w-6 h-6 text-white" />
        </div>
      </div>
    </div>
  );
}

function RecentActivity({ events }) {
  const recentEvents = events.slice(0, 10);

  return (
    <div className="bg-[#161b22] rounded-xl border border-[#30363d]">
      <div className="p-4 border-b border-[#30363d]">
        <h3 className="font-semibold flex items-center gap-2">
          <Activity className="w-5 h-5 text-cyan-400" />
          Recent Activity
        </h3>
      </div>
      <div className="p-2 max-h-[400px] overflow-y-auto">
        {recentEvents.length > 0 ? (
          recentEvents.map((event, index) => (
            <div
              key={event.id || index}
              className="flex items-center gap-3 p-3 hover:bg-[#21262d]/50 rounded-lg"
            >
              <div className="w-2 h-2 rounded-full bg-cyan-500" />
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">
                  <span className="text-cyan-400">{event.computer_name}</span>
                  {" - "}
                  <span className="text-gray-400">{event.event_type}</span>
                </p>
              </div>
              <span className="text-xs text-gray-500">
                {event.timestamp &&
                  new Date(
                    event.timestamp.endsWith("Z")
                      ? event.timestamp
                      : event.timestamp + "Z"
                  ).toLocaleTimeString()}
              </span>
            </div>
          ))
        ) : (
          <div className="text-center py-8 text-gray-500">
            <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No recent activity</p>
          </div>
        )}
      </div>
    </div>
  );
}

function OnlineComputers({ computers }) {
  const onlineComputers = computers.filter((c) => c.is_online);

  return (
    <div className="bg-[#161b22] rounded-xl border border-[#30363d]">
      <div className="p-4 border-b border-[#30363d]">
        <h3 className="font-semibold flex items-center gap-2">
          <Monitor className="w-5 h-5 text-green-400" />
          Online Computers ({onlineComputers.length})
        </h3>
      </div>
      <div className="p-2 max-h-[400px] overflow-y-auto">
        {onlineComputers.length > 0 ? (
          onlineComputers.map((computer) => (
            <div
              key={computer.id}
              className="flex items-center gap-3 p-3 hover:bg-[#21262d]/50 rounded-lg"
            >
              <div className="w-8 h-8 rounded-lg bg-green-500/20 flex items-center justify-center">
                <Monitor className="w-4 h-4 text-green-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm">{computer.computer_name}</p>
                <p className="text-xs text-gray-500">{computer.username}</p>
              </div>
              <div className="w-2 h-2 rounded-full status-online" />
            </div>
          ))
        ) : (
          <div className="text-center py-8 text-gray-500">
            <Monitor className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No computers online</p>
          </div>
        )}
      </div>
    </div>
  );
}

function Dashboard({ computers, events }) {
  const [stats, setStats] = useState({
    total_computers: 0,
    online_computers: 0,
    total_events: 0,
    events_24h: 0,
    events_by_category: {},
  });

  // Fetch stats
  useEffect(() => {
    fetch("/api/stats")
      .then((res) => res.json())
      .then((data) => setStats(data))
      .catch(console.error);

    // Refresh stats every 30 seconds
    const interval = setInterval(() => {
      fetch("/api/stats")
        .then((res) => res.json())
        .then((data) => setStats(data))
        .catch(console.error);
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-6 overflow-y-auto h-full">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-display text-3xl font-bold">Dashboard</h1>
        <p className="text-gray-500 mt-1">
          Monitor all activity across your network
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          title="Total Computers"
          value={stats.total_computers}
          icon={Monitor}
          color="cyan"
        />
        <StatCard
          title="Online Now"
          value={stats.online_computers}
          icon={Users}
          color="green"
        />
        <StatCard
          title="Events Today"
          value={stats.events_24h.toLocaleString()}
          icon={Activity}
          color="orange"
        />
        <StatCard
          title="Total Events"
          value={stats.total_events.toLocaleString()}
          icon={Keyboard}
          color="purple"
        />
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RecentActivity events={events} />
        <OnlineComputers computers={computers} />
      </div>

      {/* Event Categories */}
      <div className="mt-6 bg-[#161b22] rounded-xl border border-[#30363d] p-5">
        <h3 className="font-semibold mb-4">Events by Category</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(stats.events_by_category || {}).map(
            ([category, count]) => (
              <div key={category} className="bg-[#21262d] rounded-lg p-4">
                <p className="text-gray-500 text-sm capitalize">{category}</p>
                <p className="text-2xl font-bold font-display mt-1">
                  {count.toLocaleString()}
                </p>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
