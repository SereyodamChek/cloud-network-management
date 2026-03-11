from scapy.all import ARP, Ether, srp
from mac_vendor_lookup import MacLookup

# create vendor lookup once (faster)
mac_lookup = MacLookup()


def detect_device_type(vendor):
    v = vendor.lower()

    # Apple devices
    if "apple" in v:
        return "Apple Device"

    # Android brands
    if "samsung" in v:
        return "Android (Samsung)"
    if "vivo" in v:
        return "Android (Vivo)"
    if "xiaomi" in v or "redmi" in v:
        return "Android (Xiaomi)"
    if "oppo" in v:
        return "Android (Oppo)"
    if "huawei" in v:
        return "Android (Huawei)"
    if "realme" in v:
        return "Android (Realme)"

    # Network devices
    if "cisco" in v:
        return "Router/Switch"
    if "mikrotik" in v:
        return "Router"
    if "tp-link" in v or "tplink" in v:
        return "Router/AP"
    if "d-link" in v:
        return "Router/AP"
    if "ubiquiti" in v:
        return "Access Point / Router"

    # Computer brands
    if "intel" in v:
        return "PC / Laptop"
    if "dell" in v or "hp" in v or "lenovo" in v:
        return "PC / Laptop"

    return "Unknown"


def scan_network(network):

    arp_request = ARP(pdst=network)
    broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
    packet = broadcast / arp_request

    # faster timeout
    result = srp(packet, timeout=1, verbose=0)[0]

    devices = []

    for sent, received in result:

        ip = received.psrc
        mac = received.hwsrc

        try:
            vendor = mac_lookup.lookup(mac)
        except Exception:
            vendor = "Unknown"

        device_type = detect_device_type(vendor)

        devices.append({
            "ip": ip,
            "mac": mac,
            "vendor": vendor,
            "hostname": "N/A",
            "device_type": device_type,
            "possible_model": vendor
        })

    return devices