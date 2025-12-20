from flask import Flask, render_template, request, redirect, session, flash
import csv, os, random
from datetime import datetime
from gmail_oauth import send_email  # Gmail OAuth email sender

# ========================= CONFIG =========================
ADMIN_PASSWORD = "admin123"
ORDERS_CSV = 'orders.csv'
PHONE_NUMBER = '85676756756'

app = Flask(__name__)
app.secret_key = 'why'

# ========================= SECURITY =========================
@app.before_request
def protect_admin_routes():
    admin_paths_allowed = ["/admin", "/admin/logout"]

    if request.path.startswith("/admin"):
        if request.path in admin_paths_allowed:
            return  # allow login & logout

        if not session.get("admin_logged_in"):
            return redirect("/admin")

@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self';"
    return response

# ========================= USER ROUTES =========================
@app.route('/')
def home():
    return render_template('index.html')  # Main landing page

@app.route('/payment', methods=['POST'])
def payment():
    session['name'] = request.form['name']
    session['phone'] = request.form['phone']
    session['upi_id'] = request.form['upi_id']
    session['details'] = request.form['details']
    return render_template("pay_now.html", name=session['name'], phone=session['phone'],
                           upi_id=session['upi_id'], details=session['details'], phone_number=PHONE_NUMBER)

@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    order_id = request.form.get('order_id')
    user_email = request.form.get('gmail')
    session['order_id'] = order_id
    session['user_email'] = user_email
    otp = str(random.randint(100000, 999999))
    session['otp'] = otp
    send_email(user_email, f"OTP for your order #{order_id}", f"Your OTP is: {otp}")
    return render_template("otp_verify.html", order_id=order_id)

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
            last_number = int(rows[-1][0].replace('ORD', '')) if len(rows) > 1 else 1000
            order_number = f'ORD{last_number + 1}'
    except FileNotFoundError:
        order_number = 'ORD1001'

    status = "Pending"
    preview_link = ""
    file_needs_header = not os.path.isfile(ORDERS_CSV) or os.stat(ORDERS_CSV).st_size == 0

    with open(ORDERS_CSV, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if file_needs_header:
            writer.writerow(['Order ID','Time','Name','Phone','Gmail','UPI ID','Details','Status','PreviewLink'])
        writer.writerow([order_number, time_now, name, phone, gmail, upi_id, details, status, preview_link])

    send_email(gmail, f"Order {order_number} Confirmed", f"Your order {order_number} is confirmed.\nStatus: {status}")

    return render_template('thanks.html', order_id=order_number)

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
        <input type="text" name="order_id" required placeholder="Enter Order Number">
        <button type="submit">Check Status</button>
    </form>
    '''

# ========================= ADMIN ROUTES =========================
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            orders = []
            if os.path.exists(ORDERS_CSV):
                with open(ORDERS_CSV, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    orders = list(reader)
            return render_template('admin_panel.html', orders=orders)
        else:
            flash("❌ Incorrect password")
            return redirect('/admin')
    return render_template('admin_login.html')

@app.route('/admin/update', methods=['POST'])
def update_orders():
    if not session.get("admin_logged_in"):
        return "", 403

    updated_orders = []
    orders_to_remove = []

    if os.path.exists(ORDERS_CSV):
        with open(ORDERS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            all_orders = list(reader)

        for order in all_orders:
            order_id = order['Order ID']
            if order_id in request.form.getlist("update_ids"):
                order['Status'] = request.form.get(f'status_{order_id}', order['Status'])
                order['PreviewLink'] = request.form.get(f'preview_{order_id}', order['PreviewLink'])

            if request.form.get('send_email_id') == order_id:
                send_email(order['Gmail'], f"Order {order_id} Update",
                           f"Status: {order['Status']}\nPreview: {order['PreviewLink']}")
                orders_to_remove.append(order_id)

            updated_orders.append(order)

        updated_orders = [o for o in updated_orders if o['Order ID'] not in orders_to_remove]

        with open(ORDERS_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_orders)

    return redirect('/admin')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin')

# ========================= RUN =========================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
