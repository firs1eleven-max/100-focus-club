#!/usr/bin/env python3
import os, sqlite3, json, secrets, hashlib, smtplib, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
from pathlib import Path
from email.message import EmailMessage

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get('FOCUS_DATA_DIR', str(ROOT)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB = DATA_DIR / 'focusclub.db'
ADMIN_USER = os.environ.get('FOCUS_ADMIN_USER','admin')
ADMIN_PASSWORD = os.environ.get('FOCUS_ADMIN_PASSWORD','')
ADMIN_EMAIL = os.environ.get('FOCUS_ADMIN_EMAIL','')
SMTP_HOST = os.environ.get('SMTP_HOST','')
SMTP_PORT = int(os.environ.get('SMTP_PORT','587'))
SMTP_USER = os.environ.get('SMTP_USER','')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD','')
SMTP_FROM = os.environ.get('SMTP_FROM', SMTP_USER)
PORT = int(os.environ.get('PORT','10000'))
SESSIONS = {}
SESSION_TTL = int(os.environ.get('SESSION_TTL','28800'))

def db():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    return c

def init_db():
    c=db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS submissions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      reference TEXT UNIQUE NOT NULL,
      type TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'New',
      name TEXT, email TEXT, phone TEXT,
      payload TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      notes TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS notification_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      submission_id INTEGER NOT NULL,
      recipient TEXT NOT NULL,
      subject TEXT NOT NULL,
      sent_at TEXT NOT NULL,
      success INTEGER NOT NULL,
      error TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_submissions_type ON submissions(type);
    CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);
    ''')
    c.commit(); c.close()

def ref(prefix):
    return f"{prefix}-{secrets.token_hex(4).upper()}"

def auth_ok(handler):
    cookie=handler.headers.get('Cookie','')
    token=next((x.split('=',1)[1] for x in cookie.split('; ') if x.startswith('fc_session=')),None)
    
    created = SESSIONS.get(token)
    if not created: return False
    if time.time() - created > SESSION_TTL:
        SESSIONS.pop(token, None)
        return False
    return True



def send_notification(reference, typ, data):
    if not (SMTP_HOST and ADMIN_EMAIL and SMTP_FROM):
        return False, 'Email is not configured'
    subject = f"100% Focus Club — New {typ} ({reference})"
    name = data.get('name') or data.get('contact_name') or 'Website visitor'
    email = data.get('email') or ''
    body = (f"A new {typ.lower()} was submitted on the 100% Focus Club website.\n\n"
            f"Reference: {reference}\nName: {name}\nEmail: {email}\n\n"
            "Please sign in to the admin dashboard to review the complete submission.")
    msg=EmailMessage(); msg['Subject']=subject; msg['From']=SMTP_FROM; msg['To']=ADMIN_EMAIL; msg.set_content(body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            if SMTP_USER: smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
        return True, ''
    except Exception as e:
        return False, str(e)

def html_page(title, body):
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>body{{font-family:Inter,Arial,sans-serif;background:#f7f1e3;color:#0b1f3a;margin:0}}header{{background:#0b1f3a;color:#fff;padding:10px 20px;display:flex;justify-content:space-between;align-items:center}}.admin-brand{{display:flex;align-items:center;gap:4px;text-decoration:none}}.admin-wordmark{{width:136px;height:auto;display:block;filter:brightness(0) invert(1)}}.admin-emblem{{width:44px;height:44px;object-fit:contain;display:block}}main{{max-width:1100px;margin:28px auto;padding:0 18px}}a,button{{font:inherit}}.card{{background:#fff;border-radius:14px;padding:20px;margin:16px 0;box-shadow:0 4px 20px #0b1f3a12}}table{{width:100%;border-collapse:collapse;background:#fff}}th,td{{padding:12px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}}th{{background:#0b1f3a;color:#fff}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}.stat{{background:#fff;padding:18px;border-radius:14px}}.stat b{{font-size:28px;display:block}}.btn{{background:#f4a51c;color:#0b1f3a;border:0;border-radius:8px;padding:10px 14px;font-weight:700;cursor:pointer}}input,select{{padding:10px;border:1px solid #ccc;border-radius:7px}}@media(max-width:700px){{.grid{{grid-template-columns:1fr 1fr}}table{{font-size:13px;display:block;overflow-x:auto;white-space:nowrap}}}} </style></head><body>{body}</body></html>'''

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT),**kwargs)
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','SAMEORIGIN')
        self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
        self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()')
        if os.environ.get('PUBLIC_HTTPS','1') == '1':
            self.send_header('Strict-Transport-Security','max-age=31536000; includeSubDomains')
        super().end_headers()
    def send_json(self,obj,status=200):
        raw=json.dumps(obj).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def body_json(self):
        n=int(self.headers.get('Content-Length','0')); return json.loads(self.rfile.read(n) or '{}')
    def do_POST(self):
        path=urlparse(self.path).path
        if path=='/api/submit':
            try:
                x=self.body_json(); typ=x.get('type','').strip(); data=x.get('data',{})
                allowed={'School Request':'SCHOOL','Youth Registration':'YOUTH','Sponsor / Donor Interest':'SUPPORT','Contact Message':'CONTACT'}
                if typ not in allowed: return self.send_json({'error':'Invalid submission type'},400)
                now=datetime.now(timezone.utc).isoformat(); prefix=allowed[typ]; reference=ref(prefix)
                c=db(); cur=c.execute('INSERT INTO submissions(reference,type,name,email,phone,payload,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(reference,typ,data.get('name'),data.get('email'),data.get('phone'),json.dumps(data),now,now)); submission_id=cur.lastrowid; c.commit(); c.close()
                ok, err = send_notification(reference, typ, data)
                c=db(); c.execute('INSERT INTO notification_log(submission_id,recipient,subject,sent_at,success,error) VALUES(?,?,?,?,?,?)',(submission_id,ADMIN_EMAIL or 'not-configured',f'New {typ} ({reference})',now,1 if ok else 0,err)); c.commit(); c.close()
                return self.send_json({'ok':True,'reference':reference,'notification_sent':ok})
            except Exception as e: return self.send_json({'error':str(e)},500)
        if path=='/admin/login':
            x=self.body_json()
            if ADMIN_PASSWORD and x.get('username')==ADMIN_USER and secrets.compare_digest(str(x.get('password','')), ADMIN_PASSWORD):
                token=secrets.token_urlsafe(24); SESSIONS[token]=time.time()
                self.send_response(302); self.send_header('Set-Cookie',f'fc_session={token}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age={SESSION_TTL}'); self.send_header('Location','/admin'); self.end_headers(); return
            self.send_response(302); self.send_header('Location','/admin-login?error=1'); self.end_headers(); return
        if path=='/admin/status':
            if not auth_ok(self): return self.send_json({'error':'Unauthorized'},401)
            x=self.body_json(); c=db(); now=datetime.now(timezone.utc).isoformat(); c.execute('UPDATE submissions SET status=?,notes=?,updated_at=? WHERE id=?',(x.get('status'),x.get('notes',''),now,int(x.get('id')))); c.commit(); c.close(); return self.send_json({'ok':True})
        return super().do_POST()
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/health':
            return self.send_json({'ok': True})
        if path=='/admin-logout':
            cookie=self.headers.get('Cookie',''); token=next((x.split('=',1)[1] for x in cookie.split('; ') if x.startswith('fc_session=')),None)
            if token: SESSIONS.pop(token,None)
            self.send_response(302); self.send_header('Set-Cookie','fc_session=; Max-Age=0; HttpOnly; SameSite=Lax'); self.send_header('Location','/admin-login'); self.end_headers(); return
        if path=='/admin-login':
            err='Invalid login.' if parse_qs(urlparse(self.path).query).get('error') else ''
            body=f'''<header><a href="/" class="admin-brand" aria-label="100% Focus Club home"><img class="admin-emblem" src="/100_Focus_Club_Emblem_Transparent.png" alt=""><img class="admin-wordmark" src="/100_Focus_Club_Wordmark_Transparent.png" alt="100% Focus Club"></a></header><main><div class="card"><h1>Admin Login</h1><p>{err}</p><form method="post" action="/admin-login"><p><input name="username" placeholder="Username" required></p><p><input type="password" name="password" placeholder="Password" required></p><button class="btn">Sign in</button></form></div></main>'''
            # browser form posts urlencoded; handle below via do_POST replacement isn't parsing it, so provide JS JSON form
            body=body.replace('<form method="post" action="/admin-login">','<form id="f"><script>document.addEventListener("DOMContentLoaded",()=>document.getElementById("f").addEventListener("submit",async e=>{e.preventDefault();let f=e.target;let r=await fetch("/admin/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:f.username.value,password:f.password.value})});location.href=r.redirected?r.url:"/admin-login?error=1"}))</script>')
            raw=html_page('Admin Login',body).encode(); self.send_response(200); self.send_header('Content-Type','text/html'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        if path=='/admin':
            if not auth_ok(self): self.send_response(302); self.send_header('Location','/admin-login'); self.end_headers(); return
            c=db(); qs=parse_qs(urlparse(self.path).query); ftype=qs.get('type',[''])[0]; fstatus=qs.get('status',[''])[0]; fsearch=qs.get('q',[''])[0].strip(); where=[]; args=[];
            if ftype: where.append('type=?'); args.append(ftype)
            if fstatus: where.append('status=?'); args.append(fstatus)
            if fsearch:
                like=f'%{fsearch}%'; where.append('(reference LIKE ? OR name LIKE ? OR email LIKE ? OR phone LIKE ? OR payload LIKE ?)'); args.extend([like,like,like,like,like])
            sql='SELECT * FROM submissions' + ((' WHERE '+' AND '.join(where)) if where else '') + ' ORDER BY created_at DESC'; rows=c.execute(sql,args).fetchall(); counts={r['type']:c.execute('SELECT COUNT(*) n FROM submissions WHERE type=?',(r['type'],)).fetchone()['n'] for r in c.execute('SELECT DISTINCT type FROM submissions')}
            total=c.execute('SELECT COUNT(*) n FROM submissions').fetchone()['n']; new_count=c.execute("SELECT COUNT(*) n FROM submissions WHERE status='New'").fetchone()['n']; contacted=c.execute("SELECT COUNT(*) n FROM submissions WHERE status='Contacted'").fetchone()['n']; scheduled=c.execute("SELECT COUNT(*) n FROM submissions WHERE status='Scheduled'").fetchone()['n']; c.close(); stats=f'<div class="stat"><span>Total</span><b>{total}</b></div><div class="stat"><span>New</span><b>{new_count}</b></div><div class="stat"><span>Contacted</span><b>{contacted}</b></div><div class="stat"><span>Scheduled</span><b>{scheduled}</b></div>'
            trs=''
            for r in rows:
                trs+=f'<tr><td>{r["reference"]}</td><td>{r["type"]}</td><td>{r["name"] or ""}<br>{r["email"] or ""}</td><td>{r["created_at"][:19].replace("T"," ")}</td><td><select data-id="{r["id"]}" onchange="status({r["id"]},this.value)"><option {"selected" if r["status"]=="New" else ""}>New</option><option {"selected" if r["status"]=="Contacted" else ""}>Contacted</option><option {"selected" if r["status"]=="Scheduled" else ""}>Scheduled</option><option {"selected" if r["status"]=="Completed" else ""}>Completed</option><option {"selected" if r["status"]=="Cancelled" else ""}>Cancelled</option><option {"selected" if r["status"]=="Registered" else ""}>Registered</option><option {"selected" if r["status"]=="Training Scheduled" else ""}>Training Scheduled</option><option {"selected" if r["status"]=="Active" else ""}>Active</option><option {"selected" if r["status"]=="Discussion" else ""}>Discussion</option><option {"selected" if r["status"]=="Partnership" else ""}>Partnership</option><option {"selected" if r["status"]=="Closed" else ""}>Closed</option></select></td><td><details><summary>View</summary><pre>{r["payload"]}</pre><label>Admin notes</label><textarea id="n{r["id"]}" style="width:100%;min-height:70px">{r["notes"]}</textarea><button class="btn" onclick="saveNotes({r["id"]})">Save notes</button><span id="m{r["id"]}" style="margin-left:8px"></span></details></td></tr>'
            body=f'''<header><a href="/" class="admin-brand" aria-label="100% Focus Club home"><img class="admin-emblem" src="/100_Focus_Club_Emblem_Transparent.png" alt=""><img class="admin-wordmark" src="/100_Focus_Club_Wordmark_Transparent.png" alt="100% Focus Club"> src="/100_Focus_Club_Emblem_Transparent.png" alt=""></a><span><a href="/" style="color:#fff;margin-right:18px">View site</a><a href="/admin-logout" style="color:#fff">Sign out</a></span></header><main><h1>Submissions</h1><div class="grid">{stats}</div><div class="card"><form method="get" style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px"><input name="q" value="{fsearch}" placeholder="Search name, email, phone or reference"><select name="type"><option value="">All types</option><option>School Request</option><option>Youth Registration</option><option>Sponsor / Donor Interest</option><option>Contact Message</option></select><select name="status"><option value="">All statuses</option><option>New</option><option>Contacted</option><option>Scheduled</option><option>Completed</option><option>Cancelled</option><option>Registered</option><option>Training Scheduled</option><option>Active</option><option>Discussion</option><option>Partnership</option><option>Closed</option></select><button class="btn">Filter</button></form><table><thead><tr><th>Reference</th><th>Type</th><th>Contact</th><th>Received</th><th>Status</th><th>Details</th></tr></thead><tbody>{trs}</tbody></table></div><script>async function status(id,status){{let r=await fetch('/admin/status',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id,status}})}});if(r.ok)location.reload()}} async function saveNotes(id){{let notes=document.getElementById('n'+id).value;let select=document.querySelector('select[data-id="'+id+'"]');let r=await fetch('/admin/status',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id:id,status:select.value,notes:notes}})}});let m=document.getElementById('m'+id);m.textContent=r.ok?'Saved':'Save failed';setTimeout(()=>m.textContent='',2000)}}</script></main>'''
            raw=html_page('Admin Dashboard',body).encode(); self.send_response(200); self.send_header('Content-Type','text/html'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        return super().do_GET()

if __name__=='__main__':
    init_db(); print(f'100% Focus Club running at http://localhost:{PORT}'); print(f'Admin: http://localhost:{PORT}/admin-login'); print('Set FOCUS_ADMIN_PASSWORD before deployment; the server will refuse admin login if it is empty.')
    ThreadingHTTPServer(('0.0.0.0',PORT),Handler).serve_forever()
