#!/usr/bin/env python3
import os, time, subprocess, base64, requests
from pathlib import Path
from payapy_lib.payapy_integration import get_paypay_uuid, check_payment_by_url

VPN_GATE_API = 'http://www.vpngate.net/api/iphone/'
VPN_DIR = Path('./vpn_configs')
UUID_FILE = Path('./paypay_uuid.txt')

def ensure_vpn_dir():
    VPN_DIR.mkdir(parents=True, exist_ok=True)

def get_vpngate_servers():
    r = requests.get(VPN_GATE_API, timeout=15)
    lines = r.text.splitlines()
    servers = []
    for line in lines:
        if not line or line.startswith('*') or line.startswith('#'):
            continue
        cols = line.split(',')
        if len(cols) > 14:
            country = cols[6]
            ovpn_b64 = cols[-1]
            servers.append({'country': country, 'ovpn_b64': ovpn_b64})
    return servers

def connect_vpn():
    ensure_vpn_dir()
    servers = get_vpngate_servers()
    if not servers:
        raise RuntimeError('VPN Gate servers not available')
    jp = [s for s in servers if s.get('country') == 'JP']
    chosen = jp[int(time.time()) % len(jp)] if jp else servers[int(time.time()) % len(servers)]
    cfg_path = VPN_DIR / 'tmp_vpn.conf'
    with open(cfg_path, 'wb') as f:
        f.write(base64.b64decode(chosen['ovpn_b64']))
    proc = subprocess.Popen(['openvpn', '--config', str(cfg_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(8)
    return proc

def disconnect_vpn(proc):
    try:
        proc.terminate()
    except Exception:
        pass

def save_uuid(uuid):
    try:
        UUID_FILE.write_text(str(uuid))
    except Exception:
        pass

def load_uuid_from_file():
    if UUID_FILE.exists():
        return UUID_FILE.read_text().strip()
    return None

def wrapper_get_uuid(phone=None, password=None):
    uuid, err = get_paypay_uuid(phone, password)
    if uuid:
        save_uuid(uuid)
        return uuid, None
    return None, err

def wrapper_check_payment(uuid, url):
    return check_payment_by_url(uuid, url)
