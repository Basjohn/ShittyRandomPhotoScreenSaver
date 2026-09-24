"""Bounded-DNS HTTP entry points for the IO-lane network families.

``requests`` and ``urllib`` both resolve host names with an unbounded
``getaddrinfo`` inside their connection code, on every redirect hop. These
wrappers resolve each hop's connection host (the proxy's, when one applies)
through ``core.network.bounded_dns`` first, so the connection that follows
reuses the operating system's cached answer and a stalled DNS server costs at
most the lookup deadline, honours the caller's retirement fence and the
process exit fence. Redirects are therefore followed here, one bounded hop at
a time, using the libraries' own redirect semantics (``Response.next`` for
``requests``; ``HTTPRedirectHandler`` for ``urllib``).

A lookup that fails surfaces as the library's own connection error
(``requests.ConnectionError``; ``urllib.error.URLError``), so every family's
existing error handling applies unchanged. Neither library is imported until a
request is made.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable
from urllib.parse import urlparse

from .bounded_dns import DEFAULT_DNS_TIMEOUT, DnsLookupError, resolve_bounded

if TYPE_CHECKING:
    import requests
    import urllib.request

DEFAULT_MAX_REDIRECTS = 30  # requests' own default ceiling


def _host_port(url: str) -> tuple[str, int]:
    target = urlparse(url if "://" in url else f"http://{url}")
    default = 443 if target.scheme.casefold() in {"https", "wss"} else 80
    try:
        port = target.port or default
    except ValueError:
        port = default
    return target.hostname or "", port


def requests_connection_host(url: str, *, session: "requests.Session | None" = None,
                             proxies: dict | None = None) -> tuple[str, int]:
    """The host ``requests`` will resolve to reach ``url``: its proxy's, if one applies."""
    import requests.utils

    merged: dict = {}
    trust_env = True if session is None else bool(getattr(session, "trust_env", False))
    if trust_env and requests.utils.getproxies():
        merged.update(requests.utils.get_environ_proxies(url))
    if session is not None:
        merged.update(getattr(session, "proxies", None) or {})
    merged.update(proxies or {})
    proxy = requests.utils.select_proxy(url, merged) if merged else None
    return _host_port(proxy or url)


def urllib_connection_host(url: str) -> tuple[str, int]:
    """The host ``urllib`` will resolve to reach ``url``: its proxy's, if one applies."""
    import urllib.request

    host, port = _host_port(url)
    proxy = urllib.request.getproxies().get(urlparse(url).scheme.casefold())
    if proxy and not urllib.request.proxy_bypass(host):
        return _host_port(proxy)
    return host, port


def _resolve(host: str, port: int, *, should_continue: Callable[[], bool] | None,
             dns_timeout: float) -> None:
    if host:
        resolve_bounded(host, port, timeout=dns_timeout, should_continue=should_continue)


def bounded_request(
    method: str,
    url: str,
    *,
    session: "requests.Session | None" = None,
    should_continue: Callable[[], bool] | None = None,
    dns_timeout: float = DEFAULT_DNS_TIMEOUT,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    **kwargs: Any,
) -> "requests.Response":
    """``session.request(method, url, **kwargs)`` with every hop's DNS bounded.

    Without a ``session`` a temporary one is used and closed, exactly like
    ``requests.get``. ``allow_redirects`` keeps its ``requests`` meaning.
    """
    import requests

    active = session if session is not None else requests.Session()
    follow = bool(kwargs.pop("allow_redirects", True))
    proxies = kwargs.get("proxies")

    def resolve_hop(target: str) -> None:
        host, port = requests_connection_host(target, session=active, proxies=proxies)
        try:
            _resolve(host, port, should_continue=should_continue, dns_timeout=dns_timeout)
        except (DnsLookupError, OSError) as exc:
            raise requests.exceptions.ConnectionError(f"DNS lookup failed: {exc}") from exc

    try:
        resolve_hop(url)
        response = active.request(method, url, allow_redirects=False, **kwargs)
        hops = 0
        while follow and response.is_redirect and response.next is not None:
            if hops >= max(0, int(max_redirects)):
                response.close()
                raise requests.exceptions.TooManyRedirects(
                    f"Exceeded {max_redirects} redirects.", response=response)
            following = response.next
            response.close()
            resolve_hop(following.url)
            settings = active.merge_environment_settings(
                following.url, proxies or {}, kwargs.get("stream"),
                kwargs.get("verify"), kwargs.get("cert"))
            response = active.send(following, allow_redirects=False,
                                   timeout=kwargs.get("timeout"), **settings)
            hops += 1
        return response
    finally:
        if session is None:
            active.close()


def bounded_urlopen(
    request: "urllib.request.Request | str",
    timeout: float,
    *,
    should_continue: Callable[[], bool] | None = None,
    dns_timeout: float = DEFAULT_DNS_TIMEOUT,
) -> Any:
    """``urllib.request.urlopen(request, timeout=timeout)`` with every hop's DNS bounded."""
    import urllib.error
    import urllib.request

    def resolve_hop(target: str) -> None:
        host, port = urllib_connection_host(target)
        try:
            _resolve(host, port, should_continue=should_continue, dns_timeout=dns_timeout)
        except (DnsLookupError, OSError) as exc:
            raise urllib.error.URLError(exc) from exc

    class _BoundedRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401 - urllib hook
            following = super().redirect_request(req, fp, code, msg, headers, newurl)
            if following is not None:
                resolve_hop(following.full_url)
            return following

    target = request.full_url if isinstance(request, urllib.request.Request) else str(request)
    resolve_hop(target)
    return urllib.request.build_opener(_BoundedRedirectHandler()).open(request, timeout=timeout)


__all__ = [
    "DEFAULT_MAX_REDIRECTS",
    "bounded_request",
    "bounded_urlopen",
    "requests_connection_host",
    "urllib_connection_host",
]
