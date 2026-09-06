from flask import Flask, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import json
import secrets
import uuid
from datetime import datetime

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY', 'letsgo-cayman-secret-2026')

# ── DATABASE CONFIG (Render PostgreSQL compatible) ─────────
uri = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
if uri.startswith('postgres://'):
    uri = uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ── ADMIN CREDENTIALS (env vars with defaults) ─────────────
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'letsgo2026')

# ── TWILIO CONFIG (stored in env / overridable via admin) ──
TWILIO_CONFIG = {
    'accountSid': os.environ.get('TWILIO_ACCOUNT_SID', ''),
    'authToken': os.environ.get('TWILIO_AUTH_TOKEN', ''),
    'fromNumber': os.environ.get('TWILIO_FROM_NUMBER', ''),
}

# Runtime override (persists until restart)
_twilio_override = {}


# ═══════════════════════════════════════════════════════════
# ROBOTS / CRAWL CONTROL
# ═══════════════════════════════════════════════════════════
ROBOTS_TXT = """User-agent: *
Disallow: /admin/
Disallow: /delete-account
Disallow: /track/
Disallow: /sos/
Disallow: /driver
Disallow: /drivers
Disallow: /maps
Disallow: /api/

Allow: /
Allow: /support

Sitemap: https://www.letsgocayman.com/sitemap.xml
"""

SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.letsgocayman.com/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://www.letsgocayman.com/support</loc>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
</urlset>
"""


@app.route('/robots.txt')
def robots_txt():
    from flask import Response
    return Response(ROBOTS_TXT, mimetype='text/plain')


@app.route('/sitemap.xml')
def sitemap_xml():
    from flask import Response
    return Response(SITEMAP_XML, mimetype='application/xml')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    phone_number = db.Column(db.String(20), nullable=True, default='')
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DriverRoute(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    driver_name = db.Column(db.String(120), nullable=False)
    driver_phone = db.Column(db.String(30), nullable=False)
    username = db.Column(db.String(80), nullable=False)
    bus_id = db.Column(db.String(40), nullable=False)
    route_id = db.Column(db.String(20), nullable=False)
    route_name = db.Column(db.String(120), nullable=False)
    route_color = db.Column(db.String(10), default='#F5C518')
    frequency = db.Column(db.String(40), default='Every 15 minutes')
    description = db.Column(db.Text, default='')
    stops_json = db.Column(db.Text, default='[]')  # JSON array
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CommunityReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    stop_name = db.Column(db.String(120), nullable=False)
    route_id = db.Column(db.String(20), default='Any')
    upvotes = db.Column(db.Integer, default=0)
    upvoted_by = db.Column(db.Text, default='[]')
    status = db.Column(db.String(20), default='open')
    username = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TrackingSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(32), unique=True, nullable=False,
                      default=lambda: secrets.token_urlsafe(8))
    username = db.Column(db.String(80), nullable=False)
    phone_number = db.Column(db.String(20), default='')
    route_id = db.Column(db.String(20), default='')
    bus_id = db.Column(db.String(40), default='')
    bus_name = db.Column(db.String(120), default='')
    lat = db.Column(db.String(20), default='19.3465')
    lng = db.Column(db.String(20), default='-81.3958')
    contact_name = db.Column(db.String(80), default='')
    contact_phone = db.Column(db.String(20), default='')
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class SOSAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(32), unique=True, nullable=False,
                      default=lambda: secrets.token_urlsafe(8))
    username = db.Column(db.String(80), nullable=False)
    phone_number = db.Column(db.String(20), default='')
    route_id = db.Column(db.String(20), default='')
    bus_id = db.Column(db.String(40), default='')
    lat = db.Column(db.String(20), default='')
    lng = db.Column(db.String(20), default='')
    contacts = db.Column(db.Text, default='[]')
    resolved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class EmergencyContact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, index=True)
    contact_name = db.Column(db.String(120), nullable=False)
    phone_number = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class SMSLog(db.Model):
    """Logs every outbound SMS sent by the server for admin visibility."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), default='')  # rider who triggered it
    to_phone = db.Column(db.String(30), nullable=False)  # recipient number
    message_type = db.Column(db.String(40), default='general')  # sos / journey_share / offline / general
    route_id = db.Column(db.String(20), default='')
    bus_id = db.Column(db.String(40), default='')
    bus_name = db.Column(db.String(120), default='')
    eta_minutes = db.Column(db.Integer, default=0)
    lat = db.Column(db.String(20), default='')
    lng = db.Column(db.String(20), default='')
    track_url = db.Column(db.String(200), default='')
    body_preview = db.Column(db.String(200), default='')  # first 200 chars of message
    sent = db.Column(db.Boolean, default=False)
    twilio_detail = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DeviceRequest(db.Model):
    """Driver device connection requests."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending / contacted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()

# ═══════════════════════════════════════════════════════════
# SHARED CSS / JS HELPERS
# ═══════════════════════════════════════════════════════════

ADMIN_STYLE = """
<style>
  :root{--gold:#F5C518;--navy:#0B1F3A;--teal:#00897B;--red:#dc2626;--green:#16a34a}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0d1117;color:#e6edf3;min-height:100vh}
  a{color:var(--gold);text-decoration:none}
  a:hover{text-decoration:underline}

  .admin-nav{background:#161b22;border-bottom:1px solid #30363d;padding:0 32px;height:56px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
  .admin-nav .brand{font-size:18px;font-weight:700;color:var(--gold);display:flex;align-items:center;gap:8px}
  .admin-nav .nav-links{display:flex;gap:4px}
  .admin-nav .nav-links a{color:#8b949e;padding:6px 14px;border-radius:8px;font-size:13px;font-weight:500;transition:all .2s}
  .admin-nav .nav-links a:hover,.admin-nav .nav-links a.active{background:rgba(245,197,24,.1);color:var(--gold);text-decoration:none}
  .admin-nav .nav-links a.sos-link{color:#f87171}
  .admin-nav .nav-links a.sos-link:hover,.admin-nav .nav-links a.sos-link.active{background:rgba(239,68,68,.12);color:#ef4444}
  .admin-nav .nav-links a.sms-link{color:#818cf8}
  .admin-nav .nav-links a.sms-link:hover,.admin-nav .nav-links a.sms-link.active{background:rgba(129,140,248,.12);color:#818cf8}
  .admin-nav .logout{color:#8b949e;font-size:13px;padding:6px 14px;border-radius:8px;border:1px solid #30363d;transition:all .2s}
  .admin-nav .logout:hover{border-color:var(--red);color:var(--red);text-decoration:none}

  .admin-main{max-width:1100px;margin:0 auto;padding:32px 24px}
  .page-header{margin-bottom:28px;display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:12px}
  .page-header h1{font-size:24px;font-weight:700;color:#f0f6fc}
  .page-header p{font-size:14px;color:#8b949e;margin-top:4px}
  .badge{display:inline-flex;align-items:center;background:rgba(245,197,24,.12);border:1px solid rgba(245,197,24,.3);color:var(--gold);padding:5px 14px;border-radius:20px;font-size:13px;font-weight:600}

  .card{background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;margin-bottom:24px}
  .card-header{padding:16px 20px;border-bottom:1px solid #30363d;display:flex;align-items:center;justify-content:space-between}
  .card-header h2{font-size:15px;font-weight:600;color:#f0f6fc}
  .card-body{padding:20px}

  .table-wrap{overflow-x:auto}
  table{width:100%;border-collapse:collapse}
  thead tr{background:#0d1117}
  th{padding:11px 14px;text-align:left;font-size:12px;font-weight:600;color:#8b949e;letter-spacing:.5px;text-transform:uppercase;white-space:nowrap}
  td{padding:12px 14px;border-top:1px solid #21262d;font-size:14px;vertical-align:middle}
  tr:hover td{background:rgba(255,255,255,.02)}
  .avatar{width:34px;height:34px;border-radius:50%;background:rgba(245,197,24,.15);color:var(--gold);display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0}
  .lock{color:#484f58;font-size:12px}
  .date-cell{color:#6e7681;font-size:12px;white-space:nowrap}
  .empty-row td{text-align:center;padding:48px;color:#484f58;font-size:14px}

  .status{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600}
  .status.open{background:rgba(220,38,38,.12);color:#f87171}
  .status.in_progress{background:rgba(234,88,12,.12);color:#fb923c}
  .status.resolved{background:rgba(22,163,74,.12);color:#4ade80}

  .btn{display:inline-flex;align-items:center;gap:6px;padding:7px 16px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none;transition:all .2s}
  .btn-primary{background:var(--gold);color:#0d1117}
  .btn-primary:hover{background:#e8b400}
  .btn-danger{background:rgba(220,38,38,.12);color:#f87171;border:1px solid rgba(220,38,38,.2)}
  .btn-danger:hover{background:rgba(220,38,38,.2)}
  .btn-success{background:rgba(22,163,74,.12);color:#4ade80;border:1px solid rgba(22,163,74,.2)}
  .btn-success:hover{background:rgba(22,163,74,.22)}
  .btn-ghost{background:transparent;color:#8b949e;border:1px solid #30363d}
  .btn-ghost:hover{border-color:#8b949e;color:#e6edf3}

  .form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
  .form-group{display:flex;flex-direction:column;gap:6px}
  .form-group label{font-size:12px;font-weight:600;color:#8b949e;text-transform:uppercase;letter-spacing:.5px}
  .form-group input,.form-group select,.form-group textarea{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:10px 12px;font-size:14px;color:#e6edf3;outline:none;transition:border-color .2s;font-family:inherit}
  .form-group input:focus,.form-group select:focus,.form-group textarea:focus{border-color:var(--gold)}
  .form-group textarea{resize:vertical;min-height:80px}
  .form-group select option{background:#0d1117}

  .overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:200;align-items:center;justify-content:center}
  .overlay.show{display:flex}
  .modal{background:#161b22;border:1px solid #30363d;border-radius:16px;padding:28px;max-width:420px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,.5)}
  .modal h3{font-size:17px;font-weight:700;color:#f0f6fc;margin-bottom:8px}
  .modal p{font-size:14px;color:#8b949e;margin-bottom:22px;line-height:1.5}
  .modal-btns{display:flex;gap:10px;justify-content:flex-end}

  .toast{position:fixed;bottom:24px;right:24px;background:#161b22;border:1px solid #30363d;color:#e6edf3;padding:12px 20px;border-radius:10px;font-size:14px;opacity:0;transform:translateY(16px);transition:all .3s;z-index:300;max-width:360px}
  .toast.show{opacity:1;transform:translateY(0)}
  .toast.success{border-color:rgba(22,163,74,.5);color:#4ade80}
  .toast.error{border-color:rgba(220,38,38,.5);color:#f87171}

  .settings-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
  @media(max-width:700px){.form-row,.settings-grid{grid-template-columns:1fr}.admin-nav .nav-links{display:none}}

  .refresh-bar{font-size:12px;color:#484f58;text-align:right;margin-bottom:8px}

  @keyframes blink_{0%,100%{opacity:1}50%{opacity:.15}}
  @keyframes sosPulse{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.4)}50%{box-shadow:0 0 0 8px rgba(239,68,68,0)}}
</style>
"""

ADMIN_JS = """
<script>
function showToast(msg, type='success'){
  const t=document.getElementById('toast');
  t.textContent=msg; t.className='toast '+type+' show';
  setTimeout(()=>t.className='toast',3000);
}
function closeModal(id){ document.getElementById(id).classList.remove('show'); }
function openModal(id){ document.getElementById(id).classList.add('show'); }
</script>
"""


def nav_html(active='users'):
    return f"""
    <nav class="admin-nav">
      <div class="brand">🚌 LetsGo Admin</div>
      <div class="nav-links">
        <a href="/users" class="{'active' if active == 'users' else ''}">Users</a>
        <a href="/community-reports" class="{'active' if active == 'community' else ''}">Community Reports</a>
        <a href="/admin/drivers" class="driver-link {'active' if active == 'drivers' else ''}">🚌 Drivers</a>
        <a href="/admin/sos-alerts" class="sos-link {'active' if active == 'sos' else ''}">🆘 SOS Alerts</a>
        <a href="/admin/sms-alerts" class="sms-link {'active' if active == 'sms' else ''}">💬 SMS Alerts</a>
        <a href="/admin/settings" class="{'active' if active == 'settings' else ''}">Settings</a>
        <a href="/" style="margin-left:4px">← Site</a>
      </div>
      <a href="/admin/logout" class="logout">Logout</a>
    </nav>"""


def require_admin(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect('/admin/login')
        return fn(*args, **kwargs)

    return wrapper


# ═══════════════════════════════════════════════════════════
# LANDING PAGE HTML
# ═══════════════════════════════════════════════════════════

LANDING_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LetsGo Cayman — Smart Bus Transport</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --gold:#F5C518;--gold2:#E8B400;--navy:#0B1F3A;--navy2:#0E2847;
  --teal:#00897B;--teal2:#00695C;--sand:#F9F4E8;--white:#FFFFFF;
  --text:#1A1A2E;--muted:#6B7B8D;--coral:#FF6B35;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'Outfit',sans-serif;background:var(--white);color:var(--text);overflow-x:hidden}
.cur{width:12px;height:12px;background:var(--gold);border-radius:50%;position:fixed;pointer-events:none;z-index:9999;transform:translate(-50%,-50%);transition:width .2s,height .2s;mix-blend-mode:multiply}
.cur.big{width:36px;height:36px}
nav{position:fixed;top:0;left:0;right:0;z-index:200;padding:0 60px;height:72px;display:flex;align-items:center;justify-content:space-between;transition:background .3s,box-shadow .3s}
nav.scrolled{background:rgba(11,31,58,0.97);box-shadow:0 2px 30px rgba(0,0,0,0.3)}
.nav-logo{font-family:'Playfair Display',serif;font-size:24px;font-weight:900;color:var(--gold);letter-spacing:1px;display:flex;align-items:center;gap:8px;text-decoration:none}
.nav-logo .dot{width:8px;height:8px;background:var(--gold);border-radius:50%;animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
.nav-links{display:flex;gap:32px;list-style:none}
.nav-links a{color:rgba(255,255,255,0.8);text-decoration:none;font-size:14px;font-weight:500;transition:color .2s}
.nav-links a:hover{color:var(--gold)}
.nav-dl{background:var(--gold);color:var(--navy);padding:10px 26px;border-radius:50px;font-weight:700;font-size:13px;text-decoration:none;transition:transform .2s,box-shadow .2s}
.nav-dl:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(245,197,24,.4)}
.page-nav{display:flex;position:fixed;top:72px;left:0;right:0;z-index:190;background:var(--navy);border-bottom:2px solid rgba(245,197,24,.2);justify-content:center}
.pnav-btn{background:none;border:none;color:rgba(255,255,255,.6);font-family:'Outfit',sans-serif;font-size:13px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;padding:12px 28px;cursor:pointer;transition:color .2s,border-bottom .2s;border-bottom:2px solid transparent;margin-bottom:-2px}
.pnav-btn.active,.pnav-btn:hover{color:var(--gold);border-bottom-color:var(--gold)}
.page{display:none;min-height:100vh}
.page.active{display:block}
.hero{min-height:100vh;background:var(--navy);position:relative;overflow:hidden;display:flex;align-items:center;padding:140px 60px 80px}
.flag-stripe{position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,#003F87 33%,#FFFFFF 33%,#FFFFFF 66%,#CC0001 66%)}
.stars{position:absolute;inset:0;pointer-events:none}
.star{position:absolute;width:2px;height:2px;background:rgba(255,255,255,.6);border-radius:50%;animation:twinkle var(--d,3s) ease-in-out infinite var(--delay,0s)}
@keyframes twinkle{0%,100%{opacity:.2}50%{opacity:1}}
.palm-left{position:absolute;left:0;bottom:0;pointer-events:none;opacity:.15}
.palm-right{position:absolute;right:0;bottom:0;pointer-events:none;opacity:.12}
.hero-waves{position:absolute;bottom:0;left:0;right:0;pointer-events:none}
.hero-content{position:relative;z-index:10;max-width:620px}
.hero-tag{display:inline-flex;align-items:center;gap:8px;background:rgba(245,197,24,.12);border:1px solid rgba(245,197,24,.35);color:var(--gold);font-size:11px;font-weight:700;letter-spacing:2.5px;padding:7px 16px;border-radius:50px;margin-bottom:28px;animation:fadeUp .8s ease both}
.live-dot{width:6px;height:6px;background:#4CAF50;border-radius:50%;animation:blink 1s infinite}
h1.hero-title{font-family:'Playfair Display',serif;font-size:clamp(54px,8vw,96px);font-weight:900;line-height:.95;color:var(--white);animation:fadeUp .8s .1s ease both}
h1.hero-title .gold{color:var(--gold)}
.hero-sub{font-size:17px;color:rgba(255,255,255,.6);line-height:1.75;margin-top:22px;max-width:480px;animation:fadeUp .8s .2s ease both}
.hero-cta-row{display:flex;gap:14px;margin-top:40px;flex-wrap:wrap;animation:fadeUp .8s .3s ease both}
.btn-primary{display:flex;align-items:center;gap:10px;background:var(--gold);color:var(--navy);padding:15px 30px;border-radius:50px;font-weight:700;font-size:14px;text-decoration:none;transition:transform .2s,box-shadow .2s}
.btn-primary:hover{transform:translateY(-3px);box-shadow:0 16px 48px rgba(245,197,24,.35)}
.btn-primary svg,.btn-secondary svg{width:20px;height:20px}
.btn-secondary{display:flex;align-items:center;gap:10px;background:rgba(255,255,255,.08);color:var(--white);padding:15px 30px;border-radius:50px;font-weight:600;font-size:14px;text-decoration:none;border:1.5px solid rgba(255,255,255,.2);transition:all .2s}
.btn-secondary:hover{background:rgba(245,197,24,.1);border-color:var(--gold);color:var(--gold)}
.stats-bar{display:flex;gap:48px;margin-top:60px;padding-top:40px;border-top:1px solid rgba(255,255,255,.1);animation:fadeUp .8s .4s ease both}
.stat-item .num{font-family:'Playfair Display',serif;font-size:38px;font-weight:900;color:var(--gold);line-height:1}
.stat-item .lbl{font-size:12px;color:rgba(255,255,255,.4);letter-spacing:1.5px;text-transform:uppercase;margin-top:4px}
.hero-bus-wrap{position:absolute;right:0;bottom:60px;width:560px;animation:fadeUp 1s .4s ease both}
.bus-anim{animation:busFloat 4s ease-in-out infinite}
@keyframes busFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
.wheel-spin{animation:wspin .7s linear infinite;transform-box:fill-box;transform-origin:center}
@keyframes wspin{to{transform:rotate(360deg)}}
.exhaust{position:absolute;left:-10px;bottom:72px}
.puff{position:absolute;border-radius:50%;background:rgba(255,255,255,.15);animation:puffUp 1.6s ease-out infinite}
.puff:nth-child(1){width:16px;height:16px;left:0;bottom:0}
.puff:nth-child(2){width:11px;height:11px;left:-12px;bottom:6px;animation-delay:.55s}
.puff:nth-child(3){width:7px;height:7px;left:6px;bottom:10px;animation-delay:1.1s}
@keyframes puffUp{0%{opacity:.7;transform:translate(0,0) scale(1)}100%{opacity:0;transform:translate(-35px,-40px) scale(2.8)}}
.road-strip{position:absolute;bottom:0;left:0;right:0;height:60px;background:#0d1a2e;border-top:3px solid rgba(245,197,24,.25)}
.road-mark{position:absolute;top:50%;transform:translateY(-50%);height:4px;width:70px;background:rgba(245,197,24,.35);border-radius:2px;animation:roadMark 1.4s linear infinite}
.road-mark:nth-child(2){animation-delay:-.47s}
.road-mark:nth-child(3){animation-delay:-.94s}
@keyframes roadMark{from{transform:translateY(-50%) translateX(600px)}to{transform:translateY(-50%) translateX(-200px)}}
@keyframes fadeUp{from{opacity:0;transform:translateY(32px)}to{opacity:1;transform:translateY(0)}}
.why-section{padding:100px 60px;background:var(--sand)}
.section-eyebrow{font-size:11px;font-weight:700;letter-spacing:3px;color:var(--teal);text-transform:uppercase;margin-bottom:14px}
.section-title{font-family:'Playfair Display',serif;font-size:clamp(36px,5vw,60px);font-weight:900;line-height:1.05;color:var(--navy)}
.section-title .accent{color:var(--gold2)}
.why-grid{display:grid;grid-template-columns:1fr 1fr;gap:60px;margin-top:60px;align-items:center}
.why-text p{font-size:16px;color:var(--muted);line-height:1.8;margin-bottom:18px}
.why-text p strong{color:var(--navy)}
.why-highlights{display:flex;flex-direction:column;gap:16px;margin-top:28px}
.why-hl{display:flex;align-items:center;gap:14px;padding:16px 20px;background:var(--white);border-radius:14px;border-left:4px solid var(--gold);box-shadow:0 2px 12px rgba(0,0,0,.06);transition:transform .2s}
.why-hl:hover{transform:translateX(6px)}
.why-hl-icon{font-size:22px;width:44px;height:44px;display:flex;align-items:center;justify-content:center;background:rgba(245,197,24,.12);border-radius:10px;flex-shrink:0}
.why-hl-text{font-size:14px;font-weight:600;color:var(--navy)}
.why-hl-sub{font-size:12px;color:var(--muted);margin-top:2px}
.cayman-visual{background:var(--navy);border-radius:24px;padding:40px;min-height:360px;display:flex;align-items:center;justify-content:center}
.cayman-map-svg{width:100%;max-width:360px}
.route-dot{animation:routePulse 2s ease-in-out infinite}
.route-dot:nth-child(2){animation-delay:.4s}.route-dot:nth-child(3){animation-delay:.8s}.route-dot:nth-child(4){animation-delay:1.2s}
@keyframes routePulse{0%,100%{r:5}50%{r:8}}
.features-section{padding:100px 60px;background:var(--white)}
.features-intro{max-width:600px;margin-bottom:64px}
.features-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:24px}
.feat-card{background:var(--sand);border-radius:20px;padding:40px;position:relative;overflow:hidden;transition:transform .3s,box-shadow .3s;border:1.5px solid transparent}
.feat-card::after{content:'';position:absolute;inset:0;border-radius:20px;border:1.5px solid var(--gold);opacity:0;transition:opacity .3s}
.feat-card:hover{transform:translateY(-6px);box-shadow:0 20px 60px rgba(11,31,58,.12)}
.feat-card:hover::after{opacity:1}
.feat-card:hover .feat-icon-wrap{transform:scale(1.1) rotate(-5deg)}
.feat-card.featured{background:var(--navy);grid-column:span 2}
.feat-card.featured .feat-title,.feat-card.featured .feat-num{color:var(--white)}
.feat-card.featured .feat-desc{color:rgba(255,255,255,.6)}
.feat-card.featured .feat-num{color:rgba(245,197,24,.3)}
.feat-num{font-size:11px;letter-spacing:3px;color:rgba(11,31,58,.2);margin-bottom:20px}
.feat-icon-wrap{width:56px;height:56px;border-radius:16px;background:rgba(245,197,24,.15);display:flex;align-items:center;justify-content:center;font-size:26px;margin-bottom:20px;transition:transform .3s}
.feat-title{font-family:'Playfair Display',serif;font-size:22px;font-weight:700;color:var(--navy);margin-bottom:10px}
.feat-desc{font-size:14px;color:var(--muted);line-height:1.75}
.feat-pill{display:inline-block;margin-top:18px;background:rgba(245,197,24,.15);color:var(--gold2);font-size:10px;font-weight:700;letter-spacing:2px;padding:5px 14px;border-radius:50px}
.feat-card.featured .feat-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:32px;margin-top:16px}
.feat-stat .fs-num{font-family:'Playfair Display',serif;font-size:32px;color:var(--gold);font-weight:900}
.feat-stat .fs-lbl{font-size:12px;color:rgba(255,255,255,.4);margin-top:4px}
.how-section{padding:100px 60px;background:var(--navy)}
.how-section .section-title{color:var(--white)}
.how-section .section-title .accent{color:var(--gold)}
.how-section .section-eyebrow{color:var(--gold);opacity:.7}
.steps-row{display:grid;grid-template-columns:repeat(4,1fr);gap:2px;margin-top:60px;position:relative}
.steps-row::before{content:'';position:absolute;top:36px;left:12.5%;right:12.5%;height:2px;background:rgba(245,197,24,.2)}
.step-card{background:rgba(255,255,255,.04);padding:32px 24px;text-align:center;transition:background .3s}
.step-card:first-child{border-radius:16px 0 0 16px}
.step-card:last-child{border-radius:0 16px 16px 0}
.step-card:hover{background:rgba(245,197,24,.08)}
.step-num{width:52px;height:52px;background:var(--gold);color:var(--navy);border-radius:50%;display:flex;align-items:center;justify-content:center;font-family:'Playfair Display',serif;font-size:20px;font-weight:900;margin:0 auto 20px;position:relative;z-index:1}
.step-title{font-size:15px;font-weight:700;color:var(--white);margin-bottom:8px}
.step-desc{font-size:13px;color:rgba(255,255,255,.45);line-height:1.6}
.dl-section{padding:100px 60px;background:var(--gold);position:relative;overflow:hidden;text-align:center}
.dl-section::before{content:'LETSGO';font-family:'Playfair Display',serif;font-size:240px;font-weight:900;color:rgba(11,31,58,.06);position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);white-space:nowrap;pointer-events:none;letter-spacing:8px}
.dl-title{font-family:'Playfair Display',serif;font-size:clamp(44px,7vw,88px);font-weight:900;color:var(--navy);line-height:.95;margin-bottom:16px}
.dl-sub{font-size:17px;color:rgba(11,31,58,.6);max-width:400px;margin:0 auto 48px;line-height:1.65}
.dl-btns{display:flex;justify-content:center;gap:16px;flex-wrap:wrap}
.dl-app-btn{display:flex;align-items:center;gap:14px;background:var(--navy);color:var(--white);padding:16px 32px;border-radius:16px;text-decoration:none;transition:transform .2s,box-shadow .2s}
.dl-app-btn:hover{transform:translateY(-4px);box-shadow:0 20px 48px rgba(11,31,58,.3)}
.dl-app-btn svg{width:26px;height:26px;flex-shrink:0}
.dl-app-btn .dl-t small{display:block;font-size:10px;opacity:.5;letter-spacing:1px;text-transform:uppercase}
.dl-app-btn .dl-t strong{display:block;font-size:17px;font-weight:700}
.team-hero{background:var(--navy);padding:160px 60px 100px;text-align:center;position:relative;overflow:hidden}
.team-hero .section-title{color:var(--white);max-width:700px;margin:12px auto 0}
.team-hero .section-title .accent{color:var(--gold)}
.team-hero-sub{font-size:17px;color:rgba(255,255,255,.5);max-width:500px;margin:20px auto 0;line-height:1.7}
.team-main{padding:80px 60px;background:var(--sand)}
.team-intro{max-width:680px;margin:0 auto 70px;text-align:center}
.team-intro p{font-size:16px;color:var(--muted);line-height:1.8}
.team-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:32px;max-width:860px;margin:0 auto}
.team-card{background:var(--white);border-radius:24px;overflow:hidden;box-shadow:0 4px 24px rgba(11,31,58,.08);transition:transform .3s,box-shadow .3s;border:1.5px solid transparent}
.team-card:hover{transform:translateY(-8px);box-shadow:0 24px 60px rgba(11,31,58,.15);border-color:var(--gold)}
.team-card-header{height:180px;display:flex;align-items:flex-end;padding:24px;overflow:hidden}
.bg1{background:linear-gradient(135deg,var(--navy) 0%,#1a3a6b 100%)}
.bg2{background:linear-gradient(135deg,var(--teal2) 0%,#00BCD4 100%)}
.team-avatar{width:80px;height:80px;border-radius:50%;border:3px solid var(--gold);font-family:'Playfair Display',serif;font-size:28px;font-weight:900;color:var(--gold);display:flex;align-items:center;justify-content:center;background:rgba(11,31,58,.5);flex-shrink:0}
.team-hdr-info{margin-left:18px}
.team-name{font-family:'Playfair Display',serif;font-size:20px;font-weight:700;color:var(--white)}
.team-role{font-size:12px;font-weight:600;letter-spacing:1.5px;color:rgba(255,255,255,.6);text-transform:uppercase;margin-top:3px}
.team-role-badge{display:inline-block;background:var(--gold);color:var(--navy);font-size:10px;font-weight:700;letter-spacing:1px;padding:3px 12px;border-radius:50px;margin-top:8px}
.team-body{padding:28px 30px 32px}
.team-quote{font-size:15px;color:var(--muted);line-height:1.8;font-style:italic;padding-left:20px;border-left:3px solid var(--gold);margin-bottom:20px}
.team-skills{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:4px}
.skill-tag{background:var(--sand);color:var(--navy);font-size:11px;font-weight:600;padding:4px 12px;border-radius:50px}
.team-linkedin{display:inline-flex;align-items:center;gap:6px;margin-top:18px;color:var(--teal);font-size:13px;font-weight:600;text-decoration:none;transition:color .2s}
.team-linkedin:hover{color:var(--gold2)}
.love-banner{background:var(--navy);padding:60px;text-align:center}
.love-text{font-family:'Playfair Display',serif;font-size:clamp(22px,4vw,40px);color:var(--white);font-weight:700}
.love-text .gold{color:var(--gold)}
.love-sub{font-size:14px;color:rgba(255,255,255,.4);margin-top:12px;letter-spacing:1px}
footer{background:var(--navy);border-top:1px solid rgba(245,197,24,.1);padding:40px 60px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px}
.footer-logo{font-family:'Playfair Display',serif;font-size:20px;font-weight:900;color:var(--gold)}
.footer-links{display:flex;gap:24px}
.footer-links a{color:rgba(255,255,255,.35);font-size:13px;text-decoration:none;transition:color .2s}
.footer-links a:hover{color:var(--gold)}
.footer-copy{font-size:12px;color:rgba(255,255,255,.25)}
.footer-admin{color:rgba(255,255,255,.2);font-size:11px;text-decoration:none;padding:4px 10px;border:1px solid rgba(255,255,255,.1);border-radius:6px;transition:all .2s}
.footer-admin:hover{color:var(--gold);border-color:rgba(245,197,24,.3)}
.reveal{opacity:0;transform:translateY(36px);transition:opacity .7s ease,transform .7s ease}
.reveal.visible{opacity:1;transform:translateY(0)}
.reveal-delay-1{transition-delay:.1s}
.reveal-delay-2{transition-delay:.2s}
.reveal-delay-3{transition-delay:.3s}

.dl-btns{display:flex;justify-content:center;gap:20px;flex-wrap:wrap}
@media(max-width:900px){
  nav{padding:0 20px}
  .page-nav{overflow-x:auto}
  .pnav-btn{padding:10px 16px;font-size:11px}
  .hero{padding:120px 20px 80px}
  .hero-bus-wrap{display:none}
  .why-grid,.features-grid,.steps-row,.team-grid{grid-template-columns:1fr}
  .feat-card.featured{grid-column:span 1}
  .feat-card.featured .feat-row{grid-template-columns:1fr}
  .why-section,.features-section,.how-section,.dl-section,
  .team-hero,.team-main,.love-banner{padding-left:20px;padding-right:20px}
  footer{padding:30px 20px;flex-direction:column;text-align:center}
  .stats-bar{gap:24px;flex-wrap:wrap}
}
.notice-bar{position:relative;z-index:210;background:#7F1D1D;color:#fff;text-align:center;padding:10px 20px;font-family:'Outfit',sans-serif;font-size:13px;font-weight:600;letter-spacing:.3px}
.notice-bar a{color:#F5C518;text-decoration:underline;font-weight:700}
</style>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5902518344335566"
     crossorigin="anonymous"></script>
</head>
<body>
<div class="notice-bar">
  🚌 Bus driver currently unavailable — please call <a href="tel:517-8784">517-8784</a> for assistance.
</div>
<div class="cur" id="cur"></div>
<nav id="nav">
  <a class="nav-logo" href="#"><span class="dot"></span> LetsGo</a>
  <ul class="nav-links">
  <li><a href="#" onclick="showPage('home')">Home</a></li>
  <li><a href="#" onclick="showPage('home');setTimeout(...)">Features</a></li>
  <li><a href="#" onclick="showPage('team')">Our Team</a></li>
  <li><a href="/drivers" style="color:var(--gold)">🚌 Drivers</a></li>
</ul>
  <a href="#dl" class="nav-dl" onclick="showPage('home')">Download App</a>
</nav>
<div class="page-nav">
  <button class="pnav-btn active" id="tab-home" onclick="showPage('home')">Home</button>
  <button class="pnav-btn" id="tab-team" onclick="showPage('team')">Meet Our Team</button>
  <button class="pnav-btn" onclick="window.location.href='/drivers'">For Drivers</button>
</div>
<div class="page active" id="page-home">
  <section class="hero">
    <div class="flag-stripe"></div>
    <div class="stars" id="stars"></div>
    <svg class="palm-left" width="200" height="400" viewBox="0 0 200 400"><path d="M100 400 Q95 300 80 250 Q40 200 10 180 Q50 190 70 220 Q60 170 20 140 Q65 165 80 200 Q75 150 50 110 Q85 145 90 190 Q90 130 70 80 Q100 130 95 200 Q110 130 130 80 Q110 140 115 200 Q120 150 150 110 Q125 155 120 200 Q135 165 180 140 Q145 170 130 220 Q150 190 190 180 Q160 200 120 250 Q105 300 105 400Z" fill="white"/></svg>
    <svg class="palm-right" width="180" height="360" viewBox="0 0 180 360" style="right:0"><path d="M90 360 Q85 270 70 225 Q35 180 8 162 Q45 172 63 198 Q54 153 18 126 Q59 149 72 180 Q68 135 45 99 Q77 131 81 171 Q81 117 63 72 Q90 117 86 180 Q99 117 117 72 Q99 126 103 180 Q108 135 136 99 Q113 139 109 180 Q121 149 162 126 Q131 153 117 198 Q135 172 172 162 Q145 180 110 225 Q95 270 95 360Z" fill="white"/></svg>
    <div class="hero-content">
      <div class="hero-tag"><span class="live-dot"></span>CAYMAN ISLANDS · AI-POWERED TRANSIT</div>
      <h1 class="hero-title">RIDE<br><span class="gold">SMARTER</span><br>CAYMAN</h1>
      <p class="hero-sub">The Cayman Islands' first AI-powered smart bus app — live tracking, offline payments, and community safety features built for Grand Cayman life.</p>
      <div class="hero-cta-row">
        <a href="#dl" class="btn-primary" onclick="showPage('home')">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>
          App Store
        </a>
        <a href="#dl" class="btn-secondary" onclick="showPage('home')">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M3.18 23.76c.3.17.64.22.99.14l12.82-7.41-2.79-2.79-11.02 10.06zM.35 1.33C.13 1.66 0 2.1 0 2.67v18.66c0 .57.13 1.01.36 1.34l.07.07 10.46-10.46v-.25L.42 1.27l-.07.06zM20.96 10.18l-2.64-1.53-3.13 3.13 3.13 3.13 2.65-1.54c.76-.44.76-1.15 0-1.6l-.01.41zM4.17.24l12.82 7.41-2.79 2.79L4.17.24c.35-.09.7-.04.99.14l-.99-.14z"/></svg>
          Google Play
        </a>
      </div>
      <div class="stats-bar">
        <div class="stat-item"><div class="num">9+</div><div class="lbl">Active Routes</div></div>
        <div class="stat-item"><div class="num">24/7</div><div class="lbl">Live Tracking</div></div>
        <div class="stat-item"><div class="num">CI$2.50</div><div class="lbl">From Per Ride</div></div>
        <div class="stat-item"><div class="num">100%</div><div class="lbl">Offline Ready</div></div>
      </div>
    </div>
    <div class="hero-bus-wrap">
      <div class="exhaust"><div class="puff"></div><div class="puff"></div><div class="puff"></div></div>
      <div class="bus-anim">
        <svg width="540" height="200" viewBox="0 0 540 200" fill="none">
          <rect x="20" y="28" width="470" height="132" rx="22" fill="#F5C518"/>
          <rect x="20" y="92" width="470" height="28" fill="#0B1F3A"/>
          <rect x="40" y="18" width="420" height="18" rx="8" fill="#E8B400"/>
          <rect x="462" y="28" width="28" height="132" rx="10" fill="#E8B400"/>
          <rect x="474" y="58" width="18" height="28" rx="6" fill="#FFFDE0"/>
          <rect x="474" y="110" width="18" height="18" rx="4" fill="#FF8C00" opacity=".7"/>
          <rect x="60" y="40" width="62" height="42" rx="8" fill="#0B1F3A" stroke="#F5C518" stroke-width="2"/>
          <rect x="64" y="44" width="54" height="34" rx="5" fill="#1a3a6b" opacity=".9"/>
          <rect x="148" y="40" width="62" height="42" rx="8" fill="#0B1F3A" stroke="#F5C518" stroke-width="2"/>
          <rect x="152" y="44" width="54" height="34" rx="5" fill="#1a3a6b" opacity=".9"/>
          <rect x="236" y="40" width="62" height="42" rx="8" fill="#0B1F3A" stroke="#F5C518" stroke-width="2"/>
          <rect x="240" y="44" width="54" height="34" rx="5" fill="#1a3a6b" opacity=".9"/>
          <rect x="324" y="40" width="62" height="42" rx="8" fill="#0B1F3A" stroke="#F5C518" stroke-width="2"/>
          <rect x="328" y="44" width="54" height="34" rx="5" fill="#1a3a6b" opacity=".9"/>
          <rect x="60" y="103" width="320" height="16" rx="4" fill="#0B1F3A"/>
          <text x="220" y="115" text-anchor="middle" fill="#F5C518" font-family="monospace" font-size="10" font-weight="bold">&#8594; GEORGE TOWN &#183; SEVEN MILE BEACH</text>
          <text x="215" y="152" text-anchor="middle" fill="#0B1F3A" font-family="serif" font-size="16" font-weight="900" letter-spacing="5">LETSGO</text>
          <rect x="410" y="78" width="40" height="78" rx="5" fill="#E8B400" stroke="#0B1F3A" stroke-width="1.5"/>
          <line x1="430" y1="80" x2="430" y2="154" stroke="#0B1F3A" stroke-width="1.5"/>
          <circle cx="440" cy="118" r="3" fill="#0B1F3A"/>
          <rect x="36" y="155" width="414" height="8" rx="3" fill="#C89A00"/>
          <line x1="440" y1="18" x2="440" y2="2" stroke="#F5C518" stroke-width="2"/>
          <circle cx="440" cy="2" r="3" fill="#F5C518"><animate attributeName="r" values="3;5;3" dur="1.5s" repeatCount="indefinite"/><animate attributeName="opacity" values="1;0.4;1" dur="1.5s" repeatCount="indefinite"/></circle>
          <g class="wheel-spin"><circle cx="108" cy="172" r="28" fill="#0B1F3A" stroke="#F5C518" stroke-width="2.5"/><circle cx="108" cy="172" r="17" fill="#1a2a3a" stroke="#F5C518" stroke-width="1.5"/><circle cx="108" cy="172" r="5" fill="#F5C518"/><line x1="108" y1="156" x2="108" y2="188" stroke="#F5C518" stroke-width="1.5" opacity=".5"/><line x1="92" y1="172" x2="124" y2="172" stroke="#F5C518" stroke-width="1.5" opacity=".5"/></g>
          <g class="wheel-spin"><circle cx="376" cy="172" r="28" fill="#0B1F3A" stroke="#F5C518" stroke-width="2.5"/><circle cx="376" cy="172" r="17" fill="#1a2a3a" stroke="#F5C518" stroke-width="1.5"/><circle cx="376" cy="172" r="5" fill="#F5C518"/><line x1="376" y1="156" x2="376" y2="188" stroke="#F5C518" stroke-width="1.5" opacity=".5"/><line x1="360" y1="172" x2="392" y2="172" stroke="#F5C518" stroke-width="1.5" opacity=".5"/></g>
        </svg>
      </div>
    </div>
    <div class="road-strip"><div class="road-mark"></div><div class="road-mark" style="left:300px"></div><div class="road-mark" style="left:600px"></div></div>
    <svg class="hero-waves" viewBox="0 0 1440 80" preserveAspectRatio="none" style="display:block"><path d="M0,60 C360,100 1080,20 1440,60 L1440,80 L0,80Z" fill="#F9F4E8" opacity=".5"/></svg>
  </section>
  <section class="why-section">
    <div class="section-eyebrow">Built for Cayman</div>
    <div class="why-grid">
      <div class="why-text reveal">
        <h2 class="section-title">TRANSPORT<br>THAT KNOWS<br><span class="accent">GRAND CAYMAN</span></h2>
        <p style="margin-top:24px">Getting around Grand Cayman just got smarter. Whether you're heading to work in George Town, school in Bodden Town, or the beach on Seven Mile — <strong>LetsGo has your route covered</strong>.</p>
        <p>We know the roads, the schedules, and the Cayman way of life. No more guessing when the next bus comes. No more missed rides. Just tap and go.</p>
        <div class="why-highlights">
          <div class="why-hl reveal reveal-delay-1"><div class="why-hl-icon">&#128506;</div><div><div class="why-hl-text">All 9 Grand Cayman Routes</div><div class="why-hl-sub">George Town · West Bay · Bodden Town · East End</div></div></div>
          <div class="why-hl reveal reveal-delay-2"><div class="why-hl-icon">&#127754;</div><div><div class="why-hl-text">Works in Dead Zones</div><div class="why-hl-sub">Full offline support — even along the coast roads</div></div></div>
          <div class="why-hl reveal reveal-delay-3"><div class="why-hl-icon">&#127472;&#127486;</div><div><div class="why-hl-text">Made for Caymanians</div><div class="why-hl-sub">Local team, local knowledge, local pride</div></div></div>
        </div>
      </div>
      <div class="cayman-visual reveal">
        <svg class="cayman-map-svg" viewBox="0 0 340 200" fill="none">
          <path d="M20 100 Q40 60 80 50 Q130 35 200 40 Q260 42 300 60 Q330 75 320 100 Q310 120 280 130 Q240 145 180 148 Q120 152 70 140 Q35 130 20 100Z" fill="rgba(255,255,255,0.05)" stroke="rgba(245,197,24,0.3)" stroke-width="1.5"/>
          <path d="M60 100 Q120 80 200 85 Q260 88 300 95" stroke="rgba(245,197,24,0.4)" stroke-width="2" stroke-dasharray="6 4" fill="none"/>
          <path d="M80 110 Q130 120 170 118 Q210 115 240 125" stroke="rgba(0,137,123,0.5)" stroke-width="1.5" stroke-dasharray="5 4" fill="none"/>
          <circle class="route-dot" cx="60" cy="100" r="5" fill="#F5C518"/>
          <circle class="route-dot" cx="130" cy="90" r="5" fill="#F5C518"/>
          <circle class="route-dot" cx="200" cy="85" r="5" fill="#00897B"/>
          <circle class="route-dot" cx="270" cy="92" r="5" fill="#F5C518"/>
          <circle class="route-dot" cx="300" cy="95" r="4" fill="#FF6B35"/>
          <text x="55" y="120" fill="rgba(255,255,255,0.5)" font-family="Outfit" font-size="9">George Town</text>
          <text x="185" y="78" fill="rgba(255,255,255,0.5)" font-family="Outfit" font-size="9">Seven Mile</text>
          <text x="262" y="108" fill="rgba(255,255,255,0.5)" font-family="Outfit" font-size="9">Bodden Town</text>
          <rect x="145" y="82" width="20" height="10" rx="3" fill="#F5C518"><animateTransform attributeName="transform" type="translate" values="0,0;60,3;0,0" dur="5s" repeatCount="indefinite"/></rect>
          <circle cx="22" cy="170" r="4" fill="#F5C518"/>
          <text x="32" y="174" fill="rgba(255,255,255,0.4)" font-family="Outfit" font-size="9">Your stop</text>
          <rect x="100" y="167" width="16" height="6" rx="2" fill="#F5C518"/>
          <text x="122" y="174" fill="rgba(255,255,255,0.4)" font-family="Outfit" font-size="9">Live bus</text>
          <circle cx="210" cy="170" r="4" fill="#FF6B35"/>
          <text x="220" y="174" fill="rgba(255,255,255,0.4)" font-family="Outfit" font-size="9">Next stop</text>
        </svg>
      </div>
    </div>
  </section>
  <section class="features-section" id="features">
    <div class="features-intro reveal"><div class="section-eyebrow">What's inside</div><h2 class="section-title">EVERYTHING<br>YOUR <span class="accent">RIDE</span> NEEDS</h2></div>
   <div class="features-grid">
  <div class="feat-card featured reveal">
    <div class="feat-num">01 ——</div><div class="feat-icon-wrap">📍</div>
    <div class="feat-title" style="font-size:28px;color:var(--white)">Real-Time Tracking — Online & Offline</div>
    <div class="feat-desc" style="max-width:560px">See your bus live on the map with ETA, speed, stops, and distance. No signal? Our AI-powered device switches seamlessly to offline SMS tracking — so you're never left guessing, no matter where you are on the island.</div>
    <div class="feat-row">
      <div class="feat-stat"><div class="fs-num">&lt;60s</div><div class="fs-lbl">ETA accuracy</div></div>
      <div class="feat-stat"><div class="fs-num">100%</div><div class="fs-lbl">Offline ready</div></div>
      <div class="feat-stat"><div class="fs-num">Live</div><div class="fs-lbl">GPS updates</div></div>
    </div>
    <span class="feat-pill">AI · MACHINE LEARNING · ALWAYS ON</span>
  </div>

  <div class="feat-card reveal reveal-delay-1">
    <div class="feat-num">02 ——</div><div class="feat-icon-wrap">💳</div>
    <div class="feat-title">Smart Payment — One Tap</div>
    <div class="feat-desc">Forget cash and coins. Our NFC device is installed on every bus — just tap your phone once to pay. Buy a single ride or a monthly pass instantly, even without internet. Fast, secure, and completely cashless.</div>
    <span class="feat-pill">NFC · ONE TAP · CASHLESS</span>
  </div>

  <div class="feat-card reveal reveal-delay-2">
    <div class="feat-num">03 ——</div><div class="feat-icon-wrap">🛡</div>
    <div class="feat-title">Safety Features</div>
    <div class="feat-desc">Share your live journey with family or friends in one tap. If anything feels wrong, hit SOS — your exact GPS location is sent to your emergency contacts instantly, with 911 integrated directly in the app. Every rider is protected.</div>
    <span class="feat-pill">SOS · LIVE SHARE · 911 INTEGRATED</span>
  </div>

  <div class="feat-card reveal reveal-delay-1">
    <div class="feat-num">04 ——</div><div class="feat-icon-wrap">📣</div>
    <div class="feat-title">Community Reports</div>
    <div class="feat-desc">Riders flag broken stops, overcrowding, and delays in real time. We collect that data, analyse it, and resolve issues as fast as possible — making the entire bus network smarter and more reliable for everyone.</div>
    <span class="feat-pill">CROWDSOURCED · REAL TIME · RESOLVED FAST</span>
  </div>
</div>
  </section>
  <section class="how-section">
    <div class="section-eyebrow">Simple as 1-2-3-4</div>
    <h2 class="section-title">HOW IT <span class="accent">WORKS</span></h2>
    <div class="steps-row">
      <div class="step-card reveal"><div class="step-num">1</div><div class="step-title">Download Free</div><div class="step-desc">Get LetsGo on iOS or Android in seconds. Free forever for riders.</div></div>
      <div class="step-card reveal reveal-delay-1"><div class="step-num">2</div><div class="step-title">Find Your Route</div><div class="step-desc">Type where you're going or browse all 9 Grand Cayman routes on the live map.</div></div>
      <div class="step-card reveal reveal-delay-2"><div class="step-num">3</div><div class="step-title">Tap &amp; Pay</div><div class="step-desc">Load your wallet once. Tap your phone at the reader — even with no signal.</div></div>
      <div class="step-card reveal reveal-delay-3"><div class="step-num">4</div><div class="step-title">Track &amp; Ride</div><div class="step-desc">Watch your bus approach in real time. Get notified before it arrives. Sit back, relax.</div></div>
    </div>
  </section>
  <section class="dl-section" id="dl">
    <p class="section-eyebrow" style="color:rgba(11,31,58,.5)">Free to download</p>
    <h2 class="dl-title">GET ON<br>THE BUS</h2>
    <p class="dl-sub">Available on iOS and Android. Ride smarter across Grand Cayman starting today.</p>
    <div class="dl-btns reveal">
      <a href="https://apps.apple.com/us/app/letsgo-cayman/id6768839802" target="_blank" class="dl-app-btn">
        <svg viewBox="0 0 24 24" fill="currentColor" style="width:26px;height:26px;flex-shrink:0"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>
        <div class="dl-t"><small>Download on the</small><strong>App Store</strong></div>
      </a>
      <a href="https://play.google.com/store/apps/details?id=com.letsgocayman" target="_blank" class="dl-app-btn">
        <svg viewBox="0 0 24 24" fill="currentColor" style="width:26px;height:26px;flex-shrink:0"><path d="M3.18 23.76c.3.17.64.22.99.14l12.82-7.41-2.79-2.79-11.02 10.06zM.35 1.33C.13 1.66 0 2.1 0 2.67v18.66c0 .57.13 1.01.36 1.34l.07.07 10.46-10.46v-.25L.42 1.27l-.07.06zM20.96 10.18l-2.64-1.53-3.13 3.13 3.13 3.13 2.65-1.54c.76-.44.76-1.15 0-1.6l-.01.41zM4.17.24l12.82 7.41-2.79 2.79L4.17.24c.35-.09.7-.04.99.14l-.99-.14z"/></svg>
        <div class="dl-t"><small>Get it on</small><strong>Google Play</strong></div>
      </a>
    </div>
  </section>
  <footer>
    <div class="footer-logo">&#128652; LetsGo</div>
    <div class="footer-links"><a href="#" onclick="showPage('home')">Home</a><a href="#features" onclick="showPage('home')">Features</a><a href="#" onclick="showPage('team')">Team</a></div>
    <div class="footer-copy">&#169; 2026 LetsGo · Cayman Islands</div>
    <a href="/admin/login" class="footer-admin">Admin</a>
  </footer>
</div>
<div class="page" id="page-team">
  <section class="team-hero">
    <div class="section-eyebrow" style="color:var(--gold)">The people behind the app</div>
    <h2 class="section-title">MEET THE <span class="accent">MINDS</span><br>BEHIND LETSGO</h2>
    <p class="team-hero-sub">A passionate team that believed Cayman deserved smarter, more connected public transport — and built it.</p>
    <svg viewBox="0 0 1440 80" preserveAspectRatio="none" style="position:absolute;bottom:0;left:0;right:0;display:block"><path d="M0,40 C480,90 960,10 1440,50 L1440,80 L0,80Z" fill="#F9F4E8"/></svg>
  </section>
  <section class="team-main">
    <div class="team-intro reveal"><p>LetsGo was born from a simple frustration — getting around Grand Cayman on public transport shouldn't be a guessing game. This small team of technologists decided to do something about it.</p></div>
    <div class="team-grid">
      <div class="team-card reveal">
        <div class="team-card-header bg1"><div class="team-avatar">SA</div><div class="team-hdr-info"><div class="team-name">Saaleha AbrarAli</div><div class="team-role-badge">Founder</div></div></div>
        <div class="team-body"><p class="team-quote">"It was really cool to bring up the idea and make it live in Cayman Island, mainly for bus transport."</p><a href="https://www.linkedin.com/in/saaleha-aafreen-a56b49105/" target="_blank" class="team-linkedin"><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>Connect on LinkedIn</a></div>
      </div>
      <div class="team-card reveal reveal-delay-1">
        <div class="team-card-header bg2"><div class="team-avatar">SF</div><div class="team-hdr-info"><div class="team-name">Safee</div><div class="team-role-badge">Co-Founder</div></div></div>
        <div class="team-body"><p class="team-quote">"Every line of code was written with one goal — making daily life in Cayman easier, safer, and more connected."</p><a href="https://www.linkedin.com/in/mohammad-safeeullah-a64007a5/" target="_blank" class="team-linkedin"><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>Connect on LinkedIn</a></div>
      </div>
    </div>
    <div style="max-width:860px;margin:64px auto 0;background:var(--navy);border-radius:24px;padding:48px;text-align:center" class="reveal">
      <div class="section-eyebrow" style="color:var(--gold);margin-bottom:16px">Our mission</div>
      <h3 style="font-family:'Playfair Display',serif;font-size:clamp(24px,4vw,38px);font-weight:900;color:var(--white);line-height:1.1;margin-bottom:16px">To make public transport in the Cayman Islands as <span style="color:var(--gold)">reliable, safe, and effortless</span> as the island life itself.</h3>
      <p style="color:rgba(255,255,255,.45);font-size:15px;line-height:1.7;max-width:500px;margin:0 auto">We believe every Caymanian deserves to know exactly when their bus is coming — whether they have signal or not.</p>
    </div>
  </section>
  <div class="love-banner reveal"><div class="love-text">Made with <span class="gold">love</span> in the Cayman Islands &#127472;&#127486;</div><div class="love-sub">GRAND CAYMAN · CAYMAN BRAC · LITTLE CAYMAN</div></div>
  <footer>
    <div class="footer-logo">&#128652; LetsGo</div>
    <div class="footer-links"><a href="#" onclick="showPage('home')">Home</a><a href="#" onclick="showPage('team')">Team</a></div>
    <div class="footer-copy">&#169; 2026 LetsGo · Cayman Islands</div>
    <a href="/admin/login" class="footer-admin">Admin</a>
  </footer>
</div>
<script>
const cur=document.getElementById('cur');
document.addEventListener('mousemove',e=>{cur.style.left=e.clientX+'px';cur.style.top=e.clientY+'px';});
document.querySelectorAll('a,button,.feat-card,.team-card,.why-hl,.step-card').forEach(el=>{
  el.addEventListener('mouseenter',()=>cur.classList.add('big'));
  el.addEventListener('mouseleave',()=>cur.classList.remove('big'));
});
window.addEventListener('scroll',()=>{document.getElementById('nav').classList.toggle('scrolled',window.scrollY>40);});
(function(){const c=document.getElementById('stars');if(!c)return;for(let i=0;i<60;i++){const s=document.createElement('div');s.className='star';s.style.cssText=`left:${Math.random()*100}%;top:${Math.random()*100}%;--d:${2+Math.random()*3}s;--delay:${Math.random()*4}s`;c.appendChild(s);}})();
function showPage(name){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.pnav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  document.getElementById('tab-'+name).classList.add('active');
  window.scrollTo({top:0,behavior:'smooth'});
  setTimeout(runReveal,100);
}
function runReveal(){
  const obs=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting)e.target.classList.add('visible');});},{threshold:0.12});
  document.querySelectorAll('.reveal:not(.visible)').forEach(el=>obs.observe(el));
}
runReveal();
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════
# ADMIN AUTH ROUTES
# ═══════════════════════════════════════════════════════════

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = ''
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect('/users')
        error = 'Invalid username or password.'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LetsGo Admin Login</title>
<meta name="robots" content="noindex, nofollow">
{ADMIN_STYLE}
<style>
  body{{display:flex;align-items:center;justify-content:center;min-height:100vh;background:radial-gradient(ellipse at 60% 40%, #0e2847 0%, #0d1117 70%)}}
  .login-box{{background:#161b22;border:1px solid #30363d;border-radius:20px;padding:48px 40px;width:100%;max-width:400px;box-shadow:0 24px 80px rgba(0,0,0,.5)}}
  .login-logo{{text-align:center;margin-bottom:32px}}
  .login-logo .icon{{font-size:40px;display:block;margin-bottom:8px}}
  .login-logo h1{{font-size:22px;font-weight:700;color:#f0f6fc}}
  .login-logo p{{font-size:13px;color:#6e7681;margin-top:4px}}
  .login-field{{margin-bottom:16px}}
  .login-field label{{display:block;font-size:12px;font-weight:600;color:#8b949e;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}}
  .login-field input{{width:100%;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:11px 14px;font-size:14px;color:#e6edf3;outline:none;transition:border-color .2s}}
  .login-field input:focus{{border-color:var(--gold)}}
  .login-btn{{width:100%;background:var(--gold);color:#0d1117;border:none;border-radius:10px;padding:13px;font-size:15px;font-weight:700;cursor:pointer;margin-top:8px;transition:background .2s}}
  .login-btn:hover{{background:#e8b400}}
  .login-error{{background:rgba(220,38,38,.1);border:1px solid rgba(220,38,38,.3);color:#f87171;padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:16px}}
  .back-link{{display:block;text-align:center;margin-top:20px;font-size:13px;color:#6e7681}}
  .back-link a{{color:#8b949e}}
  .back-link a:hover{{color:var(--gold)}}
</style>
</head>
<body>
<div class="login-box">
  <div class="login-logo">
    <span class="icon">🚌</span>
    <h1>LetsGo Admin</h1>
    <p>Sign in to the dashboard</p>
  </div>
  {'<div class="login-error">⚠ ' + error + '</div>' if error else ''}
  <form method="POST">
    <div class="login-field">
      <label>Username</label>
      <input type="text" name="username" placeholder="admin" autocomplete="username" required autofocus>
    </div>
    <div class="login-field">
      <label>Password</label>
      <input type="password" name="password" placeholder="••••••••" autocomplete="current-password" required>
    </div>
    <button type="submit" class="login-btn">Sign In →</button>
  </form>
  <div class="back-link"><a href="/">← Back to LetsGo site</a></div>
</div>
</body>
</html>"""


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin/login')


# ═══════════════════════════════════════════════════════════
# ADMIN SETTINGS PAGE
# ═══════════════════════════════════════════════════════════

@app.route('/admin/settings', methods=['GET', 'POST'])
@require_admin
def admin_settings():
    global _twilio_override
    saved_msg = ''
    saved_type = ''

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'twilio':
            _twilio_override = {
                'accountSid': request.form.get('accountSid', '').strip(),
                'authToken': request.form.get('authToken', '').strip(),
                'fromNumber': request.form.get('fromNumber', '').strip(),
            }
            saved_msg = '✓ Twilio config updated (active until server restart)'
            saved_type = 'success'

    current_twilio = {**TWILIO_CONFIG, **_twilio_override}

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Settings — LetsGo Admin</title>
<meta name="robots" content="noindex, nofollow">
{ADMIN_STYLE}
</head>
<body>
{nav_html('settings')}
<div class="admin-main">
  <div class="page-header">
    <div><h1>⚙ Settings</h1><p>Configure Twilio SMS and admin credentials</p></div>
  </div>

  {'<div class="toast show ' + saved_type + '" style="position:relative;bottom:auto;right:auto;margin-bottom:20px;opacity:1;transform:none">' + saved_msg + '</div>' if saved_msg else ''}

  <div class="card">
    <div class="card-header">
      <h2>📱 Twilio SMS Configuration</h2>
      <span style="font-size:12px;color:#484f58">Used for SOS alerts, journey sharing &amp; offline safety SMS</span>
    </div>
    <div class="card-body">
      <form method="POST">
        <input type="hidden" name="action" value="twilio">
        <div class="form-row">
          <div class="form-group">
            <label>Account SID</label>
            <input type="text" name="accountSid" value="{current_twilio.get('accountSid', '')}" placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx">
          </div>
          <div class="form-group">
            <label>From Number</label>
            <input type="text" name="fromNumber" value="{current_twilio.get('fromNumber', '')}" placeholder="+1345XXXXXXX">
          </div>
        </div>
        <div class="form-group" style="margin-bottom:20px">
          <label>Auth Token</label>
          <input type="password" name="authToken" value="{current_twilio.get('authToken', '')}" placeholder="Your Twilio auth token">
        </div>
        <button type="submit" class="btn btn-primary">Save Twilio Config</button>
      </form>
    </div>
  </div>

  <div class="card">
    <div class="card-header"><h2>🔐 Admin Credentials</h2></div>
    <div class="card-body">
      <p style="font-size:14px;color:#8b949e;line-height:1.7;margin-bottom:12px">Admin credentials are set via environment variables on your server:</p>
      <div style="background:#0d1117;border-radius:8px;padding:16px;border:1px solid #21262d;font-family:monospace;font-size:13px;color:#e6edf3;line-height:2">
        <div><span style="color:#6e7681">ADMIN_USERNAME</span>=<span style="color:var(--gold)">your_username</span></div>
        <div><span style="color:#6e7681">ADMIN_PASSWORD</span>=<span style="color:var(--gold)">your_password</span></div>
        <div><span style="color:#6e7681">TWILIO_ACCOUNT_SID</span>=<span style="color:var(--gold)">ACxxxx</span></div>
        <div><span style="color:#6e7681">TWILIO_AUTH_TOKEN</span>=<span style="color:var(--gold)">xxxx</span></div>
        <div><span style="color:#6e7681">TWILIO_FROM_NUMBER</span>=<span style="color:var(--gold)">+1345xxxx</span></div>
        <div><span style="color:#6e7681">SECRET_KEY</span>=<span style="color:var(--gold)">your_flask_secret</span></div>
      </div>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>
{ADMIN_JS}
</body>
</html>"""


# ═══════════════════════════════════════════════════════════
# USERS ADMIN PAGE
# ═══════════════════════════════════════════════════════════

@app.route('/users')
@require_admin
def show_users():
    users = User.query.order_by(User.created_at.desc()).all()

    rows = ""
    for user in users:
        initials = ''.join([n[0].upper() for n in user.full_name.split()[:2]])
        joined = user.created_at.strftime('%d %b %Y, %H:%M')
        rows += f"""
        <tr id="row-{user.id}">
          <td><div class="avatar">{initials}</div></td>
          <td><strong style="color:#f0f6fc">{user.username}</strong></td>
          <td style="color:#8b949e">{user.full_name}</td>
          <td style="color:#8b949e">{user.phone_number}</td>
          <td><span class="lock">🔒 hidden</span></td>
          <td class="date-cell">{joined}</td>
          <td>
            <button class="btn btn-danger" onclick="openEditModal({user.id}, '{user.username}', '{user.full_name}', '{user.phone_number}')">Edit</button>
            <button class="btn btn-danger" style="margin-left:6px" onclick="confirmDelete({user.id}, '{user.username}')">Delete</button>
          </td>
        </tr>"""

    if not rows:
        rows = '<tr><td colspan="7" style="text-align:center;padding:48px;color:#484f58">No users registered yet.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Users — LetsGo Admin</title>
<meta name="robots" content="noindex, nofollow">
{ADMIN_STYLE}
</head>
<body>
{nav_html('users')}
<div class="admin-main">
  <div class="page-header">
    <div>
      <h1>👥 Registered Users</h1>
      <p>Users who signed up via the LetsGo app</p>
    </div>
    <div style="display:flex;gap:12px;align-items:center">
      <span class="badge" id="user-count">{len(users)} user(s)</span>
    </div>
  </div>
  <div class="refresh-bar">Auto-refreshes every 15s &nbsp;|&nbsp; <span id="last-updated">Updated just now</span></div>
  <div class="card">
    <div class="table-wrap">
      <table>
        <thead><tr><th></th><th>Username</th><th>Full Name</th><th>Phone</th><th>Password</th><th>Joined</th><th>Actions</th></tr></thead>
        <tbody id="user-tbody">{rows}</tbody>
      </table>
    </div>
  </div>
</div>

<div class="overlay" id="edit-overlay">
  <div class="modal" style="max-width:480px">
    <h3>✏ Edit User</h3>
    <p>Update user details below.</p>
    <input type="hidden" id="edit-id">
    <div class="form-row">
      <div class="form-group"><label>Username</label><input type="text" id="edit-username" placeholder="username"></div>
      <div class="form-group"><label>Full Name</label><input type="text" id="edit-fullname" placeholder="Full Name"></div>
    </div>
    <div class="form-group" style="margin-bottom:20px"><label>Phone Number</label><input type="text" id="edit-phone" placeholder="+1 345 XXX XXXX"></div>
    <div class="modal-btns">
      <button class="btn btn-ghost" onclick="closeModal('edit-overlay')">Cancel</button>
      <button class="btn btn-primary" onclick="saveEdit()">Save Changes</button>
    </div>
  </div>
</div>

<div class="overlay" id="del-overlay">
  <div class="modal">
    <h3>🗑 Delete User</h3>
    <p id="del-msg">Are you sure you want to delete this user?</p>
    <div class="modal-btns">
      <button class="btn btn-ghost" onclick="closeModal('del-overlay')">Cancel</button>
      <button class="btn btn-danger" id="confirm-del-btn">Delete</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>
{ADMIN_JS}
<script>
let pendingDeleteId=null;

function openEditModal(id, username, fullName, phone){{
  document.getElementById('edit-id').value=id;
  document.getElementById('edit-username').value=username;
  document.getElementById('edit-fullname').value=fullName;
  document.getElementById('edit-phone').value=phone;
  openModal('edit-overlay');
}}

async function saveEdit(){{
  const id=document.getElementById('edit-id').value;
  const body={{username:document.getElementById('edit-username').value,fullName:document.getElementById('edit-fullname').value,phoneNumber:document.getElementById('edit-phone').value}};
  try{{
    const res=await fetch(`/api/users/${{id}}`,{{method:'PATCH',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
    const data=await res.json();
    if(res.ok){{closeModal('edit-overlay');showToast('✓ User updated');refreshUsers();}}
    else showToast('✗ '+data.message,'error');
  }}catch(e){{showToast('✗ Update failed','error');}}
}}

function confirmDelete(id, username){{
  pendingDeleteId=id;
  document.getElementById('del-msg').textContent=`Delete "${{username}}"? This cannot be undone.`;
  openModal('del-overlay');
}}

document.getElementById('confirm-del-btn').addEventListener('click', async()=>{{
  if(!pendingDeleteId)return; closeModal('del-overlay');
  try{{
    const res=await fetch(`/api/users/${{pendingDeleteId}}`,{{method:'DELETE'}});
    const data=await res.json();
    if(res.ok){{document.getElementById(`row-${{pendingDeleteId}}`).remove();showToast('✓ '+data.message);refreshCount();}}
    else showToast('✗ '+data.message,'error');
  }}catch(e){{showToast('✗ Delete failed','error');}}
  pendingDeleteId=null;
}});

function refreshCount(){{
  const rows=document.querySelectorAll('#user-tbody tr[id]').length;
  document.getElementById('user-count').textContent=rows+' user(s)';
}}

async function refreshUsers(){{
  try{{
    const res=await fetch('/api/users'); const data=await res.json();
    const tbody=document.getElementById('user-tbody');
    if(data.users.length===0){{tbody.innerHTML='<tr><td colspan="7" style="text-align:center;padding:48px;color:#484f58">No users registered yet.</td></tr>';document.getElementById('user-count').textContent='0 user(s)';return;}}
    tbody.innerHTML=data.users.map(u=>{{
      const ini=u.fullName.split(' ').map(n=>n[0]).join('').toUpperCase().slice(0,2);
      return `<tr id="row-${{u.id}}"><td><div class="avatar">${{ini}}</div></td><td><strong style="color:#f0f6fc">${{u.username}}</strong></td><td style="color:#8b949e">${{u.fullName}}</td><td style="color:#8b949e">${{u.phoneNumber}}</td><td><span class="lock">🔒 hidden</span></td><td class="date-cell">${{u.createdAt}}</td><td><button class="btn btn-danger" onclick="openEditModal(${{u.id}},'${{u.username}}','${{u.fullName}}','${{u.phoneNumber}}')">Edit</button><button class="btn btn-danger" style="margin-left:6px" onclick="confirmDelete(${{u.id}},'${{u.username}}')">Delete</button></td></tr>`;
    }}).join('');
    document.getElementById('user-count').textContent=data.total+' user(s)';
    document.getElementById('last-updated').textContent='Updated '+new Date().toLocaleTimeString();
  }}catch(e){{console.error(e);}}
}}
setInterval(refreshUsers,15000);
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════
# COMMUNITY REPORTS ADMIN PAGE
# ═══════════════════════════════════════════════════════════

@app.route('/community-reports')
@require_admin
def show_community_reports():
    reports = CommunityReport.query.order_by(CommunityReport.created_at.desc()).all()

    rows = ""
    for r in reports:
        color = '#f87171' if r.status == 'open' else ('#fb923c' if r.status == 'in_progress' else '#4ade80')
        label = {'open': 'Open', 'in_progress': 'In Progress', 'resolved': 'Resolved'}.get(r.status, r.status)
        joined = r.created_at.strftime('%d %b %Y, %H:%M')
        msg_preview = (r.message[:60] + '…') if len(r.message) > 60 else r.message
        rows += f"""
        <tr id="rep-row-{r.id}">
          <td style="color:#6e7681;font-size:12px">#{r.id}</td>
          <td><span style="background:rgba(245,197,24,.1);color:var(--gold);padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600">{r.category}</span></td>
          <td style="color:#8b949e;max-width:220px">{msg_preview}</td>
          <td style="color:#8b949e;font-size:13px">{r.stop_name}</td>
          <td style="color:#8b949e;font-size:13px">{r.route_id}</td>
          <td style="color:var(--gold);font-weight:600">{r.upvotes} 👍</td>
          <td><span style="color:{color};background:{color}18;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600">{label}</span></td>
          <td style="color:#6e7681;font-size:12px">{r.username}</td>
          <td class="date-cell">{joined}</td>
          <td>
            <button class="btn btn-ghost" style="font-size:12px;padding:5px 10px" onclick="openRepEdit({r.id}, '{r.status}', '{r.message[:60].replace(chr(39), '').replace(chr(34), '')}')">Edit</button>
            <button class="btn btn-danger" style="font-size:12px;padding:5px 10px;margin-left:4px" onclick="confirmRepDelete({r.id})">Del</button>
          </td>
        </tr>"""

    if not rows:
        rows = '<tr><td colspan="10" style="text-align:center;padding:48px;color:#484f58">No community reports yet.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Community Reports — LetsGo Admin</title>
<meta name="robots" content="noindex, nofollow">
{ADMIN_STYLE}
<style>table td{{max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}</style>
</head>
<body>
{nav_html('community')}
<div class="admin-main">
  <div class="page-header">
    <div><h1>📣 Community Reports</h1><p>Reports submitted by LetsGo riders</p></div>
    <span class="badge" id="rep-count">{len(reports)} report(s)</span>
  </div>
  <div class="refresh-bar">Auto-refreshes every 15s &nbsp;|&nbsp; <span id="rep-last-updated">Updated just now</span></div>
  <div class="card">
    <div class="table-wrap">
      <table>
        <thead><tr><th>#</th><th>Category</th><th>Message</th><th>Stop</th><th>Route</th><th>Upvotes</th><th>Status</th><th>Author</th><th>Submitted</th><th>Actions</th></tr></thead>
        <tbody id="rep-tbody">{rows}</tbody>
      </table>
    </div>
  </div>
</div>

<div class="overlay" id="rep-edit-overlay">
  <div class="modal" style="max-width:500px">
    <h3>✏ Edit Report</h3>
    <p>Update the status or message of this report.</p>
    <input type="hidden" id="rep-edit-id">
    <div class="form-group" style="margin-bottom:16px">
      <label>Status</label>
      <select id="rep-edit-status">
        <option value="open">Open</option>
        <option value="in_progress">In Progress</option>
        <option value="resolved">Resolved</option>
      </select>
    </div>
    <div class="form-group" style="margin-bottom:20px">
      <label>Message</label>
      <textarea id="rep-edit-msg" rows="3"></textarea>
    </div>
    <div class="modal-btns">
      <button class="btn btn-ghost" onclick="closeModal('rep-edit-overlay')">Cancel</button>
      <button class="btn btn-primary" onclick="saveRepEdit()">Save Changes</button>
    </div>
  </div>
</div>

<div class="overlay" id="rep-del-overlay">
  <div class="modal">
    <h3>🗑 Delete Report</h3>
    <p id="rep-del-msg">Delete this report permanently?</p>
    <div class="modal-btns">
      <button class="btn btn-ghost" onclick="closeModal('rep-del-overlay')">Cancel</button>
      <button class="btn btn-danger" id="confirm-rep-del-btn">Delete</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>
{ADMIN_JS}
<script>
let pendingRepDeleteId=null;
function openRepEdit(id,status,msg){{document.getElementById('rep-edit-id').value=id;document.getElementById('rep-edit-status').value=status;document.getElementById('rep-edit-msg').value=msg;openModal('rep-edit-overlay');}}
async function saveRepEdit(){{
  const id=document.getElementById('rep-edit-id').value;
  const body={{status:document.getElementById('rep-edit-status').value,message:document.getElementById('rep-edit-msg').value}};
  try{{const res=await fetch(`/api/community/reports/${{id}}`,{{method:'PATCH',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});const data=await res.json();if(res.ok){{closeModal('rep-edit-overlay');showToast('✓ Report updated');refreshReports();}}else showToast('✗ '+data.message,'error');}}catch(e){{showToast('✗ Update failed','error');}}
}}
function confirmRepDelete(id){{pendingRepDeleteId=id;document.getElementById('rep-del-msg').textContent=`Delete report #${{id}} permanently?`;openModal('rep-del-overlay');}}
document.getElementById('confirm-rep-del-btn').addEventListener('click',async()=>{{
  if(!pendingRepDeleteId)return;closeModal('rep-del-overlay');
  try{{const res=await fetch(`/api/community/reports/${{pendingRepDeleteId}}`,{{method:'DELETE'}});const data=await res.json();if(res.ok){{document.getElementById(`rep-row-${{pendingRepDeleteId}}`).remove();showToast('✓ '+data.message);}}else showToast('✗ '+data.message,'error');}}catch(e){{showToast('✗ Delete failed','error');}}
  pendingRepDeleteId=null;
}});
async function refreshReports(){{
  try{{
    const res=await fetch('/api/community/reports/');const data=await res.json();
    const tbody=document.getElementById('rep-tbody');
    const STATUS={{'open':['#f87171','Open'],'in_progress':['#fb923c','In Progress'],'resolved':['#4ade80','Resolved']}};
    if(!data.reports||data.reports.length===0){{tbody.innerHTML='<tr><td colspan="10" style="text-align:center;padding:48px;color:#484f58">No community reports yet.</td></tr>';document.getElementById('rep-count').textContent='0 report(s)';return;}}
    tbody.innerHTML=data.reports.map(r=>{{
      const[color,label]=STATUS[r.status]||['#8b949e',r.status];
      const preview=r.message.length>60?r.message.slice(0,60)+'…':r.message;
      return `<tr id="rep-row-${{r.id}}"><td style="color:#6e7681;font-size:12px">#${{r.id}}</td><td><span style="background:rgba(245,197,24,.1);color:var(--gold);padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600">${{r.category}}</span></td><td style="color:#8b949e;max-width:220px">${{preview}}</td><td style="color:#8b949e;font-size:13px">${{r.stopName}}</td><td style="color:#8b949e;font-size:13px">${{r.routeId}}</td><td style="color:var(--gold);font-weight:600">${{r.upvotes}} 👍</td><td><span style="color:${{color}};background:${{color}}18;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600">${{label}}</span></td><td style="color:#6e7681;font-size:12px">${{r.username}}</td><td class="date-cell">${{r.createdAt}}</td><td><button class="btn btn-ghost" style="font-size:12px;padding:5px 10px" onclick="openRepEdit(${{r.id}},'${{r.status}}',\`${{r.message}}\`)">Edit</button><button class="btn btn-danger" style="font-size:12px;padding:5px 10px;margin-left:4px" onclick="confirmRepDelete(${{r.id}})">Del</button></td></tr>`;
    }}).join('');
    document.getElementById('rep-count').textContent=data.total+' report(s)';
    document.getElementById('rep-last-updated').textContent='Updated '+new Date().toLocaleTimeString();
  }}catch(e){{console.error(e);}}
}}
setInterval(refreshReports,15000);
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════
# SOS ALERTS ADMIN PAGE  (/admin/sos-alerts)
# ═══════════════════════════════════════════════════════════

@app.route('/admin/sos-alerts')
@require_admin
def admin_sos_alerts():
    alerts = SOSAlert.query.order_by(SOSAlert.created_at.desc()).all()
    active_count = sum(1 for a in alerts if not a.resolved)

    rows = ""
    for a in alerts:
        contacts = json.loads(a.contacts or '[]')
        contact_names = ', '.join(c.get('name', '?') for c in contacts[:3])
        if len(contacts) > 3:
            contact_names += f' +{len(contacts) - 3}'
        triggered = a.created_at.strftime('%d %b %Y, %H:%M')
        status_color = '#4ade80' if a.resolved else '#ef4444'
        status_bg = 'rgba(74,222,128,.1)' if a.resolved else 'rgba(239,68,68,.12)'
        status_label = 'Resolved' if a.resolved else 'ACTIVE'
        dot = '' if a.resolved else '<span style="width:6px;height:6px;border-radius:50%;background:#ef4444;display:inline-block;animation:blink_ 0.8s infinite;margin-right:4px"></span>'
        resolve_btn = (
            f'<button class="btn btn-success" style="font-size:12px;padding:5px 10px;margin-left:4px" onclick="resolveAlert({a.id}, \'{a.token}\')">Resolve</button>'
            if not a.resolved else
            '<span style="font-size:11px;color:#484f58;padding:0 8px">✓ Done</span>'
        )
        rows += f"""
        <tr id="sos-row-{a.id}">
          <td style="color:#6e7681;font-size:12px;font-family:monospace">#{a.id}</td>
          <td>
            <div style="font-weight:600;color:#f0f6fc">{a.username}</div>
            <div style="font-size:11px;color:#6e7681;margin-top:2px">{a.phone_number or '—'}</div>
          </td>
          <td style="color:#8b949e;font-size:13px">{a.route_id or '—'}</td>
          <td style="color:#8b949e;font-size:13px">{a.bus_id or '—'}</td>
          <td>
            <div style="font-family:monospace;font-size:11px;color:#8b949e">{a.lat or '—'}</div>
            <div style="font-family:monospace;font-size:11px;color:#8b949e">{a.lng or '—'}</div>
          </td>
          <td style="max-width:160px">
            {f'<span style="color:#f0f6fc;font-size:12px">{contact_names}</span>' if contact_names else '<span style="color:#484f58">None</span>'}
            <div style="font-size:10px;color:#484f58;margin-top:2px">{len(contacts)} contact(s)</div>
          </td>
          <td>
            <span style="display:inline-flex;align-items:center;background:{status_bg};color:{status_color};padding:4px 11px;border-radius:20px;font-size:11px;font-weight:700;border:1px solid {status_color}33">
              {dot}{status_label}
            </span>
          </td>
          <td class="date-cell">{triggered}</td>
          <td>
            <a href="/sos/{a.token}" target="_blank" class="btn btn-ghost" style="font-size:12px;padding:5px 10px">View</a>
            {resolve_btn}
          </td>
        </tr>"""

    if not rows:
        rows = '<tr><td colspan="9" style="text-align:center;padding:48px;color:#484f58">No SOS alerts yet.</td></tr>'

    active_pill = (
        f'<span style="display:inline-flex;align-items:center;gap:6px;background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.3);color:#ef4444;padding:5px 16px;border-radius:20px;font-size:13px;font-weight:700"><span style="width:7px;height:7px;border-radius:50%;background:#ef4444;animation:blink_ 0.8s infinite;display:inline-block"></span>🔴 {active_count} ACTIVE</span>'
        if active_count > 0 else
        '<span style="display:inline-flex;align-items:center;gap:6px;background:rgba(74,222,128,.1);border:1px solid rgba(74,222,128,.3);color:#4ade80;padding:5px 16px;border-radius:20px;font-size:13px;font-weight:700">✅ All Clear</span>'
    )

    active_banner = ''
    if active_count > 0:
        active_banner = f'''
        <div style="background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.25);border-radius:12px;padding:16px 20px;margin-bottom:20px;display:flex;align-items:center;gap:14px">
          <span style="font-size:28px">🚨</span>
          <div>
            <div style="font-weight:700;color:#ef4444;font-size:15px">{active_count} Active Emergency Alert{'s' if active_count != 1 else ''}</div>
            <div style="font-size:13px;color:#8b949e;margin-top:3px">Unresolved SOS alerts require immediate attention. Check rider location and contact emergency services if needed.</div>
          </div>
        </div>'''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SOS Alerts — LetsGo Admin</title>
<meta name="robots" content="noindex, nofollow">
{ADMIN_STYLE}
<style>table td{{max-width:180px;overflow:hidden;text-overflow:ellipsis}}</style>
</head>
<body>
{nav_html('sos')}
<div class="admin-main">
  <div class="page-header">
    <div>
      <h1>🆘 SOS Alerts</h1>
      <p>Emergency alerts triggered by riders in the LetsGo app</p>
    </div>
    <div style="display:flex;gap:12px;align-items:center">
      {active_pill}
      <span class="badge" id="sos-total-count">{len(alerts)} total</span>
    </div>
  </div>
  <div class="refresh-bar">Auto-refreshes every 10s &nbsp;|&nbsp; <span id="sos-last-updated">Updated just now</span></div>

  {active_banner}

  <div class="card">
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Rider</th>
            <th>Route</th>
            <th>Bus</th>
            <th>GPS</th>
            <th>Contacts</th>
            <th>Status</th>
            <th>Triggered</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="sos-tbody">{rows}</tbody>
      </table>
    </div>
  </div>
</div>

<div class="overlay" id="resolve-overlay">
  <div class="modal">
    <h3>✅ Mark as Resolved</h3>
    <p id="resolve-msg">Mark this SOS alert as resolved?</p>
    <div class="modal-btns">
      <button class="btn btn-ghost" onclick="closeModal('resolve-overlay')">Cancel</button>
      <button class="btn btn-success" id="confirm-resolve-btn">Mark Resolved</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>
{ADMIN_JS}
<script>
let pendingResolveId=null, pendingResolveToken=null;

function resolveAlert(id, token){{
  pendingResolveId=id; pendingResolveToken=token;
  document.getElementById('resolve-msg').textContent=`Mark SOS #${{id}} as resolved?`;
  openModal('resolve-overlay');
}}

document.getElementById('confirm-resolve-btn').addEventListener('click', async()=>{{
  if(!pendingResolveToken)return;
  closeModal('resolve-overlay');
  try{{
    const res=await fetch(`/api/safety/sos/${{pendingResolveToken}}/resolve`,{{method:'POST'}});
    const data=await res.json();
    if(res.ok){{showToast('✓ SOS marked resolved');refreshAlerts();}}
    else showToast('✗ '+(data.message||'Failed'),'error');
  }}catch(e){{showToast('✗ Request failed','error');}}
  pendingResolveId=null; pendingResolveToken=null;
}});

async function refreshAlerts(){{
  try{{
    const res=await fetch('/api/admin/sos-alerts');
    const data=await res.json();
    const tbody=document.getElementById('sos-tbody');
    if(!data.alerts||data.alerts.length===0){{
      tbody.innerHTML='<tr><td colspan="9" style="text-align:center;padding:48px;color:#484f58">No SOS alerts yet.</td></tr>';
      document.getElementById('sos-total-count').textContent='0 total';
      return;
    }}
    tbody.innerHTML=data.alerts.map(a=>{{
      const sc=a.resolved?'#4ade80':'#ef4444';
      const sbg=a.resolved?'rgba(74,222,128,.1)':'rgba(239,68,68,.12)';
      const sl=a.resolved?'Resolved':'ACTIVE';
      const dot=a.resolved?'':'<span style="width:6px;height:6px;border-radius:50%;background:#ef4444;display:inline-block;animation:blink_ 0.8s infinite;margin-right:4px"></span>';
      const names=(a.contacts||[]).slice(0,3).map(c=>c.name||'?').join(', ')+(a.contacts&&a.contacts.length>3?` +${{a.contacts.length-3}}`:'');
      const resolveBtn=a.resolved?'<span style="font-size:11px;color:#484f58;padding:0 8px">✓ Done</span>':`<button class="btn btn-success" style="font-size:12px;padding:5px 10px;margin-left:4px" onclick="resolveAlert(${{a.id}},'${{a.token}}')">Resolve</button>`;
      return `<tr id="sos-row-${{a.id}}">
        <td style="color:#6e7681;font-size:12px;font-family:monospace">#${{a.id}}</td>
        <td><div style="font-weight:600;color:#f0f6fc">${{a.username}}</div><div style="font-size:11px;color:#6e7681;margin-top:2px">${{a.phone||'—'}}</div></td>
        <td style="color:#8b949e;font-size:13px">${{a.routeId||'—'}}</td>
        <td style="color:#8b949e;font-size:13px">${{a.busId||'—'}}</td>
        <td><div style="font-family:monospace;font-size:11px;color:#8b949e">${{a.lat||'—'}}</div><div style="font-family:monospace;font-size:11px;color:#8b949e">${{a.lng||'—'}}</div></td>
        <td style="max-width:160px">${{names?`<span style="color:#f0f6fc;font-size:12px">${{names}}</span>`:'<span style="color:#484f58">None</span>'}}<div style="font-size:10px;color:#484f58;margin-top:2px">${{(a.contacts||[]).length}} contact(s)</div></td>
        <td><span style="display:inline-flex;align-items:center;background:${{sbg}};color:${{sc}};padding:4px 11px;border-radius:20px;font-size:11px;font-weight:700;border:1px solid ${{sc}}33">${{dot}}${{sl}}</span></td>
        <td class="date-cell">${{a.createdAt}}</td>
        <td><a href="/sos/${{a.token}}" target="_blank" class="btn btn-ghost" style="font-size:12px;padding:5px 10px">View</a>${{resolveBtn}}</td>
      </tr>`;
    }}).join('');
    document.getElementById('sos-total-count').textContent=data.total+' total';
    document.getElementById('sos-last-updated').textContent='Updated '+new Date().toLocaleTimeString();
  }}catch(e){{console.error(e);}}
}}
setInterval(refreshAlerts,10000);
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════

@app.route('/ping')
def ping():
    return jsonify({'status': 'ok'}), 200


@app.route('/api/auth/signup/', methods=['POST'])
def signup():
    data = request.get_json()
    full_name = data.get('fullName', '').strip()
    username = data.get('username', '').strip()
    phone_number = data.get('phoneNumber', '').strip()  # optional
    password = data.get('password', '')

    if not all([full_name, username, password]):
        return jsonify({'message': 'Full name, username, and password are required'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'Username already exists'}), 409

    new_user = User(
        username=username,
        full_name=full_name,
        phone_number=phone_number,  # stored if provided, empty string if not
        password=generate_password_hash(password)
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'user': {
        'id': str(new_user.id),
        'username': new_user.username,
        'fullName': new_user.full_name,
        'phoneNumber': new_user.phone_number,
    }}), 201


@app.route('/api/auth/login/', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({'message': 'Invalid username or password'}), 401

    return jsonify({'user': {
        'id': str(user.id),
        'username': user.username,
        'fullName': user.full_name,
        'phoneNumber': user.phone_number,
    }}), 200


@app.route('/api/auth/delete-account', methods=['POST'])
def delete_own_account():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '')

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({'message': 'Incorrect username or password'}), 401

    # ── Delete all associated data ────────────────────────
    EmergencyContact.query.filter_by(username=username).delete()
    TrackingSession.query.filter_by(username=username).delete()
    SOSAlert.query.filter_by(username=username).delete()
    SMSLog.query.filter_by(username=username).delete()
    CommunityReport.query.filter_by(username=username).delete()
    db.session.delete(user)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Account and all associated data permanently deleted.'
    }), 200


@app.route('/delete-account', methods=['GET', 'POST'])
def delete_account_page():
    error = ''
    success = False

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm') or ''

        if confirm != 'DELETE':
            error = 'Type DELETE in the confirmation box to proceed.'
        elif not username or not password:
            error = 'Username and password are required.'
        else:
            user = User.query.filter_by(username=username).first()
            if not user or not check_password_hash(user.password, password):
                error = 'Incorrect username or password.'
            else:
                EmergencyContact.query.filter_by(username=username).delete()
                TrackingSession.query.filter_by(username=username).delete()
                SOSAlert.query.filter_by(username=username).delete()
                SMSLog.query.filter_by(username=username).delete()
                CommunityReport.query.filter_by(username=username).delete()
                db.session.delete(user)
                db.session.commit()
                success = True

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Delete Account — LetsGo Cayman</title>
<meta name="robots" content="noindex, nofollow">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:#0a0f1e;--surface:#111827;--surface2:#1a2235;
    --accent:#00d4aa;--red:#ef4444;--red-bg:rgba(239,68,68,.08);
    --red-border:rgba(239,68,68,.25);
    --text:#e8edf5;--text-muted:#8fa0b8;--border:rgba(0,212,170,0.15);
    --gradient:linear-gradient(135deg,#00d4aa 0%,#0099ff 100%);
  }}
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  body{{
    font-family:'DM Sans',sans-serif;font-weight:300;
    background:var(--bg);color:var(--text);
    min-height:100vh;display:flex;flex-direction:column;
  }}
  .topbar{{
    background:rgba(10,15,30,.95);backdrop-filter:blur(12px);
    border-bottom:1px solid var(--border);
    padding:18px 40px;display:flex;align-items:center;
    justify-content:space-between;
  }}
  .logo{{
    font-family:'Syne',sans-serif;font-weight:800;font-size:20px;
    background:var(--gradient);-webkit-background-clip:text;
    -webkit-text-fill-color:transparent;background-clip:text;
    letter-spacing:.04em;text-transform:uppercase;
  }}
  .back{{color:var(--accent);text-decoration:none;font-size:14px;font-weight:500}}
  .back:hover{{opacity:.7}}

  main{{
    flex:1;display:flex;align-items:center;justify-content:center;
    padding:48px 20px;
  }}

  .card{{
    background:var(--surface);border:1px solid var(--border);
    border-radius:16px;padding:40px;width:100%;max-width:460px;
  }}

  /* ── warning banner ── */
  .warn-banner{{
    background:var(--red-bg);border:1px solid var(--red-border);
    border-radius:10px;padding:16px 18px;
    display:flex;align-items:flex-start;gap:12px;margin-bottom:28px;
  }}
  .warn-icon{{font-size:20px;flex-shrink:0;line-height:1}}
  .warn-title{{font-family:'Syne',sans-serif;font-size:14px;font-weight:700;color:var(--red);margin-bottom:4px}}
  .warn-body{{font-size:13px;color:#f87171;line-height:1.6}}

  h1{{
    font-family:'Syne',sans-serif;font-size:22px;font-weight:800;
    margin-bottom:6px;color:var(--text);
  }}
  .subtitle{{font-size:14px;color:var(--text-muted);margin-bottom:28px;line-height:1.6}}

  /* ── form fields ── */
  .field{{margin-bottom:16px}}
  .field label{{
    display:block;font-size:11px;font-weight:600;
    color:var(--text-muted);text-transform:uppercase;
    letter-spacing:.7px;margin-bottom:7px;
  }}
  .field input{{
    width:100%;background:#0d1117;border:1px solid #30363d;
    border-radius:8px;padding:11px 14px;font-size:14px;
    color:var(--text);outline:none;font-family:'DM Sans',sans-serif;
    transition:border-color .2s;
  }}
  .field input:focus{{border-color:var(--accent)}}
  .field input.danger:focus{{border-color:var(--red)}}
  .field .hint{{font-size:12px;color:var(--text-muted);margin-top:6px}}

  /* ── error / success ── */
  .error-box{{
    background:var(--red-bg);border:1px solid var(--red-border);
    color:#f87171;padding:11px 14px;border-radius:8px;
    font-size:13px;margin-bottom:20px;display:flex;align-items:center;gap:8px;
  }}
  .success-wrap{{text-align:center;padding:16px 0}}
  .success-icon{{font-size:52px;margin-bottom:16px}}
  .success-title{{
    font-family:'Syne',sans-serif;font-size:20px;font-weight:800;
    color:var(--accent);margin-bottom:10px;
  }}
  .success-body{{font-size:14px;color:var(--text-muted);line-height:1.7;max-width:320px;margin:0 auto}}

  /* ── buttons ── */
  .btn-delete{{
    width:100%;background:var(--red);color:#fff;border:none;
    border-radius:10px;padding:13px;font-size:15px;font-weight:700;
    font-family:'Syne',sans-serif;cursor:pointer;margin-top:8px;
    transition:background .2s;letter-spacing:.03em;
  }}
  .btn-delete:hover{{background:#dc2626}}
  .btn-delete:disabled{{background:#374151;cursor:not-allowed;color:#6b7280}}

  .cancel-link{{
    display:block;text-align:center;margin-top:16px;
    font-size:13px;color:var(--text-muted);text-decoration:none;
  }}
  .cancel-link:hover{{color:var(--text)}}

  /* ── data list ── */
  .data-list{{
    background:#0d1117;border-radius:8px;
    padding:14px 16px;margin-bottom:20px;
  }}
  .data-list-title{{
    font-size:11px;font-weight:600;color:var(--text-muted);
    text-transform:uppercase;letter-spacing:.7px;margin-bottom:10px;
  }}
  .data-list ul{{list-style:none;display:flex;flex-direction:column;gap:6px}}
  .data-list li{{font-size:13px;color:#f87171;padding-left:16px;position:relative}}
  .data-list li::before{{content:'×';position:absolute;left:0;color:var(--red);font-weight:700}}

  footer{{
    text-align:center;padding:24px 20px;
    font-size:12px;color:var(--text-muted);
    border-top:1px solid var(--border);
  }}
  footer a{{color:var(--accent);text-decoration:none}}
</style>
</head>
<body>
<nav class="topbar">
  <div class="logo">LetsGo</div>
  <a href="/" class="back">← Back to site</a>
</nav>

<main>
  <div class="card">

    {'<!-- SUCCESS STATE -->' if success else ''}
    {'<div class="success-wrap"><div class="success-icon">✅</div><div class="success-title">Account deleted</div><p class="success-body">Your account and all associated data have been permanently removed from LetsGo Cayman. This cannot be undone.<br><br>Thank you for riding with us.</p></div>' if success else f'''
    <!-- FORM STATE -->
    <div class="warn-banner">
      <div class="warn-icon">⚠️</div>
      <div>
        <div class="warn-title">This action is permanent</div>
        <div class="warn-body">Your account cannot be recovered once deleted.</div>
      </div>
    </div>

    <h1>Delete your account</h1>
    <p class="subtitle">Enter your credentials to permanently delete your LetsGo account and all data associated with it.</p>

    <div class="data-list">
      <div class="data-list-title">Data that will be deleted</div>
      <ul>
        <li>Account profile and login credentials</li>
        <li>Emergency contacts</li>
        <li>Journey and tracking history</li>
        <li>SOS alert records</li>
        <li>Community reports</li>
        <li>SMS alert logs</li>
      </ul>
    </div>

    {"f'<div class=\\'error-box\\'>⚠ " + error + "</div>'" if error else ""}
    {"'<div class=\\'error-box\\'>⚠ ' + error + '</div>'" if error else ""}

    <form method="POST">
      <div class="field">
        <label>Username</label>
        <input type="text" name="username" autocomplete="username"
               placeholder="your username" required>
      </div>
      <div class="field">
        <label>Password</label>
        <input type="password" name="password" autocomplete="current-password"
               placeholder="••••••••" required>
      </div>
      <div class="field">
        <label>Type DELETE to confirm</label>
        <input type="text" name="confirm" class="danger"
               placeholder="DELETE" autocomplete="off" required
               oninput="document.getElementById(\\'del-btn\\').disabled = this.value !== \\'DELETE\\'">
        <div class="hint">Must be typed in all caps exactly as shown.</div>
      </div>
      <button type="submit" class="btn-delete" id="del-btn" disabled>
        Permanently Delete My Account
      </button>
    </form>
    <a href="/" class="cancel-link">Cancel — keep my account</a>
    '''}

  </div>
</main>

<footer>
  Questions? <a href="mailto:support@letsgocayman.com">support@letsgocayman.com</a>
  &nbsp;·&nbsp; <a href="/privacy">Privacy Policy</a>
  &nbsp;·&nbsp; <a href="/support">Help &amp; Support</a>
</footer>
</body>
</html>"""


@app.route('/api/users', methods=['GET'])
def api_users():
    users = User.query.order_by(User.created_at.desc()).all()
    current_twilio = {**TWILIO_CONFIG, **_twilio_override}
    return jsonify({
        'total': len(users),
        'users': [{
            'id': u.id,
            'username': u.username,
            'fullName': u.full_name,
            'phoneNumber': u.phone_number,
            'createdAt': u.created_at.strftime('%d %b %Y, %H:%M')
        } for u in users],
        'twilio': current_twilio,
        'config': {'twilio': current_twilio},
    })


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    username = user.username
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': f'User {username} deleted successfully'}), 200


@app.route('/api/users/<int:user_id>', methods=['PATCH'])
def update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    data = request.get_json()
    if 'username' in data:
        existing = User.query.filter_by(username=data['username']).first()
        if existing and existing.id != user_id:
            return jsonify({'message': 'Username already taken'}), 409
        user.username = data['username']
    if 'fullName' in data:
        user.full_name = data['fullName']
    if 'phoneNumber' in data:
        user.phone_number = data['phoneNumber']
    if 'password' in data and data['password']:
        user.password = generate_password_hash(data['password'])

    db.session.commit()
    return jsonify({'message': 'User updated', 'user': {
        'id': user.id, 'username': user.username,
        'fullName': user.full_name, 'phoneNumber': user.phone_number,
    }}), 200


@app.route('/api/community/reports/', methods=['GET', 'POST'])
def community_reports():
    if request.method == 'GET':
        reports = CommunityReport.query.order_by(CommunityReport.created_at.desc()).all()
        return jsonify({
            'total': len(reports),
            'reports': [{
                'id': r.id,
                'category': r.category,
                'message': r.message,
                'stopName': r.stop_name,
                'routeId': r.route_id,
                'upvotes': r.upvotes,
                'upvotedByMe': False,
                'status': r.status,
                'username': r.username,
                'createdAt': r.created_at.isoformat(),
            } for r in reports]
        })

    data = request.get_json()
    if not data:
        return jsonify({'message': 'No data provided'}), 400

    report = CommunityReport(
        category=data.get('category', 'other'),
        message=data.get('message', ''),
        stop_name=data.get('stopName', ''),
        route_id=data.get('routeId', 'Any'),
        username=data.get('username', 'anonymous'),
    )
    db.session.add(report)
    db.session.commit()

    return jsonify({'report': {
        'id': report.id,
        'category': report.category,
        'message': report.message,
        'stopName': report.stop_name,
        'routeId': report.route_id,
        'upvotes': 0,
        'upvotedByMe': False,
        'status': report.status,
        'username': report.username,
        'createdAt': report.created_at.isoformat(),
    }}), 201


@app.route('/api/community/reports/<int:report_id>', methods=['PATCH', 'DELETE'])
def community_report_detail(report_id):
    report = db.session.get(CommunityReport, report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404

    if request.method == 'DELETE':
        db.session.delete(report)
        db.session.commit()
        return jsonify({'message': f'Report #{report_id} deleted'}), 200

    data = request.get_json()
    if 'status' in data:
        report.status = data['status']
    if 'message' in data:
        report.message = data['message']
    db.session.commit()
    return jsonify({'message': 'Report updated'}), 200


@app.route('/api/community/reports/<int:report_id>/upvote/', methods=['POST'])
def upvote_report(report_id):
    report = db.session.get(CommunityReport, report_id)
    if not report:
        return jsonify({'message': 'Report not found'}), 404

    data = request.get_json() or {}
    username = data.get('username', 'anonymous')

    upvoted_list = json.loads(report.upvoted_by or '[]')
    if username in upvoted_list:
        upvoted_list.remove(username)
        report.upvotes = max(0, report.upvotes - 1)
        action = 'removed'
    else:
        upvoted_list.append(username)
        report.upvotes += 1
        action = 'added'

    report.upvoted_by = json.dumps(upvoted_list)
    db.session.commit()
    return jsonify({'upvotes': report.upvotes, 'action': action}), 200


# ── TWILIO HELPER ──────────────────────────────────────────
def _send_twilio(to_number, message_body, log_meta=None):
    """Send SMS via Twilio and log to SMSLog table.

    log_meta (optional dict) keys:
      username, message_type, route_id, bus_id, bus_name,
      eta_minutes, lat, lng, track_url
    """
    import urllib.request, urllib.parse, base64
    current_twilio = {**TWILIO_CONFIG, **_twilio_override}
    account_sid = current_twilio.get('accountSid', '').strip()
    auth_token = current_twilio.get('authToken', '').strip()
    from_number = current_twilio.get('fromNumber', '').strip()

    if not all([account_sid, auth_token, from_number]):
        _log_sms(to_number, message_body, False, 'Twilio credentials not configured', log_meta)
        return False, 'Twilio credentials not configured'

    to_clean = ''.join(c for c in to_number if c.isdigit() or c == '+')
    if not to_clean.startswith('+'):
        to_clean = '+' + to_clean

    url = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'
    payload = urllib.parse.urlencode({'To': to_clean, 'From': from_number, 'Body': message_body}).encode('utf-8')
    credentials = base64.b64encode(f'{account_sid}:{auth_token}'.encode()).decode()
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Authorization', f'Basic {credentials}')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    req.add_header('Accept', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        sid = result.get('sid', '')
        status = result.get('status', '')
        if sid:
            detail = f'Sent (sid={sid}, status={status})'
            _log_sms(to_number, message_body, True, detail, log_meta)
            return True, detail
        detail = f'Twilio error: {result.get("message", "unknown")}'
        _log_sms(to_number, message_body, False, detail, log_meta)
        return False, detail
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        detail = f'HTTP {e.code}: {body[:300]}'
        _log_sms(to_number, message_body, False, detail, log_meta)
        return False, detail
    except Exception as ex:
        detail = str(ex)
        _log_sms(to_number, message_body, False, detail, log_meta)
        return False, detail


def _log_sms(to_phone, body, sent, detail, meta=None):
    """Write a row to SMSLog. Never raises — swallows DB errors."""
    try:
        m = meta or {}
        log = SMSLog(
            username=m.get('username', ''),
            to_phone=to_phone,
            message_type=m.get('message_type', 'general'),
            route_id=m.get('route_id', ''),
            bus_id=m.get('bus_id', ''),
            bus_name=m.get('bus_name', ''),
            eta_minutes=int(m.get('eta_minutes', 0) or 0),
            lat=m.get('lat', ''),
            lng=m.get('lng', ''),
            track_url=m.get('track_url', ''),
            body_preview=body[:200],
            sent=sent,
            twilio_detail=detail[:200],
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


@app.route('/api/safety/send-sms', methods=['POST'])
def send_sms():
    data = request.get_json(force=True, silent=True) or {}
    to_number = (data.get('to') or data.get('toNumber') or '').strip()
    message = (data.get('message') or data.get('body') or '').strip()
    if not to_number or not message:
        return jsonify({'success': False, 'message': '"to" and "message" are required'}), 400
    meta = {
        'username': data.get('username', ''),
        'message_type': 'general',
        'route_id': data.get('routeId', ''),
        'bus_id': data.get('busId', ''),
        'lat': data.get('lat', ''),
        'lng': data.get('lng', ''),
        'track_url': data.get('trackUrl', ''),
    }
    ok, info = _send_twilio(to_number, message, meta)
    if ok:
        return jsonify({'success': True, 'message': 'SMS sent', 'detail': info}), 200
    return jsonify({'success': False, 'message': info}), 500


@app.route('/api/safety/offline-sms', methods=['POST'])
def offline_sms():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get('username') or 'Unknown rider').strip()
    phone_number = (data.get('phoneNumber') or data.get('phone') or '').strip()
    route_id = str(data.get('routeId') or data.get('route') or 'Unknown')
    bus_id = str(data.get('busId') or data.get('bus') or 'Unknown')
    lat = str(data.get('lat') or data.get('latitude') or '')
    lng = str(data.get('lng') or data.get('longitude') or '')
    eta_min = int(data.get('eta') or 5)

    if not phone_number:
        user = User.query.filter_by(username=username).first()
        if user:
            phone_number = user.phone_number

    location_str = ''
    maps_url = ''
    if lat and lng and lat != 'None' and lng != 'None':
        maps_url = f'https://maps.google.com/?q={lat},{lng}'
        location_str = f'\n📍 Last location: {maps_url}'

    results = []
    if phone_number:
        rider_body = (
            f"🚌 LetsGo: Hi {username}, your phone lost signal.\n"
            f"Bus {bus_id} | Route {route_id}\n"
            f"You are approximately {eta_min} min from your stop.{location_str}\n"
            f"Stay safe — your journey is being tracked."
        )
        meta = {'username': username, 'message_type': 'offline', 'route_id': route_id,
                'bus_id': bus_id, 'lat': lat, 'lng': lng, 'eta_minutes': eta_min}
        ok, info = _send_twilio(phone_number, rider_body, meta)
        results.append({'to': 'rider', 'phone': phone_number, 'sent': ok, 'detail': info})

    saved_contacts = EmergencyContact.query.filter_by(username=username).all()
    for c in saved_contacts:
        contact_body = (
            f"🚌 LetsGo Update: {username} is on Bus {bus_id} (Route {route_id}) "
            f"and will be arriving in approximately {eta_min} min.{location_str}\n"
            f"Their phone is currently offline."
        )
        meta = {'username': username, 'message_type': 'offline', 'route_id': route_id,
                'bus_id': bus_id, 'lat': lat, 'lng': lng, 'eta_minutes': eta_min}
        ok, info = _send_twilio(c.phone_number, contact_body, meta)
        results.append({'to': c.contact_name, 'phone': c.phone_number, 'sent': ok, 'detail': info})

    any_sent = any(r['sent'] for r in results)
    return jsonify({
        'success': any_sent,
        'message': 'Offline SMS sent' if any_sent else 'No SMS could be sent',
        'results': results,
    }), 200 if any_sent else 500


@app.route('/api/emergency-contacts', methods=['GET'])
def get_emergency_contacts():
    username = request.args.get('username', '').strip()
    if not username:
        return jsonify({'contacts': []}), 200
    contacts = EmergencyContact.query.filter_by(username=username).all()
    return jsonify({'contacts': [
        {'id': c.id, 'name': c.contact_name, 'phone': c.phone_number}
        for c in contacts
    ]})


@app.route('/api/emergency-contacts', methods=['POST'])
def save_emergency_contacts():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get('username') or '').strip()
    contacts = data.get('contacts') or []
    if not username:
        return jsonify({'message': 'username required'}), 400
    EmergencyContact.query.filter_by(username=username).delete()
    for c in contacts:
        name = (c.get('name') or '').strip()
        phone = (c.get('phone') or c.get('phoneNumber') or '').strip()
        if name and phone:
            db.session.add(EmergencyContact(username=username, contact_name=name, phone_number=phone))
    db.session.commit()
    return jsonify({'success': True}), 200


@app.route('/api/sms/offline', methods=['POST'])
def sms_offline_reminder():
    """
    Offline bus reminder SMS.
    Sends to the rider's own number:
      "Hey {username} don't worry I'm just {eta} min from you 🚌  Track: {url}"
    Also notifies any saved emergency contacts.
    Everything is logged to SMSLog for the admin SMS Alerts page.
    """
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get('username') or 'Rider').strip()
    phone_number = (data.get('phoneNumber') or data.get('phone') or '').strip()
    route_id = str(data.get('routeId') or data.get('route') or 'Unknown')
    bus_id = str(data.get('busId') or data.get('bus') or 'Unknown')
    bus_name = str(data.get('busName') or '')
    lat = str(data.get('lat') or data.get('latitude') or '')
    lng = str(data.get('lng') or data.get('longitude') or '')
    eta_min = int(data.get('eta') or data.get('etaMinutes') or 5)
    track_token = (data.get('trackToken') or '').strip()

    # Fall back to DB phone if not provided in payload
    if not phone_number:
        user = User.query.filter_by(username=username).first()
        if user:
            phone_number = user.phone_number

    # Build tracking / maps URL
    if track_token:
        track_url = f'https://www.letsgocayman.com/track/{track_token}'
    elif lat and lng:
        track_url = f'https://maps.google.com/?q={lat},{lng}'
    else:
        track_url = 'https://www.letsgocayman.com'

    results = []

    # ── SMS to the rider ──────────────────────────────────
    if phone_number:
        bus_label = f"Bus {bus_id}" + (f" ({bus_name})" if bus_name else "")
        rider_body = (
            f"Hey {username} don't worry I'm just {eta_min} min from you 🚌\n"
            f"{bus_label} · Route {route_id}\n"
            f"Track live: {track_url}"
        )
        meta = {
            'username': username, 'message_type': 'offline',
            'route_id': route_id, 'bus_id': bus_id, 'bus_name': bus_name,
            'eta_minutes': eta_min, 'lat': lat, 'lng': lng, 'track_url': track_url,
        }
        ok, info = _send_twilio(phone_number, rider_body, meta)
        results.append({'to': username, 'phone': phone_number, 'sent': ok, 'detail': info})

    # ── SMS to saved emergency contacts ──────────────────
    for c in EmergencyContact.query.filter_by(username=username).all():
        contact_body = (
            f"Hey {c.contact_name}, {username} is on Bus {bus_id} (Route {route_id}) "
            f"and is about {eta_min} min from their stop.\n"
            f"Track live: {track_url}\n"
            f"Their phone is offline — LetsGo Cayman 🚌"
        )
        meta = {
            'username': username, 'message_type': 'offline',
            'route_id': route_id, 'bus_id': bus_id, 'bus_name': bus_name,
            'eta_minutes': eta_min, 'lat': lat, 'lng': lng, 'track_url': track_url,
        }
        ok, info = _send_twilio(c.phone_number, contact_body, meta)
        results.append({'to': c.contact_name, 'phone': c.phone_number, 'sent': ok, 'detail': info})

    if not results:
        return jsonify({
            'success': False,
            'message': 'No phone number found for this user and no emergency contacts saved.',
            'results': [],
        }), 400

    any_sent = any(r['sent'] for r in results)
    return jsonify({
        'success': any_sent,
        'message': 'Offline reminder SMS sent' if any_sent else 'SMS could not be delivered',
        'eta': eta_min,
        'trackUrl': track_url,
        'results': results,
    }), 200 if any_sent else 500


@app.route('/api/safety/sos', methods=['POST'])
def sos_alert():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get('username') or 'Unknown').strip()
    route_id = str(data.get('routeId') or 'Unknown')
    bus_id = str(data.get('busId') or 'Unknown')
    lat = str(data.get('lat') or data.get('latitude') or '19.2869')
    lng = str(data.get('lng') or data.get('longitude') or '-81.3674')
    contacts = data.get('emergencyContacts') or []

    if not contacts:
        saved = EmergencyContact.query.filter_by(username=username).all()
        contacts = [{'name': c.contact_name, 'phone': c.phone_number} for c in saved]

    if contacts:
        EmergencyContact.query.filter_by(username=username).delete()
        for c in contacts:
            nm = (c.get('name') or '').strip()
            ph = (c.get('phone') or c.get('phoneNumber') or '').strip()
            if nm and ph:
                db.session.add(EmergencyContact(username=username, contact_name=nm, phone_number=ph))

    sos = SOSAlert(
        username=username,
        phone_number=data.get('phoneNumber') or '',
        route_id=route_id,
        bus_id=bus_id,
        lat=lat,
        lng=lng,
        contacts=json.dumps(contacts),
    )
    db.session.add(sos)
    db.session.commit()

    sos_url = f'https://www.letsgocayman.com/sos/{sos.token}'
    maps_url = f'https://maps.google.com/?q={lat},{lng}'

    sms_results = []
    for contact in contacts:
        cphone = (contact.get('phone') or contact.get('phoneNumber') or '').strip()
        cname = (contact.get('name') or 'Contact')
        if not cphone:
            continue
        sms_body = (
            f"🚨 HELP NEEDED — {username} needs help!\n"
            f"They pressed SOS on Bus {bus_id} (Route {route_id}).\n"
            f"📍 Location: {maps_url}\n"
            f"🔗 Live SOS page: {sos_url}\n"
            f"👉 Call 911 if urgent."
        )
        meta = {'username': username, 'message_type': 'sos', 'route_id': route_id,
                'bus_id': bus_id, 'lat': lat, 'lng': lng, 'track_url': sos_url}
        ok, info = _send_twilio(cphone, sms_body, meta)
        sms_results.append({'contact': cname, 'phone': cphone, 'sent': ok, 'detail': info})

    return jsonify({
        'success': True,
        'sosId': sos.token,
        'sosUrl': sos_url,
        'smsResults': sms_results,
    }), 201


@app.route('/api/bus/location/', methods=['POST'])
def bus_location():
    data = request.get_json()

    if not data or 'lat' not in data or 'lng' not in data:
        return jsonify({"error": "Missing lat/lng"}), 400

    session = TrackingSession.query.filter_by(
        bus_id='CaymanBus', active=True
    ).first()

    if not session:
        session = TrackingSession(
            bus_id='CaymanBus',
            route_id='CaymanBus',
            bus_name='Cayman Bus',
            username='pi',
            phone_number='',
            contact_name='',
            contact_phone='',
            active=True,
            token=uuid.uuid4().hex,  # 32 chars, no dashes
        )
        db.session.add(session)

    session.lat = data['lat']
    session.lng = data['lng']
    session.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"status": "ok"}), 200


@app.route('/api/tracking/start', methods=['POST'])
def start_tracking():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get('username') or 'Unknown').strip()
    route_id = data.get('routeId') or 'WB1'
    bus_id = data.get('busId') or 'CI-WB1-01'
    bus_name = data.get('busName') or 'West Bay Route 1'
    lat = data.get('lat') or '19.3465'
    lng = data.get('lng') or '-81.3958'
    contact_name = data.get('contactName') or ''
    contact_phone = (data.get('contactPhone') or '').strip()

    session_obj = TrackingSession(
        username=username,
        phone_number=data.get('phoneNumber') or '',
        route_id=str(route_id),
        bus_id=str(bus_id),
        bus_name=str(bus_name),
        lat=str(lat),
        lng=str(lng),
        contact_name=contact_name,
        contact_phone=contact_phone,
    )
    db.session.add(session_obj)
    db.session.commit()

    track_url = f'https://www.letsgocayman.com/track/{session_obj.token}'
    if contact_phone:
        body = (
            f'🚌 {username} is sharing their journey with you!\n'
            f'Bus: {bus_id} ({bus_name})\n'
            f'Track them live: {track_url}'
        )
        meta = {'username': username, 'message_type': 'journey_share', 'route_id': str(route_id),
                'bus_id': str(bus_id), 'bus_name': str(bus_name), 'lat': str(lat), 'lng': str(lng),
                'track_url': track_url}
        _send_twilio(contact_phone, body, meta)

    return jsonify({'success': True, 'token': session_obj.token, 'trackUrl': track_url}), 201


@app.route('/api/tracking/update', methods=['POST'])
def update_tracking():
    data = request.get_json(force=True, silent=True) or {}
    token = data.get('token') or ''
    sess = TrackingSession.query.filter_by(token=token, active=True).first()
    if not sess:
        return jsonify({'success': False, 'message': 'Session not found'}), 404
    if 'lat' in data:
        sess.lat = str(data['lat'])
    if 'lng' in data:
        sess.lng = str(data['lng'])
    if 'busId' in data:
        sess.bus_id = data['busId']
    sess.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True}), 200


@app.route('/api/tracking/stop', methods=['POST'])
def stop_tracking():
    data = request.get_json(force=True, silent=True) or {}
    token = data.get('token') or ''
    sess = TrackingSession.query.filter_by(token=token).first()
    if sess:
        sess.active = False
        db.session.commit()
    return jsonify({'success': True}), 200


@app.route('/api/tracking/position/<token>')
def tracking_position(token):
    sess = TrackingSession.query.filter_by(token=token, active=True).first()
    if not sess:
        return jsonify({'active': False}), 404
    return jsonify({'lat': sess.lat, 'lng': sess.lng, 'active': True,
                    'busId': sess.bus_id, 'updatedAt': sess.updated_at.isoformat() if sess.updated_at else None})


CAYMAN_ROUTES = [
    # ── Route 7A ────────────────────────────────────────────────────────────
    # Frank Sound Jct -> Old Man Bay -> Queens Hwy -> East End
    # (Source: Bus Stop and Shelter List from FS Jct, 2026)
    {
        'route_number': '7A',
        'name': 'Frank Sound Junction – Old Man Bay – Queens Highway – East End',
        'color': '#FF5722',
        'frequency': 'Every 5–10 minutes',
        'description': 'Frank Sound Junction • Clifton Hunter • Crystal Caves • Old Man Bay Dock • Bo Miller Public Beach • Morritts • Wyndham • Colliers • Cayman Parrot Sanctuary • Wreck of the Ten Sails • Compass Point • George Dixon Park • East End Primary • Health City • South Coast • Botanic Garden • Blow Holes',
        'stops': [
            ('Frank Sound Junction Bus Shelter', 19.3110, -81.1530),
            ('Clifton Hunter High School Bus Shelter', 19.3097, -81.1831),
            ('Crystal Caves Bus Stop', 19.3480, -81.1980),
            ('Old Man Bay Dock Bus Stop', 19.3735, -81.2105),
            ('Bo Miller Public Beach Bus Stop (towards EE)', 19.3150, -81.1150),
            ('Bo Miller Public Beach Bus Stop (towards NS)', 19.3160, -81.1160),
            ('Old Robin Rd Bus Stop', 19.3120, -81.1080),
            ('Morritts Shopping Center Bus Shelter', 19.3080, -81.1000),
            ('Wyndham Bus Shelter', 19.3050, -81.0950),
            ('Colliers Beach Bus Shelter', 19.3100, -81.1020),
            ('Cayman Parrot Sanctuary Bus Stop', 19.3000, -81.0900),
            ('Cayman Parrot Sanctuary Bus Stop (towards Tukka)', 19.3010, -81.0910),
            ('Wreck of the Ten Sails Bus Shelter', 19.2880, -81.0700),
            ('Compass Point Bus Stop', 19.2990, -81.1060),
            ('George Dixon Park Bus Shelter', 19.3030, -81.0930),
            ('East End Primary School Bus Shelter', 19.3020, -81.0910),
            ('Health City Bus Shelter', 19.2980, -81.0890),
            ('South Coast Bar and Grill Bus Shelter', 19.2900, -81.1000),
            ('H.M. Botanic Garden (entrance)', 19.3170, -81.1360),
            ('Blow Holes (Sea View Rd)', 19.2980, -81.0680),
        ]
    },

    # ── Route 8A ────────────────────────────────────────────────────────────
    # Frank Sound Jct -> Old Man Bay -> Hutland -> Rum Point -> Cayman Kai
    {
        'route_number': '8A',
        'name': 'Frank Sound Junction – Old Man Bay – Hutland – Rum Point – Cayman Kai',
        'color': '#4CAF50',
        'frequency': 'Every 30 minutes',
        'description': 'Frank Sound Junction • Clifton Hunter • Crystal Caves • Old Man Bay Dock • National Housing Development Trust • Melville\u2019s Lane • Rum Point • Kaibo • Cayman Kai • Chisholm\u2019s Cemetery • Hutland • Over the Edge • Compass Point • North Side Public Beach #5 • South Coast • Botanic Garden',
        'stops': [
            ('Frank Sound Junction Bus Shelter', 19.3110, -81.1530),
            ('Clifton Hunter High School Bus Shelter', 19.3097, -81.1831),
            ('Crystal Caves Bus Stop', 19.3480, -81.1980),
            ('Old Man Bay Dock Bus Shelter', 19.3730, -81.2110),
            ('National Housing Development Trust Bus Shelter', 19.3780, -81.2050),
            ("Melville's Lane Bus Stop", 19.3760, -81.1990),
            ('Rum Point Bus Stop', 19.3640, -81.2600),
            ('Rum Point Bus Shelter', 19.3655, -81.2630),
            ('Rum Point Bus Stop #2', 19.3670, -81.2660),
            ('Kaibo Bus Stop', 19.3580, -81.2530),
            ('Cayman Kai Public Beach Bus Stop', 19.3850, -81.2790),
            ('Rum Point Exit Sign Bus Stop', 19.3600, -81.2580),
            ("Rum Point Otto's Ave Bus Stop", 19.3620, -81.2610),
            ("Chisholm's Cemetery Bus Stop", 19.3500, -81.2400),
            ('Hutland Bus Shelter', 19.3450, -81.2300),
            ('Old Man Bay Dock Bus Stop', 19.3735, -81.2105),
            ('Over the Edge Bus Shelter', 19.3680, -81.2670),
            ('Compass Point Bus Stop', 19.2990, -81.1060),
            ('North Side Public Beach #5', 19.3730, -81.2010),
            ('South Coast Bar and Grill Bus Shelter', 19.2900, -81.1000),
            ('H.M. Botanic Garden (entrance)', 19.3170, -81.1360),
        ]
    },

    # ── Route 9A ────────────────────────────────────────────────────────────
    # Frank Sound Jct -> Old Man Bay -> Queens Hwy -> East End (opposite direction of 7A)
    {
        'route_number': '9A',
        'name': 'Frank Sound Junction – Queens Highway – Gun Bay – East End',
        'color': '#009688',
        'frequency': 'Every 5–10 minutes',
        'description': 'Frank Sound Junction • Clifton Hunter • Crystal Caves • Old Man Bay Dock • Bo Miller Public Beach • Morritts • Wyndham • Colliers • Cayman Parrot Sanctuary • Wreck of the Ten Sails • Compass Point • George Dixon Park • East End Primary • Health City • South Coast • Botanic Garden • Blow Holes',
        'stops': [
            ('Frank Sound Junction Bus Shelter', 19.3110, -81.1530),
            ('Clifton Hunter High School Bus Shelter', 19.3097, -81.1831),
            ('Crystal Caves Bus Stop', 19.3480, -81.1980),
            ('Old Man Bay Dock Bus Stop', 19.3735, -81.2105),
            ('Bo Miller Public Beach Bus Stop (towards EE)', 19.3150, -81.1150),
            ('Bo Miller Public Beach Bus Stop (towards NS)', 19.3160, -81.1160),
            ('Old Robin Rd Bus Stop', 19.3120, -81.1080),
            ('Morritts Shopping Center Bus Shelter', 19.3080, -81.1000),
            ('Wyndham Bus Shelter', 19.3050, -81.0950),
            ('Colliers Beach Bus Shelter', 19.3100, -81.1020),
            ('Cayman Parrot Sanctuary Bus Stop', 19.3000, -81.0900),
            ('Cayman Parrot Sanctuary Bus Stop (towards Tukka)', 19.3010, -81.0910),
            ('Wreck of the Ten Sails Bus Shelter', 19.2880, -81.0700),
            ('Compass Point Bus Stop', 19.2990, -81.1060),
            ('George Dixon Park Bus Shelter', 19.3030, -81.0930),
            ('East End Primary School Bus Shelter', 19.3020, -81.0910),
            ('Health City Bus Shelter', 19.2980, -81.0890),
            ('South Coast Bar and Grill Bus Shelter', 19.2900, -81.1000),
            ('H.M. Botanic Garden (entrance)', 19.3170, -81.1360),
            ('Blow Holes (Sea View Rd)', 19.2980, -81.0680),
        ]
    },
]


@app.route('/api/buses/registered', methods=['GET', 'POST'])
def buses_registered():
    # ── POST: driver app pushes lat/lng ───────────────────────────────────
    if request.method == 'POST':
        data = request.get_json(force=True, silent=True) or {}
        bus_id = (data.get('busId') or '').strip()
        active = data.get('active', True)

        if not bus_id:
            return jsonify({'error': 'busId is required'}), 400

        lat = data.get('lat')
        lng = data.get('lng')

        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            if active:
                return jsonify({'error': 'lat and lng are required when active=true'}), 400
            lat = lng = None

        # ── FIX: update ALL rows for this bus_id, not just .first() ──────
        sessions = TrackingSession.query.filter_by(bus_id=bus_id).all()
        if not sessions:
            sess = TrackingSession(
                bus_id=bus_id,
                route_id=data.get('routeId') or bus_id,
                bus_name=data.get('busName') or bus_id,
                username=data.get('username') or bus_id,
                phone_number=data.get('phoneNumber') or '',
                lat=str(lat) if lat is not None else '0',
                lng=str(lng) if lng is not None else '0',
                active=active,
            )
            db.session.add(sess)
        else:
            for sess in sessions:
                if lat is not None:
                    sess.lat = str(lat)
                    sess.lng = str(lng)
                sess.active = active
                sess.updated_at = datetime.utcnow()
            sess = sessions[-1]  # keep reference for response

        db.session.commit()

        return jsonify({
            'ok': True,
            'busId': bus_id,
            'online': active,
            'lat': lat,
            'lng': lng,
            'updatedAt': sess.updated_at.isoformat(),
        }), 200

    # ── GET ───────────────────────────────────────────────────────────────
    """
    Returns every bus/route row saved in the DriverRoute table,
    each enriched with its current live location (if active).

    Optional query params:
      ?busId=WestBayBus   → single bus by busId
      ?driverName=James   → all buses for one driver
    """
    bus_id_filter = request.args.get('busId', '').strip()
    driver_filter = request.args.get('driverName', '').strip()

    # ── 1. Live locations keyed by bus_id ─────────────────────────────────
    active_sessions = TrackingSession.query.filter_by(active=True).all()
    live_by_bus = {}
    for s in active_sessions:
        try:
            live_by_bus[s.bus_id] = {
                'busId': s.bus_id,
                'lat': float(s.lat),
                'lng': float(s.lng),
                'updatedAt': s.updated_at.isoformat() if s.updated_at else None,
            }
        except (ValueError, TypeError):
            continue

    # ── 2. Fetch latest DriverRoute row per bus_id ────────────────────────
    from sqlalchemy import func

    latest_ids = (
        db.session.query(func.max(DriverRoute.id))
        .group_by(DriverRoute.bus_id)
        .all()
    )
    latest_id_list = [row[0] for row in latest_ids if row[0] is not None]

    drivers = (
        DriverRoute.query
        .filter(DriverRoute.id.in_(latest_id_list))
        .order_by(DriverRoute.route_name)
        .all()
    )

    # ── 3. Apply optional filters ─────────────────────────────────────────
    if bus_id_filter:
        drivers = [d for d in drivers if d.bus_id == bus_id_filter]
    if driver_filter:
        drivers = [
            d for d in drivers
            if (d.driver_name or '').lower() == driver_filter.lower()
        ]

    if not drivers:
        msg = (
            f"No bus found with busId '{bus_id_filter}'"
            if bus_id_filter else
            f"No buses found for driver '{driver_filter}'"
            if driver_filter else
            'No registered buses found'
        )
        return jsonify({'error': msg, 'buses': []}), 404

    # ── 4. Parse stops JSON ───────────────────────────────────────────────
    def parse_stops(stops_json, route_id):
        try:
            raw = json.loads(stops_json or '[]')
        except (json.JSONDecodeError, TypeError):
            return []

        parsed = []
        for i, s in enumerate(raw):
            try:
                if isinstance(s, (list, tuple)):
                    name = str(s[0]) if len(s) > 0 else 'Stop'
                    lat = float(s[1]) if len(s) > 1 else 0.0
                    lng = float(s[2]) if len(s) > 2 else 0.0
                elif isinstance(s, dict):
                    name = (s.get('name') or s.get('stopName') or
                            s.get('stop_name') or 'Stop')
                    lat = float(s.get('lat') or s.get('latitude') or 0)
                    lng = float(s.get('lng') or s.get('longitude') or 0)
                else:
                    continue

                if lat == 0.0 and lng == 0.0:
                    continue

                parsed.append({
                    'id': f"{route_id}-S{i + 1:02}",
                    'name': name,
                    'lat': lat,
                    'lng': lng,
                })
            except (ValueError, TypeError, IndexError):
                continue

        return parsed

    # ── 5. Build response ─────────────────────────────────────────────────
    results = []
    for d in drivers:
        stops = parse_stops(d.stops_json, d.route_id or d.bus_id)
        live = live_by_bus.get(d.bus_id)
        is_online = live is not None

        results.append({
            'busId': d.bus_id,
            'routeId': d.route_id,
            'routeName': d.route_name,
            'driverName': d.driver_name,
            'color': d.route_color or '#F5C518',
            'frequency': d.frequency or 'Every 15 minutes',
            'description': d.description or '',
            'stops': stops,
            'totalStops': len(stops),
            'liveLocation': live,
            'online': is_online,
            'registeredAt': d.created_at.isoformat() if d.created_at else None,
        })

    # ── 6. Single-bus shortcut ────────────────────────────────────────────
    if bus_id_filter and len(results) == 1:
        return jsonify(results[0]), 200

    return jsonify({
        'total': len(results),
        'onlineCount': sum(1 for r in results if r['online']),
        'buses': results,
    }), 200


# ── Standalone location endpoint (still works too) ────────────────────────
@app.route('/api/buses/location', methods=['POST'])
def update_bus_location():
    return buses_registered()


@app.route('/api/buses/coordinates', methods=['GET', 'POST'])
def buses_coordinates():
    # ── POST: driver app pushes lat/lng ───────────────────────────────────
    if request.method == 'POST':
        data = request.get_json(force=True, silent=True) or {}
        bus_id = (data.get('busId') or '').strip()
        active = data.get('active', True)

        if not bus_id:
            return jsonify({'error': 'busId is required'}), 400

        lat = data.get('lat')
        lng = data.get('lng')

        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            if active:
                return jsonify({'error': 'lat and lng are required when active=true'}), 400
            lat = lng = None

        # ── FIX: update ALL rows for this bus_id, not just .first() ──────
        sessions = TrackingSession.query.filter_by(bus_id=bus_id).all()
        if not sessions:
            sess = TrackingSession(
                bus_id=bus_id,
                route_id=data.get('routeId') or bus_id,
                bus_name=data.get('busName') or bus_id,
                username=data.get('username') or bus_id,
                phone_number=data.get('phoneNumber') or '',
                lat=str(lat) if lat is not None else '0',
                lng=str(lng) if lng is not None else '0',
                active=active,
            )
            db.session.add(sess)
        else:
            for sess in sessions:
                if lat is not None:
                    sess.lat = str(lat)
                    sess.lng = str(lng)
                sess.active = active
                sess.updated_at = datetime.utcnow()
            sess = sessions[-1]  # keep reference for response

        db.session.commit()

        return jsonify({
            'ok': True,
            'busId': bus_id,
            'online': active,
            'lat': lat,
            'lng': lng,
            'updatedAt': sess.updated_at.isoformat(),
        }), 200

    # ── GET ───────────────────────────────────────────────────────────────

    # ── 1. Raspberry Pi live location for CaymanBus (unchanged) ──────────
    pi_session = TrackingSession.query.filter_by(
        active=True, route_id='CaymanBus'
    ).order_by(TrackingSession.updated_at.desc()).first()

    cayman_bus_live = None
    if pi_session:
        try:
            cayman_bus_live = {
                'lat': float(pi_session.lat),
                'lng': float(pi_session.lng),
                'busId': pi_session.bus_id,
                'updatedAt': pi_session.updated_at.isoformat() if pi_session.updated_at else None,
            }
        except (ValueError, TypeError):
            cayman_bus_live = None

    # ── 2. All active sessions keyed by route_id and bus_id ──────────────
    active_sessions = TrackingSession.query.filter_by(active=True).all()
    live_by_route = {}
    live_by_bus = {}
    for s in active_sessions:
        try:
            loc = {
                'lat': float(s.lat),
                'lng': float(s.lng),
                'busId': s.bus_id,
                'updatedAt': s.updated_at.isoformat() if s.updated_at else None,
            }
            if s.route_id:
                live_by_route[s.route_id] = loc
            live_by_bus[s.bus_id] = loc
        except (ValueError, TypeError):
            continue

    # ── 3. Pull registered buses from DriverRoute ─────────────────────────
    from sqlalchemy import func

    latest_ids = (
        db.session.query(func.max(DriverRoute.id))
        .group_by(DriverRoute.bus_id)
        .all()
    )
    latest_id_list = [row[0] for row in latest_ids if row[0] is not None]

    registered_drivers = (
        DriverRoute.query
        .filter(DriverRoute.id.in_(latest_id_list))
        .order_by(DriverRoute.route_name)
        .all()
    )

    # Index registered buses by route_id so CAYMAN_ROUTES can check overlap
    registered_by_route = {d.route_id: d for d in registered_drivers if d.route_id}
    registered_by_bus = {d.bus_id: d for d in registered_drivers}

    def parse_stops(stops_json, route_id):
        try:
            raw = json.loads(stops_json or '[]')
        except (json.JSONDecodeError, TypeError):
            return []
        parsed = []
        for i, s in enumerate(raw):
            try:
                if isinstance(s, (list, tuple)):
                    name = str(s[0]) if len(s) > 0 else 'Stop'
                    lat = float(s[1]) if len(s) > 1 else 0.0
                    lng = float(s[2]) if len(s) > 2 else 0.0
                elif isinstance(s, dict):
                    name = (s.get('name') or s.get('stopName') or
                            s.get('stop_name') or 'Stop')
                    lat = float(s.get('lat') or s.get('latitude') or
                                s.get('Lat') or 0)
                    lng = float(s.get('lng') or s.get('lon') or
                                s.get('longitude') or s.get('Lng') or 0)
                else:
                    continue
                if lat == 0.0 and lng == 0.0:
                    continue
                parsed.append({
                    'id': f"{route_id}-S{i + 1:02}",
                    'name': name,
                    'lat': lat,
                    'lng': lng,
                })
            except (ValueError, TypeError, IndexError):
                continue
        return parsed

    # ── 4. Build CAYMAN_ROUTES (static) ───────────────────────────────────
    all_routes = []
    seen_route_ids = set()

    for route in CAYMAN_ROUTES:
        rid = route['route_number']
        seen_route_ids.add(rid)

        # Prefer DB stops for this route if a registered driver has them
        db_driver = registered_by_route.get(rid)
        if db_driver and db_driver.stops_json:
            stops = parse_stops(db_driver.stops_json, rid)
        else:
            stops = [
                {
                    'id': f"{rid}-S{i + 1:02}",
                    'name': name,
                    'lat': lat,
                    'lng': lng,
                }
                for i, (name, lat, lng) in enumerate(route['stops'])
            ]

        # CaymanBus always uses the Pi session; others use active sessions
        if rid == 'CaymanBus':
            live = cayman_bus_live
        else:
            live = live_by_route.get(rid) or (
                live_by_bus.get(db_driver.bus_id) if db_driver else None
            )

        route_data = {
            'route': rid,
            'routeName': route['name'],
            'color': route['color'],
            'frequency': route['frequency'],
            'description': route['description'],
            'stops': stops,
            'totalStops': len(stops),
            'liveLocation': live,
            'online': live is not None,
        }
        if db_driver:
            route_data['busId'] = db_driver.bus_id
            route_data['driverName'] = db_driver.driver_name
            route_data['registeredAt'] = (
                db_driver.created_at.isoformat() if db_driver.created_at else None
            )

        all_routes.append(route_data)

    # ── 5. Append registered buses NOT in CAYMAN_ROUTES ───────────────────
    for d in registered_drivers:
        if d.route_id in seen_route_ids:
            continue  # already handled above

        stops = parse_stops(d.stops_json, d.route_id or d.bus_id)
        live = live_by_bus.get(d.bus_id) or live_by_route.get(d.route_id)
        is_online = live is not None

        all_routes.append({
            'route': d.route_id or d.bus_id,
            'routeName': d.route_name,
            'color': d.route_color or '#F5C518',
            'frequency': d.frequency or 'Every 15 minutes',
            'description': d.description or '',
            'stops': stops,
            'totalStops': len(stops),
            'liveLocation': live,
            'online': is_online,
            'busId': d.bus_id,
            'driverName': d.driver_name,
            'registeredAt': d.created_at.isoformat() if d.created_at else None,
        })

    return jsonify({
        'routes': all_routes,
        'totalRoutes': len(all_routes),
        'totalStops': sum(len(r['stops']) for r in all_routes),
        'liveRoutesCount': sum(1 for r in all_routes if r.get('online')),
        'generatedAt': datetime.utcnow().isoformat() + 'Z',
    }), 200


@app.route('/support')
def support():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Support — LetsGo Cayman</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0f1e;
    --surface: #111827;
    --surface2: #1a2235;
    --accent: #00d4aa;
    --accent2: #0099ff;
    --gold: #F5C518;
    --red: #ef4444;
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

  /* ── Topbar ── */
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

  /* ── Hero ── */
  .hero {
    padding: 80px 40px 60px;
    max-width: 860px;
    margin: 0 auto;
    position: relative;
  }
  .hero::before {
    content: '';
    position: absolute;
    top: 0; left: -10%;
    width: 500px; height: 350px;
    background: radial-gradient(ellipse, rgba(0, 212, 170, 0.07) 0%, transparent 70%);
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
    margin-bottom: 20px;
  }
  h1 span {
    background: var(--gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .hero p {
    font-size: 17px;
    color: var(--text-muted);
    max-width: 560px;
    line-height: 1.75;
  }

  /* ── Main ── */
  .container {
    max-width: 860px;
    margin: 0 auto;
    padding: 0 40px 100px;
  }

  /* ── Contact card ── */
  .contact-hero {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 40px;
    margin-bottom: 60px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 32px;
    align-items: center;
  }
  .contact-hero-text h2 {
    font-family: 'Syne', sans-serif;
    font-size: 24px;
    font-weight: 700;
    margin-bottom: 12px;
  }
  .contact-hero-text p {
    color: var(--text-muted);
    font-size: 15px;
    line-height: 1.7;
  }
  .contact-actions {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .contact-btn {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    border-radius: 4px;
    text-decoration: none;
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0.03em;
    transition: opacity 0.2s;
  }
  .contact-btn:hover { opacity: 0.85; }
  .contact-btn-primary {
    background: var(--gradient);
    color: #0a0f1e;
  }
  .contact-btn-secondary {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
  }
  .contact-btn .icon { font-size: 18px; flex-shrink: 0; }

  /* ── Section headers ── */
  .section-eyebrow {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.15em;
    color: var(--accent);
    text-transform: uppercase;
    margin-bottom: 10px;
    display: block;
  }
  h2.section-title {
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 26px;
    letter-spacing: -0.01em;
    margin-bottom: 24px;
  }

  /* ── FAQ ── */
  .faq-list { display: flex; flex-direction: column; gap: 2px; margin-bottom: 60px; }
  .faq-item {
    border: 1px solid var(--border);
    border-radius: 4px;
    overflow: hidden;
  }
  .faq-q {
    width: 100%;
    background: var(--surface);
    border: none;
    padding: 18px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    text-align: left;
    font-family: 'DM Sans', sans-serif;
    font-size: 15px;
    font-weight: 500;
    color: var(--text);
    transition: background 0.2s;
  }
  .faq-q:hover { background: var(--surface2); }
  .faq-q .arrow {
    font-size: 12px;
    color: var(--accent);
    transition: transform 0.25s;
    flex-shrink: 0;
    margin-left: 16px;
  }
  .faq-q.open .arrow { transform: rotate(180deg); }
  .faq-a {
    display: none;
    padding: 0 24px 18px;
    background: var(--surface);
    font-size: 14.5px;
    color: var(--text-muted);
    line-height: 1.75;
    border-top: 1px solid rgba(0,212,170,0.08);
  }
  .faq-a.open { display: block; }
  .faq-a a { color: var(--accent); text-decoration: none; }
  .faq-a a:hover { text-decoration: underline; }

  /* ── Troubleshooting steps ── */
  .steps-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 16px;
    margin-bottom: 60px;
  }
  .step-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 24px;
  }
  .step-card .step-icon { font-size: 28px; margin-bottom: 12px; }
  .step-card h3 {
    font-family: 'Syne', sans-serif;
    font-size: 15px;
    font-weight: 700;
    margin-bottom: 10px;
  }
  .step-card ol {
    list-style: none;
    counter-reset: step-counter;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .step-card ol li {
    counter-increment: step-counter;
    font-size: 13px;
    color: var(--text-muted);
    padding-left: 22px;
    position: relative;
    line-height: 1.5;
  }
  .step-card ol li::before {
    content: counter(step-counter) '.';
    position: absolute;
    left: 0;
    color: var(--accent);
    font-weight: 700;
    font-size: 11px;
  }

  /* ── Info strip ── */
  .info-strip {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 28px 32px;
    display: flex;
    gap: 40px;
    flex-wrap: wrap;
    margin-bottom: 60px;
    align-items: flex-start;
  }
  .info-item { flex: 1; min-width: 160px; }
  .info-item strong {
    display: block;
    font-family: 'Syne', sans-serif;
    font-size: 11px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--accent);
    font-weight: 700;
    margin-bottom: 6px;
  }
  .info-item span { font-size: 14px; color: var(--text-muted); }
  .info-item a { color: var(--accent); text-decoration: none; }
  .info-item a:hover { text-decoration: underline; }

  /* ── Legal links ── */
  .legal-row {
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
    padding-top: 32px;
    border-top: 1px solid var(--border);
    margin-bottom: 40px;
  }
  .legal-row a {
    color: var(--text-muted);
    font-size: 13px;
    text-decoration: none;
    transition: color 0.2s;
  }
  .legal-row a:hover { color: var(--accent); }

  /* ── Footer ── */
  footer {
    border-top: 1px solid var(--border);
    padding: 32px 40px;
    text-align: center;
    font-size: 13px;
    color: var(--text-muted);
    max-width: 860px;
    margin: 0 auto;
  }
  footer strong {
    background: var(--gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  @media (max-width: 640px) {
    .topbar { padding: 16px 20px; }
    .hero { padding: 50px 20px 40px; }
    .container { padding: 0 20px 80px; }
    .contact-hero { grid-template-columns: 1fr; padding: 24px; }
    footer { padding: 24px 20px; }
  }
</style>
</head>
<body>

<nav class="topbar">
  <div class="logo">LetsGo</div>
  <a href="https://www.letsgocayman.com" class="back-link">← letsgocayman.com</a>
</nav>

<header class="hero">
  <div class="hero-tag">Help &amp; Support</div>
  <h1>How can we<br><span>help you?</span></h1>
  <p>Get answers to common questions, troubleshoot issues, or reach our team directly. We typically respond within one business day.</p>
</header>

<main class="container">

  <!-- ── Contact ── -->
  <div class="contact-hero">
    <div class="contact-hero-text">
      <h2>Reach our team</h2>
      <p>Have a question that isn't answered below? Send us an email and we'll get back to you within <strong>1&ndash;2 business days</strong>. For urgent safety concerns, use the in-app SOS feature or call 911.</p>
    </div>
    <div class="contact-actions">
      <a href="mailto:sally@letsgocayman.com?subject=LetsGo%20App%20Support%20Request" class="contact-btn contact-btn-primary">
      <a href="/delete-account">Delete your account</a>
        <span class="icon">✉</span>
        Email support@letsgocayman.com
      </a>
      <a href="https://www.letsgocayman.com" class="contact-btn contact-btn-secondary">
        <span class="icon">🌐</span>
        Visit letsgocayman.com
      </a>
    </div>
  </div>

  <!-- ── Info strip ── -->
  <div class="info-strip">
    <div class="info-item">
      <strong>Support email</strong>
      <span><a href="mailto:support@letsgocayman.com">support@letsgocayman.com</a></span>
    </div>
    <div class="info-item">
      <strong>Response time</strong>
      <span>1&ndash;2 business days</span>
    </div>
    <div class="info-item">
      <strong>Emergency (in-app)</strong>
      <span>Use the SOS button or call 911</span>
    </div>
    <div class="info-item">
      <strong>App version</strong>
      <span>iOS &amp; Android — Cayman Islands</span>
    </div>
  </div>

  <!-- ── FAQ ── -->
  <span class="section-eyebrow">Frequently asked questions</span>
  <h2 class="section-title">Common questions</h2>

  <div class="faq-list">

    <div class="faq-item">
      <button class="faq-q" onclick="toggleFaq(this)">
        How do I track my bus in real time?
        <span class="arrow">▼</span>
      </button>
      <div class="faq-a">
        Open the app and tap <strong>Track</strong> on the home screen. Select your route from the list of all 9 Grand Cayman routes. A live map will appear showing the bus location and an estimated arrival time updated every few seconds. GPS must be enabled on your device for the best accuracy.
      </div>
    </div>

    <div class="faq-item">
      <button class="faq-q" onclick="toggleFaq(this)">
        How does offline tracking work when I lose signal?
        <span class="arrow">▼</span>
      </button>
      <div class="faq-a">
        When your phone loses internet connectivity, LetsGo automatically switches to <strong>SMS-based offline tracking</strong>. The app sends a text message to you and your saved emergency contacts with your last GPS position and the bus ETA. You will see a banner in the app when offline mode is active. To use this feature, ensure your emergency contacts are saved in the app's Safety settings.
      </div>
    </div>

    <div class="faq-item">
      <button class="faq-q" onclick="toggleFaq(this)">
        How do I pay for a ride using NFC?
        <span class="arrow">▼</span>
      </button>
      <div class="faq-a">
        Load credit into your LetsGo wallet from the <strong>Wallet</strong> tab using a debit or credit card. When you board the bus, hold your phone near the NFC reader (the yellow device near the driver). The app will deduct the fare automatically. NFC payments work even without an internet connection — your wallet balance is stored securely on your device.
      </div>
    </div>

    <div class="faq-item">
      <button class="faq-q" onclick="toggleFaq(this)">
        How does the SOS feature work?
        <span class="arrow">▼</span>
      </button>
      <div class="faq-a">
        Press and hold the red <strong>SOS</strong> button in the app for 2 seconds to trigger an emergency alert. Your exact GPS coordinates, bus ID, and route are immediately sent by SMS to all emergency contacts saved in your profile. A direct link to call 911 is also surfaced on screen. SOS alerts work even if your internet is offline. To set up emergency contacts, go to <strong>Profile → Emergency Contacts</strong>.
      </div>
    </div>

    <div class="faq-item">
      <button class="faq-q" onclick="toggleFaq(this)">
        How do I add or change my emergency contacts?
        <span class="arrow">▼</span>
      </button>
      <div class="faq-a">
        Go to <strong>Profile → Emergency Contacts</strong> in the app. Tap <em>Add Contact</em> to enter a name and phone number. You can save multiple contacts. When you press SOS or enable Live Share, all saved contacts receive an SMS notification. Contacts can be removed at any time — their information is deleted from our servers immediately.
      </div>
    </div>

    <div class="faq-item">
      <button class="faq-q" onclick="toggleFaq(this)">
        What are Community Reports and how do I submit one?
        <span class="arrow">▼</span>
      </button>
      <div class="faq-a">
        Community Reports let riders flag issues like overcrowding, broken bus stops, long delays, or safety concerns. Tap the <strong>Report</strong> button on the home screen, choose a category, select the stop or route, and describe the issue. Other riders can upvote your report. Our team reviews all reports and aims to resolve critical issues quickly.
      </div>
    </div>

    <div class="faq-item">
      <button class="faq-q" onclick="toggleFaq(this)">
        How do I delete my account and personal data?
        <span class="arrow">▼</span>
      </button>
      <div class="faq-a">
        To delete your account, email <a href="mailto:support@letsgocayman.com?subject=Account%20Deletion%20Request">support@letsgocayman.com</a> with the subject line <em>Account Deletion Request</em> and include your registered username. We will permanently delete your account and associated personal data within 30 days. Payment transaction records may be retained for up to 7 years to comply with financial regulations. See our <a href="/privacy">Privacy Policy</a> for full details.
      </div>
    </div>

  </div>

  <!-- ── Troubleshooting ── -->
  <span class="section-eyebrow">Troubleshooting</span>
  <h2 class="section-title">Fix common issues</h2>

  <div class="steps-grid">

    <div class="step-card">
      <div class="step-icon">📍</div>
      <h3>GPS not working</h3>
      <ol>
        <li>Open device Settings and find LetsGo under app permissions.</li>
        <li>Set Location to <em>Always</em> or <em>While Using</em>.</li>
        <li>Ensure Location Services is turned on globally.</li>
        <li>Step outside — GPS signals are weak indoors.</li>
        <li>Force-quit and reopen the app.</li>
      </ol>
    </div>

    <div class="step-card">
      <div class="step-icon">💳</div>
      <h3>NFC payment failing</h3>
      <ol>
        <li>Check your wallet balance in the <em>Wallet</em> tab.</li>
        <li>Go to Settings → NFC and ensure it is enabled.</li>
        <li>Hold the centre of your phone flat against the reader.</li>
        <li>Remove your phone case if it contains metal.</li>
        <li>Restart the app and try again.</li>
      </ol>
    </div>

    <div class="step-card">
      <div class="step-icon">🆘</div>
      <h3>SOS not sending</h3>
      <ol>
        <li>Make sure emergency contacts are saved in <em>Profile → Emergency Contacts</em>.</li>
        <li>Check that your phone number is correct in your account settings.</li>
        <li>Ensure SMS permissions are granted for LetsGo.</li>
        <li>In an emergency, call 911 directly.</li>
      </ol>
    </div>

    <div class="step-card">
      <div class="step-icon">🔄</div>
      <h3>App crashing or freezing</h3>
      <ol>
        <li>Update LetsGo to the latest version in the App Store or Google Play.</li>
        <li>Restart your phone.</li>
        <li>Uninstall and reinstall the app (your account and wallet data are saved).</li>
        <li>Email us with your device model and iOS/Android version.</li>
      </ol>
    </div>

    <div class="step-card">
      <div class="step-icon">📵</div>
      <h3>Offline mode not activating</h3>
      <ol>
        <li>Confirm SMS is enabled on your SIM — the feature uses text messages.</li>
        <li>Add at least one emergency contact in the app.</li>
        <li>Turn mobile data off to test that offline mode activates.</li>
        <li>Contact support if it still doesn't trigger after 60 seconds offline.</li>
      </ol>
    </div>

    <div class="step-card">
      <div class="step-icon">🔐</div>
      <h3>Can't log in</h3>
      <ol>
        <li>Check your username — it is case-sensitive.</li>
        <li>Tap <em>Forgot password</em> on the login screen.</li>
        <li>Ensure you have an internet connection.</li>
        <li>Email us if you no longer have access to your registered phone number.</li>
      </ol>
    </div>

  </div>

  <!-- ── Legal ── -->
  <div class="legal-row">
    <a href="/privacy">Privacy Policy</a>
    <a href="mailto:support@letsgocayman.com">Contact Support</a>
    <a href="https://www.letsgocayman.com">LetsGo Home</a>
    <a href="mailto:support@letsgocayman.com?subject=Account%20Deletion%20Request">Request Account Deletion</a>
  </div>

</main>

<footer>
  <p>© 2026 <strong>LetsGo Cayman</strong> · Grand Cayman, Cayman Islands</p>
  <p style="margin-top: 6px; font-size: 12px;">
    For urgent safety emergencies, call 911 directly or use the SOS button in the app.
  </p>
</footer>

<script>
function toggleFaq(btn) {
  const answer = btn.nextElementSibling;
  const isOpen = answer.classList.contains('open');
  document.querySelectorAll('.faq-a.open').forEach(a => a.classList.remove('open'));
  document.querySelectorAll('.faq-q.open').forEach(q => q.classList.remove('open'));
  if (!isOpen) {
    answer.classList.add('open');
    btn.classList.add('open');
  }
}
</script>
</body>
</html>"""


@app.route('/api/safety/sos/<token>/resolve', methods=['POST'])
def resolve_sos(token):
    sos = SOSAlert.query.filter_by(token=token).first()
    if not sos:
        return jsonify({'message': 'SOS not found'}), 404
    sos.resolved = True
    db.session.commit()
    return jsonify({'success': True, 'message': 'SOS marked resolved'}), 200


# ═══════════════════════════════════════════════════════════
# SMS ALERTS ADMIN PAGE  (/admin/sms-alerts)
# ═══════════════════════════════════════════════════════════

@app.route('/admin/sms-alerts')
@require_admin
def admin_sms_alerts():
    logs = SMSLog.query.order_by(SMSLog.created_at.desc()).all()
    sent_count = sum(1 for l in logs if l.sent)
    failed_count = sum(1 for l in logs if not l.sent)

    TYPE_LABELS = {
        'sos': ('🆘', '#ef4444', 'SOS Alert'),
        'journey_share': ('🗺', '#F5C518', 'Journey Share'),
        'offline': ('📵', '#fb923c', 'Offline Reminder'),
        'general': ('💬', '#818cf8', 'General'),
    }

    rows = ''
    for l in logs:
        icon, color, label = TYPE_LABELS.get(l.message_type, ('💬', '#818cf8', l.message_type))
        sent_at = l.created_at.strftime('%d %b %Y, %H:%M')
        status_color = '#4ade80' if l.sent else '#ef4444'
        status_label = '✓ Sent' if l.sent else '✗ Failed'
        status_bg = 'rgba(74,222,128,.1)' if l.sent else 'rgba(239,68,68,.1)'
        maps_url = f'https://maps.google.com/?q={l.lat},{l.lng}' if l.lat and l.lng else ''
        gps_cell = (
            f'<a href="{maps_url}" target="_blank" style="color:#F5C518;font-family:monospace;font-size:11px">{l.lat}, {l.lng}</a>'
            if maps_url else '<span style="color:#484f58">—</span>'
        )
        track_cell = (
            f'<a href="{l.track_url}" target="_blank" style="color:#818cf8;font-size:11px">View →</a>'
            if l.track_url else '<span style="color:#484f58">—</span>'
        )
        eta_cell = f'{l.eta_minutes} min' if l.eta_minutes else '—'

        rows += f"""
        <tr id="sms-row-{l.id}">
          <td style="color:#6e7681;font-size:12px;font-family:monospace">#{l.id}</td>
          <td>
            <div style="display:inline-flex;align-items:center;gap:6px;background:rgba(245,197,24,.1);border:1px solid rgba(245,197,24,.25);color:#F5C518;padding:4px 11px;border-radius:20px;font-size:12px;font-weight:700">
              👤 {l.username or '—'}
            </div>
          </td>
          <td>
            <div style="font-family:monospace;font-size:12px;color:#e6edf3">{l.to_phone}</div>
          </td>
          <td>
            <span style="display:inline-flex;align-items:center;gap:5px;background:{color}18;color:{color};padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;border:1px solid {color}33">
              {icon} {label}
            </span>
          </td>
          <td style="color:#8b949e;font-size:13px">{l.route_id or '—'}</td>
          <td>
            <div style="color:#8b949e;font-size:13px">{l.bus_id or '—'}</div>
            <div style="color:#484f58;font-size:11px">{l.bus_name or ''}</div>
          </td>
          <td style="color:#8b949e;font-size:13px">{eta_cell}</td>
          <td>{track_cell}</td>
          <td>{gps_cell}</td>
          <td>
            <span style="display:inline-flex;align-items:center;gap:4px;background:{status_bg};color:{status_color};padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;border:1px solid {status_color}33">
              {status_label}
            </span>
          </td>
          <td class="date-cell">{sent_at}</td>
        </tr>"""

    if not rows:
        rows = '<tr><td colspan="11" style="text-align:center;padding:48px;color:#484f58">No SMS alerts logged yet.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SMS Alerts — LetsGo Admin</title>
<meta name="robots" content="noindex, nofollow">
{ADMIN_STYLE}
<style>
  table td{{max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
  .stat-card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px 24px;display:flex;align-items:center;gap:16px}}
  .stat-card .sc-icon{{font-size:22px;width:48px;height:48px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
  .stat-card .sc-num{{font-size:26px;font-weight:700;color:#f0f6fc;line-height:1}}
  .stat-card .sc-lbl{{font-size:12px;color:#6e7681;margin-top:3px}}
</style>
</head>
<body>
{nav_html('sms')}
<div class="admin-main">
  <div class="page-header">
    <div>
      <h1>💬 SMS Alerts</h1>
      <p>All outbound SMS — offline reminders, journey shares, and SOS alerts</p>
    </div>
    <span class="badge" id="sms-total-count">{len(logs)} total</span>
  </div>

  <!-- STAT CARDS -->
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px">
    <div class="stat-card">
      <div class="sc-icon" style="background:rgba(129,140,248,.1)">💬</div>
      <div><div class="sc-num">{len(logs)}</div><div class="sc-lbl">Total SMS</div></div>
    </div>
    <div class="stat-card">
      <div class="sc-icon" style="background:rgba(74,222,128,.1)">✓</div>
      <div><div class="sc-num" style="color:#4ade80">{sent_count}</div><div class="sc-lbl">Delivered</div></div>
    </div>
    <div class="stat-card">
      <div class="sc-icon" style="background:rgba(239,68,68,.1)">✗</div>
      <div><div class="sc-num" style="color:#f87171">{failed_count}</div><div class="sc-lbl">Failed</div></div>
    </div>
    <div class="stat-card">
      <div class="sc-icon" style="background:rgba(251,146,60,.1)">📵</div>
      <div>
        <div class="sc-num" style="color:#fb923c">{sum(1 for l in logs if l.message_type == 'offline')}</div>
        <div class="sc-lbl">Offline Reminders</div>
      </div>
    </div>
  </div>

  <div class="refresh-bar">Auto-refreshes every 15s &nbsp;|&nbsp; <span id="sms-last-updated">Updated just now</span></div>

  <div class="card">
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Username</th>
            <th>Sent To (Phone)</th>
            <th>Type</th>
            <th>Route</th>
            <th>Bus</th>
            <th>ETA</th>
            <th>Tracking Link</th>
            <th>GPS</th>
            <th>Status</th>
            <th>Sent At</th>
          </tr>
        </thead>
        <tbody id="sms-tbody">{rows}</tbody>
      </table>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>
{ADMIN_JS}
<script>
async function refreshSMS() {{
  try {{
    const res  = await fetch('/api/admin/sms-alerts');
    const data = await res.json();
    const tbody = document.getElementById('sms-tbody');

    const TYPE = {{
      'sos':           ['🆘', '#ef4444', 'SOS Alert'],
      'journey_share': ['🗺', '#F5C518', 'Journey Share'],
      'offline':       ['📵', '#fb923c', 'Offline Reminder'],
      'general':       ['💬', '#818cf8', 'General'],
    }};

    if (!data.logs || data.logs.length === 0) {{
      tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;padding:48px;color:#484f58">No SMS alerts logged yet.</td></tr>';
      document.getElementById('sms-total-count').textContent = '0 total';
      return;
    }}

    tbody.innerHTML = data.logs.map(l => {{
      const [icon, color, label] = TYPE[l.messageType] || ['💬', '#818cf8', l.messageType];
      const sc  = l.sent ? '#4ade80' : '#ef4444';
      const sbg = l.sent ? 'rgba(74,222,128,.1)' : 'rgba(239,68,68,.1)';
      const sl  = l.sent ? '✓ Sent' : '✗ Failed';
      const gps = l.lat && l.lng
        ? `<a href="https://maps.google.com/?q=${{l.lat}},${{l.lng}}" target="_blank" style="color:#F5C518;font-family:monospace;font-size:11px">${{l.lat}}, ${{l.lng}}</a>`
        : '<span style="color:#484f58">—</span>';
      const track = l.trackUrl
        ? `<a href="${{l.trackUrl}}" target="_blank" style="color:#818cf8;font-size:11px">View →</a>`
        : '<span style="color:#484f58">—</span>';
      const eta = l.etaMinutes ? l.etaMinutes + ' min' : '—';

      return `<tr id="sms-row-${{l.id}}">
        <td style="color:#6e7681;font-size:12px;font-family:monospace">#${{l.id}}</td>
        <td>
          <div style="display:inline-flex;align-items:center;gap:6px;background:rgba(245,197,24,.1);border:1px solid rgba(245,197,24,.25);color:#F5C518;padding:4px 11px;border-radius:20px;font-size:12px;font-weight:700">
            👤 ${{l.username || '—'}}
          </div>
        </td>
        <td>
          <div style="font-family:monospace;font-size:12px;color:#e6edf3">${{l.toPhone}}</div>
        </td>
        <td>
          <span style="display:inline-flex;align-items:center;gap:5px;background:${{color}}18;color:${{color}};padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;border:1px solid ${{color}}33">
            ${{icon}} ${{label}}
          </span>
        </td>
        <td style="color:#8b949e;font-size:13px">${{l.routeId || '—'}}</td>
        <td>
          <div style="color:#8b949e;font-size:13px">${{l.busId || '—'}}</div>
          <div style="color:#484f58;font-size:11px">${{l.busName || ''}}</div>
        </td>
        <td style="color:#8b949e;font-size:13px">${{eta}}</td>
        <td>${{track}}</td>
        <td>${{gps}}</td>
        <td>
          <span style="display:inline-flex;align-items:center;gap:4px;background:${{sbg}};color:${{sc}};padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;border:1px solid ${{sc}}33">
            ${{sl}}
          </span>
        </td>
        <td class="date-cell">${{l.createdAt}}</td>
      </tr>`;
    }}).join('');

    document.getElementById('sms-total-count').textContent = data.total + ' total';
    document.getElementById('sms-last-updated').textContent = 'Updated ' + new Date().toLocaleTimeString();
  }} catch (e) {{
    console.error(e);
  }}
}}

setInterval(refreshSMS, 15000);
</script>
</body>
</html>"""


@app.route('/drivers')
def drivers_page():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>Drivers — LetsGo Cayman</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  --gold:#F5C518;--navy:#0B1F3A;--bg:#0d1117;--surface:#161b22;
  --border:#30363d;--text:#e6edf3;--muted:#8b949e;--dim:#484f58;
  --teal:#00897B;--green:#22c55e;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 600px 400px at 20% 10%,rgba(245,197,24,.05),transparent 70%),radial-gradient(ellipse 400px 300px at 80% 80%,rgba(0,137,123,.04),transparent 70%);pointer-events:none;z-index:0}

/* ── nav ── */
.nav{position:sticky;top:0;z-index:200;background:rgba(13,17,23,.96);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:0 32px;height:58px;display:flex;align-items:center;justify-content:space-between}
.nav-brand{font-family:'Syne',sans-serif;font-size:18px;font-weight:800;color:var(--gold);text-decoration:none;display:flex;align-items:center;gap:8px}
.nav-back{color:var(--muted);font-size:13px;text-decoration:none;display:flex;align-items:center;gap:6px;transition:color .2s}
.nav-back:hover{color:var(--gold)}

/* ── hero ── */
.hero{position:relative;z-index:1;text-align:center;padding:72px 32px 56px}
.hero-tag{display:inline-flex;align-items:center;gap:8px;background:rgba(245,197,24,.08);border:1px solid rgba(245,197,24,.25);color:var(--gold);font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;padding:6px 16px;border-radius:20px;margin-bottom:22px}
.hero h1{font-family:'Syne',sans-serif;font-size:clamp(38px,7vw,68px);font-weight:800;line-height:1.05;letter-spacing:-1px;margin-bottom:16px}
.hero h1 span{color:var(--gold)}
.hero p{font-size:16px;color:var(--muted);max-width:480px;margin:0 auto;line-height:1.7}

/* ── option cards ── */
.options{position:relative;z-index:1;max-width:860px;margin:0 auto;padding:0 24px 80px;display:grid;grid-template-columns:1fr 1fr;gap:24px}
.option-card{background:var(--surface);border:1.5px solid var(--border);border-radius:20px;padding:40px 36px;display:flex;flex-direction:column;align-items:flex-start;cursor:pointer;transition:border-color .25s,transform .25s,box-shadow .25s;position:relative;overflow:hidden}
.option-card::before{content:'';position:absolute;inset:0;border-radius:20px;opacity:0;transition:opacity .25s}
.option-card:hover{transform:translateY(-6px);box-shadow:0 24px 64px rgba(0,0,0,.3)}
.option-card.device-card{border-color:rgba(245,197,24,.3)}
.option-card.device-card::before{background:radial-gradient(ellipse at 0% 0%,rgba(245,197,24,.07),transparent 60%)}
.option-card.device-card:hover{border-color:var(--gold);box-shadow:0 24px 64px rgba(245,197,24,.1)}
.option-card.app-card{border-color:rgba(0,137,123,.3)}
.option-card.app-card::before{background:radial-gradient(ellipse at 0% 0%,rgba(0,137,123,.07),transparent 60%)}
.option-card.app-card:hover{border-color:var(--teal);box-shadow:0 24px 64px rgba(0,137,123,.1)}
.option-card:hover::before{opacity:1}

.card-icon{font-size:44px;margin-bottom:20px}
.card-badge{font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;padding:4px 12px;border-radius:20px;margin-bottom:16px;display:inline-block}
.device-card .card-badge{background:rgba(245,197,24,.1);color:var(--gold);border:1px solid rgba(245,197,24,.25)}
.app-card .card-badge{background:rgba(0,137,123,.1);color:var(--teal);border:1px solid rgba(0,137,123,.25)}
.card-title{font-family:'Syne',sans-serif;font-size:22px;font-weight:800;margin-bottom:10px}
.card-desc{font-size:14px;color:var(--muted);line-height:1.7;margin-bottom:28px;flex:1}
.card-btn{display:inline-flex;align-items:center;gap:8px;padding:12px 24px;border-radius:10px;font-family:'Syne',sans-serif;font-size:13px;font-weight:700;letter-spacing:.5px;border:none;cursor:pointer;transition:opacity .2s}
.device-card .card-btn{background:var(--gold);color:var(--navy)}
.app-card .card-btn{background:var(--teal);color:#fff}
.card-btn:hover{opacity:.88}
.card-btn svg{width:16px;height:16px;flex-shrink:0}

.divider{display:flex;align-items:center;justify-content:center;gap:16px;margin:8px 0}
.divider span{font-size:11px;font-weight:700;letter-spacing:2px;color:var(--dim);text-transform:uppercase}
.divider::before,.divider::after{content:'';flex:1;height:1px;background:var(--border)}

/* ── panels ── */
.panel{display:none;position:relative;z-index:1;max-width:560px;margin:0 auto;padding:0 24px 80px}
.panel.active{display:block}
.panel-header{display:flex;align-items:center;gap:12px;margin-bottom:28px}
.back-btn{background:transparent;border:1px solid var(--border);color:var(--muted);border-radius:8px;padding:8px 14px;font-size:13px;cursor:pointer;font-family:'DM Sans',sans-serif;transition:border-color .2s,color .2s;display:flex;align-items:center;gap:6px}
.back-btn:hover{border-color:var(--gold);color:var(--gold)}
.panel-title{font-family:'Syne',sans-serif;font-size:22px;font-weight:800}

.form-card{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:32px}
.field{margin-bottom:20px}
.field label{display:block;font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.7px;margin-bottom:8px}
.field input{width:100%;background:#0d1117;border:1px solid var(--border);border-radius:9px;padding:12px 14px;font-size:14px;color:var(--text);outline:none;font-family:'DM Sans',sans-serif;transition:border-color .2s}
.field input:focus{border-color:var(--gold)}
.field .hint{font-size:12px;color:var(--dim);margin-top:6px}

.submit-btn{width:100%;background:var(--gold);color:var(--navy);border:none;border-radius:10px;padding:14px;font-size:15px;font-weight:700;font-family:'Syne',sans-serif;cursor:pointer;margin-top:8px;transition:background .2s,opacity .2s;display:flex;align-items:center;justify-content:center;gap:8px}
.submit-btn:hover{background:#e8b400}
.submit-btn:disabled{opacity:.5;cursor:not-allowed}
.submit-btn svg{width:18px;height:18px}

/* ── success state ── */
.success-card{background:var(--surface);border:1px solid rgba(34,197,94,.3);border-radius:16px;padding:40px;text-align:center;display:none}
.success-card.show{display:block}
.success-icon{font-size:52px;margin-bottom:16px}
.success-title{font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:var(--green);margin-bottom:10px}
.success-body{font-size:14px;color:var(--muted);line-height:1.75;max-width:360px;margin:0 auto}
.success-note{margin-top:20px;background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.2);border-radius:10px;padding:12px 16px;font-size:13px;color:var(--green);font-weight:500}

/* ── toast ── */
.toast{position:fixed;bottom:24px;right:24px;background:var(--surface);border:1px solid var(--border);color:var(--text);padding:12px 20px;border-radius:10px;font-size:14px;opacity:0;transform:translateY(16px);transition:all .3s;z-index:999;max-width:340px}
.toast.show{opacity:1;transform:translateY(0)}
.toast.error{border-color:rgba(239,68,68,.5);color:#f87171}
.toast.success{border-color:rgba(34,197,94,.5);color:var(--green)}

@media(max-width:680px){
  .options{grid-template-columns:1fr}
  .hero{padding:56px 20px 40px}
  .options,.panel{padding-left:16px;padding-right:16px}
  .form-card{padding:24px}
}
</style>
</head>
<body>

<nav class="nav">
  <a href="/" class="nav-brand">🚌 LetsGo</a>
  <a href="/" class="nav-back">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"/></svg>
    Back to home
  </a>
</nav>

<!-- ═══════════ MAIN OPTIONS VIEW ═══════════ -->
<div id="view-options">
  <header class="hero">
    <div class="hero-tag">🚌 Driver Portal</div>
    <h1>Are you a<br><span>Driver?</span></h1>
    <p>Choose how you'd like to connect. Whether you have a device or prefer the app, we'll get you live on the map.</p>
  </header>

  <div class="options">

    <!-- Card 1: Device -->
    <div class="option-card device-card" onclick="showPanel('device')">
      <div class="card-icon">📡</div>
      <div class="card-badge">Hardware</div>
      <div class="card-title">Connect using device</div>
      <div class="card-desc">
        We'll install a dedicated GPS tracking device on your bus. 
        Your location will broadcast automatically every second — no phone needed while driving.
        <br><br>
        <strong style="color:var(--text)">Best for:</strong> full-time operators who want hands-free tracking.
      </div>
      <button class="card-btn" onclick="showPanel('device');event.stopPropagation()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
        Request a device
      </button>
    </div>

    <!-- Card 2: App -->
    <div class="option-card app-card" onclick="window.location.href='/driver'">
      <div class="card-icon">📱</div>
      <div class="card-badge">Mobile App</div>
      <div class="card-title">Connect using app</div>
      <div class="card-desc">
        Register your route and stops directly from your phone. 
        Your live GPS location broadcasts from the LetsGo driver app — quick to set up, no hardware required.
        <br><br>
        <strong style="color:var(--text)">Best for:</strong> drivers who want to get started immediately.
      </div>
      <button class="card-btn" onclick="window.location.href='/driver';event.stopPropagation()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="5" y="2" width="14" height="20" rx="2"/><circle cx="12" cy="18" r="1" fill="currentColor"/></svg>
        Register via app
      </button>
    </div>

  </div>
</div>

<!-- ═══════════ DEVICE REQUEST FORM ═══════════ -->
<div id="view-device" class="panel">
  <div class="panel-header">
    <button class="back-btn" onclick="showOptions()">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"/></svg>
      Back
    </button>
    <div class="panel-title">📡 Request a GPS Device</div>
  </div>

  <!-- Form -->
  <div class="form-card" id="device-form-card">
    <p style="font-size:14px;color:var(--muted);line-height:1.7;margin-bottom:24px">
      Fill in your details below and our team will reach out to arrange installation of your GPS tracking device — usually within 1–2 business days.
    </p>

    <div class="field">
      <label>Full Name / Driver ID</label>
      <input type="text" id="dev-username" placeholder="e.g. James McLean" autocomplete="name">
    </div>
    <div class="field">
      <label>Phone Number</label>
      <input type="tel" id="dev-phone" placeholder="+1 345 XXX XXXX" autocomplete="tel">
      <div class="hint">We'll call or WhatsApp you to schedule the device installation.</div>
    </div>

    <button class="submit-btn" id="dev-submit-btn" onclick="submitDeviceRequest()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13"/><path d="M22 2L15 22 11 13 2 9l20-7z"/></svg>
      Submit Request
    </button>
  </div>

  <!-- Success -->
  <div class="success-card" id="device-success">
    <div class="success-icon">✅</div>
    <div class="success-title">Request received!</div>
    <p class="success-body">
      Our team has been notified and will contact you shortly to arrange your GPS device installation.
    </p>
    <div class="success-note">
      📧 A confirmation has been sent to our team at sally@letsgocayman.com
    </div>
    <button class="submit-btn" style="margin-top:24px;background:var(--surface);color:var(--gold);border:1px solid rgba(245,197,24,.3)" onclick="showOptions()">
      ← Back to options
    </button>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
function showOptions() {
  document.getElementById('view-options').style.display = '';
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showPanel(name) {
  document.getElementById('view-options').style.display = 'none';
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById('view-' + name).classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast ' + (type || 'success') + ' show';
  setTimeout(() => t.className = 'toast', 3500);
}

async function submitDeviceRequest() {
  const username = document.getElementById('dev-username').value.trim();
  const phone    = document.getElementById('dev-phone').value.trim();

  if (!username) { showToast('Please enter your name or driver ID', 'error'); return; }
  if (!phone)    { showToast('Please enter your phone number', 'error'); return; }

  const btn = document.getElementById('dev-submit-btn');
  btn.disabled = true;
  btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="animation:spin .8s linear infinite"><path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" opacity=".25"/><path d="M21 12a9 9 0 00-9-9"/></svg> Sending…';

  try {
    const res  = await fetch('/api/driver/device-request', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, phone })
    });
    const data = await res.json();

    if (res.ok && data.success) {
      document.getElementById('device-form-card').style.display = 'none';
      document.getElementById('device-success').classList.add('show');
    } else {
      showToast('Error: ' + (data.message || 'Submission failed'), 'error');
      btn.disabled = false;
      btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13"/><path d="M22 2L15 22 11 13 2 9l20-7z"/></svg> Submit Request';
    }
  } catch (err) {
    showToast('Network error — please try again', 'error');
    btn.disabled = false;
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13"/><path d="M22 2L15 22 11 13 2 9l20-7z"/></svg> Submit Request';
  }
}
</script>

<style>
@keyframes spin { to { transform: rotate(360deg); } }
</style>
</body>
</html>"""


@app.route('/driver')
def driver_page():
    with open('driver_register.html', 'r') as f:
        return f.read()


@app.route('/admin/drivers')
@require_admin
def admin_drivers():
    drivers = DriverRoute.query.order_by(DriverRoute.created_at.desc()).all()

    rows = ''
    for d in drivers:
        stops = json.loads(d.stops_json or '[]')
        stop_count = len(stops)
        registered = d.created_at.strftime('%d %b %Y, %H:%M')
        initials = ''.join(w[0].upper() for w in d.driver_name.split()[:2])
        color_dot = f'<span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:{d.route_color};border:1px solid rgba(255,255,255,.2);flex-shrink:0"></span>'

        # check if driver has an active tracking session
        sess = TrackingSession.query.filter_by(username=d.username, active=True).first()
        live_badge = (
            '<span style="display:inline-flex;align-items:center;gap:4px;background:rgba(34,197,94,.12);'
            'border:1px solid rgba(34,197,94,.3);color:#4ade80;padding:2px 8px;border-radius:20px;'
            'font-size:10px;font-weight:700">'
            '<span style="width:5px;height:5px;border-radius:50%;background:#4ade80;animation:blink_ 1s infinite"></span>'
            'LIVE</span>'
        ) if sess else (
            '<span style="background:#21262d;color:#6e7681;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600">offline</span>'
        )

        rows += f"""
        <tr id="drv-row-{d.id}">
          <td><div class="avatar">{initials}</div></td>
          <td>
            <div style="font-weight:600;color:#f0f6fc">{d.driver_name}</div>
            <div style="font-size:11px;color:#6e7681;margin-top:2px;font-family:monospace">{d.driver_phone}</div>
          </td>
          <td style="font-family:monospace;font-size:12px;color:#8b949e">{d.username}</td>
          <td style="font-family:monospace;font-size:12px;color:#8b949e">{d.bus_id}</td>
          <td>
            <div style="display:flex;align-items:center;gap:6px">
              {color_dot}
              <div>
                <div style="font-weight:600;color:#f0f6fc;font-size:13px">{d.route_id}</div>
                <div style="font-size:11px;color:#6e7681">{d.route_name[:30] + ('…' if len(d.route_name) > 30 else '')}</div>
              </div>
            </div>
          </td>
          <td style="font-size:12px;color:#8b949e">{d.frequency}</td>
          <td>
            <span style="background:rgba(245,197,24,.1);color:var(--gold);padding:2px 9px;border-radius:20px;font-size:12px;font-weight:600">{stop_count} stop{'s' if stop_count != 1 else ''}</span>
          </td>
          <td>{live_badge}</td>
          <td class="date-cell">{registered}</td>
          <td>
            <button class="btn btn-ghost" style="font-size:12px;padding:5px 10px"
              onclick="viewStops({d.id}, '{d.driver_name.replace(chr(39), '')}', '{d.route_id}')">Stops</button>
            <button class="btn btn-danger" style="font-size:12px;padding:5px 10px;margin-left:4px"
              onclick="confirmDrvDelete({d.id}, '{d.driver_name.replace(chr(39), '')}')">Delete</button>
          </td>
        </tr>"""

    if not rows:
        rows = '<tr><td colspan="10" style="text-align:center;padding:48px;color:#484f58">No drivers registered yet. <a href="/driver" style="color:var(--gold)">Register one →</a></td></tr>'

    stat_live = sum(1 for d in drivers if TrackingSession.query.filter_by(username=d.username, active=True).first())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Drivers — LetsGo Admin</title>
<meta name="robots" content="noindex, nofollow">
{ADMIN_STYLE}
<style>
  table td{{max-width:200px;overflow:hidden;text-overflow:ellipsis}}
  .stat-card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:18px 22px;display:flex;align-items:center;gap:16px}}
  .sc-icon{{font-size:20px;width:44px;height:44px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
  .sc-num{{font-size:24px;font-weight:700;color:#f0f6fc;line-height:1}}
  .sc-lbl{{font-size:12px;color:#6e7681;margin-top:3px}}
</style>
</head>
<body>
{nav_html('drivers')}
<div class="admin-main">
  <div class="page-header">
    <div>
      <h1>🚌 Registered Drivers</h1>
      <p>Bus drivers who registered via the LetsGo Driver Portal</p>
    </div>
    <div style="display:flex;gap:10px;align-items:center">
      <a href="/driver" target="_blank" class="btn btn-primary">+ Register Driver</a>
      <span class="badge" id="drv-count">{len(drivers)} driver(s)</span>
    </div>
  </div>

  <!-- Stat cards -->
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:24px">
    <div class="stat-card">
      <div class="sc-icon" style="background:rgba(245,197,24,.1)">🚌</div>
      <div><div class="sc-num">{len(drivers)}</div><div class="sc-lbl">Total Drivers</div></div>
    </div>
    <div class="stat-card">
      <div class="sc-icon" style="background:rgba(52,211,153,.1)">📡</div>
      <div><div class="sc-num" style="color:#34d399">{stat_live}</div><div class="sc-lbl">Live Now</div></div>
    </div>
    <div class="stat-card">
      <div class="sc-icon" style="background:rgba(245,197,24,.1)">🛣</div>
      <div><div class="sc-num">{len(set(d.route_id for d in drivers))}</div><div class="sc-lbl">Unique Routes</div></div>
    </div>
  </div>

  <div class="refresh-bar">Auto-refreshes every 15s &nbsp;|&nbsp; <span id="drv-last-updated">Updated just now</span></div>

  <div class="card">
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th></th>
            <th>Driver</th>
            <th>Username</th>
            <th>Bus ID</th>
            <th>Route</th>
            <th>Frequency</th>
            <th>Stops</th>
            <th>Status</th>
            <th>Registered</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="drv-tbody">{rows}</tbody>
      </table>
    </div>
  </div>
</div>

<!-- Stops Modal -->
<div class="overlay" id="stops-overlay">
  <div class="modal" style="max-width:560px;max-height:80vh;overflow-y:auto">
    <h3 id="stops-modal-title">🚏 Bus Stops</h3>
    <p id="stops-modal-sub" style="margin-bottom:16px"></p>
    <div id="stops-list-inner" style="display:flex;flex-direction:column;gap:8px;margin-bottom:20px"></div>
    <div class="modal-btns">
      <button class="btn btn-primary" onclick="closeModal('stops-overlay')">Close</button>
    </div>
  </div>
</div>

<!-- Delete Modal -->
<div class="overlay" id="drv-del-overlay">
  <div class="modal">
    <h3>🗑 Delete Driver</h3>
    <p id="drv-del-msg">Delete this driver registration?</p>
    <div class="modal-btns">
      <button class="btn btn-ghost" onclick="closeModal('drv-del-overlay')">Cancel</button>
      <button class="btn btn-danger" id="confirm-drv-del-btn">Delete</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>
{ADMIN_JS}
<script>
let pendingDrvDeleteId = null;
const driverStops = {{}};

// Pre-load stops data from server rows
{'; '.join([f"driverStops[{d.id}]={json.dumps(json.loads(d.stops_json or '[]'))}" for d in drivers])}

function viewStops(id, name, routeId) {{
  document.getElementById('stops-modal-title').textContent = '🚏 ' + name + ' — Route ' + routeId;
  const stops = driverStops[id] || [];
  const inner = document.getElementById('stops-list-inner');
  document.getElementById('stops-modal-sub').textContent = stops.length + ' stop' + (stops.length !== 1 ? 's' : '') + ' registered';
  if (!stops.length) {{
    inner.innerHTML = '<div style="color:#484f58;text-align:center;padding:20px">No stops added</div>';
  }} else {{
    inner.innerHTML = stops.map((s, i) => {{
      const hasLoc = s.lat && s.lng;
      const mapsLink = hasLoc ? `<a href="https://maps.google.com/?q=${{s.lat}},${{s.lng}}" target="_blank" style="color:var(--gold);font-size:11px">📍 Map</a>` : '<span style="color:#484f58;font-size:11px">No GPS</span>';
      return `<div style="display:flex;align-items:center;gap:12px;background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:10px 14px">
        <div style="width:26px;height:26px;border-radius:50%;background:rgba(245,197,24,.12);border:1px solid rgba(245,197,24,.3);color:var(--gold);font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0">${{i+1}}</div>
        <div style="flex:1">
          <div style="font-weight:600;color:#f0f6fc;font-size:13px">${{s.name || 'Unnamed stop'}}</div>
          ${{hasLoc ? `<div style="font-family:monospace;font-size:10px;color:#6e7681;margin-top:2px">${{parseFloat(s.lat).toFixed(5)}}, ${{parseFloat(s.lng).toFixed(5)}}</div>` : ''}}
        </div>
        ${{mapsLink}}
      </div>`;
    }}).join('');
  }}
  openModal('stops-overlay');
}}

function confirmDrvDelete(id, name) {{
  pendingDrvDeleteId = id;
  document.getElementById('drv-del-msg').textContent = `Delete driver "${{name}}"? This cannot be undone.`;
  openModal('drv-del-overlay');
}}

document.getElementById('confirm-drv-del-btn').addEventListener('click', async () => {{
  if (!pendingDrvDeleteId) return;
  closeModal('drv-del-overlay');
  try {{
    const res = await fetch(`/api/driver/${{pendingDrvDeleteId}}`, {{ method: 'DELETE' }});
    const data = await res.json();
    if (res.ok) {{
      document.getElementById(`drv-row-${{pendingDrvDeleteId}}`).remove();
      showToast('✓ ' + data.message);
    }} else {{
      showToast('✗ ' + data.message, 'error');
    }}
  }} catch (e) {{ showToast('✗ Delete failed', 'error'); }}
  pendingDrvDeleteId = null;
}});

async function refreshDrivers() {{
  try {{
    const res = await fetch('/api/admin/drivers');
    const data = await res.json();
    document.getElementById('drv-count').textContent = data.total + ' driver(s)';
    document.getElementById('drv-last-updated').textContent = 'Updated ' + new Date().toLocaleTimeString();
    // Re-populate stops cache
    (data.drivers || []).forEach(d => {{ driverStops[d.id] = d.stops; }});
  }} catch (e) {{ console.error(e); }}
}}
setInterval(refreshDrivers, 15000);
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════
# ★ NEW: DRIVER API ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.route('/maps', methods=['POST'])
def maps_register():
    """Alias endpoint — driver registration form posts here."""
    return register_driver()


@app.route('/api/driver/device-request', methods=['POST'])
def driver_device_request():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get('username') or '').strip()
    phone = (data.get('phone') or '').strip()

    if not username or not phone:
        return jsonify({'success': False, 'message': 'Username and phone are required'}), 400

    # ── Save to DB ────────────────────────────────────────
    req = DeviceRequest(username=username, phone=phone)
    db.session.add(req)
    db.session.commit()

    # ── Send notification email ───────────────────────────
    _send_device_request_email(username, phone)

    return jsonify({
        'success': True,
        'message': 'Request received. Our team will contact you soon!'
    }), 201


def _send_device_request_email(username, phone):
    """Send a notification to sally@ when a driver requests a device."""
    import smtplib, ssl
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')
    to_email = 'sally@letsgocayman.com'

    subject = f'🚌 New Driver Device Request — {username}'
    body = f"""
Hello,

A bus driver has submitted a device connection request on LetsGo Cayman.

Driver username : {username}
Phone number    : {phone}
Submitted at    : {datetime.utcnow().strftime('%d %b %Y at %H:%M UTC')}

Please contact them to set up their GPS tracking device.

— LetsGo Cayman System
"""

    if not smtp_user or not smtp_pass:
        # No SMTP configured — just log it, request is saved in DB
        print(f'[DeviceRequest] No SMTP configured. Request saved: {username} / {phone}')
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_email, msg.as_string())
        print(f'[DeviceRequest] Email sent to {to_email}')
    except Exception as e:
        print(f'[DeviceRequest] Email failed: {e}')


@app.route('/api/driver/register', methods=['POST'])
def register_driver():
    data = request.get_json(force=True, silent=True) or {}
    print(f"[DEBUG] register_driver payload: {data}")
    print(f"[DEBUG] stops received: {data.get('stops')}")

    if not all([data.get('driverName'), data.get('driverPhone'),
                data.get('driverUsername'), data.get('routeId')]):
        return jsonify({'message': 'Missing required fields'}), 400

    raw_route_id = data['routeId']
    route_name = (data.get('routeName') or '').strip() or raw_route_id
    # If driver selected "custom", use the route name as the actual ID
    effective_route_id = route_name if raw_route_id == 'custom' else raw_route_id
    effective_bus_id = (data.get('busId') or '').strip() or effective_route_id

    route = DriverRoute(
        driver_name=data['driverName'],
        driver_phone=data['driverPhone'],
        username=data['driverUsername'],
        bus_id=effective_bus_id,
        route_id=effective_route_id,
        route_name=route_name,
        route_color=data.get('routeColor', '#F5C518'),
        frequency=data.get('frequency', 'Every 15 minutes'),
        description=data.get('description', ''),
        stops_json=json.dumps(data.get('stops', [])),
    )
    db.session.add(route)

    # Also start a live tracking session
    sess = TrackingSession(
        username=data['driverUsername'],
        phone_number=data['driverPhone'],
        route_id=effective_route_id,
        bus_id=effective_bus_id,
        bus_name=route_name,
        active=False,
    )
    db.session.add(sess)
    db.session.commit()

    return jsonify({'success': True, 'routeId': route.id,
                    'message': 'Driver registered and now live on the map!'}), 201


@app.route('/api/driver/<int:driver_id>', methods=['DELETE'])
def delete_driver(driver_id):
    driver = db.session.get(DriverRoute, driver_id)
    if not driver:
        return jsonify({'message': 'Driver not found'}), 404
    name = driver.driver_name
    db.session.delete(driver)
    db.session.commit()
    return jsonify({'message': f'Driver {name} deleted successfully'}), 200


@app.route('/api/driver/<int:driver_id>', methods=['PATCH'])
def update_driver(driver_id):
    driver = db.session.get(DriverRoute, driver_id)
    if not driver:
        return jsonify({'message': 'Driver not found'}), 404
    data = request.get_json(force=True, silent=True) or {}
    for field, col in [('driverName', 'driver_name'), ('driverPhone', 'driver_phone'),
                       ('username', 'username'), ('busId', 'bus_id'),
                       ('routeId', 'route_id'), ('routeName', 'route_name'),
                       ('routeColor', 'route_color'), ('frequency', 'frequency'),
                       ('description', 'description')]:
        if field in data:
            setattr(driver, col, data[field])
    db.session.commit()
    return jsonify({'message': 'Driver updated'}), 200


@app.route('/api/admin/drivers')
@require_admin
def api_admin_drivers():
    drivers = DriverRoute.query.order_by(DriverRoute.created_at.desc()).all()
    return jsonify({
        'total': len(drivers),
        'drivers': [{
            'id': d.id,
            'driverName': d.driver_name,
            'driverPhone': d.driver_phone,
            'username': d.username,
            'busId': d.bus_id,
            'routeId': d.route_id,
            'routeName': d.route_name,
            'routeColor': d.route_color,
            'frequency': d.frequency,
            'description': d.description,
            'stops': json.loads(d.stops_json or '[]'),
            'stopCount': len(json.loads(d.stops_json or '[]')),
            'isLive': bool(TrackingSession.query.filter_by(username=d.username, active=True).first()),
            'createdAt': d.created_at.strftime('%d %b %Y, %H:%M'),
        } for d in drivers]
    })


# ═══════════════════════════════════════════════════════════
# ADMIN SOS JSON API  (for auto-refresh)
# ═══════════════════════════════════════════════════════════

@app.route('/api/admin/sos-alerts')
@require_admin
def api_admin_sos_alerts():
    alerts = SOSAlert.query.order_by(SOSAlert.created_at.desc()).all()
    return jsonify({
        'total': len(alerts),
        'alerts': [{
            'id': a.id,
            'token': a.token,
            'username': a.username,
            'phone': a.phone_number,
            'routeId': a.route_id,
            'busId': a.bus_id,
            'lat': a.lat,
            'lng': a.lng,
            'contacts': json.loads(a.contacts or '[]'),
            'resolved': a.resolved,
            'createdAt': a.created_at.strftime('%d %b %Y, %H:%M'),
        } for a in alerts]
    })


# ═══════════════════════════════════════════════════════════
# PUBLIC TRACKING PAGE  /track/<token>
# ═══════════════════════════════════════════════════════════

@app.route('/api/tracking/session/<token>')
def api_tracking_session(token):
    sess = TrackingSession.query.filter_by(token=token).first()
    if not sess:
        return jsonify({'found': False}), 404

    # ── pull live bus location for this route/bus ─────────
    live_sess = (
        TrackingSession.query
        .filter_by(bus_id=sess.bus_id, active=True)
        .order_by(TrackingSession.updated_at.desc())
        .first()
    )

    # also check by route_id in DriverRoute table for stops
    driver = (
                 DriverRoute.query
                 .filter_by(bus_id=sess.bus_id)
                 .order_by(DriverRoute.created_at.desc())
                 .first()
             ) or (
                 DriverRoute.query
                 .filter_by(route_id=sess.route_id)
                 .order_by(DriverRoute.created_at.desc())
                 .first()
             )

    stops = []
    route_color = '#F5C518'
    frequency = 'Every 15 minutes'
    description = ''

    if driver:
        route_color = driver.route_color or '#F5C518'
        frequency = driver.frequency or 'Every 15 minutes'
        description = driver.description or ''
        try:
            raw = json.loads(driver.stops_json or '[]')
            for i, s in enumerate(raw):
                if isinstance(s, (list, tuple)) and len(s) >= 3:
                    stops.append({'name': str(s[0]), 'lat': float(s[1]), 'lng': float(s[2])})
                elif isinstance(s, dict):
                    stops.append({
                        'name': s.get('name') or s.get('stopName') or 'Stop',
                        'lat': float(s.get('lat') or s.get('latitude') or 0),
                        'lng': float(s.get('lng') or s.get('longitude') or 0),
                    })
        except Exception:
            stops = []

    # fallback: use the static CAYMAN_ROUTES list
    if not stops:
        for route in CAYMAN_ROUTES:
            if route['route_number'] in (sess.route_id, sess.bus_id):
                route_color = route['color']
                frequency = route['frequency']
                description = route['description']
                stops = [
                    {'name': name, 'lat': lat, 'lng': lng}
                    for name, lat, lng in route['stops']
                ]
                break

    bus_lat = bus_lng = None
    bus_updated = None
    if live_sess:
        try:
            bus_lat = float(live_sess.lat)
            bus_lng = float(live_sess.lng)
            bus_updated = live_sess.updated_at.isoformat() if live_sess.updated_at else None
        except (TypeError, ValueError):
            pass

    return jsonify({
        'found': True,
        'active': sess.active,
        'username': sess.username or 'Rider',
        'phoneNumber': sess.phone_number or '',
        'routeId': sess.route_id or '',
        'busId': sess.bus_id or '',
        'busName': sess.bus_name or sess.bus_id or '',
        'routeColor': route_color,
        'frequency': frequency,
        'description': description,
        'stops': stops,
        'busLat': bus_lat,
        'busLng': bus_lng,
        'busUpdated': bus_updated,
        'updatedAt': sess.updated_at.strftime('%H:%M:%S') if sess.updated_at else 'N/A',
    })


@app.route('/track/<token>')
def tracking_page(token):
    # Minimal server-side check — just confirm the token exists
    sess = TrackingSession.query.filter_by(token=token).first()
    exists = sess is not None
    active = sess.active if sess else True  # used only for the initial status pill

    sc = '#16a34a' if active else '#6b7280'
    sl = 'LIVE' if active else 'ENDED'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>LetsGo — Live Journey</title>
<meta name="robots" content="noindex, nofollow">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:100%;font-family:\'Outfit\',sans-serif;background:#f8fafc;color:#1e293b;overflow:hidden}}
body{{display:flex;flex-direction:column}}

.hdr{{background:#fff;border-bottom:1px solid #e2e8f0;padding:10px 16px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;z-index:1000;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.hdr-logo{{font-size:15px;font-weight:700;color:#0B1F3A;display:flex;align-items:center;gap:6px}}
.hdr-logo span{{color:#F5C518}}
.hdr-center{{text-align:center;min-width:0;flex:1;padding:0 12px}}
.hdr-center .title{{font-size:13px;font-weight:600;color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.hdr-center .sub{{font-size:11px;color:#94a3b8;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.live-pill{{display:inline-flex;align-items:center;gap:5px;background:{sc}15;border:1px solid {sc}50;color:{sc};padding:4px 11px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap;flex-shrink:0}}
.live-dot{{width:6px;height:6px;border-radius:50%;background:{sc};animation:pdot 1.4s infinite}}
@keyframes pdot{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}

#map{{flex:1;width:100%;min-height:0}}

.bottom{{background:#fff;border-top:1px solid #e2e8f0;flex-shrink:0;box-shadow:0 -1px 4px rgba(0,0,0,.06)}}
.info-row{{display:flex;border-bottom:1px solid #f1f5f9}}
.info-item{{flex:1;text-align:center;padding:10px 6px;border-right:1px solid #f1f5f9}}
.info-item:last-child{{border-right:none}}
.lbl{{font-size:8px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.7px}}
.val{{font-size:13px;font-weight:700;color:#1e293b;margin-top:3px;line-height:1.1}}
.sub{{font-size:9px;color:#94a3b8;margin-top:2px}}
.eta-item .val{{color:#F5C518;font-size:20px;font-weight:800}}

.coords-bar{{display:flex;align-items:center;justify-content:space-between;padding:6px 14px;background:#f8fafc;border-top:1px solid #f1f5f9}}
.ctxt{{font-size:10px;color:#94a3b8;font-family:monospace}}
.rnote{{font-size:10px;color:#cbd5e1}}
.ended-bar{{background:#fef9c3;padding:7px 16px;text-align:center;font-size:11px;color:#854d0e;border-top:1px solid #fde68a;display:none}}

/* loading overlay */
.loading-overlay{{position:absolute;inset:0;background:rgba(248,250,252,.92);display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:2000;gap:12px}}
.loading-overlay .spinner{{width:36px;height:36px;border:3px solid #e2e8f0;border-top-color:#F5C518;border-radius:50%;animation:spin .7s linear infinite}}
.loading-overlay p{{font-size:13px;color:#64748b;font-weight:500}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.not-found{{position:absolute;inset:0;background:#f8fafc;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;padding:40px;text-align:center}}
.not-found .icon{{font-size:48px}}
.not-found h2{{font-size:18px;font-weight:700;color:#1e293b}}
.not-found p{{font-size:14px;color:#64748b;line-height:1.6}}

.you-pulse{{width:36px;height:36px;border-radius:50%;background:#0ea5e9;display:flex;align-items:center;justify-content:center;font-size:18px;border:3px solid #fff;box-shadow:0 2px 8px rgba(14,165,233,.5);position:relative}}
.you-pulse::before{{content:\'\';position:absolute;inset:-8px;border-radius:50%;background:rgba(14,165,233,.2);animation:youRipple 1.8s ease-out infinite}}
.you-pulse::after{{content:\'\';position:absolute;inset:-16px;border-radius:50%;background:rgba(14,165,233,.1);animation:youRipple 1.8s ease-out .6s infinite}}
@keyframes youRipple{{0%{{transform:scale(.6);opacity:.8}}100%{{transform:scale(1.3);opacity:0}}}}

.leaflet-popup-content-wrapper{{border-radius:10px!important;box-shadow:0 4px 20px rgba(0,0,0,.12)!important}}
.leaflet-popup-content{{margin:10px 14px!important;font-family:\'Outfit\',sans-serif;font-size:12px;line-height:1.7;color:#1e293b}}
.leaflet-container .leaflet-control-attribution{{font-size:9px!important;background:rgba(255,255,255,.7)!important}}
</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-logo">🚌 <span>LetsGo</span></div>
  <div class="hdr-center">
    <div class="title" id="hdr-title">Loading journey…</div>
    <div class="sub"   id="hdr-sub">Please wait</div>
  </div>
  <div class="live-pill" id="live-pill"><div class="live-dot"></div>{sl}</div>
</div>

<div style="position:relative;flex:1;display:flex;flex-direction:column;min-height:0">
  <div id="map"></div>

  <!-- loading overlay shown until session data arrives -->
  <div class="loading-overlay" id="loading-overlay">
    <div class="spinner"></div>
    <p>Loading journey details…</p>
  </div>

  <!-- shown if token is invalid -->
  <div class="not-found" id="not-found" style="display:none">
    <div class="icon">🔍</div>
    <h2>Journey not found</h2>
    <p>This tracking link may have expired or the journey has ended.</p>
    <a href="/" style="color:#F5C518;font-size:14px;font-weight:600;text-decoration:none">← Back to LetsGo</a>
  </div>
</div>

<div class="bottom" id="bottom-bar">
  <div class="info-row">
    <div class="info-item">
      <div class="lbl">Rider</div>
      <div class="val" id="info-rider">—</div>
    </div>
    <div class="info-item">
      <div class="lbl">Bus</div>
      <div class="val" id="info-bus">—</div>
      <div class="sub" id="bus-status">Loading…</div>
    </div>
    <div class="info-item eta-item">
      <div class="lbl">ETA</div>
      <div class="val" id="eta-val">—</div>
      <div class="sub" id="eta-stop">acquiring GPS</div>
    </div>
    <div class="info-item">
      <div class="lbl">Updated</div>
      <div class="val" id="last-upd" style="font-size:11px">—</div>
      <div class="sub">bus time</div>
    </div>
  </div>
  <div class="coords-bar">
    <span class="ctxt" id="coords-txt">Acquiring your location…</span>
    <span class="rnote" id="freq-note"></span>
  </div>
  <div class="ended-bar" id="ended-bar">Journey ended — showing last known position</div>
</div>

<script>
const TOKEN = '{token}';

/* ── haversine ── */
function hav(a,b,c,d){{
  const R=6371,dL=(c-a)*Math.PI/180,dN=(d-b)*Math.PI/180,
        x=Math.sin(dL/2)**2+Math.cos(a*Math.PI/180)*Math.cos(c*Math.PI/180)*Math.sin(dN/2)**2;
  return R*2*Math.atan2(Math.sqrt(x),Math.sqrt(1-x));
}}

/* ── map (default centre = George Town) ── */
const map = L.map('map',{{zoomControl:false,attributionControl:true}})
              .setView([19.2993,-81.3816],14);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png',
  {{subdomains:'abcd',maxZoom:19,attribution:'© OpenStreetMap © CartoDB'}}).addTo(map);
L.control.zoom({{position:'topright'}}).addTo(map);

/* ── state ── */
let SESSION     = null;
let busMarker   = null, busRing  = null;
let youMarker   = null, youCircle = null;
let busLat      = null, busLng   = null;
let youLat      = null, youLng   = null;
let stopMarkers = [];
let routeLine   = null;
let geoWatchId  = null, geoRetryTimer = null, geoAttempts = 0;

/* ── icons ── */
function makeBusIcon(color) {{
  return L.divIcon({{
    html:`<div style="background:${{color}};width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:22px;border:3px solid #fff;box-shadow:0 3px 10px ${{color}}99">🚌</div>`,
    iconSize:[44,44],iconAnchor:[22,22],className:''
  }});
}}
function makeStopIcon(color) {{
  return L.divIcon({{
    html:`<div style="width:10px;height:10px;border-radius:50%;background:${{color}};border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.3)"></div>`,
    iconSize:[10,10],iconAnchor:[5,5],className:''
  }});
}}
const youIco = L.divIcon({{
  html:'<div class="you-pulse">📍</div>',
  iconSize:[36,36],iconAnchor:[18,18],className:''
}});

/* ── render stops + route line from session data ── */
function renderRoute(session) {{
  /* clear old stops */
  stopMarkers.forEach(m => map.removeLayer(m));
  stopMarkers = [];
  if (routeLine) {{ map.removeLayer(routeLine); routeLine = null; }}

  const color   = session.routeColor || '#F5C518';
  const stopIco = makeStopIcon(color);
  const coords  = [];

  (session.stops || []).forEach(s => {{
    if (!s.lat || !s.lng) return;
    const m = L.marker([s.lat,s.lng],{{icon:stopIco}}).addTo(map)
      .bindTooltip('<b style="color:#0B1F3A">'+s.name+'</b>',{{direction:'top',offset:[0,-6]}});
    stopMarkers.push(m);
    coords.push([s.lat,s.lng]);
  }});

  if (coords.length > 1) {{
    routeLine = L.polyline(coords,{{
      color:color, weight:3, opacity:.45, dashArray:'8 5'
    }}).addTo(map);
  }}
}}

/* ── update bus marker ── */
function updateBusMarker(lat, lng, session) {{
  const color = session.routeColor || '#F5C518';
  if (!busMarker) {{
    busRing   = L.circle([lat,lng],{{color,fillColor:color,fillOpacity:.08,weight:1.5,radius:70}}).addTo(map);
    busMarker = L.marker([lat,lng],{{icon:makeBusIcon(color),zIndexOffset:200}}).addTo(map)
      .bindPopup(`<b style="color:#0B1F3A">${{session.busId}}</b><br>`+
                 `<span style="color:#64748b">${{session.busName}}</span><br>`+
                 `<small style="color:#94a3b8">Route ${{session.routeId}}</small>`);
  }} else {{
    busMarker.setLatLng([lat,lng]);
    busRing.setLatLng([lat,lng]);
  }}
  busLat = lat; busLng = lng;
}}

/* ── fit map to show both markers ── */
function fitBoth() {{
  if (youLat===null || busLat===null) return;
  map.fitBounds(L.latLngBounds([[youLat,youLng],[busLat,busLng]]),
    {{padding:[60,60],maxZoom:16,animate:true}});
}}

/* ── ETA ── */
function calcETA(stops) {{
  if (youLat===null || !stops || !stops.length) return;
  let nearest=null, minD=Infinity;
  stops.forEach(s=>{{ if (!s.lat||!s.lng) return; const d=hav(youLat,youLng,s.lat,s.lng); if(d<minD){{minD=d;nearest=s;}} }});
  if (!nearest) return;
  const etaEl = document.getElementById('eta-val');
  const subEl = document.getElementById('eta-stop');
  if (busLat!==null) {{
    const dist   = hav(busLat,busLng,nearest.lat,nearest.lng);
    const etaMin = Math.max(0,Math.round(dist/30*60));
    if (etaMin===0) {{ etaEl.textContent='Now';        etaEl.style.color='#16a34a'; subEl.textContent='Bus arriving!'; }}
    else if (etaMin===1) {{ etaEl.textContent='1 min'; etaEl.style.color='#ea580c'; subEl.textContent=nearest.name; }}
    else                {{ etaEl.textContent=etaMin+' min'; etaEl.style.color=SESSION?.routeColor||'#F5C518'; subEl.textContent=nearest.name; }}
  }} else {{
    const walkMin = Math.round(minD*1000/80);
    etaEl.textContent = walkMin<1?'<1':walkMin+' min';
    etaEl.style.color = '#94a3b8';
    subEl.textContent = 'walk to '+nearest.name;
  }}
}}

/* ── fetch session + bus location ── */
async function fetchSession() {{
  try {{
    const r    = await fetch('/api/tracking/session/'+TOKEN);
    if (r.status===404) {{
      document.getElementById('loading-overlay').style.display='none';
      document.getElementById('not-found').style.display='flex';
      return;
    }}
    const data = await r.json();
    if (!data.found) {{
      document.getElementById('loading-overlay').style.display='none';
      document.getElementById('not-found').style.display='flex';
      return;
    }}

    SESSION = data;

    /* ── update header ── */
    document.getElementById('hdr-title').textContent = data.username+"\'s Journey";
    document.getElementById('hdr-sub').textContent   = data.busId+' · Route '+data.routeId;
    document.getElementById('info-rider').textContent = data.username;
    document.getElementById('info-bus').textContent   = data.busId;
    document.getElementById('last-upd').textContent   = data.updatedAt;
    document.getElementById('freq-note').textContent  = data.frequency || '';

    /* ── active/ended banner ── */
    if (!data.active) {{
      document.getElementById('ended-bar').style.display = 'block';
      const pill = document.getElementById('live-pill');
      pill.style.background='#6b728015';
      pill.style.borderColor='#6b728050';
      pill.style.color='#6b7280';
      pill.querySelector('.live-dot').style.background='#6b7280';
      pill.lastChild.textContent=' ENDED';
    }}

    /* ── render stops ── */
    renderRoute(data);

    /* ── bus live location ── */
    if (data.busLat!==null && data.busLat!==undefined) {{
      updateBusMarker(data.busLat, data.busLng, data);
      const upd = data.busUpdated ? new Date(data.busUpdated).toLocaleTimeString() : data.updatedAt;
      document.getElementById('last-upd').textContent  = upd;
      document.getElementById('bus-status').textContent = 'Online';
      fitBoth();
    }} else {{
      document.getElementById('bus-status').textContent = 'No live bus';
    }}

    calcETA(data.stops);

    /* hide loading overlay */
    document.getElementById('loading-overlay').style.display='none';

  }} catch(e) {{
    console.error('fetchSession error:', e);
    document.getElementById('loading-overlay').style.display='none';
  }}
}}

/* ══ GPS ══ */
function handlePos(pos) {{
  geoAttempts=0;
  if (geoRetryTimer) {{ clearTimeout(geoRetryTimer); geoRetryTimer=null; }}

  const lat=pos.coords.latitude, lng=pos.coords.longitude, acc=pos.coords.accuracy;
  youLat=lat; youLng=lng;

  /* push to server */
  if (SESSION?.active && TOKEN) {{
    fetch('/api/tracking/update',{{
      method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{token:TOKEN,lat,lng}})
    }}).catch(()=>{{}});
  }}

  if (!youMarker) {{
    youCircle = L.circle([lat,lng],{{color:'#0ea5e9',fillColor:'#0ea5e9',fillOpacity:.1,weight:1.5,radius:Math.max(20,acc)}}).addTo(map);
    youMarker = L.marker([lat,lng],{{icon:youIco,zIndexOffset:500}}).addTo(map)
      .bindTooltip((SESSION?.username||'You')+' — you',{{permanent:true,direction:'top',offset:[0,-22]}});
    busLat!==null ? fitBoth() : map.setView([lat,lng],15,{{animate:true}});
  }} else {{
    youMarker.setLatLng([lat,lng]);
    youCircle.setLatLng([lat,lng]);
    youCircle.setRadius(Math.max(20,acc));
  }}

  document.getElementById('coords-txt').textContent =
    '📍 You: '+lat.toFixed(5)+', '+lng.toFixed(5)+' (±'+Math.round(acc)+'m)';

  if (SESSION) calcETA(SESSION.stops);
}}

function handleGeoErr(err) {{
  const msgs = {{
    1:'🔒 Location blocked — tap the lock icon and allow location',
    2:'📡 GPS signal weak — move to an open area',
    3:'⏱ GPS timed out — retrying…'
  }};
  document.getElementById('coords-txt').textContent = msgs[err.code]||'GPS error '+err.code;
  document.getElementById('eta-stop').textContent   = 'enable GPS to see ETA';
  if (err.code===3 && geoAttempts<5) {{
    geoAttempts++;
    if (geoWatchId!==null) {{ navigator.geolocation.clearWatch(geoWatchId); geoWatchId=null; }}
    document.getElementById('coords-txt').textContent = '⏱ GPS timed out — retrying ('+geoAttempts+'/5)…';
    geoRetryTimer = setTimeout(startGeo, 3000);
  }}
}}

function startGeo() {{
  if (!navigator.geolocation) {{
    document.getElementById('coords-txt').textContent='❌ GPS not available — try Chrome or Safari';
    return;
  }}
  if (geoWatchId!==null) {{ navigator.geolocation.clearWatch(geoWatchId); geoWatchId=null; }}
  document.getElementById('coords-txt').textContent='🛰 Acquiring your location…';
  geoWatchId = navigator.geolocation.watchPosition(handlePos, handleGeoErr, {{
    enableHighAccuracy:true, timeout:15000, maximumAge:5000
  }});
}}

/* ══ boot ══ */
fetchSession();
startGeo();

/* poll every 8s for live bus updates */
setInterval(fetchSession, 8000);
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════
# PUBLIC SOS PAGE  /sos/<token>
# ═══════════════════════════════════════════════════════════

@app.route('/sos/<token>')
def sos_page(token):
    sos = SOSAlert.query.filter_by(token=token).first()

    if sos:
        username = sos.username
        phone_number = sos.phone_number
        route_id = sos.route_id
        bus_id = sos.bus_id
        lat = sos.lat or '19.3465'
        lng = sos.lng or '-81.3958'
        triggered_at = sos.created_at.strftime('%d %b %Y at %H:%M UTC')
        contacts = json.loads(sos.contacts or '[]')
        resolved = sos.resolved
    else:
        username = 'Demo Rider';
        phone_number = '+1 (345) 555-0123'
        route_id = 'WB1';
        bus_id = 'CI-WB1-01'
        lat = '19.3465';
        lng = '-81.3958'
        triggered_at = datetime.utcnow().strftime('%d %b %Y at %H:%M UTC')
        contacts = [];
        resolved = False

    # Enrich contacts from stored EmergencyContact table
    stored = EmergencyContact.query.filter_by(username=username).all()
    existing_phones = set()
    for c in contacts:
        p = (c.get('phone') or '').replace(' ', '').replace('-', '').replace('+', '')
        existing_phones.add(p)
    for c in stored:
        p = c.phone_number.replace(' ', '').replace('-', '').replace('+', '')
        if p not in existing_phones:
            contacts.append({'name': c.contact_name, 'phone': c.phone_number})

    initials = ''.join(w[0].upper() for w in username.split()[:2]) if username else 'U'
    maps_url = f'https://maps.google.com/?q={lat},{lng}'

    # Pre-build resolved banner to avoid backslash-in-f-string error
    if resolved:
        resolved_banner = (
            '<div style="background:rgba(34,197,94,.08);border:1px solid rgba(34,197,94,.25);'
            'border-radius:12px;padding:16px 20px;display:flex;align-items:center;gap:14px;margin-top:24px">'
            '<span style="font-size:28px">✅</span>'
            '<div>'
            '<div style="font-family:var(--font-display);font-size:15px;font-weight:700;color:var(--green)">This SOS has been resolved</div>'
            '<div style="font-size:12px;color:var(--text-muted);margin-top:3px">The rider is safe. No further action needed.</div>'
            '</div></div>'
        )
    else:
        resolved_banner = ''

    contact_items = ''
    for i, c in enumerate(contacts):
        name = c.get('name', 'Contact')
        phone = c.get('phone', '')
        av = name[:1].upper()
        colors = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6', '#a855f7']
        col = colors[i % len(colors)]
        contact_items += f'''
        <div class="contact-card" style="animation-delay:{i * 0.08}s">
          <div class="contact-avatar" style="background:{col}22;border-color:{col}55;color:{col}">{av}</div>
          <div class="contact-info">
            <div class="contact-name">{name}</div>
            <div class="contact-phone">{phone}</div>
            <div class="contact-status"><span class="sms-badge">✓ SMS Alert Sent</span></div>
          </div>
          <div class="contact-actions">
            <a href="tel:{phone}" class="call-btn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.8 19.79 19.79 0 01.22 1.18 2 2 0 012.2 0h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L6.91 7.91a16 16 0 006.16 6.16l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/></svg>
              Call
            </a>
            <a href="sms:{phone}" class="sms-btn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
            </a>
          </div>
        </div>'''

    no_contacts_html = '' if contacts else '''
        <div class="no-contacts">
          <div class="no-contacts-icon">👥</div>
          <p>No emergency contacts on file</p>
          <span>Contacts will appear here when the rider sets them up in the app</span>
        </div>'''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="theme-color" content="#0a0a0a">
<title>{'🔴 ACTIVE SOS' if not resolved else '✅ SOS Resolved'} — LetsGo Cayman</title>
<meta name="robots" content="noindex, nofollow">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;600;700;800&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root {{
  --red:#ef4444;--red-glow:rgba(239,68,68,0.25);
  --green:#22c55e;--green-glow:rgba(34,197,94,0.2);
  --gold:#F5C518;--gold-glow:rgba(245,197,24,0.15);
  --bg:#0a0a0a;--surface:#111111;--surface2:#1a1a1a;
  --border:#222222;--border2:#2d2d2d;
  --text:#f5f5f5;--text-muted:#888888;--text-dim:#555555;
  --font-display:'Syne',sans-serif;--font-body:'DM Sans',sans-serif;--font-mono:'DM Mono',monospace;
  --status-color:{'var(--green)' if resolved else 'var(--red)'};
  --status-glow:{'var(--green-glow)' if resolved else 'var(--red-glow)'};
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:var(--font-body);background:var(--bg);color:var(--text);min-height:100%;-webkit-font-smoothing:antialiased}}
.alert-strip{{background:{'linear-gradient(90deg,#991b1b,#dc2626,#991b1b)' if not resolved else 'linear-gradient(90deg,#14532d,#16a34a,#14532d)'};background-size:200% 100%;animation:{'stripPulse 2s ease-in-out infinite' if not resolved else 'none'};padding:10px 20px;display:flex;align-items:center;justify-content:center;gap:10px;font-family:var(--font-display);font-size:12px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:white}}
@keyframes stripPulse{{0%,100%{{background-position:0% 50%}}50%{{background-position:100% 50%}}}}
.strip-dot{{width:8px;height:8px;border-radius:50%;background:white;animation:{'blink 0.8s ease-in-out infinite' if not resolved else 'none'}}}
@keyframes blink{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.2;transform:scale(.7)}}}}
.hdr{{background:var(--surface);border-bottom:1px solid var(--border);padding:14px 20px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:1000}}
.hdr-logo{{font-family:var(--font-display);font-size:18px;font-weight:800;color:var(--gold);display:flex;align-items:center;gap:8px;text-decoration:none}}
.status-badge{{display:inline-flex;align-items:center;gap:6px;background:var(--status-glow);border:1px solid var(--status-color);color:var(--status-color);padding:6px 14px;border-radius:100px;font-family:var(--font-display);font-size:11px;font-weight:700;letter-spacing:2px}}
.status-dot{{width:7px;height:7px;border-radius:50%;background:var(--status-color);animation:{'blink 0.8s ease-in-out infinite' if not resolved else 'none'}}}
.hero{{background:var(--surface);border-bottom:1px solid var(--border);padding:28px 20px 24px;position:relative;overflow:hidden}}
.hero::before{{content:'';position:absolute;inset:0;background:{'radial-gradient(ellipse at 50% 0%,rgba(239,68,68,.08) 0%,transparent 70%)' if not resolved else 'radial-gradient(ellipse at 50% 0%,rgba(34,197,94,.06) 0%,transparent 70%)'};pointer-events:none}}
.hero-grid{{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:16px;position:relative}}
.hero-avatar{{width:68px;height:68px;border-radius:50%;background:var(--surface2);border:2px solid var(--status-color);display:flex;align-items:center;justify-content:center;font-family:var(--font-display);font-size:24px;font-weight:800;color:var(--status-color);box-shadow:0 0 20px var(--status-glow);flex-shrink:0}}
.hero-name{{font-family:var(--font-display);font-size:22px;font-weight:800;color:var(--text);line-height:1.1}}
.hero-phone{{font-family:var(--font-mono);font-size:13px;color:var(--text-muted);margin-top:5px;display:flex;align-items:center;gap:6px}}
.hero-phone a{{color:var(--gold);text-decoration:none;font-weight:500}}
.hero-triggered{{font-size:10px;color:var(--text-dim);font-family:var(--font-mono);margin-top:8px;letter-spacing:.5px}}
.hero-sos-icon{{font-size:40px;animation:{'sosBounce 1.5s ease-in-out infinite' if not resolved else 'none'};flex-shrink:0}}
@keyframes sosBounce{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.12)}}}}
.main{{max-width:640px;margin:0 auto;padding:0 16px 40px}}
.section-label{{font-family:var(--font-mono);font-size:9px;font-weight:500;color:var(--text-dim);letter-spacing:3px;text-transform:uppercase;margin:24px 0 10px;padding-left:2px}}
.info-strip{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:4px}}
.info-box{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px}}
.info-box-label{{font-family:var(--font-mono);font-size:9px;font-weight:500;color:var(--text-dim);letter-spacing:2px;text-transform:uppercase;margin-bottom:6px}}
.info-box-value{{font-family:var(--font-display);font-size:17px;font-weight:700;color:var(--text);line-height:1.2}}
.info-box.highlight{{border-color:var(--gold)33}}
.info-box.highlight .info-box-value{{color:var(--gold)}}
.coords-box{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 16px;display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:4px}}
.coords-text{{font-family:var(--font-mono);font-size:12px;color:var(--text-muted)}}
.coords-text strong{{color:var(--text);font-size:13px}}
.coords-link{{background:var(--surface2);border:1px solid var(--border2);color:var(--gold);font-size:11px;font-weight:600;padding:6px 12px;border-radius:8px;text-decoration:none;white-space:nowrap}}
.map-wrap{{border-radius:14px;overflow:hidden;border:1px solid var(--border);position:relative}}
#sos-map{{height:260px}}
.map-overlay-corner{{position:absolute;bottom:12px;right:12px;z-index:1000;background:rgba(10,10,10,.85);backdrop-filter:blur(6px);border:1px solid var(--border2);border-radius:8px;padding:6px 12px;font-family:var(--font-mono);font-size:10px;color:var(--text-muted)}}
.action-row{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.btn-911{{background:var(--red);color:white;border:none;border-radius:12px;padding:16px 12px;font-family:var(--font-display);font-size:15px;font-weight:800;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;letter-spacing:1px;box-shadow:0 4px 24px var(--red-glow);animation:{'pulseShadow 2s ease-in-out infinite' if not resolved else 'none'}}}
@keyframes pulseShadow{{0%,100%{{box-shadow:0 4px 24px rgba(239,68,68,.3)}}50%{{box-shadow:0 4px 40px rgba(239,68,68,.6)}}}}
.btn-maps{{background:var(--surface);color:var(--gold);border:1px solid var(--gold)33;border-radius:12px;padding:16px 12px;font-family:var(--font-display);font-size:14px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none}}
.btn-911 svg,.btn-maps svg{{width:18px;height:18px;flex-shrink:0}}
.contacts-list{{display:flex;flex-direction:column;gap:10px}}
.contact-card{{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:14px 16px;display:flex;align-items:center;gap:14px;animation:slideIn .4s ease both}}
@keyframes slideIn{{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:translateY(0)}}}}
.contact-avatar{{width:44px;height:44px;border-radius:50%;border:1.5px solid;display:flex;align-items:center;justify-content:center;font-family:var(--font-display);font-size:17px;font-weight:800;flex-shrink:0}}
.contact-info{{flex:1;min-width:0}}
.contact-name{{font-family:var(--font-display);font-size:15px;font-weight:700;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.contact-phone{{font-family:var(--font-mono);font-size:12px;color:var(--text-muted);margin-top:3px}}
.contact-status{{margin-top:5px}}
.sms-badge{{display:inline-flex;align-items:center;gap:4px;background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.25);color:var(--green);font-size:10px;font-weight:600;padding:2px 8px;border-radius:20px}}
.contact-actions{{display:flex;align-items:center;gap:8px;flex-shrink:0}}
.call-btn{{background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.3);color:var(--red);border-radius:10px;padding:8px 14px;font-size:12px;font-weight:700;display:flex;align-items:center;gap:6px;text-decoration:none;font-family:var(--font-display)}}
.call-btn svg{{width:14px;height:14px}}
.sms-btn{{background:var(--surface2);border:1px solid var(--border2);color:var(--text-muted);border-radius:10px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;text-decoration:none}}
.sms-btn svg{{width:15px;height:15px}}
.no-contacts{{text-align:center;padding:32px 20px;background:var(--surface);border:1px dashed var(--border2);border-radius:14px}}
.no-contacts-icon{{font-size:32px;margin-bottom:10px}}
.no-contacts p{{font-size:14px;font-weight:600;color:var(--text-muted);margin-bottom:4px}}
.no-contacts span{{font-size:12px;color:var(--text-dim)}}
.page-footer{{margin-top:32px;padding:16px 0 8px;border-top:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}}
.footer-brand{{font-family:var(--font-display);font-size:13px;font-weight:700;color:var(--gold);text-decoration:none;display:flex;align-items:center;gap:6px}}
.footer-copy{{font-size:11px;color:var(--text-dim);font-family:var(--font-mono)}}
</style>
</head>
<body>
<div class="alert-strip">
  <div class="strip-dot"></div>
  {'🆘 ACTIVE EMERGENCY — IMMEDIATE ASSISTANCE NEEDED' if not resolved else '✅ SOS RESOLVED'}
  <div class="strip-dot"></div>
</div>
<div class="hdr">
  <a href="/" class="hdr-logo">🚌 LetsGo</a>
  <div class="status-badge"><div class="status-dot"></div>{'SOS ACTIVE' if not resolved else 'RESOLVED'}</div>
</div>
<div class="hero">
  <div class="hero-grid">
    <div class="hero-avatar">{initials}</div>
    <div class="hero-info">
      <div class="hero-name">{username}</div>
      <div class="hero-phone">📞 <a href="tel:{phone_number}">{phone_number if phone_number else 'No phone on file'}</a></div>
      <div class="hero-triggered">⏱ Triggered {triggered_at}</div>
    </div>
    <div class="hero-sos-icon">{'🆘' if not resolved else '✅'}</div>
  </div>
</div>
<div class="main">
  <div class="section-label">Bus &amp; Route</div>
  <div class="info-strip">
    <div class="info-box highlight"><div class="info-box-label">Bus ID</div><div class="info-box-value">{bus_id}</div></div>
    <div class="info-box highlight"><div class="info-box-label">Route</div><div class="info-box-value">{route_id}</div></div>
  </div>
  <div class="section-label">GPS Location</div>
  <div class="coords-box">
    <div class="coords-text"><strong>{lat}, {lng}</strong><br>Last known position</div>
    <a href="{maps_url}" target="_blank" class="coords-link">Open Maps →</a>
  </div>
  <div class="map-wrap" style="margin-bottom:4px">
    <div id="sos-map"></div>
    <div class="map-overlay-corner">📍 SOS Location</div>
  </div>
  <div class="section-label">Emergency Actions</div>
  <div class="action-row">
    <a href="tel:911" class="btn-911">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.8 19.79 19.79 0 01.22 1.18 2 2 0 012.2 0h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L6.91 7.91a16 16 0 006.16 6.16l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/></svg>
      CALL 911
    </a>
    <a href="{maps_url}" target="_blank" class="btn-maps">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s-8-4.5-8-11.8A8 8 0 0112 2a8 8 0 018 8.2c0 7.3-8 11.8-8 11.8z"/><circle cx="12" cy="10" r="3"/></svg>
      View on Maps
    </a>
  </div>
  <div class="section-label">Emergency Contacts ({len(contacts)} notified)</div>
  <div class="contacts-list">
    {contact_items}
    {no_contacts_html}
  </div>
  {resolved_banner}
  <div class="page-footer">
    <a href="/" class="footer-brand">🚌 LetsGo Cayman</a>
    <span class="footer-copy">SOS · {triggered_at}</span>
  </div>
</div>
<script>
const map=L.map('sos-map',{{zoomControl:false,attributionControl:false,scrollWheelZoom:false}}).setView([{lat},{lng}],16);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{subdomains:'abcd',maxZoom:19}}).addTo(map);
L.control.zoom({{position:'topright'}}).addTo(map);
const si=L.divIcon({{
  html:`<div style="position:relative;width:52px;height:52px;display:flex;align-items:center;justify-content:center">
    <div style="position:absolute;inset:0;border-radius:50%;background:rgba(239,68,68,.2);animation:ripple 1.8s ease-out infinite"></div>
    <div style="position:absolute;inset:4px;border-radius:50%;background:rgba(239,68,68,.15);animation:ripple 1.8s ease-out infinite .6s"></div>
    <div style="width:42px;height:42px;border-radius:50%;background:#ef4444;border:3px solid white;display:flex;align-items:center;justify-content:center;font-size:20px;box-shadow:0 0 24px rgba(239,68,68,.8);position:relative;z-index:1">🆘</div>
  </div>
  <style>@keyframes ripple{{from{{opacity:.8;transform:scale(1)}}to{{opacity:0;transform:scale(2)}}}}</style>`,
  iconSize:[52,52],iconAnchor:[26,26],className:''
}});
L.marker([{lat},{lng}],{{icon:si}}).addTo(map).bindPopup(`<div style="font-family:system-ui;color:#0a0a0a;padding:4px 2px"><strong style="font-size:14px">{username}</strong><br><span style="font-size:12px;color:#555">Bus {bus_id} · Route {route_id}</span></div>`,{{maxWidth:220}}).openPopup();
L.circle([{lat},{lng}],{{color:'#ef4444',fillColor:'#ef4444',fillOpacity:.07,weight:1.5,radius:80}}).addTo(map);
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════
# LANDING PAGES
# ═══════════════════════════════════════════════════════════

@app.route('/')
def landing():
    return LANDING_HTML


@app.route('/home')
def landing_home():
    return redirect('/')


@app.route('/team')
def landing_team():
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
