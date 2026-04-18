from flask import Flask, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import json
import secrets
import uuid

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


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(200), nullable=False)
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
</style>
</head>
<body>
<div class="cur" id="cur"></div>
<nav id="nav">
  <a class="nav-logo" href="#"><span class="dot"></span> LetsGo</a>
  <ul class="nav-links">
    <li><a href="#" onclick="showPage('home')">Home</a></li>
    <li><a href="#" onclick="showPage('home');setTimeout(()=>document.getElementById('features').scrollIntoView({behavior:'smooth'}),200)">Features</a></li>
    <li><a href="#" onclick="showPage('team')">Our Team</a></li>
  </ul>
  <a href="#dl" class="nav-dl" onclick="showPage('home')">Download App</a>
</nav>
<div class="page-nav">
  <button class="pnav-btn active" id="tab-home" onclick="showPage('home')">Home</button>
  <button class="pnav-btn" id="tab-team" onclick="showPage('team')">Meet Our Team</button>
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
      <div class="qr-card">
        <div class="qr-label">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="#0B1F3A"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>
          App Store
        </div>
        <img src="data:image/png;base64,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" alt="iOS QR Code" class="qr-img"/>
        <div class="qr-hint">Scan to download on iOS</div>
      </div>
      <div class="qr-card">
        <div class="qr-label">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="#0B1F3A"><path d="M3.18 23.76c.3.17.64.22.99.14l12.82-7.41-2.79-2.79-11.02 10.06zM.35 1.33C.13 1.66 0 2.1 0 2.67v18.66c0 .57.13 1.01.36 1.34l.07.07 10.46-10.46v-.25L.42 1.27l-.07.06zM20.96 10.18l-2.64-1.53-3.13 3.13 3.13 3.13 2.65-1.54c.76-.44.76-1.15 0-1.6l-.01.41zM4.17.24l12.82 7.41-2.79 2.79L4.17.24c.35-.09.7-.04.99.14l-.99-.14z"/></svg>
          Google Play
        </div>
        <img src="data:image/png;base64,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mEACo9YgGAYHLroff0Z7r5bbz/Duv1G7svM9Qysu1WtNNddcFb6UClR2cktq3nKme6IK5Bbq3jneu9752XloKK+BklrWynWFK1+DCZ7o77N7m+TaHpLTic3I9nq43oi9HI8212N6F2U1Ma5kVU7iiUbTlEBCpREBoPUIhgOxeJm6Vv8ATfzacgv1k3Fr97/7zkZuXk/9Vt3wV7cRnzsTT/vLjP8Az1p/146GSnhOAeayEo6fsNQzvbcjE9m5+NrChqM/IIqo1KNBy3X3VOZQxq1qYRrxwHxbTU9OZbk/+K2/d86n9IabJycr92e6ub8FLe2vDZySjrnKlg6I13XureOd601Gdl5a6iXh2lrWyvUFK0+HHjRPFkgoo0/KaJZZPvTXafeLcwtGVdS628w21tLWnXQPFiTJ286fOe9+ZTlnyB9R3VyQ1O6vzCedkab1H89m3W/2768a4DZ9Bj40fMH8xigNnGVHM9A7ZDO/t96l5HbtRo9PbckkSy289aZVa17erhxUu2tNh1c1js5uZlsW9t9pZ24H6XUZGQvddknususrXhW3tpiQOdiaf95cZ/560/68BTPQY+NHzB/MYOgx8aPmD+YxX77ezqcbrWej7ebE7GBC3NamxcqKSdxgKFxzCABUwgAVHrEAxmediVn95cGf56zf68BM3MX0a/6a+VPKrk5+it36LUaj1r+ezFLLc+/wBrbThWoJnaanpz08n/xW3FubU/pDU52dlfuyW0yvhrd2U49Eooa4Lb4KUbonaYfaoVaUkllF3ioidhVIYxRSOJj+pmKJhIJR6hES07MRBtz81n4nc2nIz/btfye03+75ebkf9y27/FTtwFM7EvtYoR+e+mr49raOlRzwwOxwzv7cmmeRG7UaPUXWpKkstvJSubWtezq48OcEKxvMliRYochaL4tZkjK5LG7na8mghROoetiaSZvCMcw8ACoibxjimdk2IZkw1MV4N06X5Frmh5R0KIsy8XNbQzshmoVkRKQhmkQIKthVRAA760D9gDgKfklAvNrLB0QVvTeu7s713p8nMzF1FfAuNSl9Osa0r8GIa2jtm/megdjiblnvvUvIjDp92ae25JU992aetMqlKdvXw4m1HNiKufaIuRUy31uD1rpN0P1XSf1VK+zKPZ4d9af2q141wv5j89G40ecbnA3TqS5O/wDWafPtNbbn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" alt="Android QR Code" class="qr-img"/>
        <div class="qr-hint">Scan to download on Android</div>
      </div>
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
    <div class="footer-links"><a href="#" onclick="showPage('home')">Home</a><a href="#" onclick="showPage('team')">Team</a><a href="/demo">Demo</a></div>
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

@app.route('/demo')
def demo():
    return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LetsGo Cayman — How It Works</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #0a0a0a;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            font-family: Arial, sans-serif;
            color: white;
            padding: 20px;
        }
        .logo { font-size: 32px; font-weight: bold; color: #00C853; margin-bottom: 8px; }
        .tagline { color: #aaa; font-size: 14px; margin-bottom: 6px; }
        .subtitle { color: #00C853; font-size: 18px; font-weight: bold; margin-bottom: 24px; }
        .video-container {
            width: 100%;
            max-width: 800px;
            aspect-ratio: 16/9;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 0 40px rgba(0,200,83,0.3);
            margin-bottom: 40px;
        }
        iframe { width: 100%; height: 100%; border: none; }
        .steps {
            width: 100%;
            max-width: 800px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 40px;
        }
        .step {
            background: #1a1a1a;
            border: 1px solid #00C853;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }
        .step .icon { font-size: 32px; margin-bottom: 10px; }
        .step h3 { color: #00C853; font-size: 16px; margin-bottom: 8px; }
        .step p { color: #aaa; font-size: 13px; line-height: 1.5; }
        .cta {
            background: #00C853;
            color: black;
            font-weight: bold;
            font-size: 16px;
            padding: 14px 32px;
            border-radius: 30px;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="logo">🚌 LetsGo Cayman</div>
    <div class="tagline">The first AI-powered smart bus platform in the Cayman Islands</div>
    <div class="subtitle">Here is how it works</div>

    <div class="video-container">
        <iframe
            src="https://www.youtube.com/embed/GA60zCK3Ei8?autoplay=1&rel=0"
            allow="autoplay; encrypted-media"
            allowfullscreen>
        </iframe>
    </div>

    <div class="steps">
        <div class="step">
            <div class="icon">📍</div>
            <h3>Track Your Bus</h3>
            <p>See exactly where your bus is in real time. AI predicts arrival in under 60 seconds.</p>
        </div>
        <div class="step">
            <div class="icon">📲</div>
            <h3>Tap To Pay</h3>
            <p>Load your wallet once. Tap your phone or card and board in under 1 second. No cash needed.</p>
        </div>
        <div class="step">
            <div class="icon">🔔</div>
            <h3>Smart Reminders</h3>
            <p>We learn your commute and alert you when your bus is 5 minutes away. Never wait again.</p>
        </div>
        <div class="step">
            <div class="icon">🆘</div>
            <h3>Family SOS</h3>
            <p>One tap sends your GPS, bus ID and route to emergency contacts. Works fully offline.</p>
        </div>
        <div class="step">
            <div class="icon">📶</div>
            <h3>Works Offline</h3>
            <p>No signal? No problem. Dead reckoning and SMS fallback keep you connected anywhere.</p>
        </div>
        <div class="step">
            <div class="icon">🚩</div>
            <h3>Community Reports</h3>
            <p>Flag delays, overcrowding or safety issues instantly. Reports escalate to the transit authority.</p>
        </div>
    </div>

    <a class="cta" href="https://www.letsgocayman.com">Try It Yourself →</a>

</body>
</html>
"""

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
    full_name = data.get('fullName')
    username = data.get('username')
    phone_number = data.get('phoneNumber')
    password = data.get('password')

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


@app.route('/api/sms/debug', methods=['GET'])
@require_admin
def sms_debug():
    """Temporary debug route — remove after fixing."""
    current_twilio = {**TWILIO_CONFIG, **_twilio_override}
    
    # Check what's actually stored
    sid    = current_twilio.get('accountSid', '')
    token  = current_twilio.get('authToken', '')
    from_n = current_twilio.get('fromNumber', '')
    
    # Check last 5 SMS logs
    logs = SMSLog.query.order_by(SMSLog.created_at.desc()).limit(5).all()
    
    return jsonify({
        'twilio': {
            'accountSid_set':  bool(sid),
            'accountSid_prefix': sid[:6] if sid else 'EMPTY',
            'authToken_set':   bool(token),
            'fromNumber':      from_n or 'EMPTY',
        },
        'last_5_sms_logs': [{
            'id':       l.id,
            'username': l.username,
            'to_phone': l.to_phone,
            'sent':     l.sent,
            'detail':   l.twilio_detail,
            'type':     l.message_type,
            'time':     l.created_at.isoformat(),
        } for l in logs],
        'env_vars': {
            'TWILIO_ACCOUNT_SID': 'set' if os.environ.get('TWILIO_ACCOUNT_SID') else 'MISSING',
            'TWILIO_AUTH_TOKEN':  'set' if os.environ.get('TWILIO_AUTH_TOKEN')  else 'MISSING',
            'TWILIO_FROM_NUMBER': os.environ.get('TWILIO_FROM_NUMBER', 'MISSING'),
        }
    })

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
    # ── West Bay Routes ─────────────────────────────────────────────────────
    {
        'route_number': 'WB1',
        'name': 'Seven Mile Beach – Northwest Point – Turtle Centre',
        'color': '#F5C518',
        'frequency': 'Every 2–5 minutes',
        'description': 'Seven Mile Beach (SMB) • Northwest Point • Cayman Turtle Centre • Ed Bush Stadium',
        'stops': [
            ('George Town Depot', 19.2869, -81.3797),
            ('George Town Harbour', 19.2900, -81.3850),
            ('Seven Mile Beach South', 19.3044, -81.3939),
            ('Camana Bay', 19.3175, -81.3982),
            ('Seven Mile Beach North', 19.3340, -81.3894),
            ('Governors Square', 19.3480, -81.3870),
            ('Ed Bush Stadium', 19.3560, -81.3820),
            ('Cayman Turtle Centre', 19.3712, -81.3789),
            ('Northwest Point', 19.3800, -81.3900),
            ('Hell', 19.3744, -81.4028),
            ('West Bay Square', 19.3680, -81.3950),
        ]
    },
    {
        'route_number': 'WB2',
        'name': 'Seven Mile Beach – Watercourse Road – Hell',
        'color': '#4CAF50',
        'frequency': 'Every 2–5 minutes',
        'description': 'Seven Mile Beach (SMB) • Watercourse Road • Cayman Turtle Centre • Hell',
        'stops': [
            ('George Town Depot', 19.2869, -81.3797),
            ('George Town Harbour', 19.2900, -81.3850),
            ('Seven Mile Beach South', 19.3044, -81.3939),
            ('Camana Bay', 19.3175, -81.3982),
            ('Seven Mile Beach North', 19.3340, -81.3894),
            ('Watercourse Road', 19.3550, -81.4050),
            ('Cayman Turtle Centre', 19.3712, -81.3789),
            ('Hell', 19.3744, -81.4028),
        ]
    },
    {
        'route_number': 'WB3',
        'name': 'Owen Roberts Drive – Industrial Park – SMB – Barkers',
        'color': '#9C27B0',
        'frequency': 'Every 15 minutes',
        'description': 'Owen Roberts Drive • Industrial Park • Seven Mile Beach (SMB) • Esterley Tibbetts Hwy • Cayman Turtle Centre • Mount Pleasant • Barkers',
        'stops': [
            ('George Town Depot', 19.2869, -81.3797),
            ('Owen Roberts Drive', 19.2930, -81.3720),
            ('Industrial Park', 19.2980, -81.3680),
            ('Seven Mile Beach South', 19.3044, -81.3939),
            ('Camana Bay', 19.3175, -81.3982),
            ('Esterley Tibbetts Hwy', 19.3400, -81.4000),
            ('Mount Pleasant', 19.3550, -81.4100),
            ('Cayman Turtle Centre', 19.3712, -81.3789),
            ('Barkers', 19.3820, -81.4150),
        ]
    },

    # ── North / Interior Routes ──────────────────────────────────────────────
    {
        'route_number': '4A',
        'name': 'Walkers Road – Fairbanks Road – Hospitals',
        'color': '#00BCD4',
        'frequency': 'Every 30 minutes',
        'description': 'Walkers Road • Fairbanks Road • Hospitals • Schools',
        'stops': [
            ('George Town Depot', 19.2869, -81.3797),
            ('Walkers Road', 19.2800, -81.3650),
            ('Fairbanks Road', 19.2750, -81.3500),
            ('Health City / Hospitals', 19.2900, -81.3300),
            ('Schools Complex', 19.2950, -81.3200),
        ]
    },

    # ── East End Routes ──────────────────────────────────────────────────────
    {
        'route_number': '7A',
        'name': 'Wreck of the Ten Sails – Queens Hwy – East End',
        'color': '#FF5722',
        'frequency': 'Every 5–10 minutes',
        'description': 'Wreck of the Ten Sails • Queens High Way • East End • Lovers Wall • The Blow Holes',
        'stops': [
            ('George Town Depot', 19.2869, -81.3797),
            ('George Town Harbour', 19.2900, -81.3850),
            ('Red Bay', 19.2920, -81.3400),
            ('Prospect', 19.2936, -81.3339),
            ('Savannah', 19.2897, -81.2800),
            ('Newlands', 19.2850, -81.2500),
            ('Bodden Town', 19.2842, -81.2528),
            ('Lookout Gardens', 19.2900, -81.2000),
            ('Breakers', 19.2819, -81.1747),
            ('Frank Sound', 19.3100, -81.1500),
            ('Botanic Park', 19.3200, -81.1300),
            ('East End', 19.3036, -81.0914),
            ('Lovers Wall', 19.3000, -81.0700),
            ('The Blow Holes', 19.2950, -81.0600),
            ('Wreck of the Ten Sails', 19.2880, -81.0500),
            ('Gun Bay', 19.2950, -81.0800),
        ]
    },
    {
        'route_number': '7B',
        'name': 'Walkers Rd – Smith Cove – South Sound – East End',
        'color': '#FF9800',
        'frequency': 'Every 30 minutes',
        'description': 'Walkers Rd • Smith Cove • South Sound Dock • Rex Crighton Hwy • Oleander Drive • East End • Queens Hwy',
        'stops': [
            ('George Town Depot', 19.2869, -81.3797),
            ('Walkers Road', 19.2800, -81.3650),
            ('Smith Cove', 19.2750, -81.3850),
            ('South Sound', 19.2700, -81.3700),
            ('South Sound Dock', 19.2650, -81.3600),
            ('Rex Crighton Hwy', 19.2700, -81.3300),
            ('Oleander Drive', 19.2800, -81.3000),
            ('Newlands', 19.2850, -81.2500),
            ('Bodden Town', 19.2842, -81.2528),
            ('East End', 19.3036, -81.0914),
            ('Queens Highway', 19.3000, -81.1000),
        ]
    },

    # ── North Side Routes ────────────────────────────────────────────────────
    {
        'route_number': '8A',
        'name': 'Cayman Kai – Starfish Point – North Side – Hutland – Rum Point',
        'color': '#E91E63',
        'frequency': 'Every 30 minutes',
        'description': 'Cayman Kai • Star Fish Point • North Side • Hutland • Rum Point',
        'stops': [
            ('George Town Depot', 19.2869, -81.3797),
            ('Frank Sound Road', 19.3289, -81.1444),
            ('North Side', 19.3669, -81.1533),
            ('Hutland', 19.3800, -81.1800),
            ('Old Man Bay', 19.3900, -81.2200),
            ('Rum Point', 19.4100, -81.2500),
            ('Starfish Point', 19.3950, -81.2600),
            ('Cayman Kai', 19.3850, -81.2700),
        ]
    },
    {
        'route_number': 'CaymanBus',
        'name': 'Cayman Bus – Live Tracked',
        'color': '#000000',
        'frequency': 'Every 15 minutes',
        'description': 'Live GPS tracked bus • George Town Depot • Compass Media • Cayman Enterprise City • Hospitals • Schools',
        'stops': [
            ('George Town Depot', 19.2869, -81.3797),
            ('Walkers Road', 19.2800, -81.3650),
            ('Compass Media', 19.2993, -81.3816),
            ('Cayman Enterprise City', 19.3120, -81.3900),
            ('Fairbanks Road', 19.2750, -81.3500),
            ('Health City / Hospitals', 19.2900, -81.3300),
            ('Schools Complex', 19.2950, -81.3200),
        ]
    },
    {
        'route_number': '8B',
        'name': 'Walkers Rd – Smith Cove – South Sound – Frank Sound – Cayman Kai',
        'color': '#3F51B5',
        'frequency': 'Every 30 minutes',
        'description': 'Walkers Rd • Smith Cove • South Sound Dock • Cleander Drive • Frank Sound • Cayman Kai',
        'stops': [
            ('George Town Depot', 19.2869, -81.3797),
            ('Walkers Road', 19.2800, -81.3650),
            ('Smith Cove', 19.2750, -81.3850),
            ('South Sound', 19.2700, -81.3700),
            ('South Sound Dock', 19.2650, -81.3600),
            ('Cleander Drive', 19.2800, -81.3000),
            ('Frank Sound', 19.3100, -81.1500),
            ('Cayman Kai', 19.3850, -81.2700),
        ]
    },

    # ── Queens Highway / Far East ────────────────────────────────────────────
    {
        'route_number': '9A',
        'name': 'Queens Highway – Gun Bay – Frank Sound – Botanic Park',
        'color': '#009688',
        'frequency': 'Every 5–10 minutes',
        'description': 'Queens Highway • Gun Bay • Frank Sound • Botanic Park • Mastic Trail',
        'stops': [
            ('George Town Depot', 19.2869, -81.3797),
            ('Red Bay', 19.2920, -81.3400),
            ('Prospect', 19.2936, -81.3339),
            ('Savannah', 19.2897, -81.2800),
            ('Bodden Town', 19.2842, -81.2528),
            ('Breakers', 19.2819, -81.1747),
            ('East End', 19.3036, -81.0914),
            ('Gun Bay', 19.2950, -81.0800),
            ('Frank Sound', 19.3100, -81.1500),
            ('Botanic Park', 19.3200, -81.1300),
            ('Mastic Trail', 19.3300, -81.1600),
        ]
    },
]


@app.route('/api/buses/coordinates', methods=['GET'])
def buses_coordinates():
    # ── Get live coordinates from Raspberry Pi for CaymanBus ─────────
    session = TrackingSession.query.filter_by(
        active=True, route_id='CaymanBus'
    ).order_by(TrackingSession.updated_at.desc()).first()

    if session:
        try:
            live_location = {
                "lat": float(session.lat),
                "lng": float(session.lng),
                "busId": session.bus_id,
                "updatedAt": session.updated_at.isoformat() if session.updated_at else None,
            }
        except (ValueError, TypeError):
            live_location = None
    else:
        live_location = None

    # ── Build all routes from CAYMAN_ROUTES ──────────────────────────
    all_routes = []

    for route in CAYMAN_ROUTES:
        stops = []

        for i, (name, lat, lng) in enumerate(route['stops']):
            stops.append({
                "id": f"{route['route_number']}-S{i + 1:02}",
                "name": name,
                "lat": lat,
                "lng": lng,
            })

        route_data = {
            "route": route['route_number'],
            "routeName": route['name'],
            "color": route['color'],
            "frequency": route['frequency'],
            "description": route['description'],
            "stops": stops,
        }

        # Attach live Pi coordinates only to CaymanBus
        if route['route_number'] == 'CaymanBus':
            route_data['liveLocation'] = live_location

        all_routes.append(route_data)

    return jsonify({
        "routes": all_routes,
        "totalRoutes": len(all_routes),
        "totalStops": sum(len(r["stops"]) for r in all_routes),
        "generatedAt": datetime.utcnow().isoformat() + "Z",
    }), 200


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
    sent_count   = sum(1 for l in logs if l.sent)
    failed_count = sum(1 for l in logs if not l.sent)

    TYPE_LABELS = {
        'sos':           ('🆘', '#ef4444', 'SOS Alert'),
        'journey_share': ('🗺', '#F5C518', 'Journey Share'),
        'offline':       ('📵', '#fb923c', 'Offline Reminder'),
        'general':       ('💬', '#818cf8', 'General'),
    }

    rows = ''
    for l in logs:
        icon, color, label = TYPE_LABELS.get(l.message_type, ('💬', '#818cf8', l.message_type))
        sent_at      = l.created_at.strftime('%d %b %Y, %H:%M')
        status_color = '#4ade80' if l.sent else '#ef4444'
        status_label = '✓ Sent'  if l.sent else '✗ Failed'
        status_bg    = 'rgba(74,222,128,.1)' if l.sent else 'rgba(239,68,68,.1)'
        maps_url     = f'https://maps.google.com/?q={l.lat},{l.lng}' if l.lat and l.lng else ''
        gps_cell     = (
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
          <td>
            <button class="btn btn-danger" style="font-size:11px;padding:4px 10px" onclick="confirmDeleteSMS({l.id})">Delete</button>
          </td>
        </tr>"""

    if not rows:
        rows = '<tr><td colspan="12" style="text-align:center;padding:48px;color:#484f58">No SMS alerts logged yet.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SMS Alerts — LetsGo Admin</title>
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
    <div style="display:flex;gap:10px;align-items:center">
      <button class="btn btn-danger" onclick="confirmDeleteAllFailed()">Delete All Failed</button>
      <span class="badge" id="sms-total-count">{len(logs)} total</span>
    </div>
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
            <th>Action</th>
          </tr>
        </thead>
        <tbody id="sms-tbody">{rows}</tbody>
      </table>
    </div>
  </div>
</div>

<!-- Delete single modal -->
<div class="overlay" id="sms-del-overlay">
  <div class="modal">
    <h3>🗑 Delete SMS Log</h3>
    <p id="sms-del-msg">Delete this SMS log entry permanently?</p>
    <div class="modal-btns">
      <button class="btn btn-ghost" onclick="closeModal('sms-del-overlay')">Cancel</button>
      <button class="btn btn-danger" id="sms-del-confirm-btn">Delete</button>
    </div>
  </div>
</div>

<!-- Delete all failed modal -->
<div class="overlay" id="sms-del-all-overlay">
  <div class="modal">
    <h3>🗑 Delete All Failed Logs</h3>
    <p>This will permanently remove all <strong>✗ Failed</strong> SMS log entries. Sent logs will be kept.</p>
    <div class="modal-btns">
      <button class="btn btn-ghost" onclick="closeModal('sms-del-all-overlay')">Cancel</button>
      <button class="btn btn-danger" onclick="deleteAllFailed()">Delete Failed</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>
{ADMIN_JS}
<script>
let pendingSMSDeleteId = null;

function confirmDeleteSMS(id) {{
  pendingSMSDeleteId = id;
  document.getElementById('sms-del-msg').textContent = `Delete SMS log #${{id}} permanently?`;
  openModal('sms-del-overlay');
}}

document.getElementById('sms-del-confirm-btn').addEventListener('click', async () => {{
  if (!pendingSMSDeleteId) return;
  closeModal('sms-del-overlay');
  try {{
    const res  = await fetch(`/api/sms/log/${{pendingSMSDeleteId}}`, {{ method: 'DELETE' }});
    const data = await res.json();
    if (res.ok) {{
      document.getElementById(`sms-row-${{pendingSMSDeleteId}}`).remove();
      showToast('✓ Log entry deleted');
      updateCount();
    }} else {{
      showToast('✗ ' + (data.message || 'Delete failed'), 'error');
    }}
  }} catch (e) {{
    showToast('✗ Request failed', 'error');
  }}
  pendingSMSDeleteId = null;
}});

function confirmDeleteAllFailed() {{
  openModal('sms-del-all-overlay');
}}

async function deleteAllFailed() {{
  closeModal('sms-del-all-overlay');
  try {{
    const res  = await fetch('/api/sms/log/failed', {{ method: 'DELETE' }});
    const data = await res.json();
    if (res.ok) {{
      document.querySelectorAll('#sms-tbody tr').forEach(row => {{
        const statusSpan = row.querySelector('td:nth-child(10) span');
        if (statusSpan && statusSpan.textContent.includes('Failed')) row.remove();
      }});
      showToast(`✓ ${{data.deleted}} failed log(s) removed`);
      updateCount();
    }} else {{
      showToast('✗ ' + (data.message || 'Delete failed'), 'error');
    }}
  }} catch (e) {{
    showToast('✗ Request failed', 'error');
  }}
}}

function updateCount() {{
  const count = document.querySelectorAll('#sms-tbody tr[id]').length;
  document.getElementById('sms-total-count').textContent = count + ' total';
}}

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
      tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;padding:48px;color:#484f58">No SMS alerts logged yet.</td></tr>';
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
        <td><div style="font-family:monospace;font-size:12px;color:#e6edf3">${{l.toPhone}}</div></td>
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
        <td>
          <button class="btn btn-danger" style="font-size:11px;padding:4px 10px" onclick="confirmDeleteSMS(${{l.id}})">Delete</button>
        </td>
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


# ── Delete single SMS log entry ────────────────────────────
@app.route('/api/sms/log/<int:log_id>', methods=['DELETE'])
@require_admin
def delete_sms_log(log_id):
    log = db.session.get(SMSLog, log_id)
    if not log:
        return jsonify({'message': 'Log entry not found'}), 404
    db.session.delete(log)
    db.session.commit()
    return jsonify({'message': f'Log #{log_id} deleted'}), 200


# ── Delete all failed SMS logs ─────────────────────────────
@app.route('/api/sms/log/failed', methods=['DELETE'])
@require_admin
def delete_failed_sms_logs():
    failed = SMSLog.query.filter_by(sent=False).all()
    count  = len(failed)
    for log in failed:
        db.session.delete(log)
    db.session.commit()
    return jsonify({'message': f'{count} failed log(s) deleted', 'deleted': count}), 200
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


#### play a sound ####

@app.route('/trigger-sound', methods=['POST'])
def trigger():
    global pending
    pending = True
    return jsonify({'status': 'queued'})

@app.route('/poll', methods=['GET'])
def poll():
    global pending
    if pending:
        pending = False
        return jsonify({'play': True})
    return jsonify({'play': False})



# ═══════════════════════════════════════════════════════════
# PUBLIC TRACKING PAGE  /track/<token>
# ═══════════════════════════════════════════════════════════

@app.route('/track/<token>')
def tracking_page(token):
    sess = TrackingSession.query.filter_by(token=token).first()

    if sess:
        lat = sess.lat or '19.3465'
        lng = sess.lng or '-81.3958'
        username = sess.username or 'Rider'
        bus_id = sess.bus_id or 'CaymanBus'
        bus_name = sess.bus_name or 'Cayman Bus'
        route_id = sess.route_id or 'CaymanBus'
        active = sess.active
        updated = sess.updated_at.strftime('%H:%M:%S') if sess.updated_at else 'N/A'
    else:
        lat = '19.3465';
        lng = '-81.3958'
        username = 'Rider';
        bus_id = 'CaymanBus'
        bus_name = 'Cayman Bus';
        route_id = 'CaymanBus'
        active = True;
        updated = 'Demo'

    sc = '#16a34a' if active else '#6b7280'
    sl = 'LIVE' if active else 'ENDED'
    is_live_js = 'true' if active else 'false'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>LetsGo — {username}'s Journey</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:100%;font-family:'Outfit',sans-serif;background:#f8fafc;color:#1e293b;overflow:hidden}}
body{{display:flex;flex-direction:column}}

.hdr{{background:#fff;border-bottom:1px solid #e2e8f0;padding:10px 16px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;z-index:1000;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.hdr-logo{{font-size:15px;font-weight:700;color:#0B1F3A;display:flex;align-items:center;gap:6px}}
.hdr-logo span{{color:#F5C518}}
.hdr-center{{text-align:center}}
.hdr-center .title{{font-size:13px;font-weight:600;color:#1e293b}}
.hdr-center .sub{{font-size:11px;color:#94a3b8;margin-top:1px}}
.live-pill{{display:inline-flex;align-items:center;gap:5px;background:{sc}15;border:1px solid {sc}50;color:{sc};padding:4px 11px;border-radius:20px;font-size:11px;font-weight:700}}
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
.ended-bar{{background:#fef9c3;padding:7px 16px;text-align:center;font-size:11px;color:#854d0e;border-top:1px solid #fde68a}}

/* You-are-here pulse ring — pure CSS on a regular div, no embedded style tags */
.you-pulse{{width:36px;height:36px;border-radius:50%;background:#0ea5e9;display:flex;align-items:center;justify-content:center;font-size:18px;border:3px solid #fff;box-shadow:0 2px 8px rgba(14,165,233,.5);position:relative}}
.you-pulse::before{{content:'';position:absolute;inset:-8px;border-radius:50%;background:rgba(14,165,233,.2);animation:youRipple 1.8s ease-out infinite}}
.you-pulse::after{{content:'';position:absolute;inset:-16px;border-radius:50%;background:rgba(14,165,233,.1);animation:youRipple 1.8s ease-out .6s infinite}}
@keyframes youRipple{{0%{{transform:scale(.6);opacity:.8}}100%{{transform:scale(1.3);opacity:0}}}}

.leaflet-popup-content-wrapper{{border-radius:10px!important;box-shadow:0 4px 20px rgba(0,0,0,.12)!important}}
.leaflet-popup-content{{margin:10px 14px!important;font-family:'Outfit',sans-serif;font-size:12px;line-height:1.7;color:#1e293b}}
.leaflet-bar a{{background:#fff!important;color:#1e293b!important;border-color:#e2e8f0!important}}
.leaflet-bar a:hover{{color:#F5C518!important}}
.leaflet-container .leaflet-control-attribution{{font-size:9px!important;background:rgba(255,255,255,.7)!important}}
</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-logo">🚌 <span>LetsGo</span></div>
  <div class="hdr-center">
    <div class="title">{username}'s Journey</div>
    <div class="sub">{bus_id} · Route {route_id}</div>
  </div>
  <div class="live-pill"><div class="live-dot"></div>{sl}</div>
</div>

<div id="map"></div>

<div class="bottom">
  <div class="info-row">
    <div class="info-item">
      <div class="lbl">Rider</div>
      <div class="val">{username}</div>
    </div>
    <div class="info-item">
      <div class="lbl">Bus</div>
      <div class="val">{bus_id}</div>
      <div class="sub" id="bus-status">Searching…</div>
    </div>
    <div class="info-item eta-item">
      <div class="lbl">ETA</div>
      <div class="val" id="eta-val">—</div>
      <div class="sub" id="eta-stop">waiting for GPS</div>
    </div>
    <div class="info-item">
      <div class="lbl">Updated</div>
      <div class="val" id="last-upd" style="font-size:11px">{updated}</div>
      <div class="sub">bus time</div>
    </div>
  </div>
  <div class="coords-bar">
    <span class="ctxt" id="coords-txt">Acquiring your location…</span>
    {'<span class="rnote">Bus updates every 8s</span>' if active else ''}
  </div>
  {'<div class="ended-bar">Journey ended — showing last known position</div>' if not active else ''}
</div>

<script>
/* ── constants ── */
const TOKEN   = '{token}';
const IS_LIVE = {is_live_js};   /* proper JS boolean, not a string */

/* ── haversine (km) ── */
function hav(a,b,c,d){{
  const R=6371, dL=(c-a)*Math.PI/180, dN=(d-b)*Math.PI/180,
        x=Math.sin(dL/2)**2+Math.cos(a*Math.PI/180)*Math.cos(c*Math.PI/180)*Math.sin(dN/2)**2;
  return R*2*Math.atan2(Math.sqrt(x),Math.sqrt(1-x));
}}

/* ── map — LIGHT tiles ── */
const map = L.map('map',{{zoomControl:false,attributionControl:true}})
              .setView([19.2993,-81.3816],14);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png',
  {{subdomains:'abcd',maxZoom:19,attribution:'© OpenStreetMap © CartoDB'}}).addTo(map);
L.control.zoom({{position:'topright'}}).addTo(map);

/* ── stops ── */
const STOPS=[
  {{n:'George Town Depot',   lat:19.2869,lng:-81.3797}},
  {{n:'Walkers Road',        lat:19.2800,lng:-81.3650}},
  {{n:'Compass Media',       lat:19.2993,lng:-81.3816}},
  {{n:'Cayman Enterprise City',lat:19.3120,lng:-81.3900}},
  {{n:'Fairbanks Road',      lat:19.2750,lng:-81.3500}},
  {{n:'Hospitals',           lat:19.2900,lng:-81.3300}},
  {{n:'Schools Complex',     lat:19.2950,lng:-81.3200}},
  {{n:'Seven Mile Beach S',  lat:19.3044,lng:-81.3939}},
  {{n:'Camana Bay',          lat:19.3175,lng:-81.3982}},
  {{n:'Seven Mile Beach N',  lat:19.3340,lng:-81.3894}},
  {{n:'Cayman Turtle Centre',lat:19.3712,lng:-81.3789}},
  {{n:'Bodden Town',         lat:19.2842,lng:-81.2528}},
  {{n:'East End',            lat:19.3036,lng:-81.0914}},
  {{n:'Airport ORIA',        lat:19.2928,lng:-81.3576}},
];
const stopIco = L.divIcon({{html:'<div style="width:10px;height:10px;border-radius:50%;background:#F5C518;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.3)"></div>',iconSize:[10,10],iconAnchor:[5,5],className:''}});
STOPS.forEach(s=>{{
  L.marker([s.lat,s.lng],{{icon:stopIco}}).addTo(map)
   .bindTooltip('<b style="color:#0B1F3A">'+s.n+'</b>',{{direction:'top',offset:[0,-6],className:''}});
}});

/* route line */
L.polyline([[19.2869,-81.3797],[19.2800,-81.3650],[19.2993,-81.3816],
            [19.3120,-81.3900],[19.2750,-81.3500],[19.2900,-81.3300],[19.2950,-81.3200]],
  {{color:'#F5C518',weight:3,opacity:.45,dashArray:'8 5'}}).addTo(map);

/* ── BUS marker ── */
const busIco = L.divIcon({{
  html:'<div style="background:#F5C518;width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:22px;border:3px solid #fff;box-shadow:0 3px 10px rgba(245,197,24,.6)">🚌</div>',
  iconSize:[44,44],iconAnchor:[22,22],className:''
}});
let busMarker=null,busRing=null,busLat=null,busLng=null;

async function fetchBus(){{
  try{{
    const r=await fetch('/api/buses/coordinates');
    if(!r.ok)return;
    const data=await r.json();
    const route=(data.routes||[]).find(rt=>rt.liveLocation);
    if(!route?.liveLocation){{
      document.getElementById('bus-status').textContent='No live bus';
      return;
    }}
    const lat=parseFloat(route.liveLocation.lat),lng=parseFloat(route.liveLocation.lng);
    if(isNaN(lat)||isNaN(lng))return;
    busLat=lat; busLng=lng;
    const upd=route.liveLocation.updatedAt
      ? new Date(route.liveLocation.updatedAt).toLocaleTimeString() : 'now';
    if(!busMarker){{
      busRing=L.circle([lat,lng],{{color:'#F5C518',fillColor:'#F5C518',fillOpacity:.08,weight:1.5,radius:70}}).addTo(map);
      busMarker=L.marker([lat,lng],{{icon:busIco,zIndexOffset:200}}).addTo(map)
        .bindPopup('<b style="color:#0B1F3A">{bus_id}</b><br><span style="color:#64748b">{bus_name}</span><br><small style="color:#94a3b8">Updated '+upd+'</small>');
    }}else{{
      busMarker.setLatLng([lat,lng]);
      busRing.setLatLng([lat,lng]);
    }}
    document.getElementById('last-upd').textContent=upd;
    document.getElementById('bus-status').textContent='Online';
    calcETA();
  }}catch(e){{
    document.getElementById('bus-status').textContent='Offline';
    console.warn('bus:',e);
  }}
}}

/* ── YOU marker — note: icon html has NO embedded <style> tags ── */
const youIco = L.divIcon({{
  html:'<div class="you-pulse">📍</div>',
  iconSize:[36,36],iconAnchor:[18,18],className:''
}});
let youMarker=null,youCircle=null,youLat=null,youLng=null,geoStarted=false;

function startGeo(){{
  if(!navigator.geolocation){{
    document.getElementById('coords-txt').textContent='GPS not available on this device';
    return;
  }}
  /* getCurrentPosition fires immediately; watchPosition follows for updates */
  navigator.geolocation.getCurrentPosition(handlePos,handleGeoErr,{{enableHighAccuracy:true,timeout:15000}});
  navigator.geolocation.watchPosition(handlePos,handleGeoErr,{{enableHighAccuracy:true,maximumAge:4000,timeout:20000}});
}}

function handlePos(pos){{
  const lat=pos.coords.latitude, lng=pos.coords.longitude, acc=pos.coords.accuracy;
  youLat=lat; youLng=lng;

  /* push to server */
  if(IS_LIVE&&TOKEN){{
    fetch('/api/tracking/update',{{method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{token:TOKEN,lat,lng}})}});
  }}

  if(!youMarker){{
    youCircle=L.circle([lat,lng],{{color:'#0ea5e9',fillColor:'#0ea5e9',fillOpacity:.1,weight:1.5,radius:Math.max(20,acc)}}).addTo(map);
    youMarker=L.marker([lat,lng],{{icon:youIco,zIndexOffset:500}}).addTo(map)
      .bindTooltip('{username} — you',{{permanent:true,direction:'top',offset:[0,-22]}});
    /* pan map to show both you and bus if available */
    if(busLat!==null){{
      const bounds=L.latLngBounds([[lat,lng],[busLat,busLng]]);
      map.fitBounds(bounds,{{padding:[60,60],maxZoom:15}});
    }}else{{
      map.setView([lat,lng],15,{{animate:true}});
    }}
    geoStarted=true;
  }}else{{
    youMarker.setLatLng([lat,lng]);
    youCircle.setLatLng([lat,lng]);
    youCircle.setRadius(Math.max(20,acc));
  }}
  document.getElementById('coords-txt').textContent=
    '📍 You: '+lat.toFixed(5)+', '+lng.toFixed(5)+' (±'+Math.round(acc)+'m)';
  calcETA();
}}

function handleGeoErr(e){{
  const m={{1:'Location blocked — tap the lock icon in your browser and allow location',
           2:'GPS signal unavailable — try moving outside',
           3:'GPS timed out — retrying…'}};
  document.getElementById('coords-txt').textContent=m[e.code]||'GPS error '+e.code;
  document.getElementById('eta-stop').textContent='enable GPS to see ETA';
}}

/* ── ETA ── */
function calcETA(){{
  if(youLat===null)return;

  /* nearest stop to user */
  let nearest=null,minD=Infinity;
  STOPS.forEach(s=>{{const d=hav(youLat,youLng,s.lat,s.lng);if(d<minD){{minD=d;nearest=s;}}}});
  if(!nearest)return;

  const youToStop=Math.round(minD*1000); /* metres from you to stop */
  const etaEl=document.getElementById('eta-val');
  const subEl=document.getElementById('eta-stop');

  if(busLat!==null){{
    /* bus is online — use bus→stop distance */
    const busToStop=hav(busLat,busLng,nearest.lat,nearest.lng);
    const etaMin=Math.max(0,Math.round(busToStop/30*60)); /* 30 km/h */
    if(etaMin===0){{
      etaEl.textContent='Now'; etaEl.style.color='#16a34a';
      subEl.textContent='Bus arriving!';
    }}else if(etaMin===1){{
      etaEl.textContent='1 min'; etaEl.style.color='#ea580c';
      subEl.textContent=nearest.n;
    }}else{{
      etaEl.textContent=etaMin+' min'; etaEl.style.color='#F5C518';
      subEl.textContent=nearest.n;
    }}
  }}else{{
    /* no bus online — show walking distance to nearest stop */
    const walkMin=Math.round(youToStop/80); /* ~80m/min walking */
    etaEl.textContent=walkMin<1?'<1':walkMin+' min';
    etaEl.style.color='#94a3b8';
    subEl.textContent='walk to '+nearest.n;
  }}
}}

/* ── boot ── */
fetchBus();
startGeo();
if(IS_LIVE) setInterval(fetchBus,8000);
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
@app.route('/home')
@app.route('/team')
def landing():
    return LANDING_HTML


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
