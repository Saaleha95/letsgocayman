from flask import Flask, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import json

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
    'authToken':  os.environ.get('TWILIO_AUTH_TOKEN', ''),
    'fromNumber': os.environ.get('TWILIO_FROM_NUMBER', ''),
}

# Runtime override (persists until restart)
_twilio_override = {}


class User(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    username     = db.Column(db.String(80), unique=True, nullable=False)
    full_name    = db.Column(db.String(120), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    password     = db.Column(db.String(200), nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)


class CommunityReport(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    category   = db.Column(db.String(50), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    stop_name  = db.Column(db.String(120), nullable=False)
    route_id   = db.Column(db.String(20), default='Any')
    upvotes    = db.Column(db.Integer, default=0)
    upvoted_by = db.Column(db.Text, default='[]')   # JSON list of usernames
    status     = db.Column(db.String(20), default='open')
    username   = db.Column(db.String(80), nullable=False)
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

  /* NAV */
  .admin-nav{background:#161b22;border-bottom:1px solid #30363d;padding:0 32px;height:56px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
  .admin-nav .brand{font-size:18px;font-weight:700;color:var(--gold);display:flex;align-items:center;gap:8px}
  .admin-nav .nav-links{display:flex;gap:4px}
  .admin-nav .nav-links a{color:#8b949e;padding:6px 14px;border-radius:8px;font-size:13px;font-weight:500;transition:all .2s}
  .admin-nav .nav-links a:hover,.admin-nav .nav-links a.active{background:rgba(245,197,24,.1);color:var(--gold);text-decoration:none}
  .admin-nav .logout{color:#8b949e;font-size:13px;padding:6px 14px;border-radius:8px;border:1px solid #30363d;transition:all .2s}
  .admin-nav .logout:hover{border-color:var(--red);color:var(--red);text-decoration:none}

  /* LAYOUT */
  .admin-main{max-width:1100px;margin:0 auto;padding:32px 24px}
  .page-header{margin-bottom:28px;display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:12px}
  .page-header h1{font-size:24px;font-weight:700;color:#f0f6fc}
  .page-header p{font-size:14px;color:#8b949e;margin-top:4px}
  .badge{display:inline-flex;align-items:center;background:rgba(245,197,24,.12);border:1px solid rgba(245,197,24,.3);color:var(--gold);padding:5px 14px;border-radius:20px;font-size:13px;font-weight:600}

  /* CARDS */
  .card{background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;margin-bottom:24px}
  .card-header{padding:16px 20px;border-bottom:1px solid #30363d;display:flex;align-items:center;justify-content:space-between}
  .card-header h2{font-size:15px;font-weight:600;color:#f0f6fc}
  .card-body{padding:20px}

  /* TABLE */
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

  /* STATUS BADGES */
  .status{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600}
  .status.open{background:rgba(220,38,38,.12);color:#f87171}
  .status.in_progress{background:rgba(234,88,12,.12);color:#fb923c}
  .status.resolved{background:rgba(22,163,74,.12);color:#4ade80}

  /* BUTTONS */
  .btn{display:inline-flex;align-items:center;gap:6px;padding:7px 16px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none;transition:all .2s}
  .btn-primary{background:var(--gold);color:#0d1117}
  .btn-primary:hover{background:#e8b400}
  .btn-danger{background:rgba(220,38,38,.12);color:#f87171;border:1px solid rgba(220,38,38,.2)}
  .btn-danger:hover{background:rgba(220,38,38,.2)}
  .btn-success{background:rgba(22,163,74,.12);color:#4ade80;border:1px solid rgba(22,163,74,.2)}
  .btn-success:hover{background:rgba(22,163,74,.22)}
  .btn-ghost{background:transparent;color:#8b949e;border:1px solid #30363d}
  .btn-ghost:hover{border-color:#8b949e;color:#e6edf3}

  /* FORM */
  .form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
  .form-group{display:flex;flex-direction:column;gap:6px}
  .form-group label{font-size:12px;font-weight:600;color:#8b949e;text-transform:uppercase;letter-spacing:.5px}
  .form-group input,.form-group select,.form-group textarea{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:10px 12px;font-size:14px;color:#e6edf3;outline:none;transition:border-color .2s;font-family:inherit}
  .form-group input:focus,.form-group select:focus,.form-group textarea:focus{border-color:var(--gold)}
  .form-group textarea{resize:vertical;min-height:80px}
  .form-group select option{background:#0d1117}

  /* MODAL */
  .overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:200;align-items:center;justify-content:center}
  .overlay.show{display:flex}
  .modal{background:#161b22;border:1px solid #30363d;border-radius:16px;padding:28px;max-width:420px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,.5)}
  .modal h3{font-size:17px;font-weight:700;color:#f0f6fc;margin-bottom:8px}
  .modal p{font-size:14px;color:#8b949e;margin-bottom:22px;line-height:1.5}
  .modal-btns{display:flex;gap:10px;justify-content:flex-end}

  /* TOAST */
  .toast{position:fixed;bottom:24px;right:24px;background:#161b22;border:1px solid #30363d;color:#e6edf3;padding:12px 20px;border-radius:10px;font-size:14px;opacity:0;transform:translateY(16px);transition:all .3s;z-index:300;max-width:360px}
  .toast.show{opacity:1;transform:translateY(0)}
  .toast.success{border-color:rgba(22,163,74,.5);color:#4ade80}
  .toast.error{border-color:rgba(220,38,38,.5);color:#f87171}

  /* SETTINGS GRID */
  .settings-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
  @media(max-width:700px){.form-row,.settings-grid{grid-template-columns:1fr}.admin-nav .nav-links{display:none}}

  /* REFRESH BAR */
  .refresh-bar{font-size:12px;color:#484f58;text-align:right;margin-bottom:8px}
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
        <a href="/users" class="{'active' if active=='users' else ''}">Users</a>
        <a href="/community-reports" class="{'active' if active=='community' else ''}">Community Reports</a>
        <a href="/admin/settings" class="{'active' if active=='settings' else ''}">Settings</a>
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
          <div class="why-hl reveal reveal-delay-1"><div class="why-hl-icon">&#128506;</div><div><div class="why-hl-text">All Grand Cayman Routes</div><div class="why-hl-sub">George Town · West Bay · Bodden Town · East End</div></div></div>
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
        <div class="feat-num">01 ——</div><div class="feat-icon-wrap">&#128205;</div>
        <div class="feat-title" style="font-size:28px;color:var(--white)">AI Live Tracking &amp; ETA</div>
        <div class="feat-desc" style="max-width:560px">Real-time GPS with machine learning — predicts your bus arrival to within 60 seconds using Cayman traffic patterns, stop dwell times, and rush-hour data. Dead reckoning keeps tracking alive in coastal dead zones. Works 100% offline.</div>
        <div class="feat-row"><div class="feat-stat"><div class="fs-num">&lt;60s</div><div class="fs-lbl">ETA accuracy</div></div><div class="feat-stat"><div class="fs-num">100%</div><div class="fs-lbl">Offline ready</div></div><div class="feat-stat"><div class="fs-num">Live</div><div class="fs-lbl">GPS updates</div></div></div>
        <span class="feat-pill">AI · MACHINE LEARNING · ALWAYS ON</span>
      </div>
      <div class="feat-card reveal reveal-delay-1"><div class="feat-num">02 ——</div><div class="feat-icon-wrap">&#128179;</div><div class="feat-title">Smart Payment</div><div class="feat-desc">NFC tap-and-go that works without internet. Your signed token wallet holds up to 10 rides and syncs automatically when you reconnect. No cash, no hassle.</div><span class="feat-pill">NFC · OFFLINE · SECURE</span></div>
      <div class="feat-card reveal reveal-delay-2"><div class="feat-num">03 ——</div><div class="feat-icon-wrap">&#128483;</div><div class="feat-title">Community Reports</div><div class="feat-desc">Caymanians helping Caymanians. Report stop conditions, route issues, and bus feedback in real time. Your upvotes shape the network for everyone.</div><span class="feat-pill">CROWDSOURCED · REAL TIME</span></div>
      <div class="feat-card reveal reveal-delay-1"><div class="feat-num">04 ——</div><div class="feat-icon-wrap">&#128737;</div><div class="feat-title">Safety Features</div><div class="feat-desc">Share your live journey with family. One-tap SOS sends your exact bus GPS location to emergency contacts and our ops team. Safe arrival notifications built in.</div><span class="feat-pill">SOS · LIVE SHARE · SAFE JOURNEY</span></div>
      <div class="feat-card reveal reveal-delay-2"><div class="feat-num">05 ——</div><div class="feat-icon-wrap">&#127807;</div><div class="feat-title">Eco Impact Tracker</div><div class="feat-desc">Every bus ride over a car saves CO&#8322;. See your monthly carbon savings, earn eco badges, and help protect Cayman's coral reefs and natural environment.</div><span class="feat-pill">GREEN · CAYMAN PROUD</span></div>
    </div>
  </section>
  <section class="how-section">
    <div class="section-eyebrow">Simple as 1-2-3-4</div>
    <h2 class="section-title">HOW IT <span class="accent">WORKS</span></h2>
    <div class="steps-row">
      <div class="step-card reveal"><div class="step-num">1</div><div class="step-title">Download Free</div><div class="step-desc">Get LetsGo on iOS or Android in seconds. Free forever for riders.</div></div>
      <div class="step-card reveal reveal-delay-1"><div class="step-num">2</div><div class="step-title">Find Your Route</div><div class="step-desc">Type where you're going or browse all Grand Cayman routes on the live map.</div></div>
      <div class="step-card reveal reveal-delay-2"><div class="step-num">3</div><div class="step-title">Tap &amp; Pay</div><div class="step-desc">Load your wallet once. Tap your phone at the reader — even with no signal.</div></div>
      <div class="step-card reveal reveal-delay-3"><div class="step-num">4</div><div class="step-title">Track &amp; Ride</div><div class="step-desc">Watch your bus approach in real time. Get notified before it arrives. Sit back, relax.</div></div>
    </div>
  </section>
  <section class="dl-section" id="dl">
    <p class="section-eyebrow" style="color:rgba(11,31,58,.5)">Free to download</p>
    <h2 class="dl-title">GET ON<br>THE BUS</h2>
    <p class="dl-sub">Available on iOS and Android. Ride smarter across Grand Cayman starting today.</p>
    <div class="dl-btns reveal">
      <a href="#" class="dl-app-btn"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg><div class="dl-t"><small>Download on the</small><strong>App Store</strong></div></a>
      <a href="#" class="dl-app-btn"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M3.18 23.76c.3.17.64.22.99.14l12.82-7.41-2.79-2.79-11.02 10.06zM.35 1.33C.13 1.66 0 2.1 0 2.67v18.66c0 .57.13 1.01.36 1.34l.07.07 10.46-10.46v-.25L.42 1.27l-.07.06zM20.96 10.18l-2.64-1.53-3.13 3.13 3.13 3.13 2.65-1.54c.76-.44.76-1.15 0-1.6l-.01.41zM4.17.24l12.82 7.41-2.79 2.79L4.17.24c.35-.09.7-.04.99.14l-.99-.14z"/></svg><div class="dl-t"><small>Get it on</small><strong>Google Play</strong></div></a>
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
    <div class="team-intro reveal"><p>LetsGo was born from a simple frustration — getting around Grand Cayman on public transport shouldn't be a guessing game. This small team of technologists decided to do something about it, combining AI, offline-first engineering, and a deep love for the Cayman Islands.</p></div>
    <div class="team-grid">
      <div class="team-card reveal">
        <div class="team-card-header bg1"><div class="team-avatar">SA</div><div class="team-hdr-info"><div class="team-name">Saaleha AbrarAli</div><div class="team-role-badge">Co-Founder</div></div></div>
        <div class="team-body"><p class="team-quote">"It was really cool to bring up the idea and make it live in Cayman Island, mainly for bus transport. Seeing real riders use what we built — that's everything."</p><a href="https://www.linkedin.com/in/saaleha-aafreen-a56b49105/" target="_blank" class="team-linkedin"><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>Connect on LinkedIn</a></div>
      </div>
      <div class="team-card reveal reveal-delay-1">
        <div class="team-card-header bg2"><div class="team-avatar">SF</div><div class="team-hdr-info"><div class="team-name">Safee</div><div class="team-role-badge">Co-Founder</div></div></div>
        <div class="team-body"><p class="team-quote">"Every line of code was written with one goal — making daily life in Cayman easier, safer, and more connected for everyone on the island."</p><div class="team-skills"><span class="skill-tag">Mobile Dev</span><span class="skill-tag">Backend Systems</span><span class="skill-tag">Offline-First</span><span class="skill-tag">GPS &amp; NFC</span></div><a href="https://www.linkedin.com/in/mohammad-safeeullah-a64007a5/" target="_blank" class="team-linkedin"><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>Connect on LinkedIn</a></div>
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
                'authToken':  request.form.get('authToken', '').strip(),
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

  <!-- TWILIO CONFIG -->
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
            <input type="text" name="accountSid" value="{current_twilio.get('accountSid','')}" placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx">
          </div>
          <div class="form-group">
            <label>From Number</label>
            <input type="text" name="fromNumber" value="{current_twilio.get('fromNumber','')}" placeholder="+1345XXXXXXX">
          </div>
        </div>
        <div class="form-group" style="margin-bottom:20px">
          <label>Auth Token</label>
          <input type="password" name="authToken" value="{current_twilio.get('authToken','')}" placeholder="Your Twilio auth token">
        </div>
        <button type="submit" class="btn btn-primary">Save Twilio Config</button>
      </form>
      <div style="margin-top:16px;padding:14px 16px;background:#0d1117;border-radius:8px;border:1px solid #21262d">
        <p style="font-size:12px;color:#6e7681;line-height:1.7">
          <strong style="color:#8b949e">How it works:</strong> The app first calls <code style="color:var(--gold)">/api/safety/send-sms</code> on this server.
          If that fails, the app fetches <code style="color:var(--gold)">/api/users</code> and reads <code style="color:var(--gold)">data.twilio</code> to call Twilio directly.
          Keep credentials server-side when possible for security.
        </p>
      </div>
    </div>
  </div>

  <!-- ADMIN CREDS INFO -->
  <div class="card">
    <div class="card-header"><h2>🔐 Admin Credentials</h2></div>
    <div class="card-body">
      <p style="font-size:14px;color:#8b949e;line-height:1.7;margin-bottom:12px">
        Admin credentials are set via environment variables on your server:
      </p>
      <div style="background:#0d1117;border-radius:8px;padding:16px;border:1px solid #21262d;font-family:monospace;font-size:13px;color:#e6edf3;line-height:2">
        <div><span style="color:#6e7681">ADMIN_USERNAME</span>=<span style="color:var(--gold)">your_username</span></div>
        <div><span style="color:#6e7681">ADMIN_PASSWORD</span>=<span style="color:var(--gold)">your_password</span></div>
        <div><span style="color:#6e7681">TWILIO_ACCOUNT_SID</span>=<span style="color:var(--gold)">ACxxxx</span></div>
        <div><span style="color:#6e7681">TWILIO_AUTH_TOKEN</span>=<span style="color:var(--gold)">xxxx</span></div>
        <div><span style="color:#6e7681">TWILIO_FROM_NUMBER</span>=<span style="color:var(--gold)">+1345xxxx</span></div>
        <div><span style="color:#6e7681">SECRET_KEY</span>=<span style="color:var(--gold)">your_flask_secret</span></div>
      </div>
      <p style="font-size:12px;color:#484f58;margin-top:12px">Set these in Render → Environment → Environment Variables. Changes take effect on redeploy.</p>
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
        joined   = user.created_at.strftime('%d %b %Y, %H:%M')
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

<!-- EDIT MODAL -->
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

<!-- DELETE MODAL -->
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
  const body={{
    username: document.getElementById('edit-username').value,
    fullName: document.getElementById('edit-fullname').value,
    phoneNumber: document.getElementById('edit-phone').value,
  }};
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
      return `<tr id="row-${{u.id}}">
        <td><div class="avatar">${{ini}}</div></td>
        <td><strong style="color:#f0f6fc">${{u.username}}</strong></td>
        <td style="color:#8b949e">${{u.fullName}}</td>
        <td style="color:#8b949e">${{u.phoneNumber}}</td>
        <td><span class="lock">🔒 hidden</span></td>
        <td class="date-cell">${{u.createdAt}}</td>
        <td>
          <button class="btn btn-danger" onclick="openEditModal(${{u.id}},'${{u.username}}','${{u.fullName}}','${{u.phoneNumber}}')">Edit</button>
          <button class="btn btn-danger" style="margin-left:6px" onclick="confirmDelete(${{u.id}},'${{u.username}}')">Delete</button>
        </td>
      </tr>`;
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

    STATUS_COLORS = {
        'open': ('#f87171', 'Open'),
        'in_progress': ('#fb923c', 'In Progress'),
        'resolved': ('#4ade80', 'Resolved'),
    }

    rows = ""
    for r in reports:
        color, label = STATUS_COLORS.get(r.status, ('#8b949e', r.status))
        joined = r.created_at.strftime('%d %b %Y, %H:%M')
        msg_preview = (r.message[:60] + '…') if len(r.message) > 60 else r.message
        upvoted_list = json.loads(r.upvoted_by or '[]')
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
<style>
  table td{{max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
</style>
</head>
<body>
{nav_html('community')}
<div class="admin-main">
  <div class="page-header">
    <div>
      <h1>📣 Community Reports</h1>
      <p>Reports submitted by LetsGo riders</p>
    </div>
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

<!-- EDIT REPORT MODAL -->
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

<!-- DELETE REPORT MODAL -->
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

function openRepEdit(id, status, msg){{
  document.getElementById('rep-edit-id').value=id;
  document.getElementById('rep-edit-status').value=status;
  document.getElementById('rep-edit-msg').value=msg;
  openModal('rep-edit-overlay');
}}

async function saveRepEdit(){{
  const id=document.getElementById('rep-edit-id').value;
  const body={{status:document.getElementById('rep-edit-status').value, message:document.getElementById('rep-edit-msg').value}};
  try{{
    const res=await fetch(`/api/community/reports/${{id}}`,{{method:'PATCH',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
    const data=await res.json();
    if(res.ok){{closeModal('rep-edit-overlay');showToast('✓ Report updated');refreshReports();}}
    else showToast('✗ '+data.message,'error');
  }}catch(e){{showToast('✗ Update failed','error');}}
}}

function confirmRepDelete(id){{
  pendingRepDeleteId=id;
  document.getElementById('rep-del-msg').textContent=`Delete report #${{id}} permanently?`;
  openModal('rep-del-overlay');
}}

document.getElementById('confirm-rep-del-btn').addEventListener('click', async()=>{{
  if(!pendingRepDeleteId)return; closeModal('rep-del-overlay');
  try{{
    const res=await fetch(`/api/community/reports/${{pendingRepDeleteId}}`,{{method:'DELETE'}});
    const data=await res.json();
    if(res.ok){{document.getElementById(`rep-row-${{pendingRepDeleteId}}`).remove();showToast('✓ '+data.message);refreshRepCount();}}
    else showToast('✗ '+data.message,'error');
  }}catch(e){{showToast('✗ Delete failed','error');}}
  pendingRepDeleteId=null;
}});

function refreshRepCount(){{
  const rows=document.querySelectorAll('#rep-tbody tr[id]').length;
  document.getElementById('rep-count').textContent=rows+' report(s)';
}}

async function refreshReports(){{
  try{{
    const res=await fetch('/api/community/reports/');const data=await res.json();
    const tbody=document.getElementById('rep-tbody');
    const STATUS={{'open':['#f87171','Open'],'in_progress':['#fb923c','In Progress'],'resolved':['#4ade80','Resolved']}};
    if(!data.reports||data.reports.length===0){{tbody.innerHTML='<tr><td colspan="10" style="text-align:center;padding:48px;color:#484f58">No community reports yet.</td></tr>';document.getElementById('rep-count').textContent='0 report(s)';return;}}
    tbody.innerHTML=data.reports.map(r=>{{
      const[color,label]=STATUS[r.status]||['#8b949e',r.status];
      const preview=r.message.length>60?r.message.slice(0,60)+'…':r.message;
      return `<tr id="rep-row-${{r.id}}">
        <td style="color:#6e7681;font-size:12px">#${{r.id}}</td>
        <td><span style="background:rgba(245,197,24,.1);color:var(--gold);padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600">${{r.category}}</span></td>
        <td style="color:#8b949e;max-width:220px">${{preview}}</td>
        <td style="color:#8b949e;font-size:13px">${{r.stopName}}</td>
        <td style="color:#8b949e;font-size:13px">${{r.routeId}}</td>
        <td style="color:var(--gold);font-weight:600">${{r.upvotes}} 👍</td>
        <td><span style="color:${{color}};background:${{color}}18;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600">${{label}}</span></td>
        <td style="color:#6e7681;font-size:12px">${{r.username}}</td>
        <td class="date-cell">${{r.createdAt}}</td>
        <td>
          <button class="btn btn-ghost" style="font-size:12px;padding:5px 10px" onclick="openRepEdit(${{r.id}},'${{r.status}}',\`${{r.message}}\`)">Edit</button>
          <button class="btn btn-danger" style="font-size:12px;padding:5px 10px;margin-left:4px" onclick="confirmRepDelete(${{r.id}})">Del</button>
        </td>
      </tr>`;
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
# API ROUTES
# ═══════════════════════════════════════════════════════════

@app.route('/ping')
def ping():
    return jsonify({'status': 'ok'}), 200


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


# ── GET ALL USERS (JSON) ───────────────────────────────────
@app.route('/api/users', methods=['GET'])
def api_users():
    users = User.query.order_by(User.created_at.desc()).all()
    current_twilio = {**TWILIO_CONFIG, **_twilio_override}
    return jsonify({
        'total': len(users),
        'users': [{
            'id':          u.id,
            'username':    u.username,
            'fullName':    u.full_name,
            'phoneNumber': u.phone_number,
            'createdAt':   u.created_at.strftime('%d %b %Y, %H:%M')
        } for u in users],
        # Twilio config exposed for client-side fallback (as documented)
        'twilio': current_twilio,
        'config': {'twilio': current_twilio},
    })


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


# ── PATCH USER ─────────────────────────────────────────────
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
        'id': user.id,
        'username': user.username,
        'fullName': user.full_name,
        'phoneNumber': user.phone_number,
    }}), 200


# ── COMMUNITY REPORTS — GET / POST ─────────────────────────
@app.route('/api/community/reports/', methods=['GET', 'POST'])
def community_reports():
    if request.method == 'GET':
        reports = CommunityReport.query.order_by(CommunityReport.created_at.desc()).all()
        return jsonify({
            'total': len(reports),
            'reports': [{
                'id':        r.id,
                'category':  r.category,
                'message':   r.message,
                'stopName':  r.stop_name,
                'routeId':   r.route_id,
                'upvotes':   r.upvotes,
                'upvotedByMe': False,
                'status':    r.status,
                'username':  r.username,
                'createdAt': r.created_at.isoformat(),
            } for r in reports]
        })

    data = request.get_json()
    if not data:
        return jsonify({'message': 'No data provided'}), 400

    report = CommunityReport(
        category  = data.get('category', 'other'),
        message   = data.get('message', ''),
        stop_name = data.get('stopName', ''),
        route_id  = data.get('routeId', 'Any'),
        username  = data.get('username', 'anonymous'),
    )
    db.session.add(report)
    db.session.commit()

    return jsonify({'report': {
        'id':          report.id,
        'category':    report.category,
        'message':     report.message,
        'stopName':    report.stop_name,
        'routeId':     report.route_id,
        'upvotes':     0,
        'upvotedByMe': False,
        'status':      report.status,
        'username':    report.username,
        'createdAt':   report.created_at.isoformat(),
    }}), 201


# ── COMMUNITY REPORT — PATCH / DELETE ──────────────────────
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


# ── UPVOTE REPORT ──────────────────────────────────────────
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


# ── TWILIO SMS RELAY ───────────────────────────────────────
@app.route('/api/safety/send-sms', methods=['POST'])
def send_sms():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No data provided'}), 400

    to_number = data.get('to')
    message   = data.get('message', '')

    if not to_number or not message:
        return jsonify({'message': 'to and message are required'}), 400

    current_twilio = {**TWILIO_CONFIG, **_twilio_override}
    account_sid = current_twilio.get('accountSid', '')
    auth_token  = current_twilio.get('authToken', '')
    from_number = current_twilio.get('fromNumber', '')

    if not all([account_sid, auth_token, from_number]):
        return jsonify({'message': 'Twilio not configured. Set credentials in Admin → Settings.'}), 503

    try:
        import urllib.request, urllib.parse, base64
        url = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'
        payload = urllib.parse.urlencode({
            'To':   to_number,
            'From': from_number,
            'Body': message,
        }).encode()
        credentials = base64.b64encode(f'{account_sid}:{auth_token}'.encode()).decode()
        req = urllib.request.Request(url, data=payload, method='POST')
        req.add_header('Authorization', f'Basic {credentials}')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
        return jsonify({'message': 'SMS sent', 'sid': result.get('sid')}), 200
    except Exception as e:
        return jsonify({'message': f'SMS failed: {str(e)}'}), 500


# ── LANDING PAGE ───────────────────────────────────────────
@app.route('/')
@app.route('/home')
@app.route('/team')
def landing():
    return LANDING_HTML


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
