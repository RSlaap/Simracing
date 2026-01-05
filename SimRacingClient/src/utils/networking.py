
import socket

from zeroconf import ServiceInfo, Zeroconf
from utils.monitoring import get_logger

logger = get_logger(__name__)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def register_mdns_service(config, port=5000):
    """Register this setup as discoverable via mDNS"""
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
