import os
import socket
import httpx

def register_with_consul(service_name: str, port: int) -> None:
    consul_addr = os.getenv("CONSUL_HTTP_ADDR", "http://localhost:8500")
    try:
        host = socket.gethostbyname(socket.gethostname())
    except Exception:
        host = "127.0.0.1"
    payload = {
        "Name": service_name,
        "Address": host,
        "Port": port,
        "Check": {
            "HTTP": f"http://{host}:{port}/health",
            "Interval": "10s",
            "Timeout": "5s",
            "DeregisterCriticalServiceAfter": "1m",
        },
    }
    try:
        httpx.put(f"{consul_addr}/v1/agent/service/register", json=payload, timeout=5.0)
    except Exception:
        # Consul optional in local dev without agent
        pass
