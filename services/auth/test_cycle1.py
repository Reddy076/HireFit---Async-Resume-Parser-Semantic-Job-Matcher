import os
# Cycle 1 local test: needs services running via compose.
# python test_cycle1.py
import urllib.request, json

BASE_AUTH = "http://localhost:8001"
BASE_RESUME = "http://localhost:8002"

print(urllib.request.urlopen(f"{BASE_AUTH}/health").read()[:100])
print(urllib.request.urlopen(f"{BASE_RESUME}/health").read()[:100])
print("cycle1 smoke OK - register/login/upload tested manually via docs")
