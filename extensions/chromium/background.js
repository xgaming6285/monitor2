/**
 * Background Service Worker
 * Manages event collection and local file storage
 */

// Configuration
const CONFIG = {
  maxEvents: 10000, // Maximum events to keep in memory
  autoSaveInterval: 300000, // Auto-save every 5 minutes (optional)
  autoSaveEnabled: false, // Disabled by default
};

// Event storage
let eventQueue = [];
let isMonitoring = true;
let computerId =
  "local-" + Math.random().toString(36).substring(2, 8).toUpperCase();

// Initialize
chrome.storage.local.get(
  ["computerId", "isMonitoring", "eventQueue"],
  (result) => {
    if (result.computerId) computerId = result.computerId;
    if (result.isMonitoring !== undefined) isMonitoring = result.isMonitoring;
    if (result.eventQueue && Array.isArray(result.eventQueue)) {
      eventQueue = result.eventQueue;
    }
  }
);

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

console.log("Monitor extension background service started (Local File Mode)");
