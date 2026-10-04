import ipaddress
import socket
from typing import Any
from urllib.parse import urlsplit


def public_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        return address.is_global and not address.is_multicast
    except ValueError:
        return False


def validate_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
    ):
        raise ValueError("Only public HTTPS URLs are supported")
    addresses = socket.getaddrinfo(
        parsed.hostname, 443, type=socket.SOCK_STREAM
    )
    if not addresses or any(
        not public_address(str(row[4][0])) for row in addresses
    ):
        raise ValueError("Private network destinations are blocked")


def protect_network() -> None:
    original_resolve = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def resolve(*args: Any, **kwargs: Any):
        rows = original_resolve(*args, **kwargs)
        if any(not public_address(str(row[4][0])) for row in rows):
            raise OSError("Private network destinations are blocked")
        return rows

    def connect(stream: socket.socket, address: Any):
        if stream.family in {socket.AF_INET, socket.AF_INET6}:
            if (
                not isinstance(address, tuple)
                or address[1] != 443
                or not public_address(address[0])
            ):
                raise OSError("Unsafe network destination")
        return original_connect(stream, address)

    def connect_ex(stream: socket.socket, address: Any):
        if stream.family in {socket.AF_INET, socket.AF_INET6}:
            if (
                not isinstance(address, tuple)
                or address[1] != 443
                or not public_address(address[0])
            ):
                raise OSError("Unsafe network destination")
        return original_connect_ex(stream, address)

    socket.getaddrinfo = resolve
    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
