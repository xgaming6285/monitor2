/**
 * Content Script (Firefox)
 * Captures in-page user interactions
 */

(function() {
  'use strict';

  // Debounce helper
  function debounce(func, wait) {
    let timeout;
    return function(...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  }

  // Check if extension context is still valid
  function isExtensionContextValid() {
    try {
      // Accessing browser.runtime.id can throw if context is invalidated
      return !!(typeof browser !== 'undefined' && 
                browser.runtime && 
                browser.runtime.id);
    } catch (e) {
      return false;
    }
  }

  // Track if we've already warned about invalidated context
  let contextInvalidatedWarned = false;

  // Send event to background
  function sendEvent(eventType, data) {
    // Check if extension context is still valid (prevents orphaned script errors)
    if (!isExtensionContextValid()) {
      // Only warn once to avoid console spam
      if (!contextInvalidatedWarned) {
        contextInvalidatedWarned = true;
        console.log('Monitor: Extension context invalidated, please refresh the page');
      }
      return;
    }
    
    try {
      browser.runtime.sendMessage({
        type: 'event',
        data: {
          event_type: eventType,
          category: 'browser',
          data: data
        }
      }).catch(() => {});
    } catch (e) {
      // Extension context was invalidated - silently ignore
    }
  }

  // Get element description
  function getElementInfo(element) {
    if (!element) return null;
    
    return {
      tag: element.tagName?.toLowerCase(),
      id: element.id || null,
      class: element.className || null,
      name: element.name || null,
      type: element.type || null,
      text: (element.innerText || element.value || '').substring(0, 100),
      href: element.href || null,
      placeholder: element.placeholder || null
    };
  }

  // Track clicks
  document.addEventListener('click', (e) => {
    const target = e.target;
    const elementInfo = getElementInfo(target);
    
    sendEvent('click', {
      element: elementInfo,
      x: e.clientX,
      y: e.clientY,
      button: e.button
    });
  }, true);

  // Track form inputs (debounced)
  const inputHandler = debounce((e) => {
    const target = e.target;
    if (!target.tagName) return;
    
    const tag = target.tagName.toLowerCase();
    if (tag !== 'input' && tag !== 'textarea' && tag !== 'select') return;
    
    const isPassword = target.type === 'password';
    
    sendEvent('form_input', {
      element: getElementInfo(target),
      value: isPassword ? '[PASSWORD]' : (target.value || '').substring(0, 500),
      input_type: target.type || 'text'
    });
  }, 1000);

  document.addEventListener('input', inputHandler, true);

  // Track text selection
  document.addEventListener('mouseup', () => {
    const selection = window.getSelection();
    const selectedText = selection?.toString().trim();
    
    if (selectedText && selectedText.length > 0) {
      sendEvent('text_selection', {
        text: selectedText.substring(0, 500),
        length: selectedText.length
      });
    }
  });

  // Track scroll (debounced)
  let lastScrollPosition = 0;
  const scrollHandler = debounce(() => {
    const scrollPosition = window.scrollY;
    const scrollHeight = document.documentElement.scrollHeight;
    const viewportHeight = window.innerHeight;
    const scrollPercent = Math.round((scrollPosition / (scrollHeight - viewportHeight)) * 100);
    
    sendEvent('scroll', {
      scroll_y: scrollPosition,
      scroll_percent: Math.min(100, Math.max(0, scrollPercent)),
      direction: scrollPosition > lastScrollPosition ? 'down' : 'up'
    });
    
    lastScrollPosition = scrollPosition;
  }, 500);

  window.addEventListener('scroll', scrollHandler, { passive: true });

  // Track form submissions
  document.addEventListener('submit', (e) => {
    const form = e.target;
    
    sendEvent('form_submit', {
      form_id: form.id || null,
      form_name: form.name || null,
      form_action: form.action || null,
      form_method: form.method || 'get'
    });
  }, true);

  // Track page visibility
  document.addEventListener('visibilitychange', () => {
    sendEvent('visibility_change', {
      visible: !document.hidden,
      visibility_state: document.visibilityState
    });
  });

  // Track copy events
  document.addEventListener('copy', () => {
    const selection = window.getSelection();
    const copiedText = selection?.toString().trim();
    
    if (copiedText) {
      sendEvent('copy', {
        text: copiedText.substring(0, 500),
        length: copiedText.length
      });
    }
  });

  // Track paste events
  document.addEventListener('paste', (e) => {
    const pastedText = e.clipboardData?.getData('text') || '';
    
    sendEvent('paste', {
      text: pastedText.substring(0, 500),
      length: pastedText.length
    });
  });

  // Page unload
  const pageLoadTime = Date.now();
  window.addEventListener('beforeunload', () => {
    const duration = Date.now() - pageLoadTime;
    
    sendEvent('page_unload', {
      duration_ms: duration,
      scroll_depth: Math.round((lastScrollPosition / document.documentElement.scrollHeight) * 100)
    });
  });

  console.log('Monitor content script loaded (Firefox)');
})();

