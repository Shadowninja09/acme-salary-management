import hashlib
import hmac
import ipaddress
import re
import secrets
from urllib.parse import urlsplit

from starlette.requests import Request

CSRF_COOKIE_NAME = "acme_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_TOKEN_VERSION = "v1"

_CANONICAL_SESSION_ID = re.compile(r"\A[1-9][0-9]*\Z")
_HEX_LOWER_32 = re.compile(r"\A[0-9a-f]{32}\Z")
_HEX_LOWER_64 = re.compile(r"\A[0-9a-f]{64}\Z")
_DNS_LABEL = re.compile(r"\A[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z")


def issue_csrf_token(*, session_id: int, secret: str) -> str:
    nonce = secrets.token_hex(16)
    mac = _csrf_mac(session_id=session_id, nonce=nonce, secret=secret)
    return f"{CSRF_TOKEN_VERSION}.{session_id}.{nonce}.{mac}"


def submitted_csrf_is_valid(
    *,
    cookie: str | None,
    header: str | None,
    session_id: int,
    secret: str,
) -> bool:
    if cookie is None or header is None or cookie == "" or header == "":
        return False
    if not digest_equal(cookie, header):
        return False
    return csrf_token_is_valid(token=cookie, session_id=session_id, secret=secret)


def csrf_token_is_valid(*, token: str, session_id: int, secret: str) -> bool:
    if not isinstance(token, str) or not isinstance(secret, str):
        return False
    if not isinstance(session_id, int) or isinstance(session_id, bool) or session_id < 1:
        return False
    parts = token.split(".")
    if len(parts) != 4:
        return False
    version, token_session_id, nonce, provided_mac = parts
    if version != CSRF_TOKEN_VERSION:
        return False
    if _CANONICAL_SESSION_ID.fullmatch(token_session_id) is None:
        return False
    if _HEX_LOWER_32.fullmatch(nonce) is None:
        return False
    if _HEX_LOWER_64.fullmatch(provided_mac) is None:
        return False
    if not digest_equal(token_session_id, str(session_id)):
        return False
    expected_mac = _csrf_mac(session_id=session_id, nonce=nonce, secret=secret)
    return digest_equal(provided_mac, expected_mac)


def extract_request_origin(request: Request) -> str | None:
    # Prefer Origin. A present but invalid Origin is not replaced by Referer.
    origin = (request.headers.get("origin") or "").strip()
    if origin:
        return canonicalize_origin(origin, allow_path=False)
    referer = (request.headers.get("referer") or "").strip()
    if not referer:
        return None
    return canonicalize_origin(referer, allow_path=True)


def login_origin_is_trusted(request: Request, trusted_origins: list[str]) -> bool:
    origin = extract_request_origin(request)
    if origin is None:
        return False
    trusted = False
    for allowed in trusted_origins:
        canonical_allowed = canonicalize_origin(allowed, allow_path=False)
        if canonical_allowed is not None and digest_equal(origin, canonical_allowed):
            trusted = True
    return trusted


def canonicalize_origin(value: str, *, allow_path: bool) -> str | None:
    # Origin: scheme://host[:port] with path empty or "/" and no query/fragment.
    # Referer (allow_path=True): a resource path, query, and fragment are
    # ignored; only the canonical origin is used for trust matching.
    try:
        return _canonicalize_origin(value, allow_path=allow_path)
    except Exception:
        return None


def digest_equal(left: str, right: str) -> bool:
    left_bytes = left.encode("utf-8")
    right_bytes = right.encode("utf-8")
    if len(left_bytes) != len(right_bytes):
        return False
    return hmac.compare_digest(left_bytes, right_bytes)


def _csrf_mac(*, session_id: int, nonce: str, secret: str) -> str:
    message = f"{CSRF_TOKEN_VERSION}\n{session_id}\n{nonce}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _canonicalize_origin(value: str, *, allow_path: bool) -> str | None:
    if value.strip().lower() == "null":
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        return None
    if "@" in parsed.netloc or parsed.username is not None or parsed.password is not None:
        return None
    if "*" in value:
        return None
    if not allow_path and parsed.path not in {"", "/"}:
        return None
    if not allow_path and (parsed.query or parsed.fragment):
        return None
    hostname = parsed.hostname
    if hostname is None:
        return None
    host = _normalized_hostname(hostname)
    if host is None or not _is_valid_hostname(host):
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    if port == 0:
        return None
    if not _authority_is_well_formed(parsed.netloc, hostname=hostname, port=port):
        return None
    if not _port_specifier_is_canonical(parsed.netloc, port):
        return None
    host_part = f"[{host}]" if ":" in host else host
    if port is None or _is_default_port(parsed.scheme, port):
        return f"{parsed.scheme}://{host_part}"
    return f"{parsed.scheme}://{host_part}:{port}"


def _normalized_hostname(hostname: str) -> str | None:
    # A single trailing DNS dot is an FQDN marker and is stripped. Two or more
    # trailing dots are rejected so they cannot collapse into a trusted name.
    if hostname.endswith(".."):
        return None
    if hostname.endswith("."):
        hostname = hostname[:-1]
    if not hostname:
        return None
    return hostname.lower()


def _authority_is_well_formed(netloc: str, *, hostname: str, port: int | None) -> bool:
    hostinfo = netloc.rsplit("@", 1)[-1]
    if hostinfo.count("[") > 1 or hostinfo.count("]") > 1:
        return False
    if ":" in hostname:
        if not hostinfo.startswith("[") or hostinfo.count("[") != 1 or hostinfo.count("]") != 1:
            return False
        close = hostinfo.find("]")
        if hostinfo[1:close].lower() != hostname.lower():
            return False
        rest = hostinfo[close + 1 :]
    else:
        if "[" in hostinfo or "]" in hostinfo:
            return False
        host_part, separator, port_text = hostinfo.partition(":")
        rest = f":{port_text}" if separator else ""
        allowed = {hostname.lower()}
        if hostname.endswith("."):
            allowed.add(hostname[:-1].lower())
        else:
            allowed.add(f"{hostname.lower()}.")
        if host_part.lower() not in allowed:
            return False
        if rest.count(":") > 1:
            return False
    if port is None:
        return rest == ""
    return rest == f":{port}"


def _is_default_port(scheme: str, port: int) -> bool:
    return (scheme == "http" and port == 80) or (scheme == "https" and port == 443)


def _port_specifier_is_canonical(netloc: str, port: int | None) -> bool:
    hostinfo = netloc.rsplit("@", 1)[-1]
    if port is None:
        return ":" not in hostinfo or (
            hostinfo.startswith("[") and hostinfo.endswith("]")
        )
    expected = f":{port}"
    return hostinfo.endswith(expected)


def _is_valid_hostname(host: str) -> bool:
    if not host or "*" in host:
        return False
    try:
        address = ipaddress.IPv4Address(host)
    except ValueError:
        address = None
    if address is not None:
        return host == str(address)
    try:
        ipaddress.IPv6Address(host)
        return True
    except ValueError:
        pass
    if len(host) > 253:
        return False
    labels = host.split(".")
    return bool(labels) and all(_DNS_LABEL.fullmatch(label) for label in labels)
