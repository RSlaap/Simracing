
import socket

from zeroconf import ServiceInfo, Zeroconf
from utils.monitoring import get_logger

logger = get_logger(__name__)

def get_local_ip():
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if not ip.startswith('127.'):
            return ip
    except Exception as e:
        logger.warning(f"Hostname resolution failed: {e}")
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('192.168.2.1', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        logger.error(f"Failed to connect to router: {e}")
    
    raise RuntimeError(
        "Could not determine local IP address. "
        "Please check network connection and configuration."
    )

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
