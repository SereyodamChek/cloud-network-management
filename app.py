from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from config import Config
from ping3 import ping
from datetime import datetime
from monitor import get_system_metrics
import socket
import ipaddress

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please login first.'


# =========================
# Helper Functions
# =========================
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def get_local_subnet():
    local_ip = get_local_ip()
    network = ipaddress.ip_network(f"{local_ip}/24", strict=False)
    return str(network)


def normalize_status(status):
    if not status:
        return 'Unknown'

    s = str(status).strip().lower()
    if s == 'online':
        return 'Online'
    if s == 'offline':
        return 'Offline'
    return 'Unknown'


def safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


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
    ip_address = db.Column(db.String(100), nullable=False, unique=True)
    device_type = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=True)

    status = db.Column(db.String(20), default='Unknown')
    last_checked = db.Column(db.DateTime, nullable=True)
    response_time = db.Column(db.Float, nullable=True)

    mac_address = db.Column(db.String(100), nullable=True)
    vendor = db.Column(db.String(150), nullable=True)
    hostname = db.Column(db.String(150), nullable=True)
    possible_model = db.Column(db.String(150), nullable=True)
    agent_name = db.Column(db.String(100), nullable=True)
    last_seen = db.Column(db.DateTime, nullable=True)


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
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

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
    devices = Device.query.order_by(Device.ip_address.asc()).all()

    total_devices = len(devices)
    online_devices = len([d for d in devices if d.status == 'Online'])
    offline_devices = len([d for d in devices if d.status == 'Offline'])
    unknown_devices = len([d for d in devices if d.status == 'Unknown'])

    router_count = len([d for d in devices if d.device_type and d.device_type.lower() == 'router'])
    switch_count = len([d for d in devices if d.device_type and d.device_type.lower() == 'switch'])
    pc_count = len([d for d in devices if d.device_type and d.device_type.lower() == 'pc'])
    phone_count = len([d for d in devices if d.device_type and d.device_type.lower() == 'phone'])
    server_count = len([d for d in devices if d.device_type and d.device_type.lower() == 'server'])

    last_agent_update = db.session.query(db.func.max(Device.last_seen)).scalar()

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
        server_count=server_count,
        last_agent_update=last_agent_update
    )


@app.route('/devices')
@login_required
def devices():
    all_devices = Device.query.order_by(Device.ip_address.asc()).all()
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
        device_name = request.form.get('device_name', '').strip()
        ip_address = request.form.get('ip_address', '').strip()
        device_type = request.form.get('device_type', '').strip() or 'Unknown'
        location = request.form.get('location', '').strip()

        existing = Device.query.filter_by(ip_address=ip_address).first()
        if existing:
            flash('A device with this IP address already exists.', 'danger')
            return redirect(url_for('devices'))

        new_device = Device(
            device_name=device_name or ip_address,
            ip_address=ip_address,
            device_type=device_type,
            location=location,
            status='Unknown'
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
        new_ip = request.form.get('ip_address', '').strip()

        existing = Device.query.filter(Device.ip_address == new_ip, Device.id != device.id).first()
        if existing:
            flash('Another device already uses this IP address.', 'danger')
            return redirect(url_for('edit_device', device_id=device.id))

        device.device_name = request.form.get('device_name', '').strip() or device.device_name
        device.ip_address = new_ip
        device.device_type = request.form.get('device_type', '').strip() or 'Unknown'
        device.location = request.form.get('location', '').strip()

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


# =========================
# WiFi Scan Page (Fast UI)
# =========================
@app.route('/scan-wifi')
@login_required
def scan_wifi():
    devices = Device.query.order_by(
        Device.last_seen.is_(None),
        Device.last_seen.desc(),
        Device.ip_address.asc()
    ).all()
    return render_template('scan_wifi.html', devices=devices)


@app.route('/scan-wifi/run', methods=['POST'])
@login_required
def run_scan_wifi():
    try:
        from network_scanner import scan_network, get_local_subnet

        subnet = get_local_subnet()
        raw_devices = scan_network(subnet)
        now = datetime.now()

        found_ips = []

        for item in raw_devices:
            ip_address = str(item.get('ip', '')).strip()
            if not ip_address:
                continue

            found_ips.append(ip_address)

            hostname = str(item.get('hostname', 'Unknown')).strip() or 'Unknown'
            mac_address = str(item.get('mac', '')).strip()
            vendor = str(item.get('vendor', 'Unknown')).strip()
            device_type = str(item.get('device_type', 'Unknown')).strip() or 'Unknown'
            possible_model = str(item.get('possible_model', 'Unknown')).strip()
            status = normalize_status(item.get('status', 'Unknown'))
            response_time = safe_float(item.get('response_time'))
            location = str(item.get('location', 'Local Network')).strip()

            existing = Device.query.filter_by(ip_address=ip_address).first()

            if existing:
                existing.device_name = hostname if hostname != 'Unknown' else existing.device_name
                existing.hostname = hostname
                existing.mac_address = mac_address
                existing.vendor = vendor
                existing.device_type = device_type
                existing.possible_model = possible_model
                existing.status = status
                existing.response_time = response_time
                existing.last_checked = now
                existing.last_seen = now
                existing.agent_name = 'scan-wifi-local'
                existing.location = location
            else:
                new_device = Device(
                    device_name=hostname if hostname != 'Unknown' else ip_address,
                    ip_address=ip_address,
                    device_type=device_type,
                    location=location,
                    status=status,
                    last_checked=now,
                    response_time=response_time,
                    mac_address=mac_address,
                    vendor=vendor,
                    hostname=hostname,
                    possible_model=possible_model,
                    agent_name='scan-wifi-local',
                    last_seen=now
                )
                db.session.add(new_device)

        if found_ips:
            stale_devices = Device.query.filter(
                Device.agent_name == 'scan-wifi-local',
                ~Device.ip_address.in_(found_ips)
            ).all()

            for device in stale_devices:
                device.status = 'Offline'
                device.last_checked = now
                device.last_seen = now

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Scan completed. Found {len(raw_devices)} device(s).',
            'count': len(raw_devices)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Could not scan WiFi devices: {str(e)}'
        }), 500


@app.route('/scan-wifi/data')
@login_required
def scan_wifi_data():
    devices = Device.query.order_by(
        Device.last_seen.is_(None),
        Device.last_seen.desc(),
        Device.ip_address.asc()
    ).all()

    results = []
    for d in devices:
        results.append({
            'id': d.id,
            'ip_address': d.ip_address or '',
            'mac_address': d.mac_address or '',
            'vendor': d.vendor or 'Unknown',
            'hostname': d.hostname or 'Unknown',
            'device_type': d.device_type or 'Unknown',
            'possible_model': d.possible_model or 'Unknown',
            'status': d.status or 'Unknown',
            'agent_name': d.agent_name or 'N/A',
            'response_time': d.response_time,
            'last_seen': d.last_seen.strftime('%Y-%m-%d %H:%M:%S') if d.last_seen else 'N/A'
        })

    return jsonify(results), 200


@app.route('/metrics')
@login_required
def metrics():
    data = get_system_metrics()
    return render_template('metrics.html', data=data)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))


# =========================
# Agent API Routes
# =========================
@app.route('/api/health', methods=['GET'])
def api_health():
    return jsonify({
        'status': 'ok',
        'message': 'Server is running',
        'time': datetime.utcnow().isoformat()
    }), 200


@app.route('/api/devices', methods=['GET'])
def api_devices():
    all_devices = Device.query.order_by(Device.ip_address.asc()).all()

    results = []
    for d in all_devices:
        results.append({
            'id': d.id,
            'device_name': d.device_name,
            'ip_address': d.ip_address,
            'device_type': d.device_type,
            'location': d.location,
            'status': d.status,
            'last_checked': d.last_checked.isoformat() if d.last_checked else None,
            'response_time': d.response_time,
            'mac_address': d.mac_address,
            'vendor': d.vendor,
            'hostname': d.hostname,
            'possible_model': d.possible_model,
            'agent_name': d.agent_name,
            'last_seen': d.last_seen.isoformat() if d.last_seen else None
        })

    return jsonify(results), 200


@app.route('/api/scan-results', methods=['POST'])
def api_scan_results():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({'error': 'No JSON data received'}), 400

    agent_name = str(data.get('agent_name', 'local-agent')).strip()
    scan_time_raw = data.get('scan_time')
    devices = data.get('devices', [])

    if not isinstance(devices, list):
        return jsonify({'error': 'devices must be a list'}), 400

    if scan_time_raw:
        try:
            scan_time = datetime.fromisoformat(scan_time_raw)
        except Exception:
            scan_time = datetime.utcnow()
    else:
        scan_time = datetime.utcnow()

    created_count = 0
    updated_count = 0

    for item in devices:
        if not isinstance(item, dict):
            continue

        ip_address = str(item.get('ip', '')).strip()
        if not ip_address:
            continue

        hostname = str(item.get('hostname', 'Unknown')).strip() or 'Unknown'
        mac_address = str(item.get('mac', '')).strip()
        vendor = str(item.get('vendor', 'Unknown')).strip()
        device_type = str(item.get('device_type', 'Unknown')).strip() or 'Unknown'
        possible_model = str(item.get('possible_model', 'Unknown')).strip()
        status = normalize_status(item.get('status', 'Online'))
        response_time = safe_float(item.get('response_time'))
        location = str(item.get('location', '')).strip()

        existing = Device.query.filter_by(ip_address=ip_address).first()

        if existing:
            existing.device_name = hostname if hostname != 'Unknown' else existing.device_name
            existing.hostname = hostname
            existing.mac_address = mac_address or existing.mac_address
            existing.vendor = vendor
            existing.device_type = device_type
            existing.possible_model = possible_model
            existing.status = status
            existing.response_time = response_time
            existing.last_checked = scan_time
            existing.last_seen = scan_time
            existing.agent_name = agent_name
            if location:
                existing.location = location
            updated_count += 1
        else:
            new_device = Device(
                device_name=hostname if hostname != 'Unknown' else ip_address,
                ip_address=ip_address,
                device_type=device_type,
                location=location,
                status=status,
                last_checked=scan_time,
                response_time=response_time,
                mac_address=mac_address,
                vendor=vendor,
                hostname=hostname,
                possible_model=possible_model,
                agent_name=agent_name,
                last_seen=scan_time
            )
            db.session.add(new_device)
            created_count += 1

    db.session.commit()

    return jsonify({
        'message': 'Scan results processed successfully',
        'agent_name': agent_name,
        'received_devices': len(devices),
        'created': created_count,
        'updated': updated_count
    }), 200


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


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_default_admin()

    print(app.url_map)
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)