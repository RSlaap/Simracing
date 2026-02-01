"""
Network utilities for SimRacing client.

Provides functions for IP address detection and mDNS service registration.
"""

import socket
from typing import Dict, Any, Tuple

from zeroconf import ServiceInfo, Zeroconf

from utils.monitoring import get_logger

logger = get_logger(__name__)


def get_local_ip() -> str:
    """
    Get the local IP address of this machine.

    Uses UDP socket method (most reliable) with hostname fallback.

    Returns:
        Local IP address as string.

    Raises:
        RuntimeError: If unable to determine local IP address.
    """
    # Primary: UDP socket method - most reliable for finding the "outbound" IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))  # Google DNS - doesn't actually send packets
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        logger.warning(f"UDP socket method failed: {e}")

    # Fallback: hostname resolution
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if not ip.startswith('127.'):
            return ip
    except Exception as e:
        logger.warning(f"Hostname resolution failed: {e}")

    raise RuntimeError(
        "Could not determine local IP address. "
        "Please check network connection and configuration."
    )


def register_mdns_service(
    config: Dict[str, Any],
    port: int = 5000
) -> Tuple[Zeroconf, ServiceInfo]:
    """
    Register this setup as discoverable via mDNS.

    Args:
        config: Configuration dict containing 'name' and 'id' keys.
        port: Port number for the service (default: 5000).

    Returns:
        Tuple of (Zeroconf instance, ServiceInfo instance).
    """
    local_ip = get_local_ip()

    service_type = "_simracing._tcp.local."
    service_name = f"{config['name']} SimRacing Setup.{service_type}"

    info = ServiceInfo(
        service_type,
        service_name,
        addresses=[socket.inet_aton(local_ip)],
        port=port,
        properties={
            'name': config['name'],
            'id': str(config['id']),
            'status': 'idle',
            'games': ','.join([])
        }
    )

    zeroconf = Zeroconf()
    zeroconf.register_service(info)
    logger.info(f"mDNS service registered: {service_name}")
    logger.info(f"Discoverable at: {local_ip}:{port}")
    return zeroconf, info
