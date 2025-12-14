from flask import Flask, request, redirect, render_template, session, flash, abort
import csv
from datetime import datetime
import os
import smtplib
from email.message import EmailMessage
from email.mime.text import MIMEText
import random

# ========================= CONFIG =========================
ADMIN_PASSWORD = "admin123"
ORDERS_CSV = 'orders.csv'
PHONE_NUMBER = '85676756756'
GMAIL_USER = 'premaavk@gmail.com'
GMAIL_APP_PASSWORD = 'jxhw fvph jkaw wnhk'
YOUR_UPI_ID = "Aduto@bank"
RECEIVER_UPI = "Aduto@bank"

app = Flask(__name__)
app.secret_key = 'why'  # Change to a strong random string

# ===================== SECURITY MIDDLEWARE =====================
@app.before_request
def block_cli_and_non_browser():
    """Block curl, wget, postman, python requests, etc., and require browser headers"""
    ua = request.headers.get("User-Agent", "").lower()
    blocked_tools = ["curl", "wget", "httpie", "postman", "python", "libwww", "go-http-client"]
    if any(tool in ua for tool in blocked_tools):
        return "", 204  # Silent drop

    # Require browser headers
    required_headers = ["sec-fetch-site", "sec-fetch-mode", "sec-fetch-dest", "accept-language"]
    for h in required_headers:
        if h not in request.headers:
            return "", 204  # Silent drop

@app.before_request
def protect_admin_routes():
    """Ensure /admin routes require session login"""
    if request.path.startswith("/admin") and session.get("admin_logged_in") != True and request.path != "/admin":
        return redirect("/admin")

@app.after_request
def set_security_headers(response):
    """Set HTTP security headers"""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self'; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "frame-ancestors 'none';"
    )
    return response

# ========================= EMAIL FUNCTIONS =========================
def send_status_email(to_email, order_id, status, preview_link):
    subject = f"Order {order_id} Update"
    body = f"Your order status is: {status}\nPreview link: {preview_link}\nCheck status anytime at: http://127.0.0.1:5000/status"
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = GMAIL_USER
    msg['To'] = to_email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        print(f"Email failed: {e}")

def send_email(to, subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = to
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Email failed: {e}")

# ========================= ROUTES =========================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    entered_otp = request.form['otp']
    session_otp = session.get('otp')
    if entered_otp != session_otp:
        flash("❌ Incorrect OTP. Try again.")
        return render_template("otp_verify.html", order_id=session.get('order_id'))

    # Save order
    name = session.get('name')
    phone = session.get('phone')
    gmail = session.get('user_email')
    upi_id = session.get('upi_id')
    details = session.get('details')
    time_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        with open(ORDERS_CSV, 'r', encoding='utf-8') as f:
            rows = list(csv.reader(f))
            if len(rows) > 1:
                last_order = rows[-1][0]
                last_number = int(last_order.replace('ORD', ''))
                order_number = f'ORD{last_number + 1}'
            else:
                order_number = 'ORD1001'
    except FileNotFoundError:
        order_number = 'ORD1001'

    status = "Pending"
    preview_link = ""
    file_needs_header = not os.path.isfile(ORDERS_CSV) or os.stat(ORDERS_CSV).st_size == 0

    with open(ORDERS_CSV, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if file_needs_header:
            writer.writerow(['Order ID','Time','Name','Phone','Gmail','UPI ID','Details','Status','PreviewLink'])
        writer.writerow([order_number,time_now,name,phone,gmail,upi_id,details,status,preview_link])

    return render_template('thanks.html', order_id=order_number)

@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    order_id = request.form.get('order_id')
    user_email = request.form.get('gmail')
    session['order_id'] = order_id
    session['user_email'] = user_email
    otp = str(random.randint(100000, 999999))
    session['otp'] = otp
    subject = f"OTP for your order #{order_id}"
    body = f"Your OTP is: {otp}"
    send_email(user_email, subject, body)
    return render_template("otp_verify.html", order_id=order_id)

@app.route('/payment', methods=['POST'])
def payment():
    session['name'] = request.form['name']
    session['phone'] = request.form['phone']
    session['upi_id'] = request.form['upi_id']
    session['details'] = request.form['details']
    return render_template("pay_now.html", name=session['name'], phone=session['phone'], upi_id=session['upi_id'], details=session['details'], phone_number=PHONE_NUMBER)

@app.route('/status', methods=['GET', 'POST'])
def check_status():
    if request.method == 'POST':
        order_id = request.form['order_id']
        try:
            with open(ORDERS_CSV, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row[0] == order_id:
                        return f"<h1>📦 Order Status</h1><p><strong>Status:</strong> {row[7]}</p><p><strong>Preview Link:</strong> {row[8]}</p>"
            return "<p>❌ Order not found.</p>"
        except:
            return "<p>⚠️ Error reading orders file.</p>"
    return '''
    <h1>🔍 Track Your Order</h1>
    <form method="post">
        <label>Enter Order Number:</label>
        <input type="text" name="order_id" required>
        <button type="submit">Check Status</button>
    </form>
    '''

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        password = request.form['password']
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            orders = []
            try:
                with open(ORDERS_CSV, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        orders.append(row)
            except FileNotFoundError:
                orders = []
            return render_template('admin_panel.html', orders=orders)
        else:
            return "❌ Incorrect password"
    return render_template('admin_login.html')

@app.route('/admin/update', methods=['POST'])
def update_orders():
    if session.get("admin_logged_in") != True:
        return "", 403
    updated_orders = []
    send_email_id = request.form.get('send_email')
    try:
        with open(ORDERS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            all_orders = list(reader)
            fieldnames = reader.fieldnames
    except FileNotFoundError:
        return "Orders file not found"

    for order in all_orders:
        order_id = order['Order ID']
        if order_id in request.form.getlist("update_ids"):
            order['Status'] = request.form.get(f'status_{order_id}', '')
            order['PreviewLink'] = request.form.get(f'preview_{order_id}', '')
        if send_email_id == order_id and order.get('Gmail'):
            send_status_email(order['Gmail'], order_id, order['Status'], order['PreviewLink'])
        updated_orders.append(order)

    with open(ORDERS_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_orders)
    return redirect('/admin')

@app.route('/admin/send_email', methods=['POST'])
def send_individual_email():
    if session.get("admin_logged_in") != True:
        return "", 403
    order_id = request.form.get('order_id')
    status = request.form.get('status')
    preview_link = request.form.get('preview')
    email = request.form.get('email')
    if email:
        send_status_email(email, order_id, status, preview_link)
        flash(f"✅ Email sent to {email} for order {order_id}")
    return redirect('/admin')

@app.route('/confirm', methods=['POST'])
def confirm():
    name = request.form['name']
    phone = request.form['phone']
    gmail = request.form['gmail']
    upi_id = request.form['upi_id']
    details = request.form['details']
    time_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(ORDERS_CSV, 'r', encoding='utf-8') as f:
            rows = list(csv.reader(f))
            last_number = int(rows[-1][0].replace('ORD', '')) if len(rows) > 1 else 1000
            order_number = f"ORD{last_number + 1}"
    except FileNotFoundError:
        order_number = "ORD1001"

    status = "Pending"
    preview_link = ""
    file_needs_header = not os.path.isfile(ORDERS_CSV) or os.stat(ORDERS_CSV).st_size == 0
    with open(ORDERS_CSV, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if file_needs_header:
            writer.writerow(['Order ID','Time','Name','Phone','Gmail','UPI ID','Details','Status','PreviewLink'])
        writer.writerow([order_number,time_now,name,phone,gmail,upi_id,details,status,preview_link])

    return f"<h1>✅ Order Confirmed!</h1><p>Your order number is <strong>{order_number}</strong></p>"

# ========================= RUN =========================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
