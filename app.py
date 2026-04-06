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
    phone_number = db.Column(db.String(20), nullable=False)
    password     = db.Column(db.String(200), nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()


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

/* NAV */
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

/* PAGE TABS */
.page-nav{display:flex;position:fixed;top:72px;left:0;right:0;z-index:190;background:var(--navy);border-bottom:2px solid rgba(245,197,24,.2);justify-content:center}
.pnav-btn{background:none;border:none;color:rgba(255,255,255,.6);font-family:'Outfit',sans-serif;font-size:13px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;padding:12px 28px;cursor:pointer;transition:color .2s,border-bottom .2s;border-bottom:2px solid transparent;margin-bottom:-2px}
.pnav-btn.active,.pnav-btn:hover{color:var(--gold);border-bottom-color:var(--gold)}

.page{display:none;min-height:100vh}
.page.active{display:block}

/* HERO */
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

/* BUS */
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

/* WHY CAYMAN */
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

/* FEATURES */
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

/* HOW IT WORKS */
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

/* DOWNLOAD */
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

/* TEAM PAGE */
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

/* FOOTER */
footer{background:var(--navy);border-top:1px solid rgba(245,197,24,.1);padding:40px 60px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px}
.footer-logo{font-family:'Playfair Display',serif;font-size:20px;font-weight:900;color:var(--gold)}
.footer-links{display:flex;gap:24px}
.footer-links a{color:rgba(255,255,255,.35);font-size:13px;text-decoration:none;transition:color .2s}
.footer-links a:hover{color:var(--gold)}
.footer-copy{font-size:12px;color:rgba(255,255,255,.25)}
.footer-admin{color:rgba(255,255,255,.2);font-size:11px;text-decoration:none;padding:4px 10px;border:1px solid rgba(255,255,255,.1);border-radius:6px;transition:all .2s}
.footer-admin:hover{color:var(--gold);border-color:rgba(245,197,24,.3)}

/* REVEAL */
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

<!-- NAV -->
<nav id="nav">
  <a class="nav-logo" href="#"><span class="dot"></span> LetsGo</a>
  <ul class="nav-links">
    <li><a href="#" onclick="showPage('home')">Home</a></li>
    <li><a href="#" onclick="showPage('home');setTimeout(()=>document.getElementById('features').scrollIntoView({behavior:'smooth'}),200)">Features</a></li>
    <li><a href="#" onclick="showPage('team')">Our Team</a></li>
  </ul>
  <a href="#dl" class="nav-dl" onclick="showPage('home')">Download App</a>
</nav>

<!-- PAGE TABS -->
<div class="page-nav">
  <button class="pnav-btn active" id="tab-home" onclick="showPage('home')">Home</button>
  <button class="pnav-btn" id="tab-team" onclick="showPage('team')">Meet Our Team</button>
</div>

<!-- ═══ HOME PAGE ═══ -->
<div class="page active" id="page-home">
  <section class="hero">
    <div class="flag-stripe"></div>
    <div class="stars" id="stars"></div>
    <svg class="palm-left" width="200" height="400" viewBox="0 0 200 400">
      <path d="M100 400 Q95 300 80 250 Q40 200 10 180 Q50 190 70 220 Q60 170 20 140 Q65 165 80 200 Q75 150 50 110 Q85 145 90 190 Q90 130 70 80 Q100 130 95 200 Q110 130 130 80 Q110 140 115 200 Q120 150 150 110 Q125 155 120 200 Q135 165 180 140 Q145 170 130 220 Q150 190 190 180 Q160 200 120 250 Q105 300 105 400Z" fill="white"/>
    </svg>
    <svg class="palm-right" width="180" height="360" viewBox="0 0 180 360" style="right:0">
      <path d="M90 360 Q85 270 70 225 Q35 180 8 162 Q45 172 63 198 Q54 153 18 126 Q59 149 72 180 Q68 135 45 99 Q77 131 81 171 Q81 117 63 72 Q90 117 86 180 Q99 117 117 72 Q99 126 103 180 Q108 135 136 99 Q113 139 109 180 Q121 149 162 126 Q131 153 117 198 Q135 172 172 162 Q145 180 110 225 Q95 270 95 360Z" fill="white"/>
    </svg>
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
    <!-- Animated bus -->
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
          <circle cx="440" cy="2" r="3" fill="#F5C518">
            <animate attributeName="r" values="3;5;3" dur="1.5s" repeatCount="indefinite"/>
            <animate attributeName="opacity" values="1;0.4;1" dur="1.5s" repeatCount="indefinite"/>
          </circle>
          <g class="wheel-spin">
            <circle cx="108" cy="172" r="28" fill="#0B1F3A" stroke="#F5C518" stroke-width="2.5"/>
            <circle cx="108" cy="172" r="17" fill="#1a2a3a" stroke="#F5C518" stroke-width="1.5"/>
            <circle cx="108" cy="172" r="5" fill="#F5C518"/>
            <line x1="108" y1="156" x2="108" y2="188" stroke="#F5C518" stroke-width="1.5" opacity=".5"/>
            <line x1="92" y1="172" x2="124" y2="172" stroke="#F5C518" stroke-width="1.5" opacity=".5"/>
          </g>
          <g class="wheel-spin">
            <circle cx="376" cy="172" r="28" fill="#0B1F3A" stroke="#F5C518" stroke-width="2.5"/>
            <circle cx="376" cy="172" r="17" fill="#1a2a3a" stroke="#F5C518" stroke-width="1.5"/>
            <circle cx="376" cy="172" r="5" fill="#F5C518"/>
            <line x1="376" y1="156" x2="376" y2="188" stroke="#F5C518" stroke-width="1.5" opacity=".5"/>
            <line x1="360" y1="172" x2="392" y2="172" stroke="#F5C518" stroke-width="1.5" opacity=".5"/>
          </g>
        </svg>
      </div>
    </div>
    <div class="road-strip">
      <div class="road-mark"></div>
      <div class="road-mark" style="left:300px"></div>
      <div class="road-mark" style="left:600px"></div>
    </div>
    <svg class="hero-waves" viewBox="0 0 1440 80" preserveAspectRatio="none" style="display:block">
      <path d="M0,60 C360,100 1080,20 1440,60 L1440,80 L0,80Z" fill="#F9F4E8" opacity=".5"/>
    </svg>
  </section>

  <!-- WHY CAYMAN -->
  <section class="why-section">
    <div class="section-eyebrow">Built for Cayman</div>
    <div class="why-grid">
      <div class="why-text reveal">
        <h2 class="section-title">TRANSPORT<br>THAT KNOWS<br><span class="accent">GRAND CAYMAN</span></h2>
        <p style="margin-top:24px">Getting around Grand Cayman just got smarter. Whether you're heading to work in George Town, school in Bodden Town, or the beach on Seven Mile — <strong>LetsGo has your route covered</strong>.</p>
        <p>We know the roads, the schedules, and the Cayman way of life. No more guessing when the next bus comes. No more missed rides. Just tap and go.</p>
        <div class="why-highlights">
          <div class="why-hl reveal reveal-delay-1">
            <div class="why-hl-icon">&#128506;</div>
            <div><div class="why-hl-text">All 9 Grand Cayman Routes</div><div class="why-hl-sub">George Town · West Bay · Bodden Town · East End</div></div>
          </div>
          <div class="why-hl reveal reveal-delay-2">
            <div class="why-hl-icon">&#127754;</div>
            <div><div class="why-hl-text">Works in Dead Zones</div><div class="why-hl-sub">Full offline support — even along the coast roads</div></div>
          </div>
          <div class="why-hl reveal reveal-delay-3">
            <div class="why-hl-icon">&#127472;&#127486;</div>
            <div><div class="why-hl-text">Made for Caymanians</div><div class="why-hl-sub">Local team, local knowledge, local pride</div></div>
          </div>
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
          <rect x="145" y="82" width="20" height="10" rx="3" fill="#F5C518">
            <animateTransform attributeName="transform" type="translate" values="0,0;60,3;0,0" dur="5s" repeatCount="indefinite"/>
          </rect>
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

  <!-- FEATURES -->
  <section class="features-section" id="features">
    <div class="features-intro reveal">
      <div class="section-eyebrow">What's inside</div>
      <h2 class="section-title">EVERYTHING<br>YOUR <span class="accent">RIDE</span> NEEDS</h2>
    </div>
    <div class="features-grid">
      <div class="feat-card featured reveal">
        <div class="feat-num">01 ——</div>
        <div class="feat-icon-wrap">&#128205;</div>
        <div class="feat-title" style="font-size:28px;color:var(--white)">AI Live Tracking &amp; ETA</div>
        <div class="feat-desc" style="max-width:560px">Real-time GPS with machine learning — predicts your bus arrival to within 60 seconds using Cayman traffic patterns, stop dwell times, and rush-hour data. Dead reckoning keeps tracking alive in coastal dead zones. Works 100% offline.</div>
        <div class="feat-row">
          <div class="feat-stat"><div class="fs-num">&lt;60s</div><div class="fs-lbl">ETA accuracy</div></div>
          <div class="feat-stat"><div class="fs-num">100%</div><div class="fs-lbl">Offline ready</div></div>
          <div class="feat-stat"><div class="fs-num">Live</div><div class="fs-lbl">GPS updates</div></div>
        </div>
        <span class="feat-pill">AI · MACHINE LEARNING · ALWAYS ON</span>
      </div>
      <div class="feat-card reveal reveal-delay-1">
        <div class="feat-num">02 ——</div>
        <div class="feat-icon-wrap">&#128179;</div>
        <div class="feat-title">Smart Payment</div>
        <div class="feat-desc">NFC tap-and-go that works without internet. Your signed token wallet holds up to 10 rides and syncs automatically when you reconnect. No cash, no hassle.</div>
        <span class="feat-pill">NFC · OFFLINE · SECURE</span>
      </div>
      <div class="feat-card reveal reveal-delay-2">
        <div class="feat-num">03 ——</div>
        <div class="feat-icon-wrap">&#128483;</div>
        <div class="feat-title">Community Reports</div>
        <div class="feat-desc">Caymanians helping Caymanians. Report stop conditions, route issues, and bus feedback in real time. Your upvotes shape the network for everyone.</div>
        <span class="feat-pill">CROWDSOURCED · REAL TIME</span>
      </div>
      <div class="feat-card reveal reveal-delay-1">
        <div class="feat-num">04 ——</div>
        <div class="feat-icon-wrap">&#128737;</div>
        <div class="feat-title">Safety Features</div>
        <div class="feat-desc">Share your live journey with family. One-tap SOS sends your exact bus GPS location to emergency contacts and our ops team. Safe arrival notifications built in.</div>
        <span class="feat-pill">SOS · LIVE SHARE · SAFE JOURNEY</span>
      </div>
      <div class="feat-card reveal reveal-delay-2">
        <div class="feat-num">05 ——</div>
        <div class="feat-icon-wrap">&#127807;</div>
        <div class="feat-title">Eco Impact Tracker</div>
        <div class="feat-desc">Every bus ride over a car saves CO&#8322;. See your monthly carbon savings, earn eco badges, and help protect Cayman's coral reefs and natural environment.</div>
        <span class="feat-pill">GREEN · CAYMAN PROUD</span>
      </div>
    </div>
  </section>

  <!-- HOW IT WORKS -->
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

  <!-- DOWNLOAD -->
  <section class="dl-section" id="dl">
    <p class="section-eyebrow" style="color:rgba(11,31,58,.5)">Free to download</p>
    <h2 class="dl-title">GET ON<br>THE BUS</h2>
    <p class="dl-sub">Available on iOS and Android. Ride smarter across Grand Cayman starting today.</p>
    <div class="dl-btns reveal">
      <a href="#" class="dl-app-btn">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>
        <div class="dl-t"><small>Download on the</small><strong>App Store</strong></div>
      </a>
      <a href="#" class="dl-app-btn">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M3.18 23.76c.3.17.64.22.99.14l12.82-7.41-2.79-2.79-11.02 10.06zM.35 1.33C.13 1.66 0 2.1 0 2.67v18.66c0 .57.13 1.01.36 1.34l.07.07 10.46-10.46v-.25L.42 1.27l-.07.06zM20.96 10.18l-2.64-1.53-3.13 3.13 3.13 3.13 2.65-1.54c.76-.44.76-1.15 0-1.6l-.01.41zM4.17.24l12.82 7.41-2.79 2.79L4.17.24c.35-.09.7-.04.99.14l-.99-.14z"/></svg>
        <div class="dl-t"><small>Get it on</small><strong>Google Play</strong></div>
      </a>
    </div>
  </section>

  <footer>
    <div class="footer-logo">&#128652; LetsGo</div>
    <div class="footer-links">
      <a href="#" onclick="showPage('home')">Home</a>
      <a href="#features" onclick="showPage('home')">Features</a>
      <a href="#" onclick="showPage('team')">Team</a>
    </div>
    <div class="footer-copy">&#169; 2026 LetsGo · Cayman Islands</div>
    <a href="/users" class="footer-admin">Admin</a>
  </footer>
</div>

<!-- ═══ TEAM PAGE ═══ -->
<div class="page" id="page-team">
  <section class="team-hero">
    <div class="section-eyebrow" style="color:var(--gold)">The people behind the app</div>
    <h2 class="section-title">MEET THE <span class="accent">MINDS</span><br>BEHIND LETSGO</h2>
    <p class="team-hero-sub">A passionate team that believed Cayman deserved smarter, more connected public transport — and built it.</p>
    <svg viewBox="0 0 1440 80" preserveAspectRatio="none" style="position:absolute;bottom:0;left:0;right:0;display:block">
      <path d="M0,40 C480,90 960,10 1440,50 L1440,80 L0,80Z" fill="#F9F4E8"/>
    </svg>
  </section>
  <section class="team-main">
    <div class="team-intro reveal">
      <p>LetsGo was born from a simple frustration — getting around Grand Cayman on public transport shouldn't be a guessing game. This small team of technologists decided to do something about it, combining AI, offline-first engineering, and a deep love for the Cayman Islands.</p>
    </div>
    <div class="team-grid">
      <!-- Saaleha -->
      <div class="team-card reveal">
        <div class="team-card-header bg1">
          <div class="team-avatar">SA</div>
          <div class="team-hdr-info">
            <div class="team-name">Saaleha AbrarAli</div>
            <div class="team-role-badge">Co-Founder</div>
          </div>
        </div>
        <div class="team-body">
          <p class="team-quote">"It was really cool to bring up the idea and make it live in Cayman Island, mainly for bus transport. Seeing real riders use what we built — that's everything."</p>
          <a href="https://www.linkedin.com/in/saaleha-aafreen-a56b49105/" target="_blank" class="team-linkedin">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
            Connect on LinkedIn
          </a>
        </div>
      </div>
      <!-- Safee -->
      <div class="team-card reveal reveal-delay-1">
        <div class="team-card-header bg2">
          <div class="team-avatar">SF</div>
          <div class="team-hdr-info">
            <div class="team-name">Safee</div>
            <div class="team-role-badge">Co-Founder</div>
          </div>
        </div>
        <div class="team-body">
          <p class="team-quote">"Every line of code was written with one goal — making daily life in Cayman easier, safer, and more connected for everyone on the island."</p>
          <div class="team-skills">
            <span class="skill-tag">Mobile Dev</span>
            <span class="skill-tag">Backend Systems</span>
            <span class="skill-tag">Offline-First</span>
            <span class="skill-tag">GPS &amp; NFC</span>
          </div>
          <a href="https://www.linkedin.com/in/mohammad-safeeullah-a64007a5/" target="_blank" class="team-linkedin">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
            Connect on LinkedIn
          </a>
        </div>
      </div>
    </div>
    <!-- Mission -->
    <div style="max-width:860px;margin:64px auto 0;background:var(--navy);border-radius:24px;padding:48px;text-align:center" class="reveal">
      <div class="section-eyebrow" style="color:var(--gold);margin-bottom:16px">Our mission</div>
      <h3 style="font-family:'Playfair Display',serif;font-size:clamp(24px,4vw,38px);font-weight:900;color:var(--white);line-height:1.1;margin-bottom:16px">
        To make public transport in the Cayman Islands as <span style="color:var(--gold)">reliable, safe, and effortless</span> as the island life itself.
      </h3>
      <p style="color:rgba(255,255,255,.45);font-size:15px;line-height:1.7;max-width:500px;margin:0 auto">We believe every Caymanian deserves to know exactly when their bus is coming — whether they have signal or not.</p>
    </div>
  </section>
  <div class="love-banner reveal">
    <div class="love-text">Made with <span class="gold">love</span> in the Cayman Islands &#127472;&#127486;</div>
    <div class="love-sub">GRAND CAYMAN · CAYMAN BRAC · LITTLE CAYMAN</div>
  </div>
  <footer>
    <div class="footer-logo">&#128652; LetsGo</div>
    <div class="footer-links">
      <a href="#" onclick="showPage('home')">Home</a>
      <a href="#" onclick="showPage('team')">Team</a>
    </div>
    <div class="footer-copy">&#169; 2026 LetsGo · Cayman Islands</div>
    <a href="/users" class="footer-admin">Admin</a>
  </footer>
</div>

<script>
const cur = document.getElementById('cur');
document.addEventListener('mousemove', e => { cur.style.left=e.clientX+'px'; cur.style.top=e.clientY+'px'; });
document.querySelectorAll('a,button,.feat-card,.team-card,.why-hl,.step-card').forEach(el => {
  el.addEventListener('mouseenter', () => cur.classList.add('big'));
  el.addEventListener('mouseleave', () => cur.classList.remove('big'));
});
window.addEventListener('scroll', () => {
  document.getElementById('nav').classList.toggle('scrolled', window.scrollY > 40);
});
(function(){
  const c = document.getElementById('stars');
  if (!c) return;
  for (let i=0;i<60;i++){
    const s=document.createElement('div');
    s.className='star';
    s.style.cssText=`left:${Math.random()*100}%;top:${Math.random()*100}%;--d:${2+Math.random()*3}s;--delay:${Math.random()*4}s`;
    c.appendChild(s);
  }
})();
function showPage(name){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.pnav-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  document.getElementById('tab-'+name).classList.add('active');
  window.scrollTo({top:0,behavior:'smooth'});
  setTimeout(runReveal,100);
}
function runReveal(){
  const obs=new IntersectionObserver(entries=>{
    entries.forEach(e=>{ if(e.isIntersecting) e.target.classList.add('visible'); });
  },{threshold:0.12});
  document.querySelectorAll('.reveal:not(.visible)').forEach(el=>obs.observe(el));
}
runReveal();
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════

# ── LANDING PAGE ───────────────────────────────────────────
@app.route('/')
@app.route('/home')
@app.route('/team')
def landing():
    return LANDING_HTML


# ── HEALTH CHECK ────────────────────────────────────────────
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


# ── DELETE USER ────────────────────────────────────────────
@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    username = user.username          # capture BEFORE delete
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


# ── ADMIN DASHBOARD ────────────────────────────────────────
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
          <td><span class="lock">&#128274; hidden</span></td>
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
  <title>LetsGo — Admin Dashboard</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f2f5;padding:30px 20px;color:#333}}
    .header{{max-width:1000px;margin:0 auto 24px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}}
    .header h1{{font-size:22px;font-weight:600}}
    .header p{{font-size:13px;color:#888;margin-top:3px}}
    .header-right{{display:flex;align-items:center;gap:12px}}
    .badge{{background:#0B1F3A;color:#F5C518;padding:6px 16px;border-radius:20px;font-size:13px;font-weight:500}}
    .back-link{{color:#0B1F3A;font-size:13px;text-decoration:none;border:1px solid #ddd;padding:6px 14px;border-radius:8px;transition:all .2s}}
    .back-link:hover{{background:#0B1F3A;color:#F5C518;border-color:#0B1F3A}}
    .refresh-note{{max-width:1000px;margin:0 auto 12px;font-size:12px;color:#aaa;text-align:right}}
    .table-wrap{{max-width:1000px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08)}}
    table{{width:100%;border-collapse:collapse}}
    thead{{background:#0B1F3A;color:#F5C518}}
    th{{padding:14px 16px;text-align:left;font-size:13px;font-weight:500}}
    td{{padding:12px 16px;border-bottom:1px solid #f0f0f0;font-size:14px;vertical-align:middle}}
    tr:last-child td{{border-bottom:none}}
    tr:hover td{{background:#fafaff}}
    .avatar{{width:36px;height:36px;border-radius:50%;background:#e0e7ff;color:#0B1F3A;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:600}}
    .lock{{color:#999;font-size:12px}}
    .date{{color:#aaa;font-size:12px}}
    .empty{{text-align:center;padding:50px;color:#bbb;font-size:15px}}
    .del-btn{{background:#fee2e2;color:#dc2626;border:1px solid #fca5a5;padding:5px 14px;border-radius:6px;font-size:12px;cursor:pointer;transition:background .2s}}
    .del-btn:hover{{background:#fecaca}}
    .toast{{position:fixed;bottom:30px;right:30px;background:#1e1e2e;color:white;padding:12px 20px;border-radius:10px;font-size:14px;opacity:0;transition:opacity .3s;z-index:999}}
    .toast.show{{opacity:1}}
    .overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.4);z-index:100;align-items:center;justify-content:center}}
    .overlay.show{{display:flex}}
    .modal{{background:white;border-radius:12px;padding:28px 32px;max-width:360px;width:90%;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,0.15)}}
    .modal h3{{font-size:17px;margin-bottom:8px}}
    .modal p{{font-size:14px;color:#666;margin-bottom:22px}}
    .modal-btns{{display:flex;gap:10px;justify-content:center}}
    .btn-cancel{{padding:8px 22px;border-radius:8px;border:1px solid #ddd;background:white;cursor:pointer;font-size:14px}}
    .btn-confirm{{padding:8px 22px;border-radius:8px;border:none;background:#dc2626;color:white;cursor:pointer;font-size:14px}}
    .btn-confirm:hover{{background:#b91c1c}}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>&#128203; Registered Users</h1>
      <p>Users who signed up via the LetsGo app</p>
    </div>
    <div class="header-right">
      <span class="badge" id="user-count">{len(users)} user(s)</span>
      <a href="/" class="back-link">&#8592; Back to Site</a>
    </div>
  </div>
  <div class="refresh-note">
    Auto-refreshes every 10s &nbsp;|&nbsp;
    <span id="last-updated">Last updated: just now</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr><th></th><th>Username</th><th>Full Name</th><th>Phone Number</th><th>Password</th><th>Joined</th><th>Action</th></tr>
      </thead>
      <tbody id="user-tbody">{rows}</tbody>
    </table>
  </div>
  <div class="overlay" id="overlay">
    <div class="modal">
      <h3>Delete User</h3>
      <p id="modal-msg">Are you sure?</p>
      <div class="modal-btns">
        <button class="btn-cancel" onclick="closeModal()">Cancel</button>
        <button class="btn-confirm" id="confirm-btn">Delete</button>
      </div>
    </div>
  </div>
  <div class="toast" id="toast"></div>
  <script>
    let pendingDeleteId=null;
    function deleteUser(id,username){{
      pendingDeleteId=id;
      document.getElementById('modal-msg').textContent=`Delete "${{username}}"? This cannot be undone.`;
      document.getElementById('overlay').classList.add('show');
    }}
    function closeModal(){{pendingDeleteId=null;document.getElementById('overlay').classList.remove('show');}}
    document.getElementById('confirm-btn').addEventListener('click',async()=>{{
      if(!pendingDeleteId)return;closeModal();
      try{{
        const res=await fetch(`/api/users/${{pendingDeleteId}}`,{{method:'DELETE'}});
        const data=await res.json();
        if(res.ok){{document.getElementById(`row-${{pendingDeleteId}}`).remove();showToast('&#9989; '+data.message);refreshCount();}}
        else showToast('&#10060; '+data.message);
      }}catch(e){{showToast('&#10060; Delete failed');}}
      pendingDeleteId=null;
    }});
    function showToast(msg){{const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),3000);}}
    function refreshCount(){{const rows=document.querySelectorAll('#user-tbody tr[id]').length;document.getElementById('user-count').textContent=rows+' user(s)';}}
    async function refreshUsers(){{
      try{{
        const res=await fetch('/api/users');const data=await res.json();
        const tbody=document.getElementById('user-tbody');
        if(data.users.length===0){{tbody.innerHTML='<tr><td colspan="7" class="empty">No users registered yet.</td></tr>';document.getElementById('user-count').textContent='0 user(s)';return;}}
        tbody.innerHTML=data.users.map(u=>{{
          const initials=u.fullName.split(' ').map(n=>n[0]).join('').toUpperCase().slice(0,2);
          return `<tr id="row-${{u.id}}"><td><div class="avatar">${{initials}}</div></td><td><strong>${{u.username}}</strong></td><td>${{u.fullName}}</td><td>${{u.phoneNumber}}</td><td><span class="lock">&#128274; hidden</span></td><td class="date">${{u.createdAt}}</td><td><button class="del-btn" onclick="deleteUser(${{u.id}},'${{u.username}}')">Delete</button></td></tr>`;
        }}).join('');
        document.getElementById('user-count').textContent=data.total+' user(s)';
        document.getElementById('last-updated').textContent='Last updated: '+new Date().toLocaleTimeString();
      }}catch(e){{console.error('Refresh failed',e);}}
    }}
    setInterval(refreshUsers,10000);
  </script>
</body>
</html>"""
    return html


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
