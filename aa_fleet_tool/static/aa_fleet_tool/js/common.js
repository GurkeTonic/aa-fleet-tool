/* Shared helpers for all Fleet Tool pages.
 *
 * Templated values (the translated error string) are injected via
 * window.FT_COMMON in a small inline <script> the page renders before this
 * file, so the logic itself can live in a cacheable static file.
 */
(function () {
  "use strict";

  const CSRF = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";
  const cfg = window.FT_COMMON || {};
  const SERVER_ERROR = (cfg.i18n && cfg.i18n.serverError) || "Server error.";

  // POST helper with CSRF; always resolves to a parsed JSON object.
  window.ftPost = function (url, data) {
    const fd = new FormData();
    fd.append("csrfmiddlewaretoken", CSRF);
    for (const [k, v] of Object.entries(data || {})) fd.append(k, v);
    return fetch(url, { method: "POST", body: fd })
      .then(r => r.json())
      .catch(err => { console.error("POST failed:", url, err); return { ok: false, error: SERVER_ERROR }; });
  };

  window.ftReload = function () { window.location.reload(); };
}());
