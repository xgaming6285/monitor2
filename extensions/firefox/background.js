/**
 * Background Script (Firefox)
 * Manages event collection and server communication
 */

// Configuration
const CONFIG = {
  serverUrl: 'http://localhost:5000',
  batchSize: 50,
  batchInterval: 5000, // 5 seconds
};

// Event queue
let eventQueue = [];
let apiKey = null;
let computerId = null;

// Initialize
browser.storage.local.get(['apiKey', 'computerId', 'serverUrl']).then((result) => {
  if (result.apiKey) apiKey = result.apiKey;
  if (result.computerId) computerId = result.computerId;
  if (result.serverUrl) CONFIG.serverUrl = result.serverUrl;
});

// Tab tracking
const tabStartTimes = new Map();

browser.tabs.onActivated.addListener((activeInfo) => {
  const now = Date.now();
  
  // Log previous tab duration
  for (const [tabId, startTime] of tabStartTimes) {
    if (tabId !== activeInfo.tabId) {
      browser.tabs.get(tabId).then((tab) => {
        queueEvent({
          event_type: 'tab_deactivated',
          category: 'browser',
          browser: 'firefox',
          url: tab.url,
          data: {
            tab_id: tabId,
            title: tab.title,
            duration_ms: now - startTime
          }
        });
      }).catch(() => {});
      tabStartTimes.delete(tabId);
    }
  }
  
  // Track new tab
  tabStartTimes.set(activeInfo.tabId, now);
  
  browser.tabs.get(activeInfo.tabId).then((tab) => {
    queueEvent({
      event_type: 'tab_activated',
      category: 'browser',
      browser: 'firefox',
      url: tab.url,
      data: {
        tab_id: activeInfo.tabId,
        title: tab.title
      }
    });
  }).catch(() => {});
});

// Page navigation
browser.webNavigation.onCompleted.addListener((details) => {
  if (details.frameId !== 0) return; // Main frame only
  
  browser.tabs.get(details.tabId).then((tab) => {
    queueEvent({
      event_type: 'page_load',
      category: 'browser',
      browser: 'firefox',
      url: details.url,
      data: {
        tab_id: details.tabId,
        title: tab.title
      }
    });
  }).catch(() => {});
});

// Message handler from content scripts
browser.runtime.onMessage.addListener((message, sender) => {
  if (message.type === 'event') {
    queueEvent({
      ...message.data,
      browser: 'firefox',
      url: sender.tab?.url
    });
    return Promise.resolve({ success: true });
  }
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
      eventQueue = batch.concat(eventQueue);
      console.error('Failed to send batch:', response.status);
    } else {
      console.log('Sent batch:', batch.length, 'events');
    }
  } catch (error) {
    eventQueue = batch.concat(eventQueue);
    console.error('Error sending batch:', error);
  }
}

// Periodic batch sending
setInterval(sendBatch, CONFIG.batchInterval);

// Storage changes
browser.storage.onChanged.addListener((changes, namespace) => {
  if (namespace === 'local') {
    if (changes.apiKey) apiKey = changes.apiKey.newValue;
    if (changes.computerId) computerId = changes.computerId.newValue;
    if (changes.serverUrl) CONFIG.serverUrl = changes.serverUrl.newValue;
  }
});

console.log('Monitor extension background script started (Firefox)');

