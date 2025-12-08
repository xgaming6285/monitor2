/**
 * Background Service Worker
 * Manages event collection and sends to dashboard server
 */

// Configuration
const CONFIG = {
  maxEvents: 10000, // Maximum events to keep in memory
  batchSize: 50, // Events per batch to send
  batchInterval: 5000, // Send batch every 5 seconds
  heartbeatInterval: 30000, // Heartbeat every 30 seconds
  retryDelay: 5000, // Retry delay on failure
  maxRetries: 3, // Max retries before giving up
};

// State
let eventQueue = [];
let pendingEvents = []; // Events waiting to be sent
let isMonitoring = true;
let computerId = null;
let apiKey = null;
let serverUrl = "";
let isConnected = false;
let computerName =
  "Browser-" + Math.random().toString(36).substring(2, 8).toUpperCase();

// Intervals
let batchSendInterval = null;
let heartbeatInterval = null;

// Initialize
chrome.storage.local.get(
  [
    "computerId",
    "apiKey",
    "serverUrl",
    "computerName",
    "isMonitoring",
    "eventQueue",
  ],
  (result) => {
    if (result.computerId) computerId = result.computerId;
    if (result.apiKey) apiKey = result.apiKey;
    if (result.serverUrl) serverUrl = result.serverUrl;
    if (result.computerName) computerName = result.computerName;
    if (result.isMonitoring !== undefined) isMonitoring = result.isMonitoring;
    if (result.eventQueue && Array.isArray(result.eventQueue)) {
      eventQueue = result.eventQueue;
    }

    // Auto-reconnect if we have credentials
    if (serverUrl && apiKey) {
      startServerConnection();
    }
  }
);

// ============== Server Connection ==============

async function registerWithServer(url, name) {
  try {
    const response = await fetch(`${url}/api/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        computer_name: name,
        username: "Browser Extension",
        os_version: navigator.userAgent,
        agent_version: chrome.runtime.getManifest().version,
        device_type: "extension", // Identify as browser extension for linking
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Registration failed");
    }

    const data = await response.json();

    // Save credentials
    computerId = data.computer_id;
    apiKey = data.api_key;
    serverUrl = url;
    computerName = name;

    // Save parent computer ID if linked to a desktop agent
    const parentComputerId = data.parent_computer_id || null;

    await chrome.storage.local.set({
      computerId,
      apiKey,
      serverUrl,
      computerName,
      parentComputerId,
    });

    // Start sending events
    startServerConnection();

    return {
      success: true,
      computerId,
      message: data.message,
      parentComputerId: parentComputerId,
    };
  } catch (error) {
    console.error("Registration failed:", error);
    return { success: false, error: error.message };
  }
}

function startServerConnection() {
  if (!serverUrl || !apiKey) return;

  isConnected = true;

  // Start batch sending
  if (batchSendInterval) clearInterval(batchSendInterval);
  batchSendInterval = setInterval(sendEventBatch, CONFIG.batchInterval);

  // Start heartbeat
  if (heartbeatInterval) clearInterval(heartbeatInterval);
  heartbeatInterval = setInterval(sendHeartbeat, CONFIG.heartbeatInterval);

  // Send any pending events immediately
  sendEventBatch();

  console.log("Server connection started");
}

function stopServerConnection() {
  isConnected = false;

  if (batchSendInterval) {
    clearInterval(batchSendInterval);
    batchSendInterval = null;
  }

  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
    heartbeatInterval = null;
  }

  console.log("Server connection stopped");
}

async function sendEventBatch() {
  if (!isConnected || !apiKey || !serverUrl) return;
  if (eventQueue.length === 0) return;

  // Take a batch of events
  const batch = eventQueue.splice(0, CONFIG.batchSize);

  try {
    const response = await fetch(`${serverUrl}/api/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
      },
      body: JSON.stringify({ events: batch }),
    });

    if (!response.ok) {
      // Put events back on failure
      eventQueue.unshift(...batch);

      if (response.status === 401) {
        // API key invalid, stop connection
        console.error("API key invalid, disconnecting");
        stopServerConnection();
        apiKey = null;
        await chrome.storage.local.remove(["apiKey"]);
      }
      return;
    }

    const data = await response.json();
    console.log(`Sent ${data.processed} events to server`);

    // Save remaining events to storage
    saveEventsToStorage();
  } catch (error) {
    // Network error - put events back
    console.error("Failed to send events:", error);
    eventQueue.unshift(...batch);
  }
}

async function sendHeartbeat() {
  if (!isConnected || !apiKey || !serverUrl) return;

  try {
    const response = await fetch(`${serverUrl}/api/heartbeat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
      },
      body: JSON.stringify({
        agent_version: chrome.runtime.getManifest().version,
      }),
    });

    if (!response.ok) {
      if (response.status === 401) {
        stopServerConnection();
        apiKey = null;
        await chrome.storage.local.remove(["apiKey"]);
      }
    }
  } catch (error) {
    console.error("Heartbeat failed:", error);
  }
}

async function disconnectFromServer() {
  stopServerConnection();

  // Clear credentials but keep events locally
  apiKey = null;
  computerId = null;

  await chrome.storage.local.remove(["apiKey", "computerId"]);

  return { success: true };
}

// Tab tracking
const tabStartTimes = new Map();

chrome.tabs.onActivated.addListener((activeInfo) => {
  if (!isMonitoring) return;

  const now = Date.now();

  // Log previous tab duration
  for (const [tabId, startTime] of tabStartTimes) {
    if (tabId !== activeInfo.tabId) {
      chrome.tabs.get(tabId, (tab) => {
        if (chrome.runtime.lastError) return;

        queueEvent({
          event_type: "tab_deactivated",
          category: "browser",
          browser: "chrome",
          url: tab.url,
          data: {
            tab_id: tabId,
            title: tab.title,
            duration_ms: now - startTime,
          },
        });
      });
      tabStartTimes.delete(tabId);
    }
  }

  // Track new tab
  tabStartTimes.set(activeInfo.tabId, now);

  chrome.tabs.get(activeInfo.tabId, (tab) => {
    if (chrome.runtime.lastError) return;

    queueEvent({
      event_type: "tab_activated",
      category: "browser",
      browser: "chrome",
      url: tab.url,
      data: {
        tab_id: activeInfo.tabId,
        title: tab.title,
      },
    });
  });
});

// Page navigation - using tabs.onUpdated instead of webNavigation
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (!isMonitoring) return;

  if (changeInfo.status === "complete" && tab.url) {
    queueEvent({
      event_type: "page_load",
      category: "browser",
      browser: "chrome",
      url: tab.url,
      data: {
        tab_id: tabId,
        title: tab.title,
      },
    });
  }
});

// Message handler from content scripts and popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "event") {
    if (isMonitoring) {
      queueEvent({
        ...message.data,
        browser: "chrome",
        url: sender.tab?.url,
      });
    }
    sendResponse({ success: true });
  } else if (message.type === "getStatus") {
    sendResponse({
      eventCount: eventQueue.length,
      isMonitoring: isMonitoring,
      computerId: computerId,
      computerName: computerName,
      serverUrl: serverUrl,
      isConnected: isConnected && !!apiKey,
    });
  } else if (message.type === "toggleMonitoring") {
    isMonitoring = message.enabled;
    chrome.storage.local.set({ isMonitoring: isMonitoring });
    sendResponse({ success: true, isMonitoring: isMonitoring });
  } else if (message.type === "downloadLogs") {
    downloadLogs(message.format || "txt");
    sendResponse({ success: true });
  } else if (message.type === "clearLogs") {
    eventQueue = [];
    saveEventsToStorage();
    sendResponse({ success: true });
  } else if (message.type === "setComputerId") {
    computerId = message.computerId;
    chrome.storage.local.set({ computerId: computerId });
    sendResponse({ success: true });
  } else if (message.type === "connect") {
    // Handle async registration
    registerWithServer(message.serverUrl, message.computerName).then(
      sendResponse
    );
    return true; // Keep channel open for async response
  } else if (message.type === "disconnect") {
    disconnectFromServer().then(sendResponse);
    return true;
  } else if (message.type === "setComputerName") {
    computerName = message.computerName;
    chrome.storage.local.set({ computerName: computerName });
    sendResponse({ success: true });
  }
  return true;
});

// Queue event
function queueEvent(event) {
  event.timestamp = new Date().toISOString();
  event.computer_id = computerId;
  eventQueue.push(event);

  // Trim if exceeding max
  if (eventQueue.length > CONFIG.maxEvents) {
    eventQueue = eventQueue.slice(-CONFIG.maxEvents);
  }

  // Save to storage periodically (every 100 events)
  if (eventQueue.length % 100 === 0) {
    saveEventsToStorage();
  }
}

// Save events to Chrome storage for persistence
function saveEventsToStorage() {
  // Only save last 1000 events to storage to avoid quota issues
  const eventsToSave = eventQueue.slice(-1000);
  chrome.storage.local.set({ eventQueue: eventsToSave });
}

// Download logs as file
function downloadLogs(format = "txt") {
  if (eventQueue.length === 0) {
    console.log("No events to download");
    return;
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  let content, filename, mimeType;

  if (format === "json") {
    content = JSON.stringify(eventQueue, null, 2);
    filename = `activity-log-${timestamp}.json`;
    mimeType = "application/json";
  } else {
    // Text format - human readable
    content = formatEventsAsText(eventQueue);
    filename = `activity-log-${timestamp}.txt`;
    mimeType = "text/plain";
  }

  // Use data URL (Service Workers don't have URL.createObjectURL)
  const base64Content = btoa(unescape(encodeURIComponent(content)));
  const dataUrl = `data:${mimeType};base64,${base64Content}`;

  chrome.downloads.download(
    {
      url: dataUrl,
      filename: filename,
      saveAs: true,
    },
    (downloadId) => {
      if (chrome.runtime.lastError) {
        console.error("Download failed:", chrome.runtime.lastError);
      } else {
        console.log("Download started:", downloadId);
      }
    }
  );
}

// Format events as human-readable text
function formatEventsAsText(events) {
  const lines = [
    "=".repeat(80),
    "ACTIVITY LOG",
    `Generated: ${new Date().toISOString()}`,
    `Computer ID: ${computerId}`,
    `Total Events: ${events.length}`,
    "=".repeat(80),
    "",
  ];

  for (const event of events) {
    const time = new Date(event.timestamp).toLocaleString();
    const type = event.event_type.toUpperCase().padEnd(20);

    let details = "";

    switch (event.event_type) {
      case "page_load":
      case "tab_activated":
      case "tab_deactivated":
        details = `URL: ${event.url || "N/A"}\n         Title: ${
          event.data?.title || "N/A"
        }`;
        if (event.data?.duration_ms) {
          details += `\n         Duration: ${Math.round(
            event.data.duration_ms / 1000
          )}s`;
        }
        break;
      case "click":
      case "double_click":
      case "right_click":
      case "mouse_down":
      case "mouse_up":
        details = `Element: <${event.data?.element?.tag || "unknown"}> ${
          event.data?.element?.text || ""
        }`.substring(0, 100);
        break;
      case "keystroke":
        details = `Key: ${event.data?.key} on ${
          event.data?.target?.selector || "unknown"
        }`;
        break;
      case "focus":
        details = `Element: ${event.data?.element?.selector || "unknown"}`;
        break;
      case "blur":
        details = `Element: ${
          event.data?.element?.selector
        } (Duration: ${Math.round(event.data?.duration_ms || 0)}ms)`;
        break;
      case "form_input":
        details = `Field: ${
          event.data?.element?.name || event.data?.element?.id || "unknown"
        } (${event.data?.input_type || "text"})`;
        break;
      case "form_submit":
        details = `Form: ${
          event.data?.form_name || event.data?.form_id || "unknown"
        } -> ${event.data?.form_action || "N/A"}`;
        break;
      case "text_selection":
      case "copy":
      case "paste":
        details = `Text: "${(event.data?.text || "").substring(0, 80)}${
          event.data?.text?.length > 80 ? "..." : ""
        }"`;
        break;
      case "scroll":
        details = `Position: ${event.data?.scroll_percent || 0}% (${
          event.data?.direction || "unknown"
        })`;
        break;
      case "download_click":
        details = `File: ${event.data?.href || "N/A"}`;
        break;
      case "visibility_change":
        details = `Visible: ${event.data?.visible ? "Yes" : "No"}`;
        break;
      default:
        details = JSON.stringify(event.data || {}).substring(0, 100);
    }

    lines.push(`[${time}] ${type}`);
    lines.push(`         ${details}`);
    if (
      event.url &&
      !["page_load", "tab_activated", "tab_deactivated"].includes(
        event.event_type
      )
    ) {
      lines.push(`         Page: ${event.url}`);
    }
    lines.push("");
  }

  lines.push("=".repeat(80));
  lines.push("END OF LOG");
  lines.push("=".repeat(80));

  return lines.join("\n");
}

// Storage listener
chrome.storage.onChanged.addListener((changes, namespace) => {
  if (namespace === "local") {
    if (changes.computerId) computerId = changes.computerId.newValue;
    if (changes.isMonitoring !== undefined)
      isMonitoring = changes.isMonitoring.newValue;
  }
});

// Auto-save on extension suspend (Service Worker)
self.addEventListener("beforeunload", () => {
  saveEventsToStorage();
});

console.log("Monitor extension background service started");
