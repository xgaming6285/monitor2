/**
 * Background Service Worker
 * Manages event collection and server communication
 */

// Configuration
const CONFIG = {
  serverUrl: 'http://localhost:5000',
  batchSize: 50,
  batchInterval: 5000, // 5 seconds
  heartbeatInterval: 30000, // 30 seconds
};

// Event queue
let eventQueue = [];
let apiKey = null;
let computerId = null;

// Initialize
chrome.storage.local.get(['apiKey', 'computerId', 'serverUrl'], (result) => {
  if (result.apiKey) apiKey = result.apiKey;
  if (result.computerId) computerId = result.computerId;
  if (result.serverUrl) CONFIG.serverUrl = result.serverUrl;
});

// Tab tracking
const tabStartTimes = new Map();

chrome.tabs.onActivated.addListener((activeInfo) => {
  const now = Date.now();
  
  // Log previous tab duration
  for (const [tabId, startTime] of tabStartTimes) {
    if (tabId !== activeInfo.tabId) {
      chrome.tabs.get(tabId, (tab) => {
        if (chrome.runtime.lastError) return;
        
        queueEvent({
          event_type: 'tab_deactivated',
          category: 'browser',
          browser: 'chrome',
          url: tab.url,
          data: {
            tab_id: tabId,
            title: tab.title,
            duration_ms: now - startTime
          }
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
      event_type: 'tab_activated',
      category: 'browser',
      browser: 'chrome',
      url: tab.url,
      data: {
        tab_id: activeInfo.tabId,
        title: tab.title
      }
    });
  });
});

// Page navigation - using tabs.onUpdated instead of webNavigation
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    queueEvent({
      event_type: 'page_load',
      category: 'browser',
      browser: 'chrome',
      url: tab.url,
      data: {
        tab_id: tabId,
        title: tab.title
      }
    });
  }
});

// Message handler from content scripts and popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'event') {
    queueEvent({
      ...message.data,
      browser: 'chrome',
      url: sender.tab?.url
    });
    sendResponse({ success: true });
  } else if (message.type === 'getStatus') {
    sendResponse({
      queueCount: eventQueue.length,
      connected: !!apiKey,
      computerId: computerId
    });
  } else if (message.type === 'configUpdated') {
    // Reload config from storage
    chrome.storage.local.get(['apiKey', 'computerId', 'serverUrl'], (result) => {
      apiKey = result.apiKey || null;
      computerId = result.computerId || null;
      if (result.serverUrl) CONFIG.serverUrl = result.serverUrl;
      
      // Try to send queued events now
      if (apiKey && eventQueue.length > 0) {
        sendBatch();
      }
    });
    sendResponse({ success: true });
  }
  return true;
});

// Queue event
function queueEvent(event) {
  event.timestamp = new Date().toISOString();
  eventQueue.push(event);
  
  // Send if batch is full
  if (eventQueue.length >= CONFIG.batchSize) {
    sendBatch();
  }
}

// Send batch to server
async function sendBatch() {
  if (eventQueue.length === 0) return;
  if (!apiKey) {
    console.log('No API key, events queued:', eventQueue.length);
    return;
  }
  
  const batch = eventQueue.splice(0, CONFIG.batchSize);
  
  try {
    const response = await fetch(`${CONFIG.serverUrl}/api/events`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey
      },
      body: JSON.stringify({ events: batch })
    });
    
    if (!response.ok) {
      // Put events back in queue
      eventQueue = batch.concat(eventQueue);
      console.error('Failed to send batch:', response.status);
    } else {
      console.log('Sent batch:', batch.length, 'events');
    }
  } catch (error) {
    // Put events back in queue
    eventQueue = batch.concat(eventQueue);
    console.error('Error sending batch:', error);
  }
}

// Periodic batch sending
setInterval(sendBatch, CONFIG.batchInterval);

// Storage for configuration
chrome.storage.onChanged.addListener((changes, namespace) => {
  if (namespace === 'local') {
    if (changes.apiKey) apiKey = changes.apiKey.newValue;
    if (changes.computerId) computerId = changes.computerId.newValue;
    if (changes.serverUrl) CONFIG.serverUrl = changes.serverUrl.newValue;
  }
});

console.log('Monitor extension background service started');

