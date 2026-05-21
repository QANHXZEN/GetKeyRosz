from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import sqlite3
from datetime import datetime, timedelta
import secrets
import hashlib

app = Flask(__name__)
app.secret_key = "supersecretkey_6778346_bankey"

# ==================== CẤU HÌNH ====================
ADMIN_KEY = "6778346"  # Admin key bí mật

# Giá các gói (VNĐ)
PRICES = {
    "1day": 5000,      # 5K - 1 ngày
    "1week": 20000,    # 20K - 1 tuần
    "1month": 50000,   # 50K - 1 tháng
    "forever": 200000  # 200K - Vĩnh viễn (100 năm)
}

DAYS_MAP = {
    "1day": 1,
    "1week": 7,
    "1month": 30,
    "forever": 36500  # 100 năm
}

PLAN_NAMES = {
    "1day": "VIP 1 Ngày",
    "1week": "VIP 1 Tuần",
    "1month": "VIP 1 Tháng",
    "forever": "VIP Vĩnh Viễn"
}

# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect('bot_data.db')
    
    # Bảng keys
    conn.execute('''
        CREATE TABLE IF NOT EXISTS premium_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_text TEXT UNIQUE NOT NULL,
            plan TEXT NOT NULL,
            duration_days INTEGER NOT NULL,
            price INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            order_id TEXT UNIQUE,
            buyer_name TEXT,
            buyer_email TEXT,
            buyer_telegram TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            used_by INTEGER,
            used_at TIMESTAMP,
            is_used BOOLEAN DEFAULT 0,
            payment_method TEXT,
            payment_status TEXT DEFAULT 'pending'
        )
    ')
    
    # Bảng orders
    conn.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            plan TEXT NOT NULL,
            amount INTEGER NOT NULL,
            buyer_name TEXT,
            buyer_email TEXT,
            buyer_telegram TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            paid_at TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

init_db()

# ==================== HÀM HỖ TRỢ ====================
def generate_order_id():
    """Tạo mã đơn hàng duy nhất"""
    return f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4).upper()}"

def generate_key(plan, days):
    """Tạo key premium"""
    key = f"{plan.upper()}-{secrets.token_hex(8).upper()}"
    expires_at = datetime.now() + timedelta(days=days)
    return key, expires_at

def create_order(plan, buyer_name, buyer_email, buyer_telegram):
    """Tạo đơn hàng mới"""
    order_id = generate_order_id()
    amount = PRICES[plan]
    days = DAYS_MAP[plan]
    
    conn = sqlite3.connect('bot_data.db')
    
    # Tạo key
    key_text, expires_at = generate_key(plan, days)
    
    # Lưu key
    conn.execute('''
        INSERT INTO premium_keys (key_text, plan, duration_days, price, order_id, 
                   buyer_name, buyer_email, buyer_telegram, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (key_text, plan, days, amount, order_id, buyer_name, buyer_email, buyer_telegram, expires_at))
    
    # Lưu order
    conn.execute('''
        INSERT INTO orders (order_id, plan, amount, buyer_name, buyer_email, buyer_telegram)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (order_id, plan, amount, buyer_name, buyer_email, buyer_telegram))
    
    conn.commit()
    conn.close()
    
    return order_id, key_text, amount

def confirm_payment(order_id, payment_method="bank"):
    """Xác nhận thanh toán"""
    conn = sqlite3.connect('bot_data.db')
    
    # Cập nhật key
    conn.execute('''
        UPDATE premium_keys 
        SET status = 'active', payment_method = ?, payment_status = 'paid'
        WHERE order_id = ?
    ''', (payment_method, order_id))
    
    # Cập nhật order
    conn.execute('''
        UPDATE orders 
        SET status = 'paid', paid_at = CURRENT_TIMESTAMP
        WHERE order_id = ?
    ''', (order_id,))
    
    conn.commit()
    conn.close()
    return True

def get_key_info(key_text):
    """Lấy thông tin key"""
    conn = sqlite3.connect('bot_data.db')
    conn.row_factory = sqlite3.Row
    key = conn.execute(
        "SELECT * FROM premium_keys WHERE key_text = ?",
        (key_text,)
    ).fetchone()
    conn.close()
    return dict(key) if key else None

# ==================== WEB ROUTES ====================
@app.route('/')
def index():
    """Trang chủ - Bán key"""
    return render_template('index.html', prices=PRICES, plan_names=PLAN_NAMES)

@app.route('/buy/<plan>')
def buy_page(plan):
    """Trang mua key theo gói"""
    if plan not in PRICES:
        return redirect(url_for('index'))
    
    return render_template('buy.html', 
                         plan=plan, 
                         plan_name=PLAN_NAMES[plan],
                         price=PRICES[plan],
                         days=DAYS_MAP[plan])

@app.route('/api/create-order', methods=['POST'])
def create_order_api():
    """API tạo đơn hàng"""
    data = request.json
    plan = data.get('plan')
    buyer_name = data.get('name', '')
    buyer_email = data.get('email', '')
    buyer_telegram = data.get('telegram', '')
    
    if plan not in PRICES:
        return jsonify({'error': 'Gói không hợp lệ'}), 400
    
    if not buyer_telegram:
        return jsonify({'error': 'Vui lòng nhập Telegram username'}), 400
    
    order_id, key_text, amount = create_order(plan, buyer_name, buyer_email, buyer_telegram)
    
    return jsonify({
        'order_id': order_id,
        'key_text': key_text,
        'amount': amount,
        'bank_info': {
            'bank': 'Vietcombank',
            'account_name': 'NGUYEN VAN A',
            'account_number': '1234567890',
            'content': order_id
        }
    })

@app.route('/api/confirm-payment', methods=['POST'])
def confirm_payment_api():
    """API xác nhận thanh toán"""
    data = request.json
    order_id = data.get('order_id')
    payment_method = data.get('payment_method', 'bank')
    
    if confirm_payment(order_id, payment_method):
        # Lấy key đã tạo
        conn = sqlite3.connect('bot_data.db')
        key = conn.execute(
            "SELECT key_text FROM premium_keys WHERE order_id = ?",
            (order_id,)
        ).fetchone()
        conn.close()
        
        return jsonify({
            'success': True,
            'key': key[0] if key else None,
            'message': 'Thanh toán thành công! Key đã được kích hoạt.'
        })
    
    return jsonify({'success': False, 'message': 'Lỗi xác nhận thanh toán'}), 400

@app.route('/check-key')
def check_key_page():
    """Trang kiểm tra key"""
    return render_template('check_key.html')

@app.route('/api/check-key', methods=['POST'])
def check_key_api():
    """API kiểm tra thông tin key"""
    data = request.json
    key_text = data.get('key')
    
    key_info = get_key_info(key_text)
    
    if not key_info:
        return jsonify({'valid': False, 'message': 'Key không tồn tại'})
    
    is_valid = key_info['is_used'] == 0 and key_info['status'] == 'active'
    expires_at = datetime.fromisoformat(key_info['expires_at']) if key_info['expires_at'] else None
    is_expired = expires_at and expires_at < datetime.now()
    
    return jsonify({
        'valid': is_valid and not is_expired,
        'plan': PLAN_NAMES.get(key_info['plan'], key_info['plan']),
        'duration': f"{key_info['duration_days']} ngày",
        'expires_at': key_info['expires_at'],
        'is_used': key_info['is_used'],
        'message': '✅ Key còn hiệu lực' if (is_valid and not is_expired) else '❌ Key đã hết hạn hoặc đã được sử dụng'
    })

@app.route('/admin')
def admin_page():
    """Trang admin - Yêu cầu admin key"""
    return render_template('admin.html')

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Đăng nhập admin"""
    data = request.json
    if data.get('admin_key') == ADMIN_KEY:
        session['admin_logged_in'] = True
        return jsonify({'success': True})
    return jsonify({'success': False}), 401

@app.route('/api/admin/keys')
def admin_get_keys():
    """API lấy danh sách keys (admin only)"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = sqlite3.connect('bot_data.db')
    conn.row_factory = sqlite3.Row
    keys = conn.execute('''
        SELECT * FROM premium_keys ORDER BY created_at DESC
    ''').fetchall()
    conn.close()
    
    return jsonify([dict(k) for k in keys])

@app.route('/api/admin/orders')
def admin_get_orders():
    """API lấy danh sách đơn hàng (admin only)"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = sqlite3.connect('bot_data.db')
    conn.row_factory = sqlite3.Row
    orders = conn.execute('''
        SELECT * FROM orders ORDER BY created_at DESC
    ''').fetchall()
    conn.close()
    
    return jsonify([dict(o) for o in orders])

@app.route('/api/admin/stats')
def admin_get_stats():
    """API lấy thống kê (admin only)"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = sqlite3.connect('bot_data.db')
    
    total_keys = conn.execute("SELECT COUNT(*) FROM premium_keys").fetchone()[0]
    active_keys = conn.execute("SELECT COUNT(*) FROM premium_keys WHERE status='active' AND is_used=0").fetchone()[0]
    used_keys = conn.execute("SELECT COUNT(*) FROM premium_keys WHERE is_used=1").fetchone()[0]
    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    paid_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status='paid'").fetchone()[0]
    total_revenue = conn.execute("SELECT SUM(amount) FROM orders WHERE status='paid'").fetchone()[0] or 0
    
    conn.close()
    
    return jsonify({
        'total_keys': total_keys,
        'active_keys': active_keys,
        'used_keys': used_keys,
        'total_orders': total_orders,
        'paid_orders': paid_orders,
        'total_revenue': total_revenue
    })

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_page'))

if __name__ == '__main__':
    print("=" * 50)
    print("🌐 WEB BÁN KEY PREMIUM")
    print("🔗 http://localhost:5000")
    print("🔐 Admin Key: 6778346")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)