# R-98 — Gmail IMAP Connected Unverified; Every Direct HTTPS Connection Reloaded The Trust Store

Date: 2026-09-25  
Status: FIXED IN CODE / AWAITING VALIDATION — Gmail refresh on Windows must still succeed with verification on

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure

This was found while attributing the R-97 handle slope, which correlates with Gmail refreshes.

- **Security.** `imaplib.IMAP4_SSL(host, port, timeout=...)` without `ssl_context` uses
  `ssl._create_stdlib_context`, which is `_create_unverified_context` (`CERT_NONE`, no hostname check; checked in
  CPython 3.11). The Gmail app password was therefore sent to any interceptor on the path.
- **GUI/Visualizer stalls.** `urllib` (Steam, through `bounded_urlopen`) and the feed/wallpaper artwork transport
  built a system-trust context for every connection. On Windows each build enumerates the CA and ROOT certificate
  stores and parses every certificate with the GIL held. A Linux probe with ~145 certificates measured 22 ms
  (median) per build, during which another Python thread stalled up to 36 ms. Memory stayed flat over 1500
  builds, so this is a stall defect, not a leak.

## Fix

`core.network.tls.verified_client_context()` builds one verified client context lazily for the process (system
trust, certificate and hostname checks on). `bounded_urlopen`, the artwork transport and Gmail IMAP share it.
`requests` paths keep their library-owned context. A Gmail certificate failure surfaces as the existing
`[GMAIL_IMAP] Connection error` ERROR line; there is no unverified fallback.

## Regression Coverage

`tests/test_network_tls_context.py` covers three properties: the context is built once across threads and is
verified; real `urllib`/`http.client` connections load no trust store per connection; and Gmail connects with the
verified context. `tests/test_feed_artwork_transport_f3.py` checks that every artwork hop reuses it.

## Guardrail

Contracts § Network transports: direct-socket TLS uses the one verified context.
