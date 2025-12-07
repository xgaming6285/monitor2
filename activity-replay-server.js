/**
 * Activity Replay Proxy Server
 *
 * This server proxies web pages and removes iframe-blocking headers,
 * allowing the activity replay to scroll pages and interact with them.
 *
 * Usage: node activity-replay-server.js
 * Then open: http://localhost:3333
 */

const http = require("http");
const https = require("https");
const fs = require("fs");
const path = require("path");
const url = require("url");

const PORT = 3333;

// MIME types for static files
const MIME_TYPES = {
  ".html": "text/html",
  ".js": "application/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
};

const server = http.createServer(async (req, res) => {
  const parsedUrl = url.parse(req.url, true);

  // CORS headers for all responses
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "*");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  // Serve the main HTML file
  if (parsedUrl.pathname === "/" || parsedUrl.pathname === "/index.html") {
    const htmlPath = path.join(__dirname, "activity-replay-proxy.html");
    if (fs.existsSync(htmlPath)) {
      res.writeHead(200, { "Content-Type": "text/html" });
      fs.createReadStream(htmlPath).pipe(res);
    } else {
      res.writeHead(404);
      res.end("activity-replay-proxy.html not found");
    }
    return;
  }

  // Proxy endpoint
  if (parsedUrl.pathname === "/proxy") {
    const targetUrl = parsedUrl.query.url;

    if (!targetUrl) {
      res.writeHead(400, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Missing url parameter" }));
      return;
    }

    try {
      console.log(`[Proxy] Fetching: ${targetUrl}`);

      const proxyRes = await fetchUrl(targetUrl);

      // Get content type
      let contentType = proxyRes.headers["content-type"] || "text/html";

      // Remove security headers that block iframes
      const headersToRemove = [
        "x-frame-options",
        "content-security-policy",
        "content-security-policy-report-only",
        "x-content-type-options",
      ];

      // Copy safe headers
      const safeHeaders = {};
      for (const [key, value] of Object.entries(proxyRes.headers)) {
        if (!headersToRemove.includes(key.toLowerCase())) {
          safeHeaders[key] = value;
        }
      }

      // If HTML, rewrite URLs to go through proxy
      if (contentType.includes("text/html")) {
        let html = proxyRes.body;

        // Parse base URL for relative URLs
        const baseUrl = new URL(targetUrl);
        const baseHref = `${baseUrl.protocol}//${baseUrl.host}`;

        // Inject base tag and scroll control script
        const injection = `
          <base href="${baseHref}/">
          <script>
            // Allow parent to control scroll
            window.addEventListener('message', (e) => {
              if (e.data.type === 'scroll') {
                window.scrollTo({
                  top: e.data.position,
                  behavior: e.data.smooth ? 'smooth' : 'instant'
                });
              }
              if (e.data.type === 'getScrollHeight') {
                parent.postMessage({
                  type: 'scrollHeight',
                  height: document.documentElement.scrollHeight,
                  viewportHeight: window.innerHeight
                }, '*');
              }
            });
            // Report scroll height after load
            window.addEventListener('load', () => {
              parent.postMessage({
                type: 'scrollHeight',
                height: document.documentElement.scrollHeight,
                viewportHeight: window.innerHeight
              }, '*');
            });
          </script>
        `;

        // Insert after <head> or at start
        if (html.includes("<head>")) {
          html = html.replace("<head>", "<head>" + injection);
        } else if (html.includes("<HEAD>")) {
          html = html.replace("<HEAD>", "<HEAD>" + injection);
        } else {
          html = injection + html;
        }

        res.writeHead(200, {
          "Content-Type": "text/html; charset=utf-8",
          "Cache-Control": "no-cache",
        });
        res.end(html);
      } else {
        // For non-HTML content, pass through
        res.writeHead(proxyRes.statusCode, safeHeaders);
        res.end(proxyRes.body);
      }
    } catch (error) {
      console.error(`[Proxy] Error: ${error.message}`);
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: error.message }));
    }
    return;
  }

  // 404 for other paths
  res.writeHead(404);
  res.end("Not Found");
});

// Fetch URL helper with redirect support
function fetchUrl(targetUrl, redirectCount = 0) {
  return new Promise((resolve, reject) => {
    if (redirectCount > 5) {
      reject(new Error("Too many redirects"));
      return;
    }

    const parsedTarget = new URL(targetUrl);
    const isHttps = parsedTarget.protocol === "https:";
    const lib = isHttps ? https : http;

    const options = {
      hostname: parsedTarget.hostname,
      port: parsedTarget.port || (isHttps ? 443 : 80),
      path: parsedTarget.pathname + parsedTarget.search,
      method: "GET",
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        Accept:
          "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "identity", // No compression for simplicity
      },
    };

    const request = lib.request(options, (response) => {
      // Handle redirects
      if (
        response.statusCode >= 300 &&
        response.statusCode < 400 &&
        response.headers.location
      ) {
        const redirectUrl = new URL(response.headers.location, targetUrl).href;
        console.log(`[Proxy] Redirect to: ${redirectUrl}`);
        resolve(fetchUrl(redirectUrl, redirectCount + 1));
        return;
      }

      const chunks = [];
      response.on("data", (chunk) => chunks.push(chunk));
      response.on("end", () => {
        resolve({
          statusCode: response.statusCode,
          headers: response.headers,
          body: Buffer.concat(chunks).toString("utf-8"),
        });
      });
    });

    request.on("error", reject);
    request.end();
  });
}

server.listen(PORT, () => {
  console.log(`
╔════════════════════════════════════════════════════════════╗
║           Activity Replay Proxy Server                     ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║   Server running at: http://localhost:${PORT}                 ║
║                                                            ║
║   Open the URL above in your browser to use the            ║
║   activity replay with full scrolling support!             ║
║                                                            ║
║   Press Ctrl+C to stop the server.                         ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
`);
});
