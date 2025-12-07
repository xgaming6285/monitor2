/**
 * Popup Script
 * Handles extension configuration and log downloads
 */

document.addEventListener("DOMContentLoaded", async () => {
  const computerNameInput = document.getElementById("computerName");
  const monitorToggle = document.getElementById("monitorToggle");
  const downloadTxtBtn = document.getElementById("downloadTxtBtn");
  const downloadJsonBtn = document.getElementById("downloadJsonBtn");
  const clearBtn = document.getElementById("clearBtn");
  const statusDiv = document.getElementById("status");
  const statusText = document.getElementById("statusText");
  const messageDiv = document.getElementById("message");
  const eventCountSpan = document.getElementById("eventCount");
  const computerIdSpan = document.getElementById("computerId");

  // Load saved settings
  const stored = await chrome.storage.local.get([
    "computerId",
    "computerName",
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

  // Update status
  updateStatus(stored.isMonitoring !== false);

  // Get status from background
  await refreshStatus();

  // Refresh status periodically
  setInterval(refreshStatus, 2000);

  // Monitor toggle
  monitorToggle.addEventListener("change", async () => {
    const enabled = monitorToggle.checked;
    try {
      await chrome.runtime.sendMessage({
        type: "toggleMonitoring",
        enabled: enabled,
      });
      updateStatus(enabled);
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
      await chrome.storage.local.set({ computerName: name });
      showMessage("Computer name saved", "success");
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
        "Are you sure you want to clear all recorded events? This cannot be undone."
      )
    ) {
      try {
        await chrome.runtime.sendMessage({ type: "clearLogs" });
        eventCountSpan.textContent = "0";
        showMessage("All logs cleared", "success");
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
        updateStatus(response.isMonitoring !== false);
      }
    } catch (e) {
      // Background might not be ready
    }
  }

  function updateStatus(isActive) {
    monitorToggle.checked = isActive;
    if (isActive) {
      statusDiv.className = "status active";
      statusText.textContent = "● Recording";
    } else {
      statusDiv.className = "status paused";
      statusText.textContent = "● Paused";
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
