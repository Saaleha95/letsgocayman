from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# ── DATABASE CONFIG (Render PostgreSQL compatible) ─────────
uri = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
if uri.startswith('postgres://'):
    uri = uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    username     = db.Column(db.String(80), unique=True, nullable=False)
    full_name    = db.Column(db.String(120), nullable=False)
    phone_number = db.Column(db.String(15), nullable=False)
    password     = db.Column(db.String(200), nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()


# ── SIGNUP ─────────────────────────────────────────────────
@app.route('/api/auth/signup/', methods=['POST'])
def signup():
    data = request.get_json()
    full_name    = data.get('fullName')
    username     = data.get('username')
    phone_number = data.get('phoneNumber')
    password     = data.get('password')

    if not all([full_name, username, phone_number, password]):
        return jsonify({'message': 'All fields are required'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'Username already exists'}), 409

    new_user = User(
        username=username,
        full_name=full_name,
        phone_number=phone_number,
        password=generate_password_hash(password)
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'user': {
        'id':          str(new_user.id),
        'username':    new_user.username,
        'fullName':    new_user.full_name,
        'phoneNumber': new_user.phone_number,
    }}), 201


# ── LOGIN ──────────────────────────────────────────────────
@app.route('/api/auth/login/', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({'message': 'Invalid username or password'}), 401

    return jsonify({'user': {
        'id':          str(user.id),
        'username':    user.username,
        'fullName':    user.full_name,
        'phoneNumber': user.phone_number,
    }}), 200


# ── DELETE USER ────────────────────────────────────────────
@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    username = user.username
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': f'User {username} deleted successfully'}), 200


# ── JSON API ───────────────────────────────────────────────
@app.route('/api/users', methods=['GET'])
def api_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({
        'total': len(users),
        'users': [{
            'id':          u.id,
            'username':    u.username,
            'fullName':    u.full_name,
            'phoneNumber': u.phone_number,
            'createdAt':   u.created_at.strftime('%d %b %Y, %H:%M')
        } for u in users]
    })

@app.route('/privacy')
def privacy():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Privacy Policy — LetsGo Cayman</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0f1e;
    --surface: #111827;
    --surface2: #1a2235;
    --accent: #00d4aa;
    --accent2: #0099ff;
    --cayman-blue: #0e7fd4;
    --text: #e8edf5;
    --text-muted: #8fa0b8;
    --border: rgba(0, 212, 170, 0.15);
    --gradient: linear-gradient(135deg, #00d4aa 0%, #0099ff 100%);
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    font-weight: 300;
    line-height: 1.8;
    font-size: 16px;
  }

  /* Top bar */
  .topbar {
    background: rgba(10, 15, 30, 0.95);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    padding: 18px 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .logo {
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 20px;
    background: var(--gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .back-link {
    color: var(--accent);
    text-decoration: none;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: 0.05em;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: opacity 0.2s;
  }
  .back-link:hover { opacity: 0.7; }

  /* Hero */
  .hero {
    padding: 80px 40px 60px;
    max-width: 900px;
    margin: 0 auto;
    position: relative;
  }

  .hero::before {
    content: '';
    position: absolute;
    top: 0; left: -20%;
    width: 600px; height: 400px;
    background: radial-gradient(ellipse, rgba(0, 212, 170, 0.08) 0%, transparent 70%);
    pointer-events: none;
  }

  .hero-tag {
    display: inline-block;
    background: rgba(0, 212, 170, 0.1);
    border: 1px solid var(--accent);
    color: var(--accent);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    padding: 6px 14px;
    border-radius: 2px;
    margin-bottom: 28px;
  }

  h1 {
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: clamp(36px, 6vw, 60px);
    line-height: 1.08;
    letter-spacing: -0.02em;
    margin-bottom: 24px;
  }

  h1 span {
    background: var(--gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .hero-meta {
    display: flex;
    gap: 32px;
    flex-wrap: wrap;
    margin-top: 32px;
    padding-top: 32px;
    border-top: 1px solid var(--border);
  }

  .meta-item {
    font-size: 13px;
    color: var(--text-muted);
    letter-spacing: 0.03em;
  }

  .meta-item strong {
    color: var(--text);
    font-weight: 500;
    display: block;
    margin-bottom: 2px;
  }

  /* Main layout */
  .container {
    max-width: 900px;
    margin: 0 auto;
    padding: 0 40px 100px;
  }

  /* Quick nav */
  .quick-nav {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 28px 32px;
    margin-bottom: 60px;
  }

  .quick-nav-title {
    font-family: 'Syne', sans-serif;
    font-size: 11px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--accent);
    font-weight: 700;
    margin-bottom: 16px;
  }

  .quick-nav ol {
    list-style: none;
    columns: 2;
    gap: 12px;
  }

  .quick-nav ol li {
    margin-bottom: 8px;
    font-size: 14px;
    counter-increment: nav-counter;
  }

  .quick-nav ol li::before {
    content: counter(nav-counter, decimal-leading-zero) " ";
    color: var(--accent);
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 11px;
    margin-right: 6px;
  }

  .quick-nav a {
    color: var(--text-muted);
    text-decoration: none;
    transition: color 0.2s;
  }

  .quick-nav a:hover { color: var(--accent); }

  /* Sections */
  section {
    margin-bottom: 60px;
    padding-top: 20px;
    border-top: 1px solid var(--border);
  }

  .section-number {
    font-family: 'Syne', sans-serif;
    font-size: 11px;
    letter-spacing: 0.15em;
    color: var(--accent);
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: 10px;
    display: block;
  }

  h2 {
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 26px;
    letter-spacing: -0.01em;
    margin-bottom: 20px;
    color: var(--text);
  }

  h3 {
    font-family: 'Syne', sans-serif;
    font-weight: 600;
    font-size: 17px;
    margin-top: 32px;
    margin-bottom: 12px;
    color: var(--text);
    display: flex;
    align-items: center;
    gap: 10px;
  }

  h3::before {
    content: '';
    display: inline-block;
    width: 18px;
    height: 2px;
    background: var(--gradient);
    flex-shrink: 0;
  }

  p {
    color: var(--text-muted);
    margin-bottom: 16px;
    font-size: 15.5px;
  }

  p strong {
    color: var(--text);
    font-weight: 500;
  }

  /* Data table */
  .data-table {
    width: 100%;
    border-collapse: collapse;
    margin: 24px 0;
    font-size: 14px;
  }

  .data-table th {
    text-align: left;
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--accent);
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
  }

  .data-table td {
    padding: 14px 16px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    color: var(--text-muted);
    vertical-align: top;
  }

  .data-table tr:last-child td { border-bottom: none; }
  .data-table tr:hover td { background: rgba(0, 212, 170, 0.03); }

  .data-table td:first-child {
    color: var(--text);
    font-weight: 500;
    white-space: nowrap;
  }

  /* Pill tags */
  .pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 2px;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.04em;
  }

  .pill-green { background: rgba(0, 212, 170, 0.1); color: var(--accent); }
  .pill-blue { background: rgba(0, 153, 255, 0.1); color: var(--accent2); }
  .pill-orange { background: rgba(255, 160, 0, 0.1); color: #ffa000; }

  /* Callout boxes */
  .callout {
    border-left: 3px solid var(--accent);
    background: rgba(0, 212, 170, 0.05);
    padding: 20px 24px;
    margin: 24px 0;
    border-radius: 0 4px 4px 0;
  }

  .callout-warning {
    border-left-color: #ffa000;
    background: rgba(255, 160, 0, 0.05);
  }

  .callout p { margin: 0; font-size: 14.5px; }
  .callout strong { color: var(--accent); }
  .callout-warning strong { color: #ffa000; }

  /* List styling */
  ul {
    list-style: none;
    margin: 12px 0 20px;
  }

  ul li {
    color: var(--text-muted);
    font-size: 15px;
    padding: 6px 0 6px 20px;
    position: relative;
  }

  ul li::before {
    content: '→';
    position: absolute;
    left: 0;
    color: var(--accent);
    font-size: 12px;
  }

  /* Contact section */
  .contact-card {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 36px;
    margin-top: 24px;
  }

  .contact-card a {
    color: var(--accent);
    text-decoration: none;
  }

  .contact-card a:hover { text-decoration: underline; }

  /* Footer */
  footer {
    border-top: 1px solid var(--border);
    padding: 32px 40px;
    text-align: center;
    font-size: 13px;
    color: var(--text-muted);
    max-width: 900px;
    margin: 0 auto;
  }

  footer strong {
    background: var(--gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  @media (max-width: 600px) {
    .topbar { padding: 16px 20px; }
    .hero { padding: 50px 20px 40px; }
    .container { padding: 0 20px 80px; }
    .quick-nav ol { columns: 1; }
    footer { padding: 24px 20px; }
    .data-table { font-size: 13px; }
    .data-table th, .data-table td { padding: 10px 10px; }
  }
</style>
</head>
<body>

<nav class="topbar">
  <div class="logo">LetsGo</div>
  <a href="https://www.letsgocayman.com" class="back-link">← letsgocayman.com</a>
</nav>

<header class="hero">
  <div class="hero-tag">Legal · Privacy</div>
  <h1>Privacy<br><span>Policy</span></h1>
  <p style="color:var(--text-muted); font-size:17px; max-width:600px;">We believe transparency is the foundation of trust. Here's exactly how LetsGo Cayman collects, uses, and protects your personal data.</p>
  <div class="hero-meta">
    <div class="meta-item">
      <strong>Effective Date</strong>
      April 16, 2026
    </div>
    <div class="meta-item">
      <strong>Last Updated</strong>
      April 16, 2026
    </div>
    <div class="meta-item">
      <strong>Jurisdiction</strong>
      Cayman Islands
    </div>
    <div class="meta-item">
      <strong>App Platforms</strong>
      iOS · Android
    </div>
  </div>
</header>

<main class="container">

  <div class="quick-nav">
    <div class="quick-nav-title">Table of Contents</div>
    <ol>
      <li><a href="#overview">Overview & Scope</a></li>
      <li><a href="#data-collected">Data We Collect</a></li>
      <li><a href="#how-used">How We Use Your Data</a></li>
      <li><a href="#sharing">Data Sharing & Disclosure</a></li>
      <li><a href="#location">Location Data</a></li>
      <li><a href="#payments">Payment Data</a></li>
      <li><a href="#sos">SOS & Emergency Features</a></li>
      <li><a href="#retention">Data Retention</a></li>
      <li><a href="#security">Security</a></li>
      <li><a href="#children">Children's Privacy</a></li>
      <li><a href="#rights">Your Rights & Choices</a></li>
      <li><a href="#contact">Contact Us</a></li>
    </ol>
  </div>

  <!-- 1. Overview -->
  <section id="overview">
    <span class="section-number">01 — Overview</span>
    <h2>Overview &amp; Scope</h2>
    <p>This Privacy Policy applies to <strong>LetsGo Cayman</strong> ("LetsGo," "we," "our," or "us"), operated by the LetsGo Cayman team based in the Cayman Islands. It governs how we collect, use, store, and share information through our mobile applications (iOS and Android), our website at <a href="https://www.letsgocayman.com" style="color:var(--accent);">letsgocayman.com</a>, and any related services (collectively, the "Service").</p>
    <p>By downloading or using the LetsGo app, you agree to the practices described in this Policy. If you do not agree, please do not use the Service.</p>
    <div class="callout">
      <p><strong>Our commitment:</strong> We collect only the data necessary to operate, improve, and keep your transit experience safe. We never sell your personal data to third parties.</p>
    </div>
  </section>

  <!-- 2. Data Collected -->
  <section id="data-collected">
    <span class="section-number">02 — Data Collected</span>
    <h2>Data We Collect</h2>
    <p>The following table summarises what we collect, why, and on what legal basis:</p>

    <table class="data-table">
      <thead>
        <tr>
          <th>Data Type</th>
          <th>What It Includes</th>
          <th>Purpose</th>
          <th>Basis</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Account Information</td>
          <td>Name, email address, phone number</td>
          <td>Account creation, notifications, receipts</td>
          <td><span class="pill pill-green">Contract</span></td>
        </tr>
        <tr>
          <td>Location Data</td>
          <td>GPS coordinates (real-time and trip history)</td>
          <td>Live bus tracking, route planning, SOS dispatch</td>
          <td><span class="pill pill-green">Contract</span> <span class="pill pill-blue">Consent</span></td>
        </tr>
        <tr>
          <td>Payment Data</td>
          <td>NFC tap events, transaction history, wallet balance; card details processed by our payment provider</td>
          <td>Fare payment, pass management</td>
          <td><span class="pill pill-green">Contract</span></td>
        </tr>
        <tr>
          <td>Emergency Contacts</td>
          <td>Names and phone numbers you voluntarily add</td>
          <td>SOS alerts, live journey sharing</td>
          <td><span class="pill pill-blue">Consent</span></td>
        </tr>
        <tr>
          <td>Community Reports</td>
          <td>Stop condition reports, overcrowding flags, delay notifications</td>
          <td>Network quality improvement</td>
          <td><span class="pill pill-blue">Consent</span></td>
        </tr>
        <tr>
          <td>Device &amp; Usage Data</td>
          <td>Device model, OS version, app version, crash logs, feature interactions</td>
          <td>Performance monitoring, bug fixes</td>
          <td><span class="pill pill-orange">Legitimate Interest</span></td>
        </tr>
        <tr>
          <td>SMS Data (Offline Mode)</td>
          <td>Automated SMS messages for bus tracking when no internet is available</td>
          <td>Offline GPS tracking continuity</td>
          <td><span class="pill pill-blue">Consent</span></td>
        </tr>
      </tbody>
    </table>

    <h3>Data You Provide Directly</h3>
    <p>When you register for an account, make a payment, add emergency contacts, or submit a community report, you provide data directly to us.</p>

    <h3>Data Collected Automatically</h3>
    <p>When you use the app, we automatically collect device identifiers, app usage analytics, crash reports, and — with your permission — location data.</p>
  </section>

  <!-- 3. How We Use -->
  <section id="how-used">
    <span class="section-number">03 — Use of Data</span>
    <h2>How We Use Your Data</h2>
    <p>We use the information we collect to:</p>
    <ul>
      <li>Operate the LetsGo app and provide real-time bus tracking on all 9 Grand Cayman routes</li>
      <li>Process NFC tap payments and manage your in-app wallet and monthly passes</li>
      <li>Send you fare receipts, service alerts, and account notifications</li>
      <li>Enable the SOS feature — instantly sharing your GPS location with emergency contacts and 911</li>
      <li>Power offline SMS tracking when you lose internet connectivity on coastal and remote roads</li>
      <li>Analyse aggregated community reports to improve route reliability and stop conditions</li>
      <li>Diagnose crashes and bugs, and improve app performance</li>
      <li>Comply with applicable Cayman Islands laws and regulations</li>
    </ul>
    <p>We use <strong>AI and machine learning</strong> models to predict bus arrival times and optimise route scheduling. These models process aggregated, de-identified location data — not individual profiles.</p>
  </section>

  <!-- 4. Sharing -->
  <section id="sharing">
    <span class="section-number">04 — Sharing</span>
    <h2>Data Sharing &amp; Disclosure</h2>
    <p>We do not sell, rent, or trade your personal data. We share information only in the following limited circumstances:</p>

    <h3>Service Providers</h3>
    <p>We work with third-party vendors who help us operate the Service — including cloud hosting, payment processing, analytics, and push notification services. These providers are contractually bound to use your data only to perform services on our behalf and to maintain appropriate security standards.</p>

    <h3>Emergency Services</h3>
    <p>When you activate the SOS feature, your real-time GPS location is shared with the emergency contacts you have designated and, where integrated, with 911 dispatch. This sharing is initiated by you and is essential to the safety feature's function.</p>

    <h3>Journey Sharing</h3>
    <p>If you use the "Live Share" feature, your real-time journey data is shared with individuals you explicitly choose to share it with. You can revoke this at any time within the app.</p>

    <h3>Legal Obligations</h3>
    <p>We may disclose your information if required to do so by law, court order, or governmental authority in the Cayman Islands or another applicable jurisdiction, or to protect the rights, safety, or property of LetsGo, our users, or the public.</p>

    <h3>Business Transfers</h3>
    <p>If LetsGo is acquired, merged, or its assets transferred, user data may be part of the transferred assets. We will notify you of any such change and your choices regarding your data.</p>
  </section>

  <!-- 5. Location -->
  <section id="location">
    <span class="section-number">05 — Location</span>
    <h2>Location Data</h2>
    <p>Location is central to how LetsGo works. Here's exactly how we handle it:</p>

    <h3>Foreground Location</h3>
    <p>When the app is open, we collect your GPS coordinates to show nearby buses, provide live ETAs, and display your position on the route map. This requires your explicit permission, which your device's operating system will request on first use.</p>

    <h3>Background Location</h3>
    <p>If you enable Live Share or SOS tracking, the app may collect location data while running in the background. You will be clearly informed when background location is active. You can disable this at any time in your device settings.</p>

    <h3>Offline SMS Tracking</h3>
    <p>When internet connectivity is unavailable, our AI-powered system may switch to offline SMS-based tracking. This transmits your approximate location via SMS to maintain service continuity. SMS-based tracking requires your consent and can be disabled in app settings.</p>

    <h3>Retention of Location Data</h3>
    <p>Trip location history is retained for <strong>90 days</strong> to enable journey history features. After 90 days, trip data is aggregated and anonymised for network analytics. Raw GPS logs are not retained beyond this period.</p>
  </section>

  <!-- 6. Payments -->
  <section id="payments">
    <span class="section-number">06 — Payments</span>
    <h2>Payment Data</h2>
    <p>LetsGo processes payments through a <strong>PCI-DSS compliant payment processor</strong>. When you tap your phone at an NFC reader on a bus or load your wallet:</p>
    <ul>
      <li>Full card numbers are never stored on LetsGo servers or on your device by LetsGo</li>
      <li>We store a tokenised reference provided by our payment processor</li>
      <li>Transaction records (amount, date, route, fare type) are retained for 7 years to comply with financial record-keeping requirements</li>
      <li>Wallet balance and pass status are stored in our system to enable offline payment functionality</li>
    </ul>
    <div class="callout">
      <p><strong>Offline payments:</strong> To support payments without internet connectivity, a cryptographically signed token representing your wallet balance is stored locally on your device. This token does not contain your card details.</p>
    </div>
  </section>

  <!-- 7. SOS -->
  <section id="sos">
    <span class="section-number">07 — SOS &amp; Safety</span>
    <h2>SOS &amp; Emergency Features</h2>
    <p>Your safety is our highest priority. The SOS feature works as follows:</p>
    <ul>
      <li>When you press SOS, your <strong>exact GPS coordinates</strong> are immediately sent to all emergency contacts you have saved in the app</li>
      <li>A direct link to call <strong>911</strong> is surfaced instantly</li>
      <li>Your location continues to update every 30 seconds until you manually end the SOS session or an emergency contact dismisses it</li>
      <li>SOS events are logged in our system for <strong>30 days</strong> to help us investigate any safety incidents at your request</li>
    </ul>
    <div class="callout callout-warning">
      <p><strong>Important:</strong> Emergency contacts you add have no access to your location data outside of an active SOS or Live Share session. Adding a contact to the app does not share your location with them automatically.</p>
    </div>
    <p>Emergency contact names and phone numbers are stored on our servers solely to enable the SOS and Live Share features. You may remove any contact at any time in app settings, which will immediately delete their information from our servers.</p>
  </section>

  <!-- 8. Retention -->
  <section id="retention">
    <span class="section-number">08 — Retention</span>
    <h2>Data Retention</h2>
    <table class="data-table">
      <thead>
        <tr>
          <th>Data Category</th>
          <th>Retention Period</th>
          <th>Reason</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Account data</td>
          <td>Until account deletion + 30 days</td>
          <td>Account recovery grace period</td>
        </tr>
        <tr>
          <td>Raw GPS trip logs</td>
          <td>90 days</td>
          <td>Journey history feature</td>
        </tr>
        <tr>
          <td>Aggregated location analytics</td>
          <td>Indefinitely (anonymised)</td>
          <td>Network improvement</td>
        </tr>
        <tr>
          <td>Payment transaction records</td>
          <td>7 years</td>
          <td>Financial compliance</td>
        </tr>
        <tr>
          <td>Emergency contacts</td>
          <td>Until deleted by user</td>
          <td>SOS functionality</td>
        </tr>
        <tr>
          <td>SOS event logs</td>
          <td>30 days</td>
          <td>Safety incident review</td>
        </tr>
        <tr>
          <td>Community reports</td>
          <td>12 months (anonymised after 30 days)</td>
          <td>Network analytics</td>
        </tr>
        <tr>
          <td>Crash &amp; error logs</td>
          <td>90 days</td>
          <td>Bug resolution</td>
        </tr>
      </tbody>
    </table>
    <p>After the applicable retention period, data is securely deleted or irreversibly anonymised.</p>
  </section>

  <!-- 9. Security -->
  <section id="security">
    <span class="section-number">09 — Security</span>
    <h2>Security</h2>
    <p>We take reasonable and industry-standard technical and organisational measures to protect your data, including:</p>
    <ul>
      <li>Encryption of data in transit using TLS 1.2 or higher</li>
      <li>Encryption of sensitive data at rest (including payment tokens and location logs)</li>
      <li>Access controls limiting data access to authorised personnel only</li>
      <li>Regular security reviews of our systems and third-party providers</li>
      <li>Cryptographically signed offline wallet tokens to prevent fraud</li>
    </ul>
    <p>No system is perfectly secure. If you suspect unauthorised access to your account, please contact us immediately at <a href="mailto:privacy@letsgocayman.com" style="color:var(--accent);">privacy@letsgocayman.com</a> and change your password.</p>
    <p>In the event of a data breach that materially affects your personal information, we will notify affected users in accordance with applicable law.</p>
  </section>

  <!-- 10. Children -->
  <section id="children">
    <span class="section-number">10 — Children</span>
    <h2>Children's Privacy</h2>
    <div class="callout callout-warning">
      <p><strong>Ages 13 and under:</strong> The LetsGo app is not directed at children under the age of 13. We do not knowingly collect personal information from children under 13. If you are a parent or guardian and believe your child has provided us with personal information, please contact us immediately at <a href="mailto:privacy@letsgocayman.com" style="color:#ffa000;">privacy@letsgocayman.com</a> and we will delete that information promptly.</p>
    </div>
    <p>Users between the ages of <strong>13 and 17</strong> may use the Service with the knowledge and consent of a parent or guardian. The Live Share and SOS features are recommended for all young riders as a safety tool.</p>
    <p>If we become aware that we have collected personal data from a child under 13 without verifiable parental consent, we will take steps to delete that information from our servers as quickly as possible.</p>
  </section>

  <!-- 11. Rights -->
  <section id="rights">
    <span class="section-number">11 — Your Rights</span>
    <h2>Your Rights &amp; Choices</h2>
    <p>Depending on your location, you may have the following rights with respect to your personal data:</p>

    <h3>Access</h3>
    <p>You may request a copy of the personal data we hold about you. We will respond within 30 days.</p>

    <h3>Correction</h3>
    <p>You may correct inaccurate personal data through the app's account settings or by contacting us directly.</p>

    <h3>Deletion</h3>
    <p>You may request deletion of your account and associated personal data. Note that some data may be retained for the periods specified above due to legal or financial obligations (e.g., payment transaction records).</p>

    <h3>Portability</h3>
    <p>You may request an export of your personal data in a common machine-readable format.</p>

    <h3>Withdraw Consent</h3>
    <p>Where processing is based on your consent (e.g., background location, Live Share), you may withdraw consent at any time through app settings or your device's permission controls without affecting the lawfulness of prior processing.</p>

    <h3>Location Permissions</h3>
    <p>You can modify location permissions at any time in your device settings (iOS: Settings → LetsGo; Android: Settings → Apps → LetsGo → Permissions). Disabling location will affect real-time tracking features.</p>

    <h3>Push Notifications</h3>
    <p>You can opt out of push notifications in your device settings or within the app's notification preferences.</p>

    <p>To exercise any of your rights, contact us at <a href="mailto:privacy@letsgocayman.com" style="color:var(--accent);">privacy@letsgocayman.com</a>. We will respond within 30 days and may need to verify your identity before fulfilling a request.</p>
  </section>

  <!-- 12. Contact -->
  <section id="contact">
    <span class="section-number">12 — Contact</span>
    <h2>Contact Us</h2>
    <p>If you have any questions, concerns, or requests regarding this Privacy Policy or the way we handle your data, please reach out:</p>
    <div class="contact-card">
      <p><strong>LetsGo Cayman — Privacy Team</strong></p>
      <p style="margin-top:16px;">📧 <a href="mailto:privacy@letsgocayman.com">privacy@letsgocayman.com</a></p>
      <p>🌐 <a href="https://www.letsgocayman.com">www.letsgocayman.com</a></p>
      <p>📍 Grand Cayman, Cayman Islands</p>
      <p style="margin-top:20px; font-size:14px; color:var(--text-muted);">We aim to respond to all privacy-related enquiries within <strong style="color:var(--text);">5 business days</strong>. For urgent safety concerns, please use the in-app SOS feature or call 911 directly.</p>
    </div>

    <h3>Changes to This Policy</h3>
    <p>We may update this Privacy Policy from time to time. When we make material changes, we will notify you via a push notification or a prominent notice in the app at least <strong>14 days</strong> before the changes take effect. Continued use of the Service after the effective date constitutes acceptance of the updated policy.</p>
    <p>The version history is maintained at <a href="https://www.letsgocayman.com/privacy" style="color:var(--accent);">letsgocayman.com/privacy</a>.</p>
  </section>

</main>

<footer>
  <p>© 2026 <strong>LetsGo Cayman</strong> · All rights reserved · <a href="https://www.letsgocayman.com" style="color:var(--accent); text-decoration:none;">letsgocayman.com</a></p>
  <p style="margin-top:8px; font-size:12px;">This document is published in satisfaction of Google Play Store and Apple App Store privacy policy requirements.</p>
</footer>

</body>
</html>"""


# ── WEBPAGE ────────────────────────────────────────────────
@app.route('/users')
def show_users():
    users = User.query.order_by(User.created_at.desc()).all()

    rows = ""
    for user in users:
        initials = ''.join([n[0].upper() for n in user.full_name.split()[:2]])
        joined   = user.created_at.strftime('%d %b %Y, %H:%M')
        rows += f"""
        <tr id="row-{user.id}">
          <td><div class="avatar">{initials}</div></td>
          <td><strong>{user.username}</strong></td>
          <td>{user.full_name}</td>
          <td>{user.phone_number}</td>
          <td><span class="lock">🔒 hidden</span></td>
          <td class="date">{joined}</td>
          <td>
            <button class="del-btn" onclick="deleteUser({user.id}, '{user.username}')">
              Delete
            </button>
          </td>
        </tr>
        """

    if not rows:
        rows = '<tr><td colspan="7" class="empty">No users registered yet.</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Registered Users</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f0f2f5;
      padding: 30px 20px;
      color: #333;
    }}
    .header {{
      max-width: 1000px;
      margin: 0 auto 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 12px;
    }}
    .header h1 {{ font-size: 22px; font-weight: 600; }}
    .header p  {{ font-size: 13px; color: #888; margin-top: 3px; }}
    .badge {{
      background: #4f46e5; color: white;
      padding: 6px 16px; border-radius: 20px;
      font-size: 13px; font-weight: 500;
    }}
    .refresh-note {{
      max-width: 1000px; margin: 0 auto 12px;
      font-size: 12px; color: #aaa; text-align: right;
    }}
    .table-wrap {{
      max-width: 1000px; margin: 0 auto;
      background: white; border-radius: 12px;
      overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    thead {{ background: #4f46e5; color: white; }}
    th {{ padding: 14px 16px; text-align: left; font-size: 13px; font-weight: 500; }}
    td {{ padding: 12px 16px; border-bottom: 1px solid #f0f0f0; font-size: 14px; vertical-align: middle; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #fafaff; }}
    .avatar {{
      width: 36px; height: 36px; border-radius: 50%;
      background: #e0e7ff; color: #4f46e5;
      display: flex; align-items: center; justify-content: center;
      font-size: 13px; font-weight: 600;
    }}
    .lock  {{ color: #999; font-size: 12px; }}
    .date  {{ color: #aaa; font-size: 12px; }}
    .empty {{ text-align: center; padding: 50px; color: #bbb; font-size: 15px; }}
    .del-btn {{
      background: #fee2e2; color: #dc2626;
      border: 1px solid #fca5a5;
      padding: 5px 14px; border-radius: 6px;
      font-size: 12px; cursor: pointer;
      transition: background 0.2s;
    }}
    .del-btn:hover {{ background: #fecaca; }}
    .toast {{
      position: fixed; bottom: 30px; right: 30px;
      background: #1e1e2e; color: white;
      padding: 12px 20px; border-radius: 10px;
      font-size: 14px; opacity: 0;
      transition: opacity 0.3s;
      z-index: 999;
    }}
    .toast.show {{ opacity: 1; }}
    .overlay {{
      display: none; position: fixed;
      inset: 0; background: rgba(0,0,0,0.4);
      z-index: 100; align-items: center; justify-content: center;
    }}
    .overlay.show {{ display: flex; }}
    .modal {{
      background: white; border-radius: 12px;
      padding: 28px 32px; max-width: 360px;
      width: 90%; text-align: center;
      box-shadow: 0 8px 32px rgba(0,0,0,0.15);
    }}
    .modal h3 {{ font-size: 17px; margin-bottom: 8px; }}
    .modal p  {{ font-size: 14px; color: #666; margin-bottom: 22px; }}
    .modal-btns {{ display: flex; gap: 10px; justify-content: center; }}
    .btn-cancel {{
      padding: 8px 22px; border-radius: 8px;
      border: 1px solid #ddd; background: white;
      cursor: pointer; font-size: 14px;
    }}
    .btn-confirm {{
      padding: 8px 22px; border-radius: 8px;
      border: none; background: #dc2626;
      color: white; cursor: pointer; font-size: 14px;
    }}
    .btn-confirm:hover {{ background: #b91c1c; }}
  </style>
</head>
<body>

  <div class="header">
    <div>
      <h1>📋 Registered Users</h1>
      <p>Users who signed up via the Rork app</p>
    </div>
    <span class="badge" id="user-count">{len(users)} user(s)</span>
  </div>

  <div class="refresh-note">
    Auto-refreshes every 10s &nbsp;|&nbsp;
    <span id="last-updated">Last updated: just now</span>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th></th>
          <th>Username</th>
          <th>Full Name</th>
          <th>Phone Number</th>
          <th>Password</th>
          <th>Joined</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody id="user-tbody">{rows}</tbody>
    </table>
  </div>

  <div class="overlay" id="overlay">
    <div class="modal">
      <h3>Delete User</h3>
      <p id="modal-msg">Are you sure you want to delete this user?</p>
      <div class="modal-btns">
        <button class="btn-cancel" onclick="closeModal()">Cancel</button>
        <button class="btn-confirm" id="confirm-btn">Delete</button>
      </div>
    </div>
  </div>

  <div class="toast" id="toast"></div>

  <script>
    let pendingDeleteId = null;

    function deleteUser(id, username) {{
      pendingDeleteId = id;
      document.getElementById('modal-msg').textContent =
        `Are you sure you want to delete "${{username}}"? This cannot be undone.`;
      document.getElementById('overlay').classList.add('show');
    }}

    function closeModal() {{
      pendingDeleteId = null;
      document.getElementById('overlay').classList.remove('show');
    }}

    document.getElementById('confirm-btn').addEventListener('click', async () => {{
      if (!pendingDeleteId) return;
      closeModal();
      try {{
        const res = await fetch(`/api/users/${{pendingDeleteId}}`, {{ method: 'DELETE' }});
        const data = await res.json();
        if (res.ok) {{
          document.getElementById(`row-${{pendingDeleteId}}`).remove();
          showToast('✅ ' + data.message);
          refreshCount();
        }} else {{
          showToast('❌ ' + data.message);
        }}
      }} catch(e) {{
        showToast('❌ Delete failed');
      }}
      pendingDeleteId = null;
    }});

    function showToast(msg) {{
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 3000);
    }}

    function refreshCount() {{
      const rows = document.querySelectorAll('#user-tbody tr[id]').length;
      document.getElementById('user-count').textContent = rows + ' user(s)';
    }}

    async function refreshUsers() {{
      try {{
        const res  = await fetch('/api/users');
        const data = await res.json();
        const tbody = document.getElementById('user-tbody');

        if (data.users.length === 0) {{
          tbody.innerHTML = '<tr><td colspan="7" class="empty">No users registered yet.</td></tr>';
          document.getElementById('user-count').textContent = '0 user(s)';
          return;
        }}

        tbody.innerHTML = data.users.map(u => {{
          const initials = u.fullName.split(' ').map(n => n[0]).join('').toUpperCase().slice(0,2);
          return `
            <tr id="row-${{u.id}}">
              <td><div class="avatar">${{initials}}</div></td>
              <td><strong>${{u.username}}</strong></td>
              <td>${{u.fullName}}</td>
              <td>${{u.phoneNumber}}</td>
              <td><span class="lock">🔒 hidden</span></td>
              <td class="date">${{u.createdAt}}</td>
              <td>
                <button class="del-btn" onclick="deleteUser(${{u.id}}, '${{u.username}}')">
                  Delete
                </button>
              </td>
            </tr>`;
        }}).join('');

        document.getElementById('user-count').textContent = data.total + ' user(s)';
        document.getElementById('last-updated').textContent =
          'Last updated: ' + new Date().toLocaleTimeString();
      }} catch(e) {{
        console.error('Refresh failed', e);
      }}
    }}

    setInterval(refreshUsers, 10000);
  </script>
</body>
</html>"""
    return html


@app.route('/')
def home():
    return '<meta http-equiv="refresh" content="0; url=/users">'


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
