from flask import Flask, request, redirect, render_template, session, flash, url_for, abort
import csv
from datetime import datetime
import os
import smtplib
from email.message import EmailMessage
import requests
import time
from email.mime.text import MIMEText
import random
ADMIN_PASSWORD = "admin123" 
ORDERS_CSV = 'orders.csv'
phone_number = '85676756756'
GMAIL_USER = 'premaavk@gmail.com'
GMAIL_APP_PASSWORD = 'jxhw fvph jkaw wnhk'
RECAPTCHA_SECRET = '6LdIdp0rAAAAAHCoaGZhQkNEV2CCyaHfq3nUUHf7'
YOUR_UPI_ID = "Aduto@bank"  # 🔁 Replace this with your real UPI ID
RECEIVER_UPI = "Aduto@bank"
app = Flask(__name__)
app.secret_key = 'why'  # Use any random string

@app.before_request
def require_browser_headers():
    required_headers = [
        "sec-fetch-site",
        "sec-fetch-mode",
        "sec-fetch-dest",
        "accept-language"
    ]

    for h in required_headers:
        if h not in request.headers:
            abort(404)
def block_cli_tools():
    ua = request.headers.get("User-Agent", "").lower()

    blocked = [
        "curl",
        "wget",
        "httpie",
        "postman",
        "python",
        "libwww",
        "go-http-client"
    ]

    if any(tool in ua for tool in blocked):
        abort(404)  # or 403

def send_status_email(to_email, order_id, status, preview_link):
    sender_email = "premaavk@gmail.com"  # replace with your Gmail
    sender_password = "jxhw fvph jkaw wnhk"  # use App Password, not Gmail password

    subject = f"Order {order_id} Update"
    body = f"Your order status is: {status}\nPreview link: {preview_link}\nCheck status anytime at: http://127.0.0.1:5000.com/status"

    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = to_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def send_email(to, subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    entered_otp = request.form['otp']
    session_otp = session.get('otp')

    if entered_otp == session_otp:
        # OTP is correct — Save the order
        name = session.get('name')
        phone = session.get('phone')
        gmail = session.get('user_email')
        upi_id = session.get('upi_id')
        details = session.get('details')
        time_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            with open('orders.csv', 'r', encoding='utf-8') as f:
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

        file_needs_header = not os.path.isfile('orders.csv') or os.stat('orders.csv').st_size == 0

        with open('orders.csv', 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if file_needs_header:
                writer.writerow(['Order ID', 'Time', 'Name', 'Phone', 'Gmail', 'UPI ID', 'Details', 'Status', 'PreviewLink'])
            writer.writerow([order_number, time_now, name, phone, gmail, upi_id, details, status, preview_link])

        # Show thanks page
        return render_template('thanks.html', order_id=order_number)

    else:
        flash("❌ Incorrect OTP. Please try again.")
        return render_template("otp_verify.html", order_id=session.get('order_id'))

@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    order_id = request.form.get('order_id')
    user_email = request.form.get('gmail')

    # Save order_id and user_email in session
    session['order_id'] = order_id
    session['user_email'] = user_email

    # Generate and store OTP
    otp = str(random.randint(100000, 999999))
    session['otp'] = otp

    # Send OTP to user email
    subject = f"OTP for your order #{order_id}"
    body = f"Hello,\n\nYour OTP to confirm your order is: {otp}\n\nThank you!"
    send_email(to=user_email, subject=subject, body=body)

    return render_template("otp_verify.html", order_id=order_id)

@app.route('/admin/update', methods=['POST'])
def update_orders():
    updated_orders = []
    send_email_id = request.form.get('send_email')

    try:
        with open('orders.csv', 'r', encoding='utf-8') as f:
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

        # If Send Email button was clicked for this order
        if send_email_id == order_id:
            customer_email = request.form.get(f'email_{order_id}')
            if customer_email:
                send_status_email(customer_email, order_id, order['Status'], order['PreviewLink'])

        updated_orders.append(order)

    with open('orders.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_orders)

    return redirect('/admin')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        password = request.form['password']
        if password == ADMIN_PASSWORD:
            # Load orders from CSV
            orders = []
            try:
                with open('orders.csv', 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        print("Row keys:", row.keys()) 
                        orders.append({
                            'order_id': row['Order ID'],
                            'name': row['Name'],
                            'phone': row['Phone'],
                            'gmail': row.get('Gmail', ''),
                            'upi_id': row['UPI ID'],
                            'details': row['Details'],
                            'status': row.get('Status', ''),
                            'preview': row.get('PreviewLink', '')
                        })
            except FileNotFoundError:
                orders = []
            return render_template('admin_panel.html', orders=orders)
        else:
            return "❌ Incorrect password"
    return render_template('admin_login.html')

@app.route('/payment', methods=['POST'])
def payment():
    name = request.form['name']
    phone = request.form['phone']
    upi_id = request.form['upi_id']
    details = request.form['details']

    session['name'] = name
    session['phone'] = phone
    session['upi_id'] = upi_id
    session['details'] = details

    return render_template("pay_now.html", name=name, phone=phone, upi_id=upi_id, details=details, phone_number =phone_number)

@app.route('/admin/send_email', methods=['POST'])
def send_individual_email():
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
    details = request.form['details'] 
    time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        with open('orders.csv', 'r', encoding='utf-8') as f:
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

    file_needs_header = not os.path.isfile('orders.csv') or os.stat('orders.csv').st_size == 0

    with open('orders.csv', 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if file_needs_header:
            writer.writerow(['Order ID', 'Time', 'Name', 'Phone', 'Gmail', 'UPI ID', 'Details', 'Status', 'PreviewLink'])
        writer.writerow([order_number, time, name, phone, gmail, upi_id, details, status, preview_link])

    return f'''
    <h1>✅ Order Confirmed!</h1>
    <p>Your order number is <strong>{order_number}</strong></p>
    '''


@app.route('/status', methods=['GET', 'POST'])
def check_status():
    if request.method == 'POST':
        order_id = request.form['order_id']
        try:
            with open('orders.csv', 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row[0] == order_id:
                        return f'''
                        <h1>📦 Order Status</h1>
                        <p><strong>Status:</strong> {row[6]}</p>
                        <p><strong>Preview Link:</strong> {row[7]}</p>
                        '''
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)




