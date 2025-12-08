/**
 * Content Script
 * Captures in-page user interactions
 */

(function () {
  "use strict";

  // Debounce helper
  function debounce(func, wait) {
    let timeout;
    return function (...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  }

  // Check if extension context is still valid
  function isExtensionContextValid() {
    try {
      // Accessing chrome.runtime.id can throw if context is invalidated
      return !!(
        typeof chrome !== "undefined" &&
        chrome.runtime &&
        chrome.runtime.id
      );
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
        console.log(
          "Monitor: Extension context invalidated, please refresh the page"
        );
      }
      return;
    }

    try {
      chrome.runtime
        .sendMessage({
          type: "event",
          data: {
            event_type: eventType,
            category: "browser",
            data: data,
          },
        })
        .catch(() => {});
    } catch (e) {
      // Extension context was invalidated - silently ignore
    }
  }

  // Get element description
  function getElementInfo(element) {
    if (!element) return null;

    const rect = element.getBoundingClientRect();

    return {
      tag: element.tagName?.toLowerCase(),
      id: element.id || null,
      class: element.className || null,
      name: element.name || null,
      type: element.type || null,
      text: (element.innerText || element.value || "").substring(0, 100),
      href: element.href || null,
      placeholder: element.placeholder || null,
      selector: getElementSelector(element),
      xpath: getXPath(element),
      aria_label: element.getAttribute("aria-label"),
      data_attributes: getDataAttributes(element),
      position: {
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
      },
    };
  }

  // Get unique CSS selector for an element
  function getElementSelector(element) {
    if (!element) return null;
    if (element.id) return `#${element.id}`;

    const path = [];
    while (element && element.nodeType === Node.ELEMENT_NODE) {
      let selector = element.nodeName.toLowerCase();
      if (element.id) {
        selector += "#" + element.id;
        path.unshift(selector);
        break;
      }

      let sibling = element;
      let nth = 1;
      while ((sibling = sibling.previousElementSibling)) {
        if (sibling.nodeName.toLowerCase() === selector) nth++;
      }

      if (nth > 1) {
        selector += `:nth-of-type(${nth})`;
      }

      path.unshift(selector);
      element = element.parentNode;
    }
    return path.join(" > ");
  }

  // Get XPath for an element
  function getXPath(element) {
    if (element.id !== "") return `id("${element.id}")`;
    if (element === document.body) return element.tagName;

    var ix = 0;
    var siblings = element.parentNode.childNodes;
    for (var i = 0; i < siblings.length; i++) {
      var sibling = siblings[i];
      if (sibling === element)
        return (
          getXPath(element.parentNode) +
          "/" +
          element.tagName +
          "[" +
          (ix + 1) +
          "]"
        );
      if (sibling.nodeType === 1 && sibling.tagName === element.tagName) ix++;
    }
  }

  function getDataAttributes(element) {
    const data = {};
    for (const attr of element.attributes) {
      if (attr.name.startsWith("data-")) {
        data[attr.name] = attr.value;
      }
    }
    return data;
  }

  function isInputElement(element) {
    return (
      element.tagName === "INPUT" ||
      element.tagName === "TEXTAREA" ||
      element.isContentEditable
    );
  }

  // Track clicks
  document.addEventListener(
    "click",
    (e) => {
      const target = e.target;
      const elementInfo = getElementInfo(target);

      sendEvent("click", {
        element: elementInfo,
        x: e.clientX,
        y: e.clientY,
        button: e.button,
        // Include viewport dimensions for accurate replay
        viewport_width: window.innerWidth,
        viewport_height: window.innerHeight,
      });
    },
    true
  );

  // Track double clicks
  document.addEventListener(
    "dblclick",
    (e) => {
      sendEvent("double_click", {
        element: getElementInfo(e.target),
        x: e.clientX,
        y: e.clientY,
      });
    },
    true
  );

  // Track right clicks
  document.addEventListener(
    "contextmenu",
    (e) => {
      sendEvent("right_click", {
        element: getElementInfo(e.target),
        x: e.clientX,
        y: e.clientY,
      });
    },
    true
  );

  // Track mouse down
  document.addEventListener(
    "mousedown",
    (e) => {
      sendEvent("mouse_down", {
        element: getElementInfo(e.target),
        x: e.clientX,
        y: e.clientY,
        button: e.button,
      });
    },
    true
  );

  // Track mouse up
  document.addEventListener(
    "mouseup",
    (e) => {
      sendEvent("mouse_up", {
        element: getElementInfo(e.target),
        x: e.clientX,
        y: e.clientY,
        button: e.button,
      });
    },
    true
  );

  // NOTE: Keystroke capture is disabled in the extension because the desktop agent
  // already captures all keystrokes system-wide via pynput. Having both enabled
  // causes duplicate characters in the live replay.
  // The extension focuses on browser-specific events (navigation, clicks, forms, etc.)

  // If you need keystroke capture ONLY from the extension (no desktop agent),
  // uncomment the following:
  /*
  document.addEventListener(
    "keydown",
    (e) => {
      const target = e.target;
      const isPassword = target.type === "password";

      sendEvent("keystroke", {
        key: isPassword ? "[REDACTED]" : e.key,
        code: e.code,
        keyCode: e.keyCode,
        isSpecial: e.key.length > 1,
        modifiers: {
          ctrl: e.ctrlKey,
          alt: e.altKey,
          shift: e.shiftKey,
          meta: e.metaKey,
        },
        target: getElementInfo(target),
        isInput: isInputElement(target),
        timestamp_ms: performance.now(),
      });
    },
    true
  );
  */

  let focusStartTime = null;
  // Track focus
  document.addEventListener(
    "focusin",
    (e) => {
      focusStartTime = performance.now();
      sendEvent("focus", {
        element: getElementInfo(e.target),
      });
    },
    true
  );

  // Track blur
  document.addEventListener(
    "focusout",
    (e) => {
      const duration = focusStartTime ? performance.now() - focusStartTime : 0;
      sendEvent("blur", {
        element: getElementInfo(e.target),
        duration_ms: duration,
      });
      focusStartTime = null;
    },
    true
  );

  // Track form inputs (debounced)
  const inputHandler = debounce((e) => {
    const target = e.target;
    if (!target.tagName) return;

    const tag = target.tagName.toLowerCase();
    if (tag !== "input" && tag !== "textarea" && tag !== "select") return;

    // Don't log password fields content
    const isPassword = target.type === "password";

    sendEvent("form_input", {
      element: getElementInfo(target),
      value: isPassword ? "[PASSWORD]" : (target.value || "").substring(0, 500),
      input_type: target.type || "text",
    });
  }, 1000);

  document.addEventListener("input", inputHandler, true);

  // Track text selection
  document.addEventListener("mouseup", () => {
    const selection = window.getSelection();
    const selectedText = selection?.toString().trim();

    if (selectedText && selectedText.length > 0) {
      sendEvent("text_selection", {
        text: selectedText.substring(0, 500),
        length: selectedText.length,
      });
    }
  });

  // Track scroll (debounced)
  let lastScrollPosition = 0;
  const scrollHandler = debounce(() => {
    const scrollPosition = window.scrollY;
    const scrollHeight = document.documentElement.scrollHeight;
    const viewportHeight = window.innerHeight;
    const scrollPercent = Math.round(
      (scrollPosition / (scrollHeight - viewportHeight)) * 100
    );

    sendEvent("scroll", {
      scroll_y: scrollPosition,
      scroll_percent: Math.min(100, Math.max(0, scrollPercent)),
      direction: scrollPosition > lastScrollPosition ? "down" : "up",
    });

    lastScrollPosition = scrollPosition;
  }, 500);

  window.addEventListener("scroll", scrollHandler, { passive: true });

  // Track form submissions
  document.addEventListener(
    "submit",
    (e) => {
      const form = e.target;

      sendEvent("form_submit", {
        form_id: form.id || null,
        form_name: form.name || null,
        form_action: form.action || null,
        form_method: form.method || "get",
      });
    },
    true
  );

  // Track page visibility
  document.addEventListener("visibilitychange", () => {
    sendEvent("visibility_change", {
      visible: !document.hidden,
      visibility_state: document.visibilityState,
    });
  });

  // Track copy events
  document.addEventListener("copy", () => {
    const selection = window.getSelection();
    const copiedText = selection?.toString().trim();

    if (copiedText) {
      sendEvent("copy", {
        text: copiedText.substring(0, 500),
        length: copiedText.length,
      });
    }
  });

  // Track paste events
  document.addEventListener("paste", (e) => {
    const pastedText = e.clipboardData?.getData("text") || "";

    sendEvent("paste", {
      text: pastedText.substring(0, 500),
      length: pastedText.length,
    });
  });

  // Track download links
  document.addEventListener(
    "click",
    (e) => {
      const link = e.target.closest(
        'a[download], a[href$=".pdf"], a[href$=".doc"], a[href$=".docx"], a[href$=".xls"], a[href$=".xlsx"], a[href$=".zip"]'
      );
      if (link) {
        sendEvent("download_click", {
          href: link.href,
          download: link.download || null,
          text: link.innerText?.substring(0, 100),
        });
      }
    },
    true
  );

  // Page unload - send session duration
  const pageLoadTime = Date.now();
  window.addEventListener("beforeunload", () => {
    const duration = Date.now() - pageLoadTime;

    // Use sendBeacon for reliable delivery
    const data = JSON.stringify({
      type: "event",
      data: {
        event_type: "page_unload",
        category: "browser",
        data: {
          duration_ms: duration,
          scroll_depth: Math.round(
            (lastScrollPosition / document.documentElement.scrollHeight) * 100
          ),
        },
      },
    });

    // Note: sendBeacon might not work for extension communication
    sendEvent("page_unload", {
      duration_ms: duration,
      scroll_depth: Math.round(
        (lastScrollPosition / document.documentElement.scrollHeight) * 100
      ),
    });
  });

  console.log("Monitor content script loaded");
})();
