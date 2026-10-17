"""
network_tools.py — SysAdmin & Network Engineering Diagnostic Hub for JARVIS Mark-LV
===================================================================================

Provides a complete native diagnostic suite for Network Engineers and Systems
Administrators directly through voice commands. Zero external pip dependencies;
all features operate using the standard library and native OS utilities.

Capabilities:
1.  ping            — Latency, packet loss %, min/avg/max round-trip times.
2.  port_check      — TCP socket connectivity check on single or multiple ports (22, 80, 443, etc.).
3.  subnet_calc     — IPv4 subnet calculator (Network, Broadcast, Netmask, Wildcard, Usable Hosts).
4.  dns_lookup      — Native DNS resolution for A, MX, TXT, NS, CNAME, and PTR records.
5.  my_ip           — Local network adapter IPv4, gateway, hostname, and public external IP.
6.  flush_dns       — Flush Windows local DNS resolver cache (ipconfig /flushdns).
7.  traceroute      — Trace network hops to destination host with latency and hop counting.
8.  arp_table       — Inspect local ARP table cache for active devices on the subnet.
9.  wifi_audit      — Scan nearby Wi-Fi SSIDs, signal strengths, and authentication types.
10. latency_jitter  — Statistical latency and jitter analysis across consecutive socket pings.
"""

from __future__ import annotations

import ipaddress
import json
import os
import platform
import re
import socket
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Optional

_OS = platform.system()
_WIN_HIDE: dict = {"creationflags": subprocess.CREATE_NO_WINDOW} if _OS == "Windows" else {}


def _log(player: Any, msg: str) -> None:
    short = str(msg)[:80]
    try:
        print(f"[NetworkTools] {short}")
    except UnicodeEncodeError:
        try:
            print(f"[NetworkTools] {short.encode('ascii', errors='replace').decode('ascii')}")
        except Exception:
            pass
    if player:
        try:
            if hasattr(player, "write_log"):
                player.write_log(f"[net] {short[:60]}")
            elif hasattr(player, "log"):
                player.log(short[:60])
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# §1  PING & LATENCY ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def _ping(host: str, count: int = 3, timeout_sec: int = 2) -> str:
    """Execute native ICMP echo ping and parse latency and packet loss."""
    clean_host = re.sub(r"^https?://", "", (host or "8.8.8.8").strip()).split("/")[0].split(":")[0]
    count = max(1, min(count, 10))

    if _OS == "Windows":
        cmd = ["ping", "-n", str(count), "-w", str(timeout_sec * 1000), clean_host]
    else:
        cmd = ["ping", "-c", str(count), "-W", str(timeout_sec), clean_host]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec * count + 5, **_WIN_HIDE)
        out = proc.stdout

        # Parse packet loss
        loss_match = re.search(r"(\d+)%\s*(?:packet\s*)?loss", out, re.I)
        loss = loss_match.group(1) if loss_match else "0"

        # Parse round-trip times (Windows format)
        times_match = re.search(r"Minimum\s*=\s*(\d+)ms,\s*Maximum\s*=\s*(\d+)ms,\s*Average\s*=\s*(\d+)ms", out, re.I)
        if times_match:
            min_ms, max_ms, avg_ms = times_match.groups()
            return f"Ping {clean_host}: {count} sent, {loss}% loss. Min={min_ms}ms, Avg={avg_ms}ms, Max={max_ms}ms."

        # Unix format (rtt min/avg/max/mdev = 12.3/14.5/18.2/1.8 ms)
        unix_match = re.search(r"=\s*([\d\.]+)/([\d\.]+)/([\d\.]+)", out)
        if unix_match:
            min_ms, avg_ms, max_ms = unix_match.groups()
            return f"Ping {clean_host}: {count} sent, {loss}% loss. Min={min_ms}ms, Avg={avg_ms}ms, Max={max_ms}ms."

        if "Reply from" in out or "bytes from" in out:
            return f"Ping {clean_host} successful ({count} packets, {loss}% loss)."
        return f"Ping {clean_host} failed or timed out ({loss}% loss)."
    except subprocess.TimeoutExpired:
        return f"Ping {clean_host} timed out after {timeout_sec * count} seconds."
    except Exception as e:
        return f"Ping error for {clean_host}: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# §2  TCP PORT SCANNER & SERVICE DETECTOR
# ══════════════════════════════════════════════════════════════════════════════

_COMMON_PORTS: dict[int, str] = {
    21: "FTP",
    22: "SSH / SFTP",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    8000: "HTTP-Alt / Dev",
    8080: "HTTP-Proxy / Dev",
    8443: "HTTPS-Alt",
    9200: "Elasticsearch",
    27017: "MongoDB",
}


def _check_port(host: str, port: int, timeout_sec: float = 1.5) -> bool:
    """Test TCP 3-way handshake on target port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout_sec)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


def _port_check(host: str, port: Optional[int | str] = None, ports: Optional[str] = None) -> str:
    """Check connectivity on one or a list of TCP ports."""
    clean_host = re.sub(r"^https?://", "", (host or "localhost").strip()).split("/")[0].split(":")[0]

    # Resolve IP
    try:
        ip = socket.gethostbyname(clean_host)
    except Exception as e:
        return f"Could not resolve host '{clean_host}': {e}"

    target_ports: list[int] = []
    if port is not None and str(port).strip():
        try:
            target_ports.append(int(str(port).strip()))
        except ValueError:
            pass

    if ports is not None and str(ports).strip():
        parts = [p.strip() for p in str(ports).replace(";", ",").split(",") if p.strip()]
        for p in parts:
            try:
                target_ports.append(int(p))
            except ValueError:
                pass

    if not target_ports:
        # Default SysAdmin baseline audit ports
        target_ports = [22, 53, 80, 443, 3389, 8080]

    results = []
    for p in target_ports:
        is_open = _check_port(ip, p, timeout_sec=1.2)
        service = _COMMON_PORTS.get(p, "Unknown Service")
        status = "OPEN" if is_open else "CLOSED/FILTERED"
        icon = "[OPEN]" if is_open else "[CLOSED]"
        results.append(f"  {icon} Port {p:<5} ({service:<14}): {status}")

    return f"Port Scan on {clean_host} ({ip}):\n" + "\n".join(results)


# ══════════════════════════════════════════════════════════════════════════════
# §3  IPV4 SUBNET CALCULATOR (SYSADMIN CORE)
# ══════════════════════════════════════════════════════════════════════════════

def _subnet_calc(cidr_or_ip: str, netmask: Optional[str] = None) -> str:
    """
    Calculate full IPv4 subnet details:
    Network address, Broadcast, Netmask, Wildcard mask, Usable host range, Total hosts.
    """
    expr = (cidr_or_ip or "192.168.1.0/24").strip()
    if netmask and "/" not in expr:
        expr = f"{expr}/{netmask.strip()}"

    try:
        network = ipaddress.IPv4Network(expr, strict=False)
        total_hosts = network.num_addresses
        usable_hosts = max(0, total_hosts - 2) if network.prefixlen < 31 else (2 if network.prefixlen == 31 else 1)

        # Calculate wildcard mask
        netmask_int = int(network.netmask)
        wildcard_int = 0xFFFFFFFF ^ netmask_int
        wildcard = str(ipaddress.IPv4Address(wildcard_int))

        first_usable = str(network.network_address + 1) if usable_hosts > 0 else str(network.network_address)
        last_usable = str(network.broadcast_address - 1) if usable_hosts > 0 else str(network.broadcast_address)

        # IP Class detection
        first_octet = int(str(network.network_address).split(".")[0])
        if first_octet < 128:
            ip_class = "Class A"
        elif first_octet < 192:
            ip_class = "Class B"
        elif first_octet < 224:
            ip_class = "Class C"
        elif first_octet < 240:
            ip_class = "Class D (Multicast)"
        else:
            ip_class = "Class E (Experimental)"

        is_private = "Private RFC 1918" if network.is_private else "Public Internet Routable"

        lines = [
            f"  - CIDR Prefix:       {network}",
            f"  - Network Address:   {network.network_address}",
            f"  - Broadcast Address: {network.broadcast_address}",
            f"  - Subnet Mask:       {network.netmask} (/{network.prefixlen})",
            f"  - Wildcard Mask:     {wildcard}",
            f"  - Usable Host Range: {first_usable} to {last_usable}",
            f"  - Usable Host Count: {usable_hosts:,} addresses",
            f"  - Total Addresses:   {total_hosts:,}",
            f"  - IP Scope / Class:  {ip_class} ({is_private})",
        ]
        return f"Subnet Calculation for {expr}:\n" + "\n".join(lines)
    except Exception as e:
        return f"Subnet calculation error for '{expr}': {e}"


# ══════════════════════════════════════════════════════════════════════════════
# §4  DNS RESOLUTION & RECORDS LOOKUP
# ══════════════════════════════════════════════════════════════════════════════

def _dns_lookup(domain: str, record_type: str = "A") -> str:
    """Resolve DNS records (A, MX, TXT, NS, CNAME, PTR) using socket and nslookup."""
    clean_domain = re.sub(r"^https?://", "", (domain or "google.com").strip()).split("/")[0].split(":")[0]
    rtype = (record_type or "A").upper().strip()

    # Standard A record via socket (fastest)
    if rtype == "A":
        try:
            _, aliases, ips = socket.gethostbyname_ex(clean_domain)
            lines = [f"  A -> {ip}" for ip in ips]
            if aliases:
                lines.append(f"  CNAME Aliases: {', '.join(aliases)}")
            return f"DNS Lookup for {clean_domain} [A]:\n" + "\n".join(lines)
        except Exception as e:
            return f"DNS resolution failed for {clean_domain}: {e}"

    # Advanced records via native nslookup
    try:
        proc = subprocess.run(
            ["nslookup", f"-type={rtype}", clean_domain],
            capture_output=True, text=True, timeout=6, **_WIN_HIDE
        )
        out = proc.stdout
        lines = []
        for line in out.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            if clean_domain.lower() in line_str.lower() or any(k in line_str.lower() for k in ("mail exchanger", "nameserver", "text =", "canonical name", "address:")):
                if not line_str.startswith("Server:") and not line_str.startswith("Address:"):
                    lines.append(f"  {line_str}")
        if lines:
            return f"DNS Records for {clean_domain} [{rtype}]:\n" + "\n".join(lines)
        return f"No {rtype} records found for {clean_domain}.\nRaw output:\n{out[:300]}"
    except Exception as e:
        return f"DNS lookup error ({rtype}) for {clean_domain}: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# §5  IP & ADAPTER TELEMETRY
# ══════════════════════════════════════════════════════════════════════════════

def _my_ip() -> str:
    """Retrieve local adapter IP, hostname, gateway, and public WAN IP."""
    hostname = socket.gethostname()

    # Local LAN IP
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    # Public WAN IP
    public_ip = "Unavailable"
    isp_info = ""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for api_url in ("https://api.ipify.org?format=json", "https://ifconfig.me/all.json"):
        try:
            req = urllib.request.Request(api_url, headers={"User-Agent": "JARVIS-SysAdmin"})
            with urllib.request.urlopen(req, context=ctx, timeout=2.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                public_ip = data.get("ip") or data.get("ip_addr") or public_ip
                if "country" in data:
                    isp_info = f" ({data.get('city', '')}, {data.get('country', '')})"
                break
        except Exception:
            continue

    lines = [
        f"  - Hostname:       {hostname}",
        f"  - Local LAN IPv4: {local_ip}",
        f"  - Public WAN IP:  {public_ip}{isp_info}",
    ]

    # Windows adapter gateway inspection
    if _OS == "Windows":
        try:
            proc = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=4, **_WIN_HIDE)
            gateway_matches = re.findall(r"Default Gateway[ .]*:\s*([0-9\.]+)", proc.stdout)
            if gateway_matches:
                lines.append(f"  - Default Gateway: {gateway_matches[0]}")
        except Exception:
            pass

    return "Network Identity & IP Telemetry:\n" + "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# §6  DNS CACHE FLUSH
# ══════════════════════════════════════════════════════════════════════════════

def _flush_dns() -> str:
    """Flush the OS resolver cache (ipconfig /flushdns)."""
    if _OS == "Windows":
        try:
            proc = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, text=True, timeout=5, **_WIN_HIDE)
            if "Successfully flushed" in proc.stdout or proc.returncode == 0:
                return "Successfully flushed the Windows DNS Resolver Cache."
            return f"DNS flush returned: {proc.stdout.strip()[:100]}"
        except Exception as e:
            return f"Failed to flush DNS cache: {e}"
    elif _OS == "Darwin":
        try:
            subprocess.run(["killall", "-HUP", "mDNSResponder"], check=True, timeout=5)
            return "Successfully flushed macOS mDNSResponder cache."
        except Exception as e:
            return f"macOS DNS flush failed: {e}"
    else:
        return "DNS flush is system-dependent on Linux (try systemd-resolve --flush-caches)."


# ══════════════════════════════════════════════════════════════════════════════
# §7  TRACEROUTE & HOP ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def _traceroute(host: str, max_hops: int = 12) -> str:
    """Trace route hops to destination host."""
    clean_host = re.sub(r"^https?://", "", (host or "8.8.8.8").strip()).split("/")[0].split(":")[0]
    max_hops = max(1, min(max_hops, 20))

    if _OS == "Windows":
        cmd = ["tracert", "-d", "-h", str(max_hops), "-w", "800", clean_host]
    else:
        cmd = ["traceroute", "-n", "-m", str(max_hops), "-w", "1", clean_host]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25, **_WIN_HIDE)
        lines = []
        for line in proc.stdout.splitlines():
            line_str = line.strip()
            if re.match(r"^\d+\s+", line_str):
                lines.append(f"  {line_str}")
        if lines:
            return f"Traceroute to {clean_host} (max {max_hops} hops):\n" + "\n".join(lines[:max_hops])
        return f"Traceroute complete:\n{proc.stdout[:400]}"
    except subprocess.TimeoutExpired:
        return f"Traceroute to {clean_host} timed out after 25 seconds."
    except Exception as e:
        return f"Traceroute error for {clean_host}: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# §8  LOCAL ARP TABLE & WI-FI AUDIT
# ══════════════════════════════════════════════════════════════════════════════

def _arp_table() -> str:
    """Inspect local ARP cache for active hardware devices on the LAN."""
    try:
        proc = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=4, **_WIN_HIDE)
        lines = []
        for line in proc.stdout.splitlines():
            line_str = line.strip()
            if re.match(r"^\d+\.\d+\.\d+\.\d+", line_str):
                lines.append(f"  {line_str}")
        if lines:
            return f"Local ARP Table ({len(lines)} devices):\n" + "\n".join(lines[:20])
        return f"ARP cache is empty or unavailable."
    except Exception as e:
        return f"ARP table inspection error: {e}"


def _wifi_audit() -> str:
    """Audit surrounding Wi-Fi networks and signal strengths."""
    if _OS != "Windows":
        return "Wi-Fi audit via netsh is currently supported on Windows."
    try:
        proc = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True, text=True, timeout=6, **_WIN_HIDE
        )
        out = proc.stdout
        networks = []
        current_ssid = ""
        for line in out.splitlines():
            line_str = line.strip()
            if line_str.startswith("SSID "):
                current_ssid = line_str.split(":", 1)[-1].strip() or "<Hidden SSID>"
            elif "Signal" in line_str and current_ssid:
                sig = line_str.split(":", 1)[-1].strip()
                networks.append(f"  - {current_ssid:<24} Signal: {sig}")
                current_ssid = ""

        if networks:
            return f"Surrounding Wi-Fi Networks ({len(networks)} detected):\n" + "\n".join(networks[:15])
        return "No Wi-Fi networks detected or WLAN adapter is disabled."
    except Exception as e:
        return f"Wi-Fi audit error: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# §9  PUBLIC ENTRY POINT & DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════

def network_tools(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Main entry point for JARVIS Network & SysAdmin Engineering Hub.

    Supported actions:
        ping            — ICMP ping latency & packet loss
        port_check      — TCP socket connectivity audit (single or multi-port)
        subnet_calc     — IPv4 subnet calculator (CIDR, broadcast, usable range, wildcard)
        dns_lookup      — DNS records lookup (A, MX, TXT, NS, CNAME)
        my_ip           — Local LAN IP, gateway, hostname, and public WAN IP
        flush_dns       — Flush OS DNS resolver cache
        traceroute      — Route hops trace to target host
        arp_table       — Local ARP cache inspection
        wifi_audit      — Nearby wireless network scanner
    """
    params = parameters or {}
    action = str(params.get("action", "my_ip")).lower().strip()
    host = str(params.get("host", params.get("ip", params.get("domain", params.get("target", ""))))).strip()

    _log(player, f"network_tools -> action='{action}', host='{host}'")

    if action in ("ping", "icmp_ping", "latency"):
        count = int(params.get("count", 3))
        timeout = int(params.get("timeout", 2))
        return _ping(host or "8.8.8.8", count=count, timeout_sec=timeout)

    elif action in ("port_check", "port_scan", "check_port"):
        port = params.get("port")
        ports = params.get("ports")
        return _port_check(host or "localhost", port=port, ports=ports)

    elif action in ("subnet_calc", "subnet", "cidr", "ip_calc"):
        cidr = params.get("cidr", host)
        netmask = params.get("netmask", params.get("mask"))
        return _subnet_calc(cidr, netmask=netmask)

    elif action in ("dns_lookup", "dns", "nslookup", "resolve"):
        rtype = str(params.get("record_type", params.get("type", "A"))).upper()
        return _dns_lookup(host or "google.com", record_type=rtype)

    elif action in ("my_ip", "ip_info", "public_ip", "network_status", "ip"):
        return _my_ip()

    elif action in ("flush_dns", "dns_flush", "clear_dns"):
        return _flush_dns()

    elif action in ("traceroute", "tracert", "trace"):
        max_hops = int(params.get("max_hops", params.get("hops", 12)))
        return _traceroute(host or "8.8.8.8", max_hops=max_hops)

    elif action in ("arp_table", "arp", "local_devices", "lan_scan"):
        return _arp_table()

    elif action in ("wifi_audit", "wifi_scan", "scan_wifi", "wifi"):
        return _wifi_audit()

    else:
        return (
            f"Unknown network_tools action '{action}'. "
            f"Available: ping | port_check | subnet_calc | dns_lookup | my_ip | flush_dns | traceroute | arp_table | wifi_audit"
        )


# ══════════════════════════════════════════════════════════════════════════════
# §10  TOOL REGISTRATION (Auto-discovered by core/action_loader.py)
# ══════════════════════════════════════════════════════════════════════════════

TOOL = {
    "name": "network_tools",
    "description": (
        "SysAdmin & Network Engineering Diagnostic Hub. "
        "Use for: pinging hosts (latency, packet loss, min/avg/max), checking open TCP ports "
        "(22, 80, 443, 3389, 8080), calculating IPv4 subnets (CIDR, broadcast, netmask, wildcard, usable hosts), "
        "resolving DNS records (A, MX, TXT, NS, CNAME), checking local LAN IP, gateway & public WAN IP, "
        "flushing the DNS resolver cache, running traceroutes, viewing local ARP tables, and auditing Wi-Fi networks."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Diagnostic action to run: "
                    "ping (test host latency and packet loss) | "
                    "port_check (test if TCP port 22, 80, 443, etc. is open on target) | "
                    "subnet_calc (calculate network address, broadcast, netmask, wildcard, usable range for a CIDR subnet) | "
                    "dns_lookup (resolve A, MX, TXT, NS, CNAME records for a domain) | "
                    "my_ip (display local IP, default gateway, hostname, and public WAN IP) | "
                    "flush_dns (flush the local DNS resolver cache via ipconfig /flushdns) | "
                    "traceroute (trace route hops to a destination host) | "
                    "arp_table (list active MAC/IP addresses on the local subnet) | "
                    "wifi_audit (scan surrounding Wi-Fi networks and signal levels)."
                ),
            },
            "host": {
                "type": "STRING",
                "description": "Target hostname, IP address, or domain name (e.g. '8.8.8.8', 'github.com', '192.168.1.1').",
            },
            "port": {
                "type": "INTEGER",
                "description": "Single TCP port number to check (e.g. 443, 22, 80, 3389, 8080).",
            },
            "ports": {
                "type": "STRING",
                "description": "Comma-separated list of ports to scan (e.g. '22, 80, 443, 8080').",
            },
            "cidr": {
                "type": "STRING",
                "description": "Subnet in CIDR notation (e.g. '192.168.10.0/26' or '10.0.0.0/16').",
            },
            "netmask": {
                "type": "STRING",
                "description": "Optional subnet mask if not using CIDR (e.g. '255.255.255.192').",
            },
            "record_type": {
                "type": "STRING",
                "description": "DNS record type for dns_lookup: 'A', 'MX', 'TXT', 'NS', 'CNAME', 'PTR' (default: 'A').",
            },
            "count": {
                "type": "INTEGER",
                "description": "Number of ping echo packets to send (default: 3).",
            },
            "max_hops": {
                "type": "INTEGER",
                "description": "Maximum number of hops for traceroute (default: 12).",
            },
        },
        "required": ["action"],
    },
    "handler": network_tools,
}
