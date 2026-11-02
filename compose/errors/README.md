# Backend fallback

Flask and nginx-proxy serve self-contained error documents with embedded mascot,
logo, fonts, and CSS. They work without the app, database, or CDNs. There is no
status badge or footer; the headline directly describes the failure.

nginx uses `internal.html` for HTTP 500, `unavailable.html` for 502/503, and
`timeout.html` for 504, preserving the original status. It leaves responses
returned by the app intact. A proxy error cannot identify a GitLab outage.

Flask recognizes GitLab SDK failures, requests/httpx failures to configured GitLab,
SourceCraft, and Yandex ID hosts, and database operational/interface errors.
It follows exception causes and uses the named service's page. A service outage
returns 503, a timeout 504, and rejected service access 502. Other internal errors
remain 500. Unknown causes do not blame a provider, and provider 404s are not
described as outages. An identity-service 5xx does not invalidate the user's session.
API requests receive the same public explanation as JSON, without exception details.
The nginx-proxy HTTP catch-all uses the generic `50x.html` when a stopped container
loses its virtual host. HTTPS still requires a valid certificate: if the virtual
host disappears entirely, nginx-proxy needs its usual `default.crt` and
`default.key` in the certificate volume to serve the catch-all over TLS.

After editing `manytask/manytask/templates/backend_error.html`, the error copy, or its assets,
rebuild the document from the `manytask/` component:

```sh
.venv/bin/python scripts/build_error_page.py
```

The whole error-assets directory is mounted read-only. Recreate the shared proxy
once to install this mount (the regular app deploy
does not recreate this stack):

```sh
docker compose -f compose/docker-compose.proxy.yml up -d
```

The default server include applies to hosts without a custom file in the
`vhost` volume. Hosts with custom vhost configuration must include
`/etc/nginx/vhost.d/default` themselves. Existing per-host error-page rules
also need to be reconciled. This fallback requires the edge proxy to be up.

Brand asset licenses are in `manytask/manytask/static/errors/`.
