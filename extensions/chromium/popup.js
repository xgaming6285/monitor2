/**
 * Popup Script
 * Handles extension configuration and server connection
 */

document.addEventListener("DOMContentLoaded", async () => {
  // Elements
  const computerNameInput = document.getElementById("computerName");
  const serverUrlInput = document.getElementById("serverUrl");
  const monitorToggle = document.getElementById("monitorToggle");
  const connectBtn = document.getElementById("connectBtn");
  const disconnectBtn = document.getElementById("disconnectBtn");
  const connectBtnWrapper = document.getElementById("connectBtnWrapper");
  const disconnectBtnWrapper = document.getElementById("disconnectBtnWrapper");
  const downloadTxtBtn = document.getElementById("downloadTxtBtn");
  const downloadJsonBtn = document.getElementById("downloadJsonBtn");
  const clearBtn = document.getElementById("clearBtn");
  const statusDiv = document.getElementById("status");
  const statusText = document.getElementById("statusText");
  const connectionStatus = document.getElementById("connectionStatus");
  const connectionText = document.getElementById("connectionText");
  const connectedUrl = document.getElementById("connectedUrl");
  const messageDiv = document.getElementById("message");
  const eventCountSpan = document.getElementById("eventCount");
  const computerIdSpan = document.getElementById("computerId");
  const modeBadge = document.getElementById("modeBadge");

  // Collapsible sections
  const serverToggle = document.getElementById("serverToggle");
  const serverContent = document.getElementById("serverContent");
  const exportToggle = document.getElementById("exportToggle");
  const exportContent = document.getElementById("exportContent");

  // Load saved settings
  const stored = await chrome.storage.local.get([
    "computerId",
    "computerName",
    "serverUrl",
    "isMonitoring",
  ]);

  if (stored.computerName) {
    computerNameInput.value = stored.computerName;
  } else {
    // Generate default computer name
    const defaultName =
      "Browser-" + Math.random().toString(36).substring(2, 8).toUpperCase();
    computerNameInput.value = defaultName;
    chrome.storage.local.set({ computerName: defaultName });
  }

  if (stored.serverUrl) {
    serverUrlInput.value = stored.serverUrl;
  } else {
    // Default server URL
    serverUrlInput.value = "http://localhost:5000";
  }

  // Update status
  updateMonitoringStatus(stored.isMonitoring !== false);

  // Get status from background
  await refreshStatus();

  // Refresh status periodically
  setInterval(refreshStatus, 2000);

  // Collapsible toggles
  serverToggle.addEventListener("click", () => {
    serverToggle.classList.toggle("collapsed");
    serverContent.classList.toggle("collapsed");
  });

  exportToggle.addEventListener("click", () => {
    exportToggle.classList.toggle("collapsed");
    exportContent.classList.toggle("collapsed");
  });

  // Monitor toggle
  monitorToggle.addEventListener("change", async () => {
    const enabled = monitorToggle.checked;
    try {
      await chrome.runtime.sendMessage({
        type: "toggleMonitoring",
        enabled: enabled,
      });
      updateMonitoringStatus(enabled);
      showMessage(
        enabled ? "Recording started" : "Recording paused",
        "success"
      );
    } catch (e) {
      showMessage("Failed to toggle monitoring", "error");
    }
  });

  // Computer name change
  computerNameInput.addEventListener("change", async () => {
    const name = computerNameInput.value.trim();
    if (name) {
      await chrome.runtime.sendMessage({
        type: "setComputerName",
        computerName: name,
      });
      await chrome.storage.local.set({ computerName: name });
      showMessage("Computer name saved", "success");
    }
  });

  // Connect to server
  connectBtn.addEventListener("click", async () => {
    const serverUrl = serverUrlInput.value.trim();
    const computerName = computerNameInput.value.trim();

    if (!serverUrl) {
      showMessage("Please enter a server URL", "error");
      return;
    }

    if (!computerName) {
      showMessage("Please enter a computer name", "error");
      return;
    }

    // Validate URL format
    try {
      new URL(serverUrl);
    } catch (e) {
      showMessage("Invalid URL format", "error");
      return;
    }

    connectBtn.disabled = true;
    connectBtn.textContent = "Connecting...";

    try {
      const response = await chrome.runtime.sendMessage({
        type: "connect",
        serverUrl: serverUrl,
        computerName: computerName,
      });

      if (response.success) {
        showMessage("Connected to dashboard!", "success");
        await chrome.storage.local.set({ serverUrl });
        updateConnectionUI(true, serverUrl);
      } else {
        showMessage(response.error || "Connection failed", "error");
      }
    } catch (e) {
      showMessage("Connection failed: " + e.message, "error");
    } finally {
      connectBtn.disabled = false;
      connectBtn.textContent = "🔗 Connect to Dashboard";
    }
  });

  // Disconnect from server
  disconnectBtn.addEventListener("click", async () => {
    if (
      confirm("Disconnect from dashboard? Events will only be stored locally.")
    ) {
      try {
        await chrome.runtime.sendMessage({ type: "disconnect" });
        showMessage("Disconnected from dashboard", "success");
        updateConnectionUI(false, "");
      } catch (e) {
        showMessage("Failed to disconnect", "error");
      }
    }
  });

  // Download TXT
  downloadTxtBtn.addEventListener("click", async () => {
    try {
      await chrome.runtime.sendMessage({ type: "downloadLogs", format: "txt" });
      showMessage("Downloading text file...", "success");
    } catch (e) {
      showMessage("Download failed: " + e.message, "error");
    }
  });

  // Download JSON
  downloadJsonBtn.addEventListener("click", async () => {
    try {
      await chrome.runtime.sendMessage({
        type: "downloadLogs",
        format: "json",
      });
      showMessage("Downloading JSON file...", "success");
    } catch (e) {
      showMessage("Download failed: " + e.message, "error");
    }
  });

  // Clear logs
  clearBtn.addEventListener("click", async () => {
    if (
      confirm(
        "Are you sure you want to clear all local events? This cannot be undone."
      )
    ) {
      try {
        await chrome.runtime.sendMessage({ type: "clearLogs" });
        eventCountSpan.textContent = "0";
        showMessage("Local logs cleared", "success");
      } catch (e) {
        showMessage("Failed to clear logs", "error");
      }
    }
  });

  async function refreshStatus() {
    try {
      const response = await chrome.runtime.sendMessage({ type: "getStatus" });
      if (response) {
        eventCountSpan.textContent = response.eventCount || 0;
        computerIdSpan.textContent = response.computerId || "-";
        updateMonitoringStatus(response.isMonitoring !== false);
        updateConnectionUI(response.isConnected, response.serverUrl);

        if (response.computerName) {
          computerNameInput.value = response.computerName;
        }
      }
    } catch (e) {
      // Background might not be ready
    }
  }

  function updateMonitoringStatus(isActive) {
    monitorToggle.checked = isActive;
    if (isActive) {
      statusDiv.className = "status active";
      statusText.textContent = "● Recording";
    } else {
      statusDiv.className = "status paused";
      statusText.textContent = "● Paused";
    }
  }

  function updateConnectionUI(isConnected, serverUrl) {
    if (isConnected) {
      connectionStatus.className = "connection-status connected";
      connectionText.textContent = "Connected to dashboard";
      connectedUrl.textContent = serverUrl || "-";
      connectBtnWrapper.style.display = "none";
      disconnectBtnWrapper.style.display = "block";
      serverUrlInput.disabled = true;
      computerNameInput.disabled = true;
      modeBadge.className = "mode-badge connected";
      modeBadge.textContent = "CONNECTED";

      // Collapse server section when connected
      serverToggle.classList.add("collapsed");
      serverContent.classList.add("collapsed");

      // Expand export section
      exportToggle.classList.remove("collapsed");
      exportContent.classList.remove("collapsed");
    } else {
      connectionStatus.className = "connection-status disconnected";
      connectionText.textContent = "Not connected to server";
      connectedUrl.textContent = "-";
      connectBtnWrapper.style.display = "block";
      disconnectBtnWrapper.style.display = "none";
      serverUrlInput.disabled = false;
      computerNameInput.disabled = false;
      modeBadge.className = "mode-badge local";
      modeBadge.textContent = "LOCAL";

      // Expand server section when disconnected
      serverToggle.classList.remove("collapsed");
      serverContent.classList.remove("collapsed");
    }
  }

  function showMessage(text, type) {
    if (!text) {
      messageDiv.style.display = "none";
      messageDiv.className = "";
      return;
    }
    messageDiv.textContent = text;
    messageDiv.className = type;
    messageDiv.style.display = "block";

    // Auto-hide after 3 seconds
    setTimeout(() => {
      messageDiv.style.display = "none";
    }, 3000);
  }
});
