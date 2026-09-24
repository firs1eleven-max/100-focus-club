#!/usr/bin/env python3
import os, sqlite3, json, secrets, hashlib, smtplib, time, html, re, mimetypes
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
from pathlib import Path
from email.message import EmailMessage
from email.parser import BytesParser
from email import policy

ROOT = Path(__file__).resolve().parent
DATA_DIR_ENV = os.environ.get('FOCUS_DATA_DIR', '').strip()
if DATA_DIR_ENV:
    DATA_DIR = Path(DATA_DIR_ENV)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not os.access(DATA_DIR, os.W_OK):
        raise RuntimeError('FOCUS_DATA_DIR is not writable: ' + str(DATA_DIR))
else:
    DATA_DIR = ROOT
DB = DATA_DIR / 'focusclub.db'
MEDIA_DIR = DATA_DIR / 'media'
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
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
    c=sqlite3.connect(DB, timeout=30)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=30000')
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
      notes TEXT NOT NULL DEFAULT '',
      archived INTEGER NOT NULL DEFAULT 0
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
    CREATE TABLE IF NOT EXISTS media (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', url TEXT NOT NULL, filename TEXT NOT NULL DEFAULT '', published INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS blog_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, slug TEXT UNIQUE NOT NULL, excerpt TEXT NOT NULL DEFAULT '', body TEXT NOT NULL, image_url TEXT NOT NULL DEFAULT '', published INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_blog_published ON blog_posts(published);
    ''')
    try:
        c.execute('ALTER TABLE submissions ADD COLUMN archived INTEGER NOT NULL DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    c.execute('CREATE INDEX IF NOT EXISTS idx_submissions_archived ON submissions(archived)')
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA synchronous=FULL')
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
    subject = f"100% Focus Club — New {typ} ({reference})"    name = data.get('name') or data.get('contact_name') or 'Website visitor'
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
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" type="image/png" href="/100_Focus_Club_Emblem_Transparent.png"><link rel="apple-touch-icon" href="/100_Focus_Club_Emblem_Transparent.png"><title>{title}</title><style>body{{font-family:Inter,Arial,sans-serif;background:#f7f1e3;color:#0b1f3a;margin:0}}.admin-header{{background:#fff;color:#0b1f3a;border-bottom:1px solid #d9dee7;box-shadow:0 2px 10px rgba(11,31,58,.08);min-height:78px;box-sizing:border-box}}.admin-header-inner{{max-width:1280px;margin:0 auto;padding:0 28px;min-height:78px;display:flex;align-items:center;justify-content:space-between;gap:32px;box-sizing:border-box}}.admin-brand{{display:flex;align-items:center;gap:12px;text-decoration:none;flex:0 0 auto}}.admin-wordmark{{width:148px;height:auto;display:block}}.admin-emblem{{width:46px;height:46px;object-fit:contain;display:block;flex:0 0 46px}}.admin-nav{{display:flex;align-items:center;justify-content:flex-end;gap:8px;flex-wrap:wrap}}.admin-nav a{{color:#0b1f3a;text-decoration:none;font-size:14px;font-weight:700;padding:10px 13px;border-radius:8px;white-space:nowrap}}.admin-nav a:hover{{background:#f7f1e3}}.admin-nav .admin-primary{{background:#f4a51c;color:#0b1f3a}}.admin-nav .admin-primary:hover{{background:#d9920e}}main{{max-width:1100px;margin:28px auto;padding:0 18px}}a,button{{font:inherit}}.card{{background:#fff;border-radius:14px;padding:20px;margin:16px 0;box-shadow:0 4px 20px #0b1f3a12}}.submission-details{{width:100%}}.submission-details>summary{{cursor:pointer;list-style:none;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 12px;border:1px solid #d9dee7;border-radius:9px;background:#fff;font-weight:800;color:#0b1f3a}}.submission-details>summary::-webkit-details-marker{{display:none}}.submission-details>summary:before{{content:'+';display:inline-grid;place-items:center;width:22px;height:22px;border-radius:50%;background:#f4a51c;margin-right:8px}}.submission-details[open]>summary:before{{content:'−'}}.submission-details>summary small{{font-weight:600;color:#6b7280}}.submission-panel{{margin-top:10px;padding:18px;border:1px solid #e3e7ed;border-radius:12px;background:#fbfcfe}}.submission-heading{{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding-bottom:14px;border-bottom:1px solid #e3e7ed}}.submission-heading h3{{margin:5px 0 0;font-size:20px}}.submission-type{{font-size:12px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:#6b7280}}.submission-status{{background:#f4a51c;color:#0b1f3a;border-radius:999px;padding:6px 10px;font-size:12px;font-weight:800}}.submission-fields{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:16px 0}}.submission-field{{margin:0;padding:11px 12px;background:#fff;border:1px solid #e3e7ed;border-radius:9px}}.submission-field dt{{font-size:11px;text-transform:uppercase;letter-spacing:.05em;font-weight:800;color:#6b7280;margin-bottom:4px}}.submission-field dd{{margin:0;line-height:1.5;overflow-wrap:anywhere}}.submission-field:has(dd br){{grid-column:1/-1}}.muted{{color:#6b7280}}.admin-notes{{border-top:1px solid #e3e7ed;padding-top:16px}}.admin-notes label{{display:block;font-weight:800;margin-bottom:7px}}.admin-notes textarea{{width:100%;min-height:88px;box-sizing:border-box;resize:vertical;padding:11px;border:1px solid #cbd3df;border-radius:8px;font:inherit;color:#0b1f3a;background:#fff}}.submission-actions{{display:flex;align-items:center;gap:8px;margin-top:10px;flex-wrap:wrap}}.btn-danger{{border-color:#c95a5a!important;color:#8f2525!important;background:#fff!important}}.save-message{{font-size:13px;font-weight:700}}@media(max-width:760px){{.submission-fields{{grid-template-columns:1fr}}.submission-field:has(dd br){{grid-column:auto}}.submission-heading{{flex-direction:column}}}}.login-page{{max-width:none;min-height:100vh;margin:0;padding:40px 18px;box-sizing:border-box;display:flex;align-items:center;justify-content:center;background:#f7f1e3}}.login-card{{width:min(440px,100%);box-sizing:border-box;background:#fff;border-radius:18px;padding:34px;box-shadow:0 12px 40px #0b1f3a18;text-align:center}}.login-brand{{display:flex;align-items:center;justify-content:center;gap:10px;text-decoration:none;margin-bottom:24px}}.login-emblem{{width:46px;height:46px;object-fit:contain}}.login-wordmark{{width:148px;height:auto}}.login-eyebrow{{margin:0 0 7px;color:#8a6918;font-size:11px;font-weight:800;letter-spacing:.12em}}.login-card h1{{margin:0;color:#0b1f3a;font-size:30px}}.login-intro{{margin:10px 0 24px;color:#667085;font-size:14px}}.login-card form{{display:grid;gap:16px;text-align:left}}.login-card label{{display:grid;gap:7px;color:#0b1f3a;font-size:13px;font-weight:700}}.login-card input{{width:100%;box-sizing:border-box;padding:12px;border:1px solid #ccd3dc;border-radius:8px;font-size:15px}}.login-card input:focus{{outline:2px solid #f4a51c;outline-offset:1px;border-color:#f4a51c}}.login-button{{width:100%;margin-top:4px}}.login-error{{margin:0 0 16px;padding:10px 12px;border-radius:8px;background:#fff0f0;color:#a12b2b;font-size:13px;font-weight:700}}.login-back{{display:inline-block;margin-top:20px;color:#0b1f3a;text-decoration:none;font-size:13px;font-weight:700}}.login-back:hover{{text-decoration:underline}}table{{width:100%;border-collapse:collapse;background:#fff}}th,td{{padding:12px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}}th{{background:#0b1f3a;color:#fff}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}.stat{{background:#fff;padding:18px;border-radius:14px}}.stat b{{font-size:28px;display:block}}.btn{{background:#f4a51c;color:#0b1f3a;border:0;border-radius:8px;padding:10px 14px;font-weight:700;cursor:pointer}}input,select{{padding:10px;border:1px solid #ccc;border-radius:7px}}@media(max-width:760px){{.admin-header-inner{{padding:12px 18px;min-height:auto;align-items:flex-start;gap:14px;flex-direction:column}}.admin-nav{{width:100%;justify-content:flex-start}}.admin-nav a{{font-size:13px;padding:8px 10px}}.admin-wordmark{{width:136px}}.admin-emblem{{width:40px;height:40px;flex-basis:40px}}.grid{{grid-template-columns:1fr 1fr}}table{{font-size:13px;display:block;overflow-x:auto;white-space:nowrap}}}}</style></head><body>{body}</body></html>'''

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
        if path=='/api/media':
            if not auth_ok(self): return self.send_json({'error':'Unauthorized'},401)
            try:
                ctype=self.headers.get('Content-Type','')
                if not ctype.startswith('multipart/form-data'): return self.send_json({'error':'Use multipart/form-data'},400)
                length=int(self.headers.get('Content-Length','0'))
                raw_body=self.rfile.read(length)
                msg=BytesParser(policy=policy.default).parsebytes(b'Content-Type: '+ctype.encode()+b'\r\nMIME-Version: 1.0\r\n\r\n'+raw_body)
                fields={}; file_data=None; file_name=''
                for part in msg.iter_parts():
                    name=part.get_param('name',header='content-disposition')
                    if not name: continue
                    if part.get_filename(): file_name=os.path.basename(part.get_filename()); file_data=part.get_payload(decode=True)
                    else: fields[name]=part.get_content()
                kind=str(fields.get('kind','photo')).strip(); title=str(fields.get('title','')).strip(); description=str(fields.get('description','')).strip(); url=str(fields.get('url','')).strip()
                if kind not in ('photo','video') or not title: return self.send_json({'error':'Type and title are required'},400)
                filename=''
                if kind=='photo':
                    if not file_name or file_data is None: return self.send_json({'error':'Choose an image'},400)
                    ext=Path(file_name).suffix.lower()
                    if ext not in {'.jpg','.jpeg','.png','.webp','.gif'}: return self.send_json({'error':'Unsupported image format'},400)
                    filename=secrets.token_hex(10)+ext; (MEDIA_DIR/filename).write_bytes(file_data); url='/media/'+filename
                elif not url: return self.send_json({'error':'Video URL is required'},400)
                now=datetime.now(timezone.utc).isoformat(); c=db(); c.execute('INSERT INTO media(kind,title,description,url,filename,created_at) VALUES(?,?,?,?,?,?)',(kind,title,description,url,filename,now)); c.commit(); c.close(); return self.send_json({'ok':True})
            except Exception as e: return self.send_json({'error':str(e)},500)
        if path=='/api/admin/media/delete':
            if not auth_ok(self): return self.send_json({'error':'Unauthorized'},401)
            x=self.body_json(); c=db(); row=c.execute('SELECT filename FROM media WHERE id=?',(int(x.get('id')),)).fetchone()
            c.execute('DELETE FROM media WHERE id=?',(int(x.get('id')),)); c.commit(); c.close()
            if row and row['filename']:
                try: (MEDIA_DIR/row['filename']).unlink()
                except FileNotFoundError: pass
            return self.send_json({'ok':True})
        if path=='/api/admin/blog':
            if not auth_ok(self): return self.send_json({'error':'Unauthorized'},401)
            x=self.body_json(); title=str(x.get('title','')).strip(); body=str(x.get('body','')).strip(); excerpt=str(x.get('excerpt','')).strip(); image=str(x.get('image_url','')).strip(); published=1 if x.get('published') else 0
            if not title or not body: return self.send_json({'error':'Title and article body are required'},400)
            slug=re.sub(r'[^a-z0-9]+','-',title.lower()).strip('-') or 'post-'+secrets.token_hex(4); now=datetime.now(timezone.utc).isoformat(); c=db()
            try:
                existing=c.execute('SELECT id FROM blog_posts WHERE slug=?',(slug,)).fetchone()
                if existing:
                    c.execute('UPDATE blog_posts SET title=?,excerpt=?,body=?,image_url=?,published=?,updated_at=? WHERE id=?',(title,excerpt,body,image,published,now,existing['id']))
                else:
                    c.execute('INSERT INTO blog_posts(title,slug,excerpt,body,image_url,published,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(title,slug,excerpt,body,image,published,now,now))
                c.commit()
            except Exception as e:
                c.close(); return self.send_json({'error':'Could not save article: '+str(e)},500)
            c.close(); return self.send_json({'ok':True,'slug':slug,'published':bool(published)})
        if path=='/api/admin/blog/publish':
            if not auth_ok(self): return self.send_json({'error':'Unauthorized'},401)
            x=self.body_json()
            try:
                post_id=int(x.get('id'))
            except Exception:
                return self.send_json({'error':'Invalid article id'},400)
            published=1 if x.get('published') else 0
            c=db(); row=c.execute('SELECT id FROM blog_posts WHERE id=?',(post_id,)).fetchone()
            if not row:
                c.close(); return self.send_json({'error':'Article not found'},404)
            now=datetime.now(timezone.utc).isoformat()
            c.execute('UPDATE blog_posts SET published=?,updated_at=? WHERE id=?',(published,now,post_id)); c.commit(); c.close()
            return self.send_json({'ok':True,'published':bool(published)})

        if path=='/api/admin/blog/delete':
            if not auth_ok(self): return self.send_json({'error':'Unauthorized'},401)
            x=self.body_json(); c=db(); row=c.execute('SELECT image_url FROM blog_posts WHERE id=?',(int(x.get('id')),)).fetchone()            c.execute('DELETE FROM blog_posts WHERE id=?',(int(x.get('id')),)); c.commit(); c.close()
            if row and row['image_url'].startswith('/media/'):
                try: (MEDIA_DIR/row['image_url'].split('/media/',1)[1]).unlink()
                except FileNotFoundError: pass
            return self.send_json({'ok':True})
        if path=='/api/submit':
            try:
                x=self.body_json(); typ=x.get('type','').strip(); data=x.get('data',{})
                allowed={'School Request':'SCHOOL','Youth Registration':'YOUTH','Sponsor / Donor Interest':'SUPPORT','Volunteer Interest':'VOLUNTEER','Contact Message':'CONTACT'}
                if typ not in allowed: return self.send_json({'error':'Invalid submission type'},400)
                now=datetime.now(timezone.utc).isoformat(); prefix=allowed[typ]; reference=ref(prefix)
                c=db(); cur=c.execute('INSERT INTO submissions(reference,type,name,email,phone,payload,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(reference,typ,data.get('name'),data.get('email'),data.get('phone'),json.dumps(data),now,now)); submission_id=cur.lastrowid; c.commit(); c.close()
                ok, err = send_notification(reference, typ, data)
                c=db(); c.execute('INSERT INTO notification_log(submission_id,recipient,subject,sent_at,success,error) VALUES(?,?,?,?,?,?)',(submission_id,ADMIN_EMAIL or 'not-configured',f'New {typ} ({reference})',now,1 if ok else 0,err)); c.commit(); c.close()
                return self.send_json({'ok':True,'reference':reference,'notification_sent':ok})
            except Exception as e: return self.send_json({'error':str(e)},500)
        if path=='/admin/login':
            ctype=self.headers.get('Content-Type','').lower()
            if ctype.startswith('application/json'):
                x=self.body_json()
            else:
                n=int(self.headers.get('Content-Length','0'))
                raw=self.rfile.read(n).decode('utf-8','replace')
                x={k:(v[0] if isinstance(v,list) else v) for k,v in parse_qs(raw).items()}
            username = str(x.get('username','')).strip()
            password = str(x.get('password',''))
            if ADMIN_PASSWORD and username.casefold()==ADMIN_USER.strip().casefold() and secrets.compare_digest(password, ADMIN_PASSWORD):
                token=secrets.token_urlsafe(24); SESSIONS[token]=time.time()
                self.send_response(302); self.send_header('Set-Cookie',f'fc_session={token}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age={SESSION_TTL}'); self.send_header('Location','/admin'); self.end_headers(); return
            self.send_response(302); self.send_header('Location','/admin-login?error=1'); self.end_headers(); return
        if path=='/admin/archive':
            if not auth_ok(self): return self.send_json({'error':'Unauthorized'},401)
            x=self.body_json(); c=db(); now=datetime.now(timezone.utc).isoformat()
            c.execute('UPDATE submissions SET archived=1,updated_at=? WHERE id=?',(now,int(x.get('id')))); c.commit(); c.close()
            return self.send_json({'ok':True})
        if path=='/admin/status':
            if not auth_ok(self): return self.send_json({'error':'Unauthorized'},401)
            x=self.body_json(); c=db(); now=datetime.now(timezone.utc).isoformat(); c.execute('UPDATE submissions SET status=?,notes=?,updated_at=? WHERE id=?',(x.get('status'),x.get('notes',''),now,int(x.get('id')))); c.commit(); c.close(); return self.send_json({'ok':True})
        return super().do_POST()
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/health':
            try:
                c=db()
                submission_count=c.execute('SELECT COUNT(*) n FROM submissions').fetchone()['n']
                media_count=c.execute('SELECT COUNT(*) n FROM media').fetchone()['n']
                blog_count=c.execute('SELECT COUNT(*) n FROM blog_posts').fetchone()['n']
                c.close()
                return self.send_json({'ok': True, 'storage': 'persistent-data-dir' if DATA_DIR_ENV else 'application-filesystem', 'data_dir': str(DATA_DIR), 'db_path': str(DB), 'db_exists': DB.exists(), 'db_bytes': DB.stat().st_size if DB.exists() else 0, 'submissions': submission_count, 'media': media_count, 'blog_posts': blog_count})
            except Exception as e:
                return self.send_json({'ok': False, 'error': str(e), 'data_dir': str(DATA_DIR), 'db_path': str(DB)}, 500)
        if path=='/admin-logout':
            cookie=self.headers.get('Cookie',''); token=next((x.split('=',1)[1] for x in cookie.split('; ') if x.startswith('fc_session=')),None)
            if token: SESSIONS.pop(token,None)
            self.send_response(302); self.send_header('Set-Cookie','fc_session=; Max-Age=0; HttpOnly; SameSite=Lax'); self.send_header('Location','/admin-login'); self.end_headers(); return
        if path.startswith('/media/'):
            fn=os.path.basename(path); fp=MEDIA_DIR/fn
            if fp.exists() and fp.is_file():
                raw=fp.read_bytes(); self.send_response(200); self.send_header('Content-Type',mimetypes.guess_type(str(fp))[0] or 'application/octet-stream'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            self.send_error(404); return
        if path=='/api/content':
            c=db(); photos=[dict(x) for x in c.execute("SELECT id,title,description,url FROM media WHERE kind='photo' AND published=1 ORDER BY created_at DESC")]; videos=[dict(x) for x in c.execute("SELECT id,title,description,url FROM media WHERE kind='video' AND published=1 ORDER BY created_at DESC")]; posts=[dict(x) for x in c.execute("SELECT id,title,slug,excerpt,body,image_url,created_at FROM blog_posts WHERE published=1 ORDER BY created_at DESC")]; c.close(); return self.send_json({'photos':photos,'videos':videos,'posts':posts})
        if path=='/admin-content':
            if not auth_ok(self): self.send_response(302); self.send_header('Location','/admin-login'); self.end_headers(); return
            c=db(); media_rows=c.execute('SELECT * FROM media ORDER BY created_at DESC').fetchall(); blog_rows=c.execute('SELECT * FROM blog_posts ORDER BY created_at DESC').fetchall(); c.close()
            media_cards=''
            for r in media_rows:
                media_cards += f'<article class="content-manage-item"><div><strong>{r["title"]}</strong><span class="content-type">{r["kind"].title()}</span></div><p>{r["description"] or ""}</p><p><a href="{r["url"]}" target="_blank" rel="noopener">Preview</a> · {"Published" if r["published"] else "Unpublished"}</p><button class="btn" type="button" onclick="deleteMedia({r["id"]},this)">Delete Permanently</button></article>'
            blog_cards=''
            for r in blog_rows:
                blog_cards += f'<article class="content-manage-item"><div><strong>{html.escape(r["title"])}</strong><span class="content-type">Blog</span></div><p>{html.escape(r["excerpt"] or "")}</p><p><strong>{"Published" if r["published"] else "Draft"}</strong></p><p><button class="btn" type="button" onclick="toggleBlog({r["id"]},{1 if not r["published"] else 0},this)">{"Publish" if not r["published"] else "Unpublish"}</button> <button class="btn" type="button" onclick="deleteBlog({r["id"]},this)">Delete Permanently</button></p></article>'
            body=f'''<header class="admin-header"><div class="admin-header-inner"><a href="/" class="admin-brand" aria-label="100% Focus Club home"><img class="admin-emblem" src="/100_Focus_Club_Emblem_Transparent.png" alt=""><img class="admin-wordmark" src="/100_Focus_Club_Wordmark_Transparent.png" alt="100% Focus Club"></a><nav class="admin-nav" aria-label="Admin navigation"><a href="/admin">Submissions</a><a href="/admin-content" class="admin-primary">Website Content</a><a href="/" target="_blank" rel="noopener">View Site</a><a href="/admin-logout">Sign Out</a></nav></div></header><main><h1>Website Content</h1><div class="card"><h2>📸 Add Photo</h2><form id="photo" enctype="multipart/form-data"><input type="hidden" name="kind" value="photo"><input required name="title" placeholder="Photo title"><input name="description" placeholder="Caption"><input required type="file" name="file" accept="image/jpeg,image/png,image/webp,image/gif"><button class="btn" type="submit">Upload Photo</button><span id="pm"></span></form></div><div class="card"><h2>🎥 Add Video</h2><form id="video"><input type="hidden" name="kind" value="video"><input required name="title" placeholder="Video title"><input name="description" placeholder="Description"><input required name="url" placeholder="YouTube or Vimeo URL"><button class="btn" type="submit">Add Video</button><span id="vm"></span></form></div><div class="card"><h2>📝 Create Blog Post</h2><form id="blog"><input required name="title" placeholder="Post title"><input name="excerpt" placeholder="Short excerpt"><input name="image_url" placeholder="Featured image URL"><textarea required name="body" placeholder="Write your article"></textarea><label><input type="checkbox" name="published" checked> Publish now</label><button class="btn" type="submit">Publish Post</button><span id="bm"></span></form></div><div class="card"><h2>Published &amp; Uploaded Content</h2><p>Manage content already added to the website. You can permanently delete photos, videos and articles after confirming the action. Permanent deletion cannot be undone.</p><div class="content-manage-list">{media_cards}{blog_cards}</div></div><script>
async function responseMessage(r,okText,failPrefix){{
  let data={{}};
  try{{data=await r.json()}}catch(e){{}}
  return r.ok ? okText : (failPrefix+(data.error?': '+data.error:' (HTTP '+r.status+')'));
}}
async function send(form,id){{
  const message=document.getElementById(id); const button=form.querySelector('button[type="submit"]');
  button.disabled=true; message.textContent='Saving…';
  try{{
    const r=await fetch('/api/media',{{method:'POST',body:new FormData(form)}});
    if(r.ok){{message.textContent=' Saved';location.reload()}}
    else{{message.textContent=await responseMessage(r,'','Failed')}}
  }}catch(e){{message.textContent='Failed: Network error'}}
  finally{{button.disabled=false}}
}}
document.getElementById('photo').addEventListener('submit',e=>{{e.preventDefault();send(e.currentTarget,'pm')}});
document.getElementById('video').addEventListener('submit',e=>{{e.preventDefault();send(e.currentTarget,'vm')}});
document.getElementById('blog').addEventListener('submit',async e=>{{
  e.preventDefault();
  const form=e.currentTarget, message=document.getElementById('bm'), button=form.querySelector('button[type="submit"]');
  button.disabled=true; message.textContent='Publishing…';
  try{{
    const f=new FormData(form);
    const x=Object.fromEntries(f.entries());
    x.published=f.get('published')==='on';
    const r=await fetch('/api/admin/blog',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(x)}});
    if(r.ok){{message.textContent=' Published';location.reload()}}
    else{{message.textContent=await responseMessage(r,'','Failed')}}  }}catch(e){{message.textContent='Failed: Network error'}}
  finally{{button.disabled=false}}
}});
async function deleteMedia(id,button){{if(!confirm('Permanently delete this photo/video? This cannot be undone.'))return;button.disabled=true;let r=await fetch('/api/admin/media/delete',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id}})}});if(r.ok)location.reload();else{{button.disabled=false;alert(await responseMessage(r,'','Delete failed'))}}}};
async function toggleBlog(id,published,button){{button.disabled=true;try{{let r=await fetch('/api/admin/blog/publish',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id,published:!!published}})}});if(r.ok)location.reload();else{{button.disabled=false;alert(await responseMessage(r,'','Publish failed'))}}}}catch(e){{button.disabled=false;alert('Publish failed: Network error')}}}}
async function deleteBlog(id,button){{if(!confirm('Permanently delete this article? This cannot be undone.'))return;button.disabled=true;let r=await fetch('/api/admin/blog/delete',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id}})}});if(r.ok)location.reload();else{{button.disabled=false;alert(await responseMessage(r,'','Delete failed'))}}}};
</script></main>'''
            raw=html_page('Website Content',body).encode(); self.send_response(200); self.send_header('Content-Type','text/html'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            raw=html_page('Website Content',body).encode(); self.send_response(200); self.send_header('Content-Type','text/html'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        if path=='/admin-login':

            err='Invalid login.' if parse_qs(urlparse(self.path).query).get('error') else ''
            body=f'''<main class="login-page"><div class="login-card"><a href="/" class="login-brand" aria-label="100% Focus Club home"><img class="login-emblem" src="/100_Focus_Club_Emblem_Transparent.png" alt=""><img class="login-wordmark" src="/100_Focus_Club_Wordmark_Transparent.png" alt="100% Focus Club"></a><p class="login-eyebrow">ADMINISTRATION</p><h1>Admin Login</h1><p class="login-intro">Sign in to manage website submissions and content.</p>{f'<p class="login-error">{err}</p>' if err else ''}<form method="post" action="/admin/login"><label>Username<input name="username" autocomplete="username" placeholder="Username" required></label><label>Password<input type="password" name="password" autocomplete="current-password" placeholder="Password" required></label><button class="btn login-button">Sign In</button></form><a class="login-back" href="/">← Back to Website</a></div></main>'''
            # The login form posts directly to the JSON/form-compatible login endpoint; no client-side JavaScript is required.
            raw=html_page('Admin Login',body).encode(); self.send_response(200); self.send_header('Content-Type','text/html'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        if path=='/admin':
            if not auth_ok(self): self.send_response(302); self.send_header('Location','/admin-login'); self.end_headers(); return
            c=db(); qs=parse_qs(urlparse(self.path).query); ftype=qs.get('type',[''])[0]; fstatus=qs.get('status',[''])[0]; fsearch=qs.get('q',[''])[0].strip(); where=[]; args=[];
            if ftype: where.append('type=?'); args.append(ftype)
            if fstatus: where.append('status=?'); args.append(fstatus)
            where.append('archived=0')
            if fsearch:
                like=f'%{fsearch}%'; where.append('(reference LIKE ? OR name LIKE ? OR email LIKE ? OR phone LIKE ? OR payload LIKE ?)'); args.extend([like,like,like,like,like])
            sql='SELECT * FROM submissions' + ((' WHERE '+' AND '.join(where)) if where else '') + ' ORDER BY created_at DESC'; rows=c.execute(sql,args).fetchall(); counts={r['type']:c.execute('SELECT COUNT(*) n FROM submissions WHERE type=?',(r['type'],)).fetchone()['n'] for r in c.execute('SELECT DISTINCT type FROM submissions')}
            total=c.execute('SELECT COUNT(*) n FROM submissions').fetchone()['n']; new_count=c.execute("SELECT COUNT(*) n FROM submissions WHERE status='New'").fetchone()['n']; contacted=c.execute("SELECT COUNT(*) n FROM submissions WHERE status='Contacted'").fetchone()['n']; scheduled=c.execute("SELECT COUNT(*) n FROM submissions WHERE status='Scheduled'").fetchone()['n']; c.close(); stats=f'<div class="stat"><span>Total</span><b>{total}</b></div><div class="stat"><span>New</span><b>{new_count}</b></div><div class="stat"><span>Contacted</span><b>{contacted}</b></div><div class="stat"><span>Scheduled</span><b>{scheduled}</b></div>'
            def submission_fields(row):
                try:
                    data=json.loads(row['payload'])
                except Exception:
                    data={}
                labels={
                    'name':'Full name','email':'Email','phone':'Phone / WhatsApp','city':'City / community',
                    'area':'Volunteer area','message':'Message','school':'School / organization','contact_name':'Contact name',
                    'location':'Location','learners':'Learner count','age_range':'Age / grade range','preferred_date':'Preferred date',
                    'alternative_date':'Alternative date','session_type':'Session type','duration':'Duration','sessions':'Number of sessions',
                    'objectives':'Objectives / challenges','additional_info':'Additional information','preferred_contact':'Preferred contact',
                    'dob':'Date of birth','gender':'Gender','country':'Country','education':'Education level','employment':'Employment status',
                    'experience':'Entrepreneurship experience','interests':'Interests','why_join':'Why I want to join','format':'Preferred format',
                    'guardian':'Guardian contact','support':'Support type','subject':'Subject','consent':'Consent'
                }
                parts=[]
                for key,value in data.items():
                    if key=='consent': continue
                    if value is None or str(value).strip()=='' : continue
                    label=labels.get(key,key.replace('_',' ').title())
                    parts.append(f'<div class="submission-field"><dt>{html.escape(label)}</dt><dd>{html.escape(str(value)).replace(chr(10),"<br>")}</dd></div>')
                return ''.join(parts) or '<p class="muted">No additional details were provided.</p>'

            trs=''
            for r in rows:
                fields=submission_fields(r)
                notes=html.escape(r["notes"] or "")
                trs+=f'<tr><td>{html.escape(r["reference"])}</td><td>{html.escape(r["type"])}</td><td>{html.escape(r["name"] or "")}<br>{html.escape(r["email"] or "")}</td><td>{r["created_at"][:19].replace("T"," ")}</td><td><select data-id="{r["id"]}" onchange="status({r["id"]},this.value)"><option {"selected" if r["status"]=="New" else ""}>New</option><option {"selected" if r["status"]=="Contacted" else ""}>Contacted</option><option {"selected" if r["status"]=="Scheduled" else ""}>Scheduled</option><option {"selected" if r["status"]=="Completed" else ""}>Completed</option><option {"selected" if r["status"]=="Cancelled" else ""}>Cancelled</option><option {"selected" if r["status"]=="Registered" else ""}>Registered</option><option {"selected" if r["status"]=="Training Scheduled" else ""}>Training Scheduled</option><option {"selected" if r["status"]=="Active" else ""}>Active</option><option {"selected" if r["status"]=="Discussion" else ""}>Discussion</option><option {"selected" if r["status"]=="Partnership" else ""}>Partnership</option><option {"selected" if r["status"]=="Closed" else ""}>Closed</option></select></td><td><details class="submission-details"><summary><span>View submission</span><small>{html.escape(r["reference"])}</small></summary><div class="submission-panel"><div class="submission-heading"><div><span class="submission-type">{html.escape(r["type"])}</span><h3>{html.escape(r["name"] or "Website visitor")}</h3></div><span class="submission-status">{html.escape(r["status"])}</span></div><dl class="submission-fields">{fields}</dl><div class="admin-notes"><label for="n{r["id"]}">Admin notes</label><textarea id="n{r["id"]}" placeholder="Add an internal note about this submission…">{notes}</textarea><div class="submission-actions"><button class="btn" type="button" onclick="saveNotes({r["id"]})">Save notes</button><button class="btn btn-danger" type="button" onclick="archiveSubmission({r["id"]})">Archive</button><span id="m{r["id"]}" class="save-message" aria-live="polite"></span></div></div></div></details></td></tr>'
            body=f'''<header class="admin-header"><div class="admin-header-inner"><a href="/" class="admin-brand" aria-label="100% Focus Club home"><img class="admin-emblem" src="/100_Focus_Club_Emblem_Transparent.png" alt=""><img class="admin-wordmark" src="/100_Focus_Club_Wordmark_Transparent.png" alt="100% Focus Club"></a><nav class="admin-nav" aria-label="Admin navigation"><a href="/admin">Submissions</a><a href="/admin-content" class="admin-primary">Website Content</a><a href="/" target="_blank" rel="noopener">View Site</a><a href="/admin-logout">Sign Out</a></nav></div></header><main><h1>Submissions</h1><div class="grid">{stats}</div><div class="card"><form method="get" style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px"><input name="q" value="{fsearch}" placeholder="Search name, email, phone or reference"><select name="type"><option value="">All types</option><option>School Request</option><option>Youth Registration</option><option>Sponsor / Donor Interest</option><option>Contact Message</option></select><select name="status"><option value="">All statuses</option><option>New</option><option>Contacted</option><option>Scheduled</option><option>Completed</option><option>Cancelled</option><option>Registered</option><option>Training Scheduled</option><option>Active</option><option>Discussion</option><option>Partnership</option><option>Closed</option></select><button class="btn">Filter</button></form><table><thead><tr><th>Reference</th><th>Type</th><th>Contact</th><th>Received</th><th>Status</th><th>Details</th></tr></thead><tbody>{trs}</tbody></table></div><script>async function archiveSubmission(id){{if(!confirm('Archive this submission? It will be hidden from the active list but kept in the database.'))return;let r=await fetch('/admin/archive',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id:id}})}});if(r.ok)location.reload()}} async function status(id,status){{let r=await fetch('/admin/status',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id,status}})}});if(r.ok)location.reload()}} async function saveNotes(id){{let notes=document.getElementById('n'+id).value;let select=document.querySelector('select[data-id="'+id+'"]');let r=await fetch('/admin/status',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id:id,status:select.value,notes:notes}})}});let m=document.getElementById('m'+id);m.textContent=r.ok?'Saved':'Save failed';setTimeout(()=>m.textContent='',2000)}}</script></main>'''
            raw=html_page('Admin Dashboard',body).encode(); self.send_response(200); self.send_header('Content-Type','text/html'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        # Clean public page routes. Keep one backend/service while giving visitors dedicated URLs.
        page_routes = {'/': 'index.html', '/about': 'about.html', '/programs': 'programs.html', '/schools': 'schools.html', '/youth': 'youth.html', '/volunteer': 'volunteer.html', '/support': 'support.html', '/stories': 'stories.html', '/contact': 'contact.html'}
        clean_path = path.rstrip('/') or '/'
        if clean_path in page_routes:
            fp = ROOT / page_routes[clean_path]
            if fp.exists():
                raw = fp.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
        return super().do_GET()

if __name__=='__main__':
    init_db()
    print(f'100% Focus Club running at http://localhost:{PORT}')
    print(f'Admin: http://localhost:{PORT}/admin-login')
    print('Set FOCUS_ADMIN_PASSWORD before deployment; the server will refuse admin login if it is empty.')
    ThreadingHTTPServer(('0.0.0.0',PORT),Handler).serve_forever()
