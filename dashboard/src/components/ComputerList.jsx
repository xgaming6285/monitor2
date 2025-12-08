import React from "react";
import {
  Monitor,
  Wifi,
  WifiOff,
  Clock,
  User,
  HardDrive,
  Globe,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";

function ComputerList({ computers, selectedComputer, onSelectComputer }) {
  // Count online devices (including extensions)
  const countOnline = (computerList) => {
    let count = 0;
    computerList.forEach((c) => {
      if (c.is_online) count++;
      if (c.extensions) {
        count += c.extensions.filter((ext) => ext.is_online).length;
      }
    });
    return count;
  };

  // Count total devices (including extensions)
  const countTotal = (computerList) => {
    let count = 0;
    computerList.forEach((c) => {
      count++;
      if (c.extensions) {
        count += c.extensions.length;
      }
    });
    return count;
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display text-2xl font-bold">Computers</h1>
          <p className="text-gray-500">
            {countOnline(computers)} online of {countTotal(computers)} total
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {computers.map((computer) => (
          <div
            key={computer.id}
            onClick={() => onSelectComputer(computer)}
            className={`bg-[#161b22] rounded-xl border cursor-pointer transition-all card-hover ${
              selectedComputer?.id === computer.id
                ? "border-cyan-500 glow-cyan"
                : "border-[#30363d] hover:border-[#484f58]"
            }`}
          >
            <div className="p-5">
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                      computer.is_online ? "bg-green-500/20" : "bg-gray-500/20"
                    }`}
                  >
                    <Monitor
                      className={`w-6 h-6 ${
                        computer.is_online ? "text-green-400" : "text-gray-500"
                      }`}
                    />
                  </div>
                  <div>
                    <h3 className="font-semibold">{computer.computer_name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <div
                        className={`w-2 h-2 rounded-full ${
                          computer.is_online
                            ? "status-online"
                            : "status-offline"
                        }`}
                      />
                      <span className="text-xs text-gray-500">
                        {computer.is_online ? "Online" : "Offline"}
                      </span>
                      {computer.device_type === "extension" && (
                        <span className="text-xs text-cyan-400 ml-1">
                          (Extension)
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Details */}
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2 text-gray-400">
                  <User className="w-4 h-4" />
                  <span>{computer.username || "Unknown"}</span>
                </div>
                <div className="flex items-center gap-2 text-gray-400">
                  <HardDrive className="w-4 h-4" />
                  <span>
                    {computer.device_type === "extension"
                      ? "Browser Extension"
                      : computer.os_version || "Windows"}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-gray-400">
                  <Clock className="w-4 h-4" />
                  <span>
                    {computer.last_seen
                      ? `Last seen ${formatDistanceToNow(
                          new Date(computer.last_seen),
                          { addSuffix: true }
                        )}`
                      : "Never connected"}
                  </span>
                </div>
              </div>

              {/* Linked Extensions */}
              {computer.extensions && computer.extensions.length > 0 && (
                <div className="mt-4 pt-4 border-t border-[#30363d]">
                  <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                    Linked Extensions
                  </h4>
                  <div className="space-y-2">
                    {computer.extensions.map((extension) => (
                      <div
                        key={extension.id}
                        className="flex items-center gap-2 text-sm p-2 rounded-lg bg-[#0d1117] hover:bg-[#1c2128] transition-colors"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectComputer(extension);
                        }}
                      >
                        <Globe
                          className={`w-4 h-4 ${
                            extension.is_online
                              ? "text-cyan-400"
                              : "text-gray-500"
                          }`}
                        />
                        <span className="text-gray-300">Extension</span>
                        <div
                          className={`w-1.5 h-1.5 rounded-full ml-auto ${
                            extension.is_online ? "bg-green-400" : "bg-gray-500"
                          }`}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {computers.length === 0 && (
          <div className="col-span-full text-center py-12">
            <Monitor className="w-12 h-12 text-gray-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-400">
              No computers registered
            </h3>
            <p className="text-gray-500 mt-1">
              Deploy agents to start monitoring
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default ComputerList;
