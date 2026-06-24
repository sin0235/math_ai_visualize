from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

from app.core.config import Settings

_METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("100.100.100.200"),
}


class UnsafeUrlError(ValueError):
    pass


def validate_openai_compat_base_url(base_url: str, settings: Settings, *, resolve_dns: bool = True) -> str:
    parsed = urlparse(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise UnsafeUrlError("Base URL OpenAI-compatible không hợp lệ.")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("Base URL không được chứa thông tin đăng nhập.")
    if settings.environment == "production" and parsed.scheme != "https":
        raise UnsafeUrlError("Production chỉ cho phép base URL HTTPS.")
    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("Base URL thiếu hostname.")
    if _host_is_blocked(host, settings, resolve_dns=resolve_dns):
        raise UnsafeUrlError("Base URL trỏ tới địa chỉ mạng không được phép.")
    normalized_path = parsed.path.rstrip("/")
    normalized = parsed._replace(path=normalized_path, params="", query="", fragment="")
    return urlunparse(normalized).rstrip("/")


def _host_is_blocked(host: str, settings: Settings, *, resolve_dns: bool) -> bool:
    ips = _resolve_host_ips(host) if resolve_dns else _literal_host_ips(host)
    if not ips:
        return False
    return any(_ip_is_blocked(ip, settings) for ip in ips)


def _literal_host_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(host.strip("[]"))]
    except ValueError:
        return []


def _resolve_host_ips(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    literal = _literal_host_ips(host)
    if literal:
        return literal
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise UnsafeUrlError("Không thể phân giải hostname của base URL.") from error
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if ip not in ips:
            ips.append(ip)
    return ips


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address, settings: Settings) -> bool:
    if ip in _METADATA_IPS:
        return True
    if ip.is_unspecified or ip.is_multicast or ip.is_link_local:
        return True
    if ip.is_loopback:
        return settings.environment == "production"
    if ip.is_private:
        return True
    return False
