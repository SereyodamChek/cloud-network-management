from scapy.all import ARP, Ether, srp
from mac_vendor_lookup import MacLookup
from ping3 import ping
import socket
import ipaddress
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

SERVER_API_URL = "http://127.0.0.1:5000/api/scan-results"
AGENT_NAME = "local-agent-1"

mac_lookup = MacLookup()


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def get_local_subnet():
    # Your current network is 10.10.17.x
    return "10.10.17.0/24"


def get_default_gateway():
    return "10.10.17.1"


def detect_device_type(vendor):
    v = (vendor or "").lower()

    if "apple" in v:
        return "Apple Device"
    if any(x in v for x in ["samsung", "vivo", "xiaomi", "redmi", "oppo", "huawei", "realme"]):
        return "Phone"
    if "cisco" in v:
        return "Switch"
    if any(x in v for x in ["mikrotik", "tp-link", "tplink", "d-link", "ubiquiti"]):
        return "Router"
    if any(x in v for x in ["intel", "dell", "hp", "lenovo", "asus", "acer"]):
        return "PC"

    return "Unknown"


def get_vendor(mac):
    try:
        return mac_lookup.lookup(mac)
    except Exception:
        return "Unknown"


def get_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return "Unknown"


def arp_scan(network):
    devices = []

    try:
        arp_request = ARP(pdst=network)
        broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = broadcast / arp_request
        result = srp(packet, timeout=1, verbose=0)[0]

        for _, received in result:
            ip = received.psrc
            mac = received.hwsrc
            vendor = get_vendor(mac)
            hostname = get_hostname(ip)
            device_type = detect_device_type(vendor)

            devices.append({
                "ip": ip,
                "mac": mac,
                "vendor": vendor,
                "hostname": hostname,
                "device_type": device_type,
                "possible_model": vendor,
                "status": "Online",
                "response_time": None,
                "location": "Local Network"
            })
    except Exception as e:
        print("ARP scan failed:", e)

    return devices


def ping_one(ip):
    try:
        result = ping(ip, timeout=0.5)
        if result is not None:
            return {
                "ip": ip,
                "mac": "",
                "vendor": "Unknown",
                "hostname": get_hostname(ip),
                "device_type": "Unknown",
                "possible_model": "Unknown",
                "status": "Online",
                "response_time": round(result * 1000, 2),
                "location": "Local Network"
            }
    except Exception:
        pass
    return None


def ping_sweep(base_prefix, start=1, end=30):
    devices = []
    futures = []

    with ThreadPoolExecutor(max_workers=30) as executor:
        for i in range(start, end + 1):
            ip = f"{base_prefix}{i}"
            futures.append(executor.submit(ping_one, ip))

        for future in as_completed(futures):
            item = future.result()
            if item:
                devices.append(item)

    return devices


def merge_devices(primary, fallback):
    by_ip = {}

    for d in fallback:
        by_ip[d["ip"]] = d

    for d in primary:
        by_ip[d["ip"]] = d

    merged = list(by_ip.values())
    merged.sort(key=lambda x: x["ip"])
    return merged


def scan_network(network=None):
    if not network:
        network = get_local_subnet()

    # 1) Try ARP scan first
    arp_devices = arp_scan(network)

    # 2) Fallback ping sweep for first 30 IPs
    base_prefix = "10.10.17."
    ping_devices = ping_sweep(base_prefix, 1, 30)

    # 3) Merge results
    devices = merge_devices(arp_devices, ping_devices)

    # 4) Ensure gateway is at least attempted
    gateway = get_default_gateway()
    if not any(d["ip"] == gateway for d in devices):
        gw = ping_one(gateway)
        if gw:
            gw["device_type"] = "Router"
            devices.append(gw)

    return devices


def send_results_to_server(devices, server_api_url=SERVER_API_URL, agent_name=AGENT_NAME):
    payload = {
        "agent_name": agent_name,
        "scan_time": datetime.utcnow().isoformat(),
        "devices": devices
    }

    try:
        response = requests.post(server_api_url, json=payload, timeout=15)
        print("Server response:", response.status_code)
        print(response.text)
        return response.status_code == 200
    except Exception as e:
        print("Failed to send scan results to server:", str(e))
        return False


if __name__ == "__main__":
    subnet = get_local_subnet()
    print(f"Scanning subnet: {subnet}")

    scanned_devices = scan_network(subnet)

    print(f"Found {len(scanned_devices)} device(s)")
    for device in scanned_devices:
        print(device)

    send_results_to_server(scanned_devices)