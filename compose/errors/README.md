# Backend fallback

Flask and nginx-proxy serve the same self-contained error document. It includes
the mascot, logo, fonts, and CSS, so it works without the app, database, or CDNs.
HTTP 500, 502, 503, and 504 keep their status codes. Flask API requests receive
a generic JSON error; nginx leaves responses returned by the app intact.
The nginx-proxy HTTP catch-all also uses this page when a stopped container
loses its virtual host. HTTPS still requires a valid certificate: if the virtual
host disappears entirely, nginx-proxy needs its usual `default.crt` and
`default.key` in the certificate volume to serve the catch-all over TLS.

After editing `manytask/manytask/templates/backend_error.html` or its assets,
rebuild the document from the `manytask/` component:

```sh
.venv/bin/python scripts/build_error_page.py
```

Recreate the shared proxy once to install the new mounts (the regular app deploy
does not recreate this stack):

```sh
docker compose -f compose/docker-compose.proxy.yml up -d
```

The default server include applies to hosts without a custom file in the
`vhost` volume. Hosts with custom vhost configuration must include
`/etc/nginx/vhost.d/default` themselves. Existing per-host error-page rules
also need to be reconciled. This fallback requires the edge proxy to be up.

Brand asset licenses are in `manytask/manytask/static/errors/`.
