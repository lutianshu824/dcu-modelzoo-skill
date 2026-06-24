#!/usr/bin/env python3
"""光合社区(developer.sourcefind.cn) HTTP 抓取，带 openssl s_client 回退。

背景：sourcefind.cn 的前置中间盒按 TLS ClientHello 指纹 reset 连接——
python urllib / 系统 curl(带 ALPN+多扩展) 的握手被杀(SSL EOF / SSL_ERROR_SYSCALL)，
但 `openssl s_client` 的极简 ClientHello 能过(实测 HTTP 200)。

策略：先试 urllib(用户本机/月度 cron 走自己网络通)；失败回退 openssl s_client 传输。
这样同一份代码在用户机器(urllib 直连)与受限环境(openssl 回退)都能拉到 live。
"""
import json, ssl, subprocess, urllib.request
from urllib.parse import urlsplit

UA = "Mozilla/5.0"
_ctx = ssl.create_default_context(); _ctx.check_hostname = False; _ctx.verify_mode = ssl.CERT_NONE


def _urllib_bytes(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    return urllib.request.urlopen(req, timeout=timeout, context=_ctx).read()


def _dechunk(body):
    out = b""; rest = body
    while rest:
        ln, sep, rest = rest.partition(b"\r\n")
        if not sep:
            break
        try:
            n = int(ln.strip().split(b";")[0], 16)
        except ValueError:
            break
        if n == 0:
            break
        out += rest[:n]; rest = rest[n + 2:]
    return out


def _openssl_bytes(url, timeout):
    u = urlsplit(url)
    host = u.hostname
    port = u.port or 443
    path = u.path + (("?" + u.query) if u.query else "")
    req = (f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: {UA}\r\n"
           f"Accept: */*\r\nConnection: close\r\n\r\n")
    p = subprocess.run(
        ["openssl", "s_client", "-quiet", "-connect", f"{host}:{port}", "-servername", host],
        input=req.encode(), capture_output=True, timeout=timeout)
    raw = p.stdout
    sep = raw.find(b"\r\n\r\n")
    if sep < 0:
        raise RuntimeError("openssl: no HTTP response")
    head, body = raw[:sep], raw[sep + 4:]
    parts = head.split(b"\r\n", 1)[0].split()
    code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    if b"transfer-encoding: chunked" in head.lower():
        body = _dechunk(body)
    if code >= 400:
        raise RuntimeError(f"openssl: HTTP {code}")
    return body


def get_bytes(url, timeout=60):
    try:
        return _urllib_bytes(url, timeout)
    except Exception:
        return _openssl_bytes(url, timeout)


def get_json(url, timeout=60):
    return json.loads(get_bytes(url, timeout).decode("utf-8", "replace"))


def get_text(url, timeout=60):
    return get_bytes(url, timeout).decode("utf-8", "replace")
