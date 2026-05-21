from flask import Flask, render_template, request, jsonify, session, redirect, url_back
from functools import wraps
import sqlite3
from datetime import datetime, timedelta
import secrets
import os

app = Flask(__name__)
app.secret_key = "supersecretkey_6778346_bankey"

# ==================== CẤU HÌNH ====================
ADMIN_KEY = "6778346"  # Admin key bí mật

# Giá các gói (VNĐ)
PRICES = {
    "1day": 5000,      # 5K - 1 ngày
    "1week": 20000,    # 20K - 1 tuần
    "1month": 50000,   # 50K - 1 tháng
    "forever": 200000  # 200K - Vĩnh viễn
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
    """Khởi tạo database"""
    conn = sqlite3.connect('bot_data.db')
    
    # Bảng premium_keys
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
    ''')
    
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

# Khởi tạo database khi chạy
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
    return render_template_string(INDEX_HTML, prices=PRICES, plan_names=PLAN_NAMES)

@app.route('/buy/<plan>')
def buy_page(plan):
    """Trang mua key theo gói"""
    if plan not in PRICES:
        return redirect(url_for('index'))
    
    return render_template_string(BUY_HTML, 
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
    return render_template_string(CHECK_KEY_HTML)

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
    return render_template_string(ADMIN_HTML)

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

# ==================== HTML TEMPLATES (Nhúng trực tiếp để tránh lỗi file) ====================

INDEX_HTML = '''
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Premium - Mua Key VIP</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 50px;
        }
        .header h1 {
            font-size: 48px;
            margin-bottom: 10px;
        }
        .pricing-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 30px;
            margin-bottom: 50px;
        }
        .pricing-card {
            background: white;
            border-radius: 20px;
            padding: 30px;
            text-align: center;
            transition: transform 0.3s;
            cursor: pointer;
            position: relative;
        }
        .pricing-card:hover {
            transform: translateY(-10px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.2);
        }
        .pricing-card.popular {
            border: 2px solid #f39c12;
            transform: scale(1.02);
        }
        .popular-badge {
            position: absolute;
            top: 20px;
            right: -30px;
            background: #f39c12;
            color: white;
            padding: 5px 30px;
            transform: rotate(45deg);
            font-size: 12px;
            font-weight: bold;
        }
        .plan-name {
            font-size: 28px;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 10px;
        }
        .price {
            font-size: 48px;
            font-weight: bold;
            color: #333;
            margin: 20px 0;
        }
        .price small {
            font-size: 16px;
            color: #999;
        }
        .duration {
            color: #666;
            margin-bottom: 20px;
        }
        .features {
            list-style: none;
            margin: 20px 0;
        }
        .features li {
            padding: 8px 0;
            color: #555;
            border-bottom: 1px solid #eee;
        }
        .features li:before {
            content: "✓";
            color: #27ae60;
            font-weight: bold;
            margin-right: 10px;
        }
        .buy-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 30px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            width: 100%;
        }
        .footer {
            text-align: center;
            color: white;
            margin-top: 50px;
        }
        .footer a {
            color: white;
            margin: 0 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Bot Premium VIP</h1>
            <p>Nâng cấp tài khoản để trải nghiệm đầy đủ tính năng</p>
        </div>
        <div class="pricing-grid">
            <div class="pricing-card">
                <div class="plan-name">⚡ VIP 1 Ngày</div>
                <div class="price">5,000đ <small>/ 1 ngày</small></div>
                <div class="duration">⏰ Thời gian: 24 giờ</div>
                <ul class="features">
                    <li>Chạy code 50+ ngôn ngữ</li>
                    <li>Tạo QR code không giới hạn</li>
                    <li>Quản lý công việc</li>
                    <li>Hỗ trợ 24/7</li>
                </ul>
                <button class="buy-btn" onclick="buyNow('1day')">Mua Ngay</button>
            </div>
            <div class="pricing-card popular">
                <div class="popular-badge">PHỔ BIẾN</div>
                <div class="plan-name">🔥 VIP 1 Tuần</div>
                <div class="price">20,000đ <small>/ 7 ngày</small></div>
                <div class="duration">⏰ Tiết kiệm 43%</div>
                <ul class="features">
                    <li>Chạy code 50+ ngôn ngữ</li>
                    <li>Tạo QR code không giới hạn</li>
                    <li>Hỗ trợ ưu tiên</li>
                    <li>+ 2 ngày tặng thêm</li>
                </ul>
                <button class="buy-btn" onclick="buyNow('1week')">Mua Ngay</button>
            </div>
            <div class="pricing-card">
                <div class="plan-name">💎 VIP 1 Tháng</div>
                <div class="price">50,000đ <small>/ 30 ngày</small></div>
                <div class="duration">⏰ Tiết kiệm 67%</div>
                <ul class="features">
                    <li>Chạy code 50+ ngôn ngữ</li>
                    <li>Tạo QR code không giới hạn</li>
                    <li>Hỗ trợ VIP 24/7</li>
                    <li>+ 5 ngày tặng thêm</li>
                </ul>
                <button class="buy-btn" onclick="buyNow('1month')">Mua Ngay</button>
            </div>
            <div class="pricing-card">
                <div class="plan-name">👑 VIP Vĩnh Viễn</div>
                <div class="price">200,000đ <small>/ mãi mãi</small></div>
                <div class="duration">⭐ Giá trị trọn đời</div>
                <ul class="features">
                    <li>Chạy code 50+ ngôn ngữ</li>
                    <li>Tất cả tính năng tương lai</li>
                    <li>Hỗ trợ ưu tiên cao nhất</li>
                    <li>Quà tặng đặc biệt</li>
                </ul>
                <button class="buy-btn" onclick="buyNow('forever')">Mua Ngay</button>
            </div>
        </div>
        <div class="footer">
            <p>📩 Sau khi thanh toán, key sẽ được gửi tự động</p>
            <p>🔍 <a href="/check-key">Kiểm tra key</a> | 👑 <a href="/admin">Admin Login</a></p>
        </div>
    </div>
    <script>
        function buyNow(plan) {
            window.location.href = `/buy/${plan}`;
        }
    </script>
</body>
</html>
'''

BUY_HTML = '''
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Thanh toán - Bot Premium</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        .card {
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .back-btn {
            display: inline-block;
            margin-bottom: 20px;
            color: white;
            text-decoration: none;
        }
        h1 { color: #667eea; margin-bottom: 20px; }
        .order-info {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
        }
        input:focus { outline: none; border-color: #667eea; }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 14px 30px;
            border-radius: 30px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            width: 100%;
        }
        .bank-info {
            background: #e8f5e9;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            display: none;
        }
        .result {
            margin-top: 20px;
            padding: 15px;
            border-radius: 10px;
            display: none;
        }
        .result.success {
            background: #d4edda;
            color: #155724;
            display: block;
        }
        .result.error {
            background: #f8d7da;
            color: #721c24;
            display: block;
        }
        .key-display {
            font-family: monospace;
            font-size: 18px;
            background: white;
            padding: 10px;
            border-radius: 5px;
            margin-top: 10px;
            word-break: break-all;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-btn">← Quay lại</a>
        <div class="card">
            <h1>💰 Thanh toán</h1>
            <div class="order-info">
                <h3>📦 Gói: <span id="planName">{{ plan_name }}</span></h3>
                <p>💰 Giá: <strong>{{ price }}đ</strong></p>
                <p>⏰ Thời gian: <span id="duration">{{ days }} ngày</span></p>
            </div>
            <form id="orderForm">
                <div class="form-group">
                    <label>👤 Họ và tên</label>
                    <input type="text" id="name" pl