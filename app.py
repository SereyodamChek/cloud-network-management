from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from config import Config
from ping3 import ping
from datetime import datetime
from monitor import get_system_metrics
import os
from network_scanner import scan_network
app = Flask(__name__)
app.config.from_object(Config)

API_TOKEN = os.environ.get("API_TOKEN", "my-agent-secret")

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please login first.'


# =========================
# Database Models
# =========================
class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)


class Device(db.Model):
    __tablename__ = 'devices'

    id = db.Column(db.Integer, primary_key=True)
    device_name = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(100), nullable=False)
    device_type = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='Unknown')
    last_checked = db.Column(db.DateTime, nullable=True)
    response_time = db.Column(db.Float, nullable=True)


class ScannedDevice(db.Model):
    __tablename__ = 'scanned_devices'

    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(50), nullable=False, unique=True)
    mac = db.Column(db.String(50), nullable=True)
    vendor = db.Column(db.String(255), nullable=True, default='Unknown')
    hostname = db.Column(db.String(255), nullable=True, default='N/A')
    device_type = db.Column(db.String(100), nullable=True, default='Unknown')
    possible_model = db.Column(db.String(255), nullable=True, default='N/A')
    status = db.Column(db.String(20), nullable=False, default='Online')
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# =========================
# Login Manager
# =========================
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# =========================
# Routes
# =========================
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    devices = Device.query.all()

    total_devices = len(devices)
    online_devices = len([d for d in devices if d.status == 'Online'])
    offline_devices = len([d for d in devices if d.status == 'Offline'])
    unknown_devices = len([d for d in devices if d.status == 'Unknown'])

    router_count = len([d for d in devices if d.device_type and d.device_type.lower() == 'router'])
    switch_count = len([d for d in devices if d.device_type and d.device_type.lower() == 'switch'])
    pc_count = len([d for d in devices if d.device_type and d.device_type.lower() == 'pc'])
    phone_count = len([d for d in devices if d.device_type and d.device_type.lower() == 'phone'])
    server_count = len([d for d in devices if d.device_type and d.device_type.lower() == 'server'])

    return render_template(
        'dashboard.html',
        devices=devices,
        total_devices=total_devices,
        online_devices=online_devices,
        offline_devices=offline_devices,
        unknown_devices=unknown_devices,
        router_count=router_count,
        switch_count=switch_count,
        pc_count=pc_count,
        phone_count=phone_count,
        server_count=server_count
    )


@app.route('/devices')
@login_required
def devices():
    all_devices = Device.query.all()
    return render_template('devices.html', devices=all_devices)


@app.route('/device/<int:device_id>')
@login_required
def device_detail(device_id):
    device = Device.query.get_or_404(device_id)
    return render_template('device_detail.html', device=device)


@app.route('/add_device', methods=['GET', 'POST'])
@login_required
def add_device():
    if request.method == 'POST':
        device_name = request.form.get('device_name')
        ip_address = request.form.get('ip_address')
        device_type = request.form.get('device_type')
        location = request.form.get('location')

        new_device = Device(
            device_name=device_name,
            ip_address=ip_address,
            device_type=device_type,
            location=location
        )

        db.session.add(new_device)
        db.session.commit()

        flash('Device added successfully!', 'success')
        return redirect(url_for('devices'))

    return render_template('add_device.html')


@app.route('/edit_device/<int:device_id>', methods=['GET', 'POST'])
@login_required
def edit_device(device_id):
    device = Device.query.get_or_404(device_id)

    if request.method == 'POST':
        device.device_name = request.form.get('device_name')
        device.ip_address = request.form.get('ip_address')
        device.device_type = request.form.get('device_type')
        device.location = request.form.get('location')

        db.session.commit()
        flash('Device updated successfully!', 'success')
        return redirect(url_for('devices'))

    return render_template('edit_device.html', device=device)


@app.route('/check_devices')
@login_required
def check_devices():
    all_devices = Device.query.all()

    for device in all_devices:
        try:
            result = ping(device.ip_address, timeout=1)
            device.last_checked = datetime.now()

            if result is not None:
                device.status = 'Online'
                device.response_time = round(result * 1000, 2)
            else:
                device.status = 'Offline'
                device.response_time = None

        except Exception:
            device.status = 'Offline'
            device.response_time = None
            device.last_checked = datetime.now()

    db.session.commit()
    flash('Device status updated successfully!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/delete_device/<int:device_id>')
@login_required
def delete_device(device_id):
    device = Device.query.get_or_404(device_id)
    db.session.delete(device)
    db.session.commit()

    flash('Device deleted successfully!', 'success')
    return redirect(url_for('devices'))


@app.route('/scan-wifi')
@login_required
def scan_wifi():
    devices = ScannedDevice.query.order_by(ScannedDevice.last_seen.desc()).all()
    return render_template('scan_wifi.html', devices=devices)


@app.route('/metrics')
@login_required
def metrics():
    data = get_system_metrics()
    return render_template('metrics.html', data=data)


# =========================
# API ROUTE FOR LOCAL AGENT
# =========================
@app.route('/api/devices/update', methods=['POST'])
def api_devices_update():
    token = request.headers.get('X-API-KEY')

    if token != API_TOKEN:
        return {"success": False, "message": "Unauthorized"}, 401

    data = request.get_json(silent=True)

    if not data or 'devices' not in data:
        return {"success": False, "message": "Invalid payload"}, 400

    devices = data.get('devices', [])

    for item in devices:
        ip = item.get('ip')
        if not ip:
            continue

        scanned = ScannedDevice.query.filter_by(ip=ip).first()

        if not scanned:
            scanned = ScannedDevice(ip=ip)

        scanned.mac = item.get('mac', '')
        scanned.vendor = item.get('vendor', 'Unknown')
        scanned.hostname = item.get('hostname', 'N/A')
        scanned.device_type = item.get('device_type', 'Unknown')
        scanned.possible_model = item.get('possible_model', 'N/A')
        scanned.status = item.get('status', 'Online')
        scanned.last_seen = datetime.utcnow()

        db.session.add(scanned)

    db.session.commit()

    return {
        "success": True,
        "message": "Devices updated successfully",
        "count": len(devices)
    }, 200


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))


# =========================
# Initialize Database
# =========================
def create_default_admin():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin_user = User(username='admin', password='admin123')
        db.session.add(admin_user)
        db.session.commit()
        print('Default admin created: admin / admin123')


with app.app_context():
    db.create_all()
    create_default_admin()


if __name__ == '__main__':
    print(app.url_map)
    app.run(debug=True, use_reloader=False)