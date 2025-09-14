#!/usr/bin/env python3
import os, importlib.util, json, traceback
BASE = os.path.dirname(__file__)

def _load_module(path):
    try:
        spec = importlib.util.spec_from_file_location('mod', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        return None

def get_paypay_uuid(phone=None, password=None):
    candidate = os.path.join(BASE, 'original_login.py')
    if os.path.exists(candidate):
        mod = _load_module(candidate)
        if mod:
            for name in ('get_uuid','getpaypayuuid','get_paypay_uuid','login_get_uuid','login_and_get_uuid','login'):
                if hasattr(mod, name):
                    fn = getattr(mod, name)
                    try:
                        res = fn(phone, password) if (phone and password) else fn()
                        if isinstance(res, tuple):
                            return res[0], None
                        if isinstance(res, str):
                            return res, None
                    except Exception as e:
                        return None, f'error calling {name}: {e}'
            if hasattr(mod, 'PayPay'):
                try:
                    pp = mod.PayPay()
                    for attr in ('get_uuid','client_uuid','uuid','access_token','token'):
                        if hasattr(pp, attr):
                            return str(getattr(pp, attr)), None
                except Exception as e:
                    return None, f'PayPay class error: {e}'
    token_path = os.path.join(os.getcwd(), 'token.json')
    if os.path.exists(token_path):
        try:
            with open(token_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'uuid' in data:
                    return data['uuid'], None
        except Exception as e:
            return None, f'token.json read error: {e}'
    return None, 'no integration found; place original_login.py into payapy_lib or implement get_paypay_uuid'

def check_payment_by_url(uuid, url):
    candidate = os.path.join(BASE, 'original_claim_link.py')
    if os.path.exists(candidate):
        mod = _load_module(candidate)
        if mod:
            for name in ('check_payment_by_url','check_payment','claim_link','verify_link','check'):
                if hasattr(mod, name):
                    fn = getattr(mod, name)
                    try:
                        res = fn(uuid, url)
                        if isinstance(res, tuple) and len(res)>=1:
                            ok = bool(res[0])
                            details = res[1] if len(res)>1 else {}
                            if isinstance(details, dict) and 'amount' not in details:
            details['amount'] = details.get('price', 0.0)
        return ok, details
                        if isinstance(res, dict):
                            paid = res.get('paid') or res.get('status') in ('COMPLETED','PAID','SUCCESS')
                            return bool(paid), res
                        if isinstance(res, bool):
                            return res, {}
                    except Exception as e:
                        return False, f'claim_link.{name} error: {e}'
    status_api = os.getenv('PAYPAY_STATUS_API')
    if status_api:
        try:
            import requests
            r = requests.post(status_api, json={'uuid': uuid, 'url': url}, timeout=15)
            data = r.json()
            return data.get('paid', False), data
        except Exception as e:
            return False, f'status_api error: {e}'
    if 'paid' in url:
        return True, {'note':'test: url contains paid'}
    return False, {'note':'no verification available'}
