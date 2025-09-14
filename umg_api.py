#!/usr/bin/env python3
import os, requests
UMG_API = os.getenv('UMG_API', 'https://umgservicejp.com/api')
UMG_API_KEY = os.getenv('UMG_API_KEY', '')

def order_umg_service(service_id, quantity):
    payload = {
        'key': UMG_API_KEY,
        'action': 'add',
        'service': service_id,
        'quantity': str(quantity)
    }
    try:
        r = requests.post(UMG_API, data=payload, timeout=30)
        try:
            return r.json()
        except Exception:
            return {'error':'invalid_response','status_code':r.status_code,'text':r.text}
    except Exception as e:
        return {'error':str(e)}
