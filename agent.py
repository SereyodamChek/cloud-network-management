import time
# import requests
from scapy.all import ARP, Ether, srp

API_URL = "https://clouddom-network-management.onrender.com/api/devices/update"
API_TOKEN = "my-agent-secret"

NETWORK = "192.168.1.0/24"
SCAN_INTERVAL = 3


def scan_network(network):

    print("Starting network scan:", network)

    arp_request = ARP(pdst=network)
    broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")

    packet = broadcast / arp_request

    result = srp(packet, timeout=2, verbose=0)[0]

    devices = []

    for sent, received in result:

        device = {
            "ip": received.psrc,
            "mac": received.hwsrc,
            "vendor": "Unknown",
            "hostname": "N/A",
            "device_type": "Unknown",
            "possible_model": "Unknown",
            "status": "Online"
        }

        devices.append(device)

    return devices


def send_to_cloud(devices):

    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": API_TOKEN
    }

    try:

        response = requests.post(
            API_URL,
            json={"devices": devices},
            headers=headers,
            timeout=10
        )

        print("Server response:", response.status_code)

        if response.status_code == 200:
            print("Upload success")
        else:
            print("Upload failed:", response.text)

    except Exception as e:

        print("Error sending to cloud:", str(e))


def main():

    while True:

        try:

            print("\nScanning network...")

            devices = scan_network(NETWORK)

            print("Devices found:", len(devices))

            send_to_cloud(devices)

        except Exception as e:

            print("Agent error:", str(e))

        print("Waiting", SCAN_INTERVAL, "seconds...\n")

        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()