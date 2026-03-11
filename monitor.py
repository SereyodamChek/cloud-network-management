import psutil
import time

def get_system_metrics():

    cpu = psutil.cpu_percent(interval=1)

    memory = psutil.virtual_memory().percent

    uptime = time.time() - psutil.boot_time()

    net1 = psutil.net_io_counters()

    time.sleep(1)

    net2 = psutil.net_io_counters()

    bandwidth_in = net2.bytes_recv - net1.bytes_recv
    bandwidth_out = net2.bytes_sent - net1.bytes_sent

    return {
        "cpu": cpu,
        "memory": memory,
        "uptime": int(uptime),
        "bandwidth_in": bandwidth_in,
        "bandwidth_out": bandwidth_out
    }