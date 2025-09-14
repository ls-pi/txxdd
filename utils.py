#!/usr/bin/env python3
import json, time, os
from pathlib import Path
DATA_DIR = Path('./data')
DATA_DIR.mkdir(exist_ok=True)
PRODUCTS_FILE = DATA_DIR / 'products.json'
ORDERS_FILE = DATA_DIR / 'orders.json'
PROFIT_FILE = DATA_DIR / 'profit_records.json'

def load_products():
    if PRODUCTS_FILE.exists():
        return json.loads(PRODUCTS_FILE.read_text(encoding='utf-8'))
    prods = [
        {'id':'srv_a','name':'サービスA','price':100.0,'umg_service_id':'1001'},
        {'id':'srv_b','name':'サービスB','price':200.5,'umg_service_id':'1002'}
    ]
    save_products(prods)
    return prods

def save_products(prods):
    PRODUCTS_FILE.write_text(json.dumps(prods, ensure_ascii=False, indent=2), encoding='utf-8')

def find_product(pid):
    for p in load_products():
        if p['id']==pid:
            return p
    return None

def create_order(user_id, product_id, quantity, paylink, amount):
    orders = []
    if ORDERS_FILE.exists():
        orders = json.loads(ORDERS_FILE.read_text(encoding='utf-8'))
    oid = int(time.time()*1000)
    order = {'order_id':oid,'user_id':user_id,'product_id':product_id,'quantity':quantity,'paylink':paylink,'amount':amount,'status':'pending','created_at':time.time()}
    orders.append(order)
    ORDERS_FILE.write_text(json.dumps(orders, ensure_ascii=False, indent=2), encoding='utf-8')
    return order

def update_order(order_id, **kwargs):
    if not ORDERS_FILE.exists():
        return
    orders = json.loads(ORDERS_FILE.read_text(encoding='utf-8'))
    for o in orders:
        if o['order_id']==order_id:
            o.update(kwargs)
    ORDERS_FILE.write_text(json.dumps(orders, ensure_ascii=False, indent=2), encoding='utf-8')

def load_orders():
    if ORDERS_FILE.exists():
        return json.loads(ORDERS_FILE.read_text(encoding='utf-8'))
    return []

def add_profit_record(order_id, profit):
    records = []
    if PROFIT_FILE.exists():
        records = json.loads(PROFIT_FILE.read_text(encoding='utf-8'))
    records.append({'order_id':order_id,'profit':profit,'ts':time.time()})
    PROFIT_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')

def get_monthly_profit(year, month):
    if not PROFIT_FILE.exists():
        return 0.0
    records = json.loads(PROFIT_FILE.read_text(encoding='utf-8'))
    s = 0.0
    for r in records:
        t = time.localtime(r['ts'])
        if t.tm_year==year and t.tm_mon==month:
            s += float(r['profit'])
    return s

def add_admin_session(user_id, ttl=3600):
    sess_file = DATA_DIR / 'admin_sessions.json'
    sess = {}
    if sess_file.exists():
        sess = json.loads(sess_file.read_text(encoding='utf-8'))
    sess[str(user_id)] = {'created':time.time(),'ttl':ttl}
    sess_file.write_text(json.dumps(sess, ensure_ascii=False, indent=2), encoding='utf-8')

def is_admin_session(user_id):
    sess_file = DATA_DIR / 'admin_sessions.json'
    if not sess_file.exists():
        return False
    sess = json.loads(sess_file.read_text(encoding='utf-8'))
    s = sess.get(str(user_id))
    if not s: return False
    if time.time() - s['created'] > s['ttl']:
        return False
    return True
