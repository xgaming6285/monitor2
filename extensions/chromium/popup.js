/**
 * Popup Script
 * Handles extension configuration and server registration
 */

document.addEventListener('DOMContentLoaded', async () => {
  const serverUrlInput = document.getElementById('serverUrl');
  const computerNameInput = document.getElementById('computerName');
  const registerBtn = document.getElementById('registerBtn');
  const disconnectBtn = document.getElementById('disconnectBtn');
  const statusDiv = document.getElementById('status');
  const messageDiv = document.getElementById('message');
  const configSection = document.getElementById('configSection');
  const connectedSection = document.getElementById('connectedSection');
  const queueCountSpan = document.getElementById('queueCount');
  const computerIdSpan = document.getElementById('computerId');

  // Load saved settings
  const stored = await chrome.storage.local.get([
    'serverUrl', 
    'apiKey', 
    'computerId', 
    'computerName'
  ]);

  if (stored.serverUrl) {
    serverUrlInput.value = stored.serverUrl;
  }
  
  if (stored.computerName) {
    computerNameInput.value = stored.computerName;
  } else {
    // Try to get a default computer name
    computerNameInput.value = 'Browser-' + Math.random().toString(36).substring(2, 8).toUpperCase();
  }

  // Update UI based on connection status
  updateUI(stored);

  // Get queue count from background
  try {
    const response = await chrome.runtime.sendMessage({ type: 'getStatus' });
    if (response) {
      queueCountSpan.textContent = response.queueCount || 0;
    }
  } catch (e) {
    // Background might not be ready
  }

  // Register button
  registerBtn.addEventListener('click', async () => {
    const serverUrl = serverUrlInput.value.trim().replace(/\/$/, '');
    const computerName = computerNameInput.value.trim();

    if (!serverUrl) {
      showMessage('Please enter a server URL', 'error');
      return;
    }

    if (!computerName) {
      showMessage('Please enter a computer name', 'error');
      return;
    }

    registerBtn.disabled = true;
    registerBtn.textContent = 'Connecting...';
    showMessage('', '');

    try {
      // Register with server
      const response = await fetch(`${serverUrl}/api/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          computer_name: computerName,
          username: 'browser-extension',
          os_version: navigator.userAgent,
          agent_version: chrome.runtime.getManifest().version
        })
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ error: 'Server error' }));
        throw new Error(error.error || `HTTP ${response.status}`);
      }

      const data = await response.json();

      // Save credentials
      await chrome.storage.local.set({
        serverUrl: serverUrl,
        apiKey: data.api_key,
        computerId: data.computer_id,
        computerName: computerName
      });

      showMessage('Connected successfully!', 'success');
      updateUI({
        serverUrl,
        apiKey: data.api_key,
        computerId: data.computer_id,
        computerName
      });

      // Notify background to start sending
      chrome.runtime.sendMessage({ type: 'configUpdated' });

    } catch (error) {
      showMessage(`Failed to connect: ${error.message}`, 'error');
    } finally {
      registerBtn.disabled = false;
      registerBtn.textContent = 'Register & Connect';
    }
  });

  // Disconnect button
  disconnectBtn.addEventListener('click', async () => {
    await chrome.storage.local.remove(['apiKey', 'computerId']);
    showMessage('Disconnected', 'success');
    updateUI({});
    chrome.runtime.sendMessage({ type: 'configUpdated' });
  });

  function updateUI(stored) {
    if (stored.apiKey && stored.computerId) {
      // Connected
      statusDiv.className = 'status connected';
      statusDiv.textContent = '● Connected to server';
      configSection.style.display = 'none';
      connectedSection.style.display = 'block';
      computerIdSpan.textContent = stored.computerId;
      
      // Show server URL as readonly info
      serverUrlInput.disabled = true;
      computerNameInput.disabled = true;
    } else {
      // Not connected
      statusDiv.className = 'status disconnected';
      statusDiv.textContent = '● Not connected';
      configSection.style.display = 'block';
      connectedSection.style.display = 'none';
      computerIdSpan.textContent = '-';
      
      serverUrlInput.disabled = false;
      computerNameInput.disabled = false;
    }
  }

  function showMessage(text, type) {
    if (!text) {
      messageDiv.style.display = 'none';
      messageDiv.className = '';
      return;
    }
    messageDiv.textContent = text;
    messageDiv.className = type;
    messageDiv.style.display = 'block';
  }
});

