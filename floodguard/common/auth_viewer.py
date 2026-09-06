"""In-memory operator credentials for the two QA pages with write controls."""

AUTH_WIDGET_HTML = r'''
<details style="position:fixed;right:12px;bottom:12px;z-index:1000;background:#fff;
color:#17202a;padding:10px;border:1px solid #999;border-radius:6px;max-width:300px">
<summary>Operator credentials for changes</summary>
<label>Operator subject <input id="fg-auth-subject" autocomplete="off"></label><br>
<label>Bearer token <input id="fg-auth-token" type="password" autocomplete="off"></label>
<p>Credentials stay in this page only. Reload clears them. Read-only QA needs no token.</p>
</details>
<script>
(() => {
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, options = {}) => {
    const target = typeof input === 'string' || input instanceof URL ? input : input.url;
    const url = new URL(target, location.href);
    const method = (options.method ||
      (input instanceof Request ? input.method : 'GET')).toUpperCase();
    if (url.origin === location.origin && !['GET','HEAD','OPTIONS'].includes(method)) {
      const token = document.getElementById('fg-auth-token').value.trim();
      const headers = new Headers(options.headers ||
        (input instanceof Request ? input.headers : {}));
      if (token) headers.set('Authorization', 'Bearer ' + token);
      options = {...options, headers};
      if (url.pathname.endsWith('/reviews') && typeof options.body === 'string') {
        try {
          const body = JSON.parse(options.body);
          body.reviewer = document.getElementById('fg-auth-subject').value.trim();
          options = {...options, body: JSON.stringify(body)};
        } catch (_) { /* The API validates malformed bodies. */ }
      }
    }
    return originalFetch(input, options);
  };
})();
</script>
'''


def with_operator_credentials(html: str) -> str:
    return html.replace("</body>", AUTH_WIDGET_HTML + "</body>")
