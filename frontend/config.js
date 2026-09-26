// Backend API base URL. Loaded before script.js.
// - Local dev: leave as-is (FastAPI running on localhost:8080 via `make run`).
// - Production: replace with your deployed Render URL, e.g.
//   "https://lexai-backend.onrender.com" (no trailing slash).
window.API_BASE_URL =
  window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://localhost:8080"
    : "https://lexai-in6o.onrender.com";
