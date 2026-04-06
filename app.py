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


@app.route('/ping')
def ping():
    return jsonify({'status': 'ok'}), 200

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
