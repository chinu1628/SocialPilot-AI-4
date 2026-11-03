import sys, os, sqlite3, csv, shutil, json, urllib.parse, requests
from datetime import datetime, date
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QAction

APP_DIR=os.path.join(os.path.expanduser("~"),"SocialPilotAI")
os.makedirs(APP_DIR,exist_ok=True)
DB=os.path.join(APP_DIR,"socialpilot.db")
BACKUP_DIR=os.path.join(APP_DIR,"Backups")
os.makedirs(BACKUP_DIR,exist_ok=True)

def dbconn():
    c=sqlite3.connect(DB)
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("CREATE TABLE IF NOT EXISTS workspaces(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE,industry TEXT,created TEXT)")
    c.execute("""CREATE TABLE IF NOT EXISTS content(
        id INTEGER PRIMARY KEY AUTOINCREMENT,workspace TEXT,channel TEXT,kind TEXT,
        caption TEXT,status TEXT DEFAULT 'Draft',scheduled TEXT,created TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS contacts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,workspace TEXT,name TEXT,phone TEXT,email TEXT,tags TEXT,created TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS campaigns(
        id INTEGER PRIMARY KEY AUTOINCREMENT,workspace TEXT,name TEXT,channel TEXT,message TEXT,status TEXT,created TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS templates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,category TEXT,body TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS wa_bulk_jobs(
        id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT, campaign_name TEXT,
        phone TEXT, contact_name TEXT, template_name TEXT, language TEXT,
        payload TEXT, status TEXT DEFAULT 'Queued', result TEXT, created TEXT, completed TEXT)""")
    # Consent is explicit and defaults OFF. Existing contacts are not automatically opted in.
    cols=[r[1] for r in c.execute("PRAGMA table_info(contacts)")]
    if "marketing_opt_in" not in cols:
        c.execute("ALTER TABLE contacts ADD COLUMN marketing_opt_in INTEGER NOT NULL DEFAULT 0")
    if "opt_in_source" not in cols:
        c.execute("ALTER TABLE contacts ADD COLUMN opt_in_source TEXT DEFAULT ''")
    if c.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]==0:
        c.execute("INSERT INTO workspaces(name,industry,created) VALUES(?,?,?)",
                  ("My Workspace","General",datetime.now().isoformat(timespec="minutes")))
    if c.execute("SELECT COUNT(*) FROM templates").fetchone()[0]==0:
        samples=[
        ("Welcome message","WhatsApp","Hi {name}! Thanks for connecting with us. How can we help you today?"),
        ("New offer","Promotion","We have something special for you! Explore our latest offer: {link}"),
        ("Reel hook","Instagram","3 things nobody tells you about {topic}…"),
        ("Educational carousel","Instagram","Slide 1: {headline}\\nSlide 2: The problem\\nSlide 3: The insight\\nSlide 4: 3 practical tips\\nSlide 5: Save this post")]
        c.executemany("INSERT INTO templates(name,category,body) VALUES(?,?,?)",samples)
    c.commit()
    return c

class FormDialog(QDialog):
    def __init__(self,title,fields,parent=None):
        super().__init__(parent); self.setWindowTitle(title); self.widgets={}
        f=QFormLayout(self)
        for label,kind,opts in fields:
            if kind=="text": w=QLineEdit()
            elif kind=="area": w=QTextEdit(); w.setMinimumSize(400,130)
            elif kind=="combo": w=QComboBox(); w.addItems(opts)
            elif kind=="date": w=QDateEdit(QDate.currentDate()); w.setCalendarPopup(True); w.setDisplayFormat("dd MMM yyyy")
            self.widgets[label]=w; f.addRow(label,w)
        bb=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); f.addRow(bb)
    def values(self):
        out={}
        for k,w in self.widgets.items():
            if isinstance(w,QComboBox): out[k]=w.currentText()
            elif isinstance(w,QTextEdit): out[k]=w.toPlainText()
            elif isinstance(w,QDateEdit): out[k]=w.date().toString("yyyy-MM-dd")
            else: out[k]=w.text()
        return out

class SocialPilot(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SocialPilot AI Desktop")
        self.resize(1320,820); self.dark=False; self.db=dbconn()
        central=QWidget(); self.setCentralWidget(central); root=QHBoxLayout(central); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        self.side=QFrame(); self.side.setFixedWidth(245); self.side.setObjectName("sidebar")
        sl=QVBoxLayout(self.side); sl.setContentsMargins(14,20,14,14)
        brand=QLabel("✦  SocialPilot AI"); brand.setObjectName("brand"); sl.addWidget(brand); sl.addSpacing(14)
        self.stack=QStackedWidget(); self.page_map={}
        nav=[
        ("Dashboard","⌂"),("Workspaces","▣"),("Content Studio","✎"),("Content Calendar","▦"),
        ("AI Content Lab","✧"),("Campaigns","◉"),("Audience & CRM","♙"),("Templates","▤"),
        ("Integrations","⇄"),("OAuth Setup","🔐"),("WhatsApp Bulk","✉"),("Automations","⚙"),("Analytics","▥"),("Settings & Backup","☷")]
        for name,ico in nav:
            b=QPushButton(f"{ico}   {name}"); b.setObjectName("nav")
            b.clicked.connect(lambda checked=False,n=name:self.navigate(n)); sl.addWidget(b)
        sl.addStretch()
        theme=QPushButton("◐  Switch appearance"); theme.clicked.connect(self.toggle_theme); sl.addWidget(theme)
        root.addWidget(self.side); root.addWidget(self.stack,1)
        for name,_ in nav:
            page=self.build_page(name); self.page_map[name]=page; self.stack.addWidget(page)
        self.set_theme(); self.navigate("Dashboard")
    def heading(self,title,subtitle):
        v=QVBoxLayout(); t=QLabel(title); t.setObjectName("heading"); s=QLabel(subtitle); s.setObjectName("subtitle")
        v.addWidget(t); v.addWidget(s); v.addSpacing(12); return v
    def card(self,title,value):
        f=QFrame(); f.setObjectName("card"); l=QVBoxLayout(f); a=QLabel(title); b=QLabel(str(value)); b.setObjectName("metric"); l.addWidget(a); l.addWidget(b); return f
    def generate_oauth_url(self):
        import urllib.parse
        app_id=self.oauth_client.text().strip()
        redirect=self.oauth_redirect.text().strip()
        scopes=self.oauth_scopes.text().strip()
        if not app_id or not redirect:
            QMessageBox.warning(self,"Missing details","Enter Meta App ID and Redirect URI first."); return
        params={"client_id":app_id,"redirect_uri":redirect,"response_type":"code","scope":scopes}
        self.oauth_url.setText("https://www.facebook.com/v22.0/dialog/oauth?"+urllib.parse.urlencode(params))
    def parse_oauth_callback(self):
        raw=self.oauth_callback.text().strip()
        try:
            parsed=urllib.parse.urlparse(raw)
            params=urllib.parse.parse_qs(parsed.query)
            code=params.get("code",[""])[0]
            if not code:
                err=params.get("error_description",params.get("error",["Meta did not return code"]))[0]
                QMessageBox.warning(self,"OAuth response",str(err))
                return
            self.oauth_code.setText(code)
            QMessageBox.information(self,"OAuth response","Authorization code extracted. It is short-lived; exchange it now.")
        except Exception as e:
            QMessageBox.warning(self,"OAuth response",f"Could not parse redirect URL: {e}")

    def exchange_oauth_code(self):
        app_id=self.oauth_client.text().strip()
        secret=self.oauth_secret.text().strip()
        code=self.oauth_code.text().strip()
        redirect=self.oauth_redirect.text().strip()
        if not all([app_id,secret,code,redirect]):
            QMessageBox.warning(self,"Missing fields","Enter App ID, App Secret, authorization code, and exact Redirect URI.")
            return
        try:
            response=requests.get("https://graph.facebook.com/v22.0/oauth/access_token",
                params={"client_id":app_id,"client_secret":secret,"redirect_uri":redirect,"code":code},
                timeout=25)
            data=response.json()
            if response.ok and data.get("access_token"):
                self.oauth_token.setText(data["access_token"])
                expires=data.get("expires_in")
                self.oauth_expiry.setText("Token expiry: "+(f"~{int(expires)//86400} days ({int(expires)} seconds)" if expires else "Meta did not return expires_in"))
                self.oauth_long_token.clear()
                QMessageBox.information(self,"Token exchange successful",
                    "Meta returned an access token. Token is displayed masked and is not saved automatically. Store it in Secure Credential Vault.")
            else:
                self.oauth_token.clear()
                QMessageBox.warning(self,"Meta token exchange failed",data.get("error",{}).get("message",f"HTTP {response.status_code}"))
        except requests.RequestException as e:
            QMessageBox.warning(self,"Network error",f"Could not contact Meta: {e}")

    def exchange_long_lived_token(self):
        short_token=self.oauth_token.text().strip()
        app_id=self.oauth_client.text().strip()
        secret=self.oauth_secret.text().strip()
        if not all([short_token,app_id,secret]):
            QMessageBox.warning(self,"Missing fields","First exchange the authorization code, then provide App ID and App Secret.")
            return
        try:
            response=requests.get("https://graph.facebook.com/v22.0/oauth_access_token",
                params={"grant_type":"fb_exchange_token","client_id":app_id,
                        "client_secret":secret,"fb_exchange_token":short_token},timeout=25)
            data=response.json()
            if response.ok and data.get("access_token"):
                self.oauth_long_token.setText(data["access_token"])
                exp=data.get("expires_in")
                self.oauth_expiry.setText("Long-lived token expiry: "+(f"~{int(exp)//86400} days ({int(exp)} seconds)" if exp else "not supplied by Meta"))
                QMessageBox.information(self,"Long-lived exchange successful",
                    "Meta returned a long-lived token. Store it in Secure Credential Vault. It is not saved automatically.")
            else:
                QMessageBox.warning(self,"Long-lived exchange failed",data.get("error",{}).get("message",f"HTTP {response.status_code}"))
        except requests.RequestException as e:
            QMessageBox.warning(self,"Network error",f"Could not contact Meta: {e}")

    def discover_meta_assets(self):
        token=(self.oauth_long_token.text().strip() or self.oauth_token.text().strip())
        if not token:
            QMessageBox.warning(self,"Token required","Complete OAuth first. Use the long-lived Instagram token where applicable.")
            return
        lines=[]
        def get(endpoint,params=None):
            q=dict(params or {}); q["access_token"]=token
            r=requests.get("https://graph.facebook.com/v22.0/"+endpoint,params=q,timeout=25)
            d=r.json()
            if not r.ok:
                err=d.get("error",{}).get("message",f"HTTP {r.status_code}")
                lines.append(f"ERROR {endpoint}: {err}")
                return {}
            return d
        try:
            pages=get("me/accounts",{"fields":"id,name,access_token,instagram_business_account{id,username,name}"})
            for page in pages.get("data",[]):
                lines.append(f"Facebook Page: {page.get('name','(unnamed)')} | ID: {page.get('id')}")
                ig=page.get("instagram_business_account")
                if ig:
                    lines.append(f"  Instagram professional account: @{ig.get('username','')} | ID: {ig.get('id')} | Name: {ig.get('name','')}")
            businesses=get("me/businesses",{"fields":"id,name"})
            for biz in businesses.get("data",[]):
                lines.append(f"Business: {biz.get('name','(unnamed)')} | ID: {biz.get('id')}")
                wa=get(f"{biz.get('id')}/owned_whatsapp_business_accounts",{"fields":"id,name"})
                for account in wa.get("data",[]):
                    lines.append(f"  WhatsApp Business Account: {account.get('name','')} | ID: {account.get('id')}")
                    phones=get(f"{account.get('id')}/phone_numbers",{"fields":"id,display_phone_number,verified_name"})
                    for phone in phones.get("data",[]):
                        lines.append(f"    Phone: {phone.get('display_phone_number','')} | verified name: {phone.get('verified_name','')} | ID: {phone.get('id')}")
            if not lines: lines.append("No assets returned. Check token scopes, app mode, roles, and asset assignments.")
            self.meta_assets.setPlainText("\\n".join(lines))
        except requests.RequestException as e:
            QMessageBox.warning(self,"Network error",f"Meta asset discovery failed: {e}")

    def open_oauth_url(self):
        import webbrowser
        if not self.oauth_url.text(): self.generate_oauth_url()
        if self.oauth_url.text(): webbrowser.open(self.oauth_url.text())
    def copy_oauth_url(self):
        QApplication.clipboard().setText(self.oauth_url.text())
        QMessageBox.information(self,"Copied","Authorization URL copied to clipboard.")

    def save_integration(self):
        workspace=self.int_workspace.currentText().strip()
        provider=self.int_provider.currentText().strip()
        account=self.int_account.text().strip()
        account_id=self.int_account_id.text().strip()
        app_id=self.int_app_id.text().strip()
        status=self.int_status.currentText()
        notes=self.int_notes.toPlainText().strip()
        if not workspace:
            QMessageBox.warning(self,"Workspace required","Create/select a workspace first."); return
        self.db.execute("""INSERT INTO integrations(workspace,provider,account_name,account_id,app_id,status,notes,updated)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(workspace,provider) DO UPDATE SET account_name=excluded.account_name,
            account_id=excluded.account_id,app_id=excluded.app_id,status=excluded.status,notes=excluded.notes,updated=excluded.updated""",
            (workspace,provider,account,account_id,app_id,status,notes,datetime.now().isoformat(timespec="minutes")))
        self.db.commit()
        QMessageBox.information(self,"Saved","Integration setup metadata saved locally. No connection or message was sent.")
        self.navigate("Integrations")

    def _vault_key(self):
        ws=self.int_workspace.currentText().strip()
        provider=self.int_provider.currentText().strip()
        return f"{ws}::{provider}"

    def save_secure_token(self):
        token=self.int_token.text().strip()
        if not self._vault_key() or not token:
            QMessageBox.warning(self,"Missing details","Select a workspace and enter an access token."); return
        try:
            import keyring
            keyring.set_password("SocialPilotAI.Meta",self._vault_key(),token)
            self.int_token.clear()
            QMessageBox.information(self,"Saved securely","Token saved in your operating system credential vault. It was not written to the app database.")
        except Exception as e:
            QMessageBox.critical(self,"Credential vault unavailable",f"Could not save securely. Install requirements and verify Windows Credential Manager is available.\\n\\n{e}")

    def check_secure_token(self):
        try:
            import keyring
            value=keyring.get_password("SocialPilotAI.Meta",self._vault_key())
            QMessageBox.information(self,"Credential vault", "A token is saved for this workspace/channel." if value else "No token found for this workspace/channel.")
        except Exception as e:
            QMessageBox.warning(self,"Credential vault unavailable",str(e))

    def delete_secure_token(self):
        try:
            import keyring
            keyring.delete_password("SocialPilotAI.Meta",self._vault_key())
            QMessageBox.information(self,"Credential removed","Saved token removed from the credential vault.")
        except Exception as e:
            QMessageBox.warning(self,"Nothing removed / vault error",str(e))

    def build_page(self,name):
        p=QWidget(); l=QVBoxLayout(p); l.setContentsMargins(26,24,26,24); l.addLayout(self.heading(name,"Offline-first workspace • Your data stays on this computer"))
        if name=="Dashboard":
            row=QHBoxLayout()
            for title,sql in [("Workspaces","select count(*) from workspaces"),("Content items","select count(*) from content"),("Contacts","select count(*) from contacts"),("Campaigns","select count(*) from campaigns")]:
                row.addWidget(self.card(title,self.db.execute(sql).fetchone()[0]))
            l.addLayout(row)
            info=QLabel("Welcome to SocialPilot AI Desktop. Prepare social content, organize contacts, manage campaign drafts and plan your calendar offline.")
            info.setWordWrap(True); info.setObjectName("card"); l.addWidget(info)
            btn=QPushButton("+ Create content"); btn.clicked.connect(self.new_content); l.addWidget(btn,alignment=Qt.AlignLeft)
            upcoming=QLabel("Recent content"); upcoming.setObjectName("section"); l.addWidget(upcoming)
            l.addWidget(self.content_table(limit=8))
        elif name=="Workspaces":
            l.addWidget(self.workspace_table())
            b=QPushButton("+ New workspace"); b.clicked.connect(self.new_workspace); l.addWidget(b,alignment=Qt.AlignLeft)
        elif name=="Content Studio":
            bar=QHBoxLayout(); b=QPushButton("+ Create content"); b.clicked.connect(self.new_content); bar.addWidget(b); bar.addStretch()
            delete=QPushButton("Delete selected"); delete.clicked.connect(lambda:self.delete_selected(self.content_table_ref)); bar.addWidget(delete); l.addLayout(bar)
            self.content_table_ref=self.content_table(); l.addWidget(self.content_table_ref)
        elif name=="Content Calendar":
            top=QHBoxLayout(); self.cal=QCalendarWidget(); self.cal.setGridVisible(True); self.cal.clicked.connect(self.calendar_date_selected)
            side=QVBoxLayout(); self.cal_date=QLabel(QDate.currentDate().toString("dddd, dd MMMM yyyy")); self.cal_date.setObjectName("section")
            self.cal_list=QListWidget(); create=QPushButton("+ Add for selected date"); create.clicked.connect(self.new_content_for_calendar)
            side.addWidget(self.cal_date); side.addWidget(self.cal_list,1); side.addWidget(create)
            top.addWidget(self.cal,1); top.addLayout(side,1); l.addLayout(top,1); self.calendar_date_selected(QDate.currentDate())
        elif name=="AI Content Lab":
            l.addWidget(QLabel("Offline idea and copy assistant"))
            form=QFormLayout(); self.ai_brand=QLineEdit(); self.ai_topic=QLineEdit(); self.ai_goal=QComboBox(); self.ai_goal.addItems(["Educate","Engage","Promote","Build trust","Announce"])
            self.ai_format=QComboBox(); self.ai_format.addItems(["Instagram caption","Reel script","Carousel outline","Story sequence","WhatsApp message"])
            form.addRow("Brand / business",self.ai_brand); form.addRow("Topic",self.ai_topic); form.addRow("Goal",self.ai_goal); form.addRow("Format",self.ai_format); l.addLayout(form)
            b=QPushButton("Generate ideas from local templates"); b.clicked.connect(self.generate_ideas); l.addWidget(b,alignment=Qt.AlignLeft)
            self.ai_result=QTextEdit(); self.ai_result.setPlaceholderText("Generated content appears here. Edit and copy it."); l.addWidget(self.ai_result,1)
            copy=QPushButton("Save as content draft"); copy.clicked.connect(self.save_ai_draft); l.addWidget(copy,alignment=Qt.AlignLeft)
            note=QLabel("This offline assistant uses built-in writing patterns, not a cloud AI model. Online AI provider integration can be added later."); note.setWordWrap(True); l.addWidget(note)
        elif name=="Campaigns":
            b=QPushButton("+ Prepare campaign"); b.clicked.connect(self.new_campaign); l.addWidget(b,alignment=Qt.AlignLeft)
            self.camp_table=QTableWidget(0,5); self.camp_table.setHorizontalHeaderLabels(["Workspace","Name","Channel","Status","Created"]); self.camp_table.horizontalHeader().setStretchLastSection(True)
            for r,row in enumerate(self.db.execute("select workspace,name,channel,status,created from campaigns order by id desc")):
                self.camp_table.insertRow(r)
                for c,v in enumerate(row): self.camp_table.setItem(r,c,QTableWidgetItem(str(v)))
            l.addWidget(self.camp_table)
            l.addWidget(QLabel("Campaigns are prepared locally. Actual sending requires online official platform integrations."))
        elif name=="Audience & CRM":
            bar=QHBoxLayout(); add=QPushButton("+ Add contact"); add.clicked.connect(self.new_contact); bar.addWidget(add)
            imp=QPushButton("Import CSV"); imp.clicked.connect(self.import_contacts); bar.addWidget(imp)
            exp=QPushButton("Export CSV"); exp.clicked.connect(self.export_contacts); bar.addWidget(exp); bar.addStretch(); l.addLayout(bar)
            self.contact_table=QTableWidget(0,6); self.contact_table.setHorizontalHeaderLabels(["Workspace","Name","Phone","Email","Tags","Created"]); self.contact_table.horizontalHeader().setStretchLastSection(True)
            for r,row in enumerate(self.db.execute("select workspace,name,phone,email,tags,created from contacts order by id desc")):
                self.contact_table.insertRow(r)
                for c,v in enumerate(row): self.contact_table.setItem(r,c,QTableWidgetItem(str(v)))
            l.addWidget(self.contact_table,1)
        elif name=="WhatsApp Bulk":
            l.addWidget(QLabel("Send approved WhatsApp Business templates to contacts who explicitly opted in. This tool does not use WhatsApp Web automation."))
            top=QFormLayout()
            self.wa_workspace=QComboBox(); self.wa_workspace.addItems([r[0] for r in self.db.execute("select name from workspaces order by name")])
            self.wa_campaign=QLineEdit(); self.wa_campaign.setPlaceholderText("Campaign name (e.g. November offer)")
            self.wa_phone_id=QLineEdit(); self.wa_phone_id.setPlaceholderText("WhatsApp Phone Number ID from Meta")
            self.wa_template=QLineEdit(); self.wa_template.setPlaceholderText("Approved template name (exact Meta name)")
            self.wa_language=QLineEdit("en_US")
            self.wa_var1=QLineEdit(); self.wa_var1.setPlaceholderText("Body variable 1 (optional; e.g. offer or name)")
            top.addRow("Workspace",self.wa_workspace); top.addRow("Campaign",self.wa_campaign)
            top.addRow("Phone Number ID",self.wa_phone_id); top.addRow("Approved template",self.wa_template)
            top.addRow("Template language",self.wa_language); top.addRow("Body variable 1",self.wa_var1)
            l.addLayout(top)
            info=QLabel("Token is read from Windows Credential Manager for the selected workspace under WhatsApp Business Platform (Meta).")
            info.setWordWrap(True); l.addWidget(info)
            actions=QHBoxLayout()
            qbtn=QPushButton("Build preview / queue opted-in contacts"); qbtn.clicked.connect(self.wa_build_queue); actions.addWidget(qbtn)
            sendbtn=QPushButton("Send queued messages"); sendbtn.clicked.connect(self.wa_send_queue); actions.addWidget(sendbtn)
            refresh=QPushButton("Refresh queue"); refresh.clicked.connect(self.wa_refresh_queue); actions.addWidget(refresh)
            l.addLayout(actions)
            self.wa_table=QTableWidget(0,5); self.wa_table.setHorizontalHeaderLabels(["Recipient","Phone","Template","Status","Result"]); self.wa_table.horizontalHeader().setStretchLastSection(True); l.addWidget(self.wa_table,1)
            self.wa_status=QLabel("Queue is empty. Sending requires online connectivity and valid Meta permissions."); self.wa_status.setWordWrap(True); l.addWidget(self.wa_status)
            self.wa_refresh_queue()
        elif name=="Templates":
            bar=QHBoxLayout(); add=QPushButton("+ New template"); add.clicked.connect(self.new_template); bar.addWidget(add); bar.addStretch(); l.addLayout(bar)
            self.template_table=QTableWidget(0,3); self.template_table.setHorizontalHeaderLabels(["Name","Category","Body"]); self.template_table.horizontalHeader().setStretchLastSection(True)
            for r,row in enumerate(self.db.execute("select name,category,body from templates order by name")):
                self.template_table.insertRow(r)
                for c,v in enumerate(row): self.template_table.setItem(r,c,QTableWidgetItem(str(v)))
            l.addWidget(self.template_table,1)
        elif name=="Integrations":
            l.addWidget(QLabel("Connect your business channels. This setup panel stores configuration metadata locally; it does not transmit or publish anything yet."))
            self.int_workspace=QComboBox()
            self.int_workspace.addItems([r[0] for r in self.db.execute("select name from workspaces order by name")])
            l.addWidget(QLabel("Workspace")); l.addWidget(self.int_workspace)
            self.int_provider=QComboBox(); self.int_provider.addItems(["Instagram Business (Meta)","WhatsApp Business Platform (Meta)"])
            self.int_account=QLineEdit(); self.int_account.setPlaceholderText("Business / display name")
            self.int_account_id=QLineEdit(); self.int_account_id.setPlaceholderText("Instagram account ID or WhatsApp Phone Number ID")
            self.int_app_id=QLineEdit(); self.int_app_id.setPlaceholderText("Meta App ID (no access token)")
            self.int_status=QComboBox(); self.int_status.addItems(["Not configured","Configuration in progress","Ready for API review","Connected (manual confirmation)"])
            self.int_notes=QTextEdit(); self.int_notes.setMaximumHeight(90); self.int_notes.setPlaceholderText("Notes: permissions, verification, callback URL, etc.")
            f=QFormLayout(); f.addRow("Channel",self.int_provider); f.addRow("Account name",self.int_account); f.addRow("Account / Phone ID",self.int_account_id); f.addRow("Meta App ID",self.int_app_id); f.addRow("Local setup status",self.int_status); f.addRow("Notes",self.int_notes); l.addLayout(f)
            save=QPushButton("Save integration setup"); save.clicked.connect(self.save_integration); l.addWidget(save,alignment=Qt.AlignLeft)
            vault_title=QLabel("Secure credential vault"); vault_title.setObjectName("heading"); l.addWidget(vault_title)
            vault_help=QLabel("Store a Meta access token in the Windows Credential Manager via Python keyring. Tokens are NOT saved in the SocialPilot SQLite database. Use only tokens you generated for your own Meta app.")
            vault_help.setWordWrap(True); vault_help.setObjectName("subtitle"); l.addWidget(vault_help)
            self.int_token=QLineEdit(); self.int_token.setPlaceholderText("Paste access token (masked)"); self.int_token.setEchoMode(QLineEdit.Password)
            vf=QFormLayout(); vf.addRow("Access token",self.int_token); l.addLayout(vf)
            vault_row=QHBoxLayout()
            save_token=QPushButton("Save token securely"); save_token.clicked.connect(self.save_secure_token); vault_row.addWidget(save_token)
            check_token=QPushButton("Check vault"); check_token.clicked.connect(self.check_secure_token); vault_row.addWidget(check_token)
            delete_token=QPushButton("Delete saved token"); delete_token.clicked.connect(self.delete_secure_token); vault_row.addWidget(delete_token)
            l.addLayout(vault_row)
            self.integr_table=QTableWidget(0,6); self.integr_table.setHorizontalHeaderLabels(["Workspace","Provider","Account","Account ID","Status","Updated"]); self.integr_table.horizontalHeader().setStretchLastSection(True)
            for r,row in enumerate(self.db.execute("select workspace,provider,account_name,account_id,status,updated from integrations order by id desc")):
                self.integr_table.insertRow(r)
                for c,v in enumerate(row): self.integr_table.setItem(r,c,QTableWidgetItem(str(v or "")))
            l.addWidget(self.integr_table,1)
            note=QLabel("Important: Instagram publishing and WhatsApp messaging require approved Meta APIs, permissions, and online connectivity. Never paste access tokens into this panel. OAuth/token vault and live API calls are a later secure integration step.")
            note.setWordWrap(True); note.setObjectName("card"); l.addWidget(note)
        elif name=="OAuth Setup":
            l.addWidget(QLabel("Meta OAuth Authorization Setup"))
            info=QLabel("Prepare an authorization URL for your Meta developer app. This opens Meta in your browser; authorization-code capture and token exchange are not yet automated. Use only your own app and accounts.")
            info.setWordWrap(True); info.setObjectName("subtitle"); l.addWidget(info)
            self.oauth_provider=QComboBox(); self.oauth_provider.addItems(["Instagram Business","WhatsApp Business"])
            self.oauth_client=QLineEdit(); self.oauth_client.setPlaceholderText("Meta App ID")
            self.oauth_redirect=QLineEdit("https://www.facebook.com/")
            self.oauth_scopes=QLineEdit()
            self.oauth_scopes.setText("instagram_basic,instagram_manage_insights,instagram_content_publish,pages_show_list")
            self.oauth_url=QLineEdit(); self.oauth_url.setReadOnly(True)
            f=QFormLayout(); f.addRow("Product",self.oauth_provider); f.addRow("App ID",self.oauth_client); f.addRow("Redirect URI (must match Meta app)",self.oauth_redirect); f.addRow("Requested scopes",self.oauth_scopes); f.addRow("Authorization URL",self.oauth_url); l.addLayout(f)
            row=QHBoxLayout()
            gen=QPushButton("Generate Authorization URL"); gen.clicked.connect(self.generate_oauth_url); row.addWidget(gen)
            op=QPushButton("Open in Browser"); op.clicked.connect(self.open_oauth_url); row.addWidget(op)
            cp=QPushButton("Copy URL"); cp.clicked.connect(self.copy_oauth_url); row.addWidget(cp)
            l.addLayout(row)
            self.oauth_code=QLineEdit(); self.oauth_code.setPlaceholderText("Paste code= from the redirect URL")
            self.oauth_secret=QLineEdit(); self.oauth_secret.setPlaceholderText("Meta App Secret (used only for this exchange)"); self.oauth_secret.setEchoMode(QLineEdit.Password)
            self.oauth_callback=QLineEdit(); self.oauth_callback.setPlaceholderText("Paste full redirected URL here to extract code")
            self.oauth_token=QLineEdit(); self.oauth_token.setReadOnly(True); self.oauth_token.setEchoMode(QLineEdit.Password)
            self.oauth_expiry=QLabel("Token expiry: not checked")
            self.oauth_long_token=QLineEdit(); self.oauth_long_token.setReadOnly(True); self.oauth_long_token.setEchoMode(QLineEdit.Password)
            l.addWidget(QLabel("Authorization response"))
            l.addWidget(self.oauth_callback)
            parsebtn=QPushButton("Extract authorization code from redirect URL")
            parsebtn.clicked.connect(self.parse_oauth_callback); l.addWidget(parsebtn)
            f2=QFormLayout(); f2.addRow("Authorization code",self.oauth_code); f2.addRow("Meta App Secret",self.oauth_secret); f2.addRow("Short-lived access token",self.oauth_token); f2.addRow("Token expiry",self.oauth_expiry); f2.addRow("Long-lived token",self.oauth_long_token); l.addLayout(f2)
            exchange=QPushButton("Exchange Code for Access Token"); exchange.clicked.connect(self.exchange_oauth_code); l.addWidget(exchange)
            longbtn=QPushButton("Exchange for Long-Lived Token (Instagram flow)"); longbtn.clicked.connect(self.exchange_long_lived_token); l.addWidget(longbtn)
            discover=QPushButton("Discover Connected Meta Assets"); discover.clicked.connect(self.discover_meta_assets); l.addWidget(discover)
            self.meta_assets=QPlainTextEdit(); self.meta_assets.setReadOnly(True); self.meta_assets.setPlaceholderText("Discovered Facebook Pages, Instagram professional profiles, and WhatsApp Business assets will appear here."); self.meta_assets.setMinimumHeight(180); l.addWidget(self.meta_assets)
            l.addWidget(QLabel("Security: App Secret and codes are not written to SQLite. Token values are masked and not auto-saved. Long-lived exchange is supported only for eligible Instagram OAuth tokens; WhatsApp token lifetimes/refresh rules differ."))
        elif name=="Automations":
            l.addWidget(QLabel("Offline automation ideas and local reminders"))
            for title,desc in [("Content planning reminder","On a chosen date, remind you to prepare content."),("Lead follow-up task","Create a local follow-up task from a new CRM contact."),("Campaign checklist","Review campaign copy, audience and CTA before sending.")]:
                f=QFrame(); f.setObjectName("card"); fl=QHBoxLayout(f); vv=QVBoxLayout(); t=QLabel(title); t.setObjectName("section"); vv.addWidget(t); vv.addWidget(QLabel(desc)); fl.addLayout(vv,1); fl.addWidget(QLabel("Template")); l.addWidget(f)
            l.addWidget(QLabel("Scheduled background execution and external triggers are planned for the connected release."))
        elif name=="Analytics":
            for label,sql in [("Content items","select count(*) from content"),("Contacts","select count(*) from contacts"),("Campaign drafts","select count(*) from campaigns"),("Workspaces","select count(*) from workspaces")]:
                l.addWidget(self.card(label,self.db.execute(sql).fetchone()[0]))
            l.addWidget(QLabel("Metrics are based on local records. Live channel analytics require connected accounts."))
        elif name=="Settings & Backup":
            l.addWidget(QLabel("Local database and backup"))
            l.addWidget(QLabel("Database: "+DB))
            b=QPushButton("Create backup now"); b.clicked.connect(self.backup_db); l.addWidget(b,alignment=Qt.AlignLeft)
            r=QPushButton("Restore from backup…"); r.clicked.connect(self.restore_db); l.addWidget(r,alignment=Qt.AlignLeft)
            exp=QPushButton("Export all local data (JSON)"); exp.clicked.connect(self.export_all_json); l.addWidget(exp,alignment=Qt.AlignLeft)
            cb=QCheckBox("Dark mode"); cb.setChecked(self.dark); cb.stateChanged.connect(self.toggle_theme); l.addWidget(cb)
            l.addWidget(QLabel("Backups are saved under your Windows user profile in SocialPilotAI\\Backups."))
        l.addStretch(); return p
    def wa_build_queue(self):
        workspace=self.wa_workspace.currentText().strip()
        campaign=self.wa_campaign.text().strip()
        phone_id=self.wa_phone_id.text().strip()
        template=self.wa_template.text().strip()
        language=self.wa_language.text().strip() or "en_US"
        if not all([workspace,campaign,phone_id,template]):
            QMessageBox.warning(self,"Required fields","Enter workspace, campaign, Phone Number ID, and approved template name."); return
        contacts=self.db.execute("SELECT id,name,phone FROM contacts WHERE workspace=? AND marketing_opt_in=1 AND phone IS NOT NULL AND trim(phone)<>''",(workspace,)).fetchall()
        if not contacts:
            QMessageBox.information(self,"No eligible contacts","No contacts in this workspace have explicit marketing opt-in and a phone number. Import/update consent first."); return
        if QMessageBox.question(self,"Confirm queue",f"Queue {len(contacts)} opted-in contacts for template '{template}'?\n\nNo messages will be sent yet.")!=QMessageBox.Yes: return
        now=datetime.now().isoformat(timespec="seconds")
        variable=self.wa_var1.text().strip()
        for cid,name,phone in contacts:
            normalized=re.sub(r"[^0-9]","",phone or "")
            if len(normalized)<8: continue
            payload={"body":[{"type":"text","text":(variable.replace("{name}",name or "") if variable else (name or ""))}]} if variable else {"body":[]}
            self.db.execute("INSERT INTO wa_bulk_jobs(workspace,campaign_name,phone,contact_name,template_name,language,payload,status,created) VALUES(?,?,?,?,?,?,?,?,?)",
                (workspace,campaign,normalized,name or "",template,language,json.dumps(payload,ensure_ascii=False),"Queued",now))
        self.db.commit(); self.wa_refresh_queue()
        QMessageBox.information(self,"Queue created","Eligible contacts queued. Review the list before sending.")

    def wa_refresh_queue(self):
        if not hasattr(self,"wa_table"): return
        self.wa_table.setRowCount(0)
        rows=self.db.execute("SELECT contact_name,phone,template_name,status,COALESCE(result,'') FROM wa_bulk_jobs ORDER BY id DESC LIMIT 500").fetchall()
        for r,row in enumerate(rows):
            self.wa_table.insertRow(r)
            for c,v in enumerate(row): self.wa_table.setItem(r,c,QTableWidgetItem(str(v)))
        if hasattr(self,"wa_status"): self.wa_status.setText(f"{len(rows)} latest queue records. Contacts without consent are excluded.")

    def wa_send_queue(self):
        workspace=self.wa_workspace.currentText().strip()
        phone_id=self.wa_phone_id.text().strip()
        template=self.wa_template.text().strip()
        language=self.wa_language.text().strip() or "en_US"
        if not all([workspace,phone_id,template]):
            QMessageBox.warning(self,"Required fields","Select workspace and enter Phone Number ID and template name."); return
        if QMessageBox.warning(self,"Confirm live send","This will send LIVE WhatsApp messages to all queued recipients with status Queued. Continue?",
                               QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes: return
        try:
            import keyring
            token=keyring.get_password("SocialPilotAI.Meta",f"{workspace}::WhatsApp Business Platform (Meta)")
        except Exception as e:
            QMessageBox.critical(self,"Credential vault error",str(e)); return
        if not token:
            QMessageBox.warning(self,"Token not found","Save a WhatsApp Business Platform access token in Integrations first."); return
        jobs=self.db.execute("SELECT id,phone,contact_name,payload FROM wa_bulk_jobs WHERE workspace=? AND status='Queued' AND template_name=? ORDER BY id",(workspace,template)).fetchall()
        if not jobs:
            QMessageBox.information(self,"Nothing queued","No queued messages match this workspace/template."); return
        sent=0; failed=0
        for jid,phone,name,payload_json in jobs:
            try:
                payload_data=json.loads(payload_json or "{}")
                components=[]
                if payload_data.get("body"):
                    components=[{"type":"body","parameters":[{"type":"text","text":x.get("text","")} for x in payload_data["body"]]}]
                body={"messaging_product":"whatsapp","to":phone,"type":"template",
                      "template":{"name":template,"language":{"code":language},"components":components}}
                response=requests.post(f"https://graph.facebook.com/v22.0/{phone_id}/messages",
                    headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},json=body,timeout=30)
                data=response.json()
                if response.ok and data.get("messages"):
                    self.db.execute("UPDATE wa_bulk_jobs SET status='Sent',result=?,completed=? WHERE id=?",
                        (str(data["messages"][0].get("id","accepted by Meta")),datetime.now().isoformat(timespec="seconds"),jid)); sent+=1
                else:
                    err=data.get("error",{}); detail=err.get("message",f"HTTP {response.status_code}")
                    self.db.execute("UPDATE wa_bulk_jobs SET status='Failed',result=?,completed=? WHERE id=?",
                        (detail[:500],datetime.now().isoformat(timespec="seconds"),jid)); failed+=1
            except Exception as e:
                self.db.execute("UPDATE wa_bulk_jobs SET status='Failed',result=?,completed=? WHERE id=?",
                    (str(e)[:500],datetime.now().isoformat(timespec="seconds"),jid)); failed+=1
            self.db.commit()
            # Deliberate conservative pacing; users must still comply with Meta limits.
            import time
            time.sleep(2.0)
        self.wa_refresh_queue()
        QMessageBox.information(self,"Bulk send finished",f"Accepted by Meta: {sent}\nFailed: {failed}\nDelivery status may arrive separately through webhooks.")

    def navigate(self,name):
        self.stack.setCurrentWidget(self.page_map[name])
    def content_table(self,limit=None):
        t=QTableWidget(0,6); t.setHorizontalHeaderLabels(["Workspace","Channel","Type","Caption","Status","Scheduled"]); t.horizontalHeader().setStretchLastSection(True)
        q="select workspace,channel,kind,caption,status,scheduled from content order by id desc"
        if limit:q+=" limit "+str(int(limit))
        for r,row in enumerate(self.db.execute(q)):
            t.insertRow(r)
            for c,v in enumerate(row): t.setItem(r,c,QTableWidgetItem(str(v or "")))
        return t
    def workspace_table(self):
        t=QTableWidget(0,3)
        t.setHorizontalHeaderLabels(["Workspace", "Industry", "Created"])
        t.horizontalHeader().setStretchLastSection(True)
        for r, row in enumerate(self.db.execute("select name,industry,created from workspaces order by id desc")):
            t.insertRow(r)
            for c, value in enumerate(row):
                t.setItem(r,c,QTableWidgetItem(str(value or "")))
        return t
    def workspaces(self):
        return [r[0] for r in self.db.execute("select name from workspaces")]
    def new_workspace(self):
        d=FormDialog("New workspace",[("Name","text",None),("Industry","text",None)],self)
        if d.exec():
            v=d.values()
            try:self.db.execute("insert into workspaces(name,industry,created) values(?,?,?)",(v["Name"],v["Industry"],datetime.now().isoformat(timespec="minutes"))); self.db.commit(); self.rebuild()
            except sqlite3.IntegrityError: QMessageBox.warning(self,"Already exists","Workspace name must be unique.")
    def new_content(self,selected_date=None):
        d=FormDialog("Create content",[("Workspace","combo",self.workspaces()),("Channel","combo",["Instagram","WhatsApp","Other"]),("Type","combo",["Caption","Reel script","Carousel","Story","Message"]),("Caption / content","area",None),("Status","combo",["Draft","Ready for review","Approved","Published"]),("Schedule date","date",None)],self)
        if selected_date: d.widgets["Schedule date"].setDate(selected_date)
        if d.exec():
            v=d.values(); scheduled=v["Schedule date"]
            self.db.execute("insert into content(workspace,channel,kind,caption,status,scheduled,created) values(?,?,?,?,?,?,?)",(v["Workspace"],v["Channel"],v["Type"],v["Caption / content"],v["Status"],scheduled,datetime.now().isoformat(timespec="minutes"))); self.db.commit(); self.rebuild()
    def calendar_date_selected(self,qd):
        self.cal_date.setText(qd.toString("dddd, dd MMMM yyyy")); self.cal_list.clear()
        ds=qd.toString("yyyy-MM-dd")
        for row in self.db.execute("select channel,kind,substr(caption,1,90),status from content where scheduled=? order by id",(ds,)):
            self.cal_list.addItem(f"{row[0]} · {row[1]} · {row[3]}\\n{row[2]}")
    def new_content_for_calendar(self): self.new_content(self.cal.selectedDate())
    def delete_selected(self,table):
        row=table.currentRow()
        if row<0:return
        item=table.item(row,0)
        # Table display deletion is intentionally not enabled without explicit record ID mapping.
        QMessageBox.information(self,"Delete content","For safety, delete/edit controls will be enabled with record-level selection in the next maintenance update.")
    def new_campaign(self):
        d=FormDialog("Prepare campaign",[("Workspace","combo",self.workspaces()),("Name","text",None),("Channel","combo",["WhatsApp","Instagram"]),("Message","area",None)],self)
        if d.exec():
            v=d.values(); self.db.execute("insert into campaigns(workspace,name,channel,message,status,created) values(?,?,?,?,?,?)",(v["Workspace"],v["Name"],v["Channel"],v["Message"],"Draft",datetime.now().isoformat())); self.db.commit(); self.rebuild()
    def new_contact(self):
        d=FormDialog("Add contact",[("Workspace","combo",self.workspaces()),("Name","text",None),("Phone","text",None),("Email","text",None),("Tags","text",None)],self)
        if d.exec():
            v=d.values(); self.db.execute("insert into contacts(workspace,name,phone,email,tags,created) values(?,?,?,?,?,?)",(v["Workspace"],v["Name"],v["Phone"],v["Email"],v["Tags"],datetime.now().isoformat())); self.db.commit(); self.rebuild()
    def import_contacts(self):
        path,_=QFileDialog.getOpenFileName(self,"Import contacts CSV","","CSV files (*.csv)")
        if not path:return
        try:
            with open(path,newline="",encoding="utf-8-sig") as f:
                reader=csv.DictReader(f); ws=self.workspaces()[0]; count=0
                for row in reader:
                    name=row.get("Name") or row.get("name") or row.get("Contact Name") or ""
                    phone=row.get("Phone") or row.get("phone") or row.get("Contact") or ""
                    email=row.get("Email") or row.get("email") or ""
                    tags=row.get("Tags") or row.get("tags") or ""
                    if name or phone or email:
                        self.db.execute("insert into contacts(workspace,name,phone,email,tags,created) values(?,?,?,?,?,?)",(ws,name,phone,email,tags,datetime.now().isoformat())); count+=1
            self.db.commit(); QMessageBox.information(self,"Import complete",f"Imported {count} contacts."); self.rebuild()
        except Exception as e: QMessageBox.critical(self,"Import failed",str(e))
    def export_contacts(self):
        path,_=QFileDialog.getSaveFileName(self,"Export contacts","","CSV files (*.csv)")
        if not path:return
        with open(path,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f); w.writerow(["Workspace","Name","Phone","Email","Tags","Created"])
            w.writerows(self.db.execute("select workspace,name,phone,email,tags,created from contacts"))
        QMessageBox.information(self,"Export complete","Contacts exported.")
    def new_template(self):
        d=FormDialog("New template",[("Name","text",None),("Category","text",None),("Body","area",None)],self)
        if d.exec():
            v=d.values(); self.db.execute("insert into templates(name,category,body) values(?,?,?)",(v["Name"],v["Category"],v["Body"])); self.db.commit(); self.rebuild()
    def generate_ideas(self):
        brand=self.ai_brand.text().strip() or "Your brand"; topic=self.ai_topic.text().strip() or "your topic"; goal=self.ai_goal.currentText(); fmt=self.ai_format.currentText()
        if fmt=="Instagram caption":
            text=f"{brand} | {goal}\\n\\nLet's talk about {topic}.\\n\\nHere are 3 useful things to remember:\\n1. Start with one small step.\\n2. Focus on consistency over perfection.\\n3. Save this for later and share it with someone who needs it.\\n\\nWhat is your experience with {topic}? Tell us below.\\n\\n#{topic.replace(' ','')} #Tips #Community"
        elif fmt=="Reel script":
            text=f"REEL: {topic}\\nHook (0–3 sec): “Have you ever wondered about {topic}?”\\nValue (3–15 sec): Share 2–3 clear, practical points.\\nExample (15–25 sec): Show a simple real-world example.\\nCTA (last 3 sec): “Follow {brand} for more. Save this reel.”"
        elif fmt=="Carousel outline":
            text=f"CAROUSEL: {topic}\\nSlide 1 — A compelling question about {topic}\\nSlide 2 — Why it matters\\nSlide 3 — Common mistake\\nSlide 4 — Practical tip #1\\nSlide 5 — Practical tip #2\\nSlide 6 — Quick recap\\nSlide 7 — Save, share, and follow {brand}"
        elif fmt=="Story sequence":
            text=f"STORY 1: “Quick question about {topic}…” (Poll)\\nSTORY 2: One useful insight\\nSTORY 3: A practical tip\\nSTORY 4: “Want more? Reply to this story.”"
        else:
            text=f"Hi {{name}}! This is {brand}. We wanted to share a quick update about {topic}. Would you like to know more? Reply here and we'll help. Reply STOP to opt out."
        self.ai_result.setPlainText(text)
    def save_ai_draft(self):
        txt=self.ai_result.toPlainText().strip()
        if not txt:return
        ws=self.workspaces()[0]
        channel = "WhatsApp" if self.ai_format.currentText().lower().startswith("whatsapp") else "Instagram"
        kind = "Message" if channel == "WhatsApp" else "Caption"
        self.db.execute("insert into content(workspace,channel,kind,caption,status,created) values(?,?,?,?,?,?)",(ws,channel,kind,txt,"Draft",datetime.now().isoformat())); self.db.commit(); QMessageBox.information(self,"Saved","Content saved as a draft."); self.rebuild()
    def backup_db(self):
        dest=os.path.join(BACKUP_DIR,"socialpilot_backup_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".db")
        self.db.commit(); shutil.copy2(DB,dest); QMessageBox.information(self,"Backup created",dest)
    def restore_db(self):
        path,_=QFileDialog.getOpenFileName(self,"Restore backup",BACKUP_DIR,"Database backups (*.db)")
        if not path:return
        if QMessageBox.question(self,"Confirm restore","This replaces current local data. Continue?")!=QMessageBox.Yes:return
        self.db.close(); shutil.copy2(path,DB); self.db=dbconn(); self.rebuild()
    def export_all_json(self):
        path,_=QFileDialog.getSaveFileName(self,"Export data","","JSON files (*.json)")
        if not path:return
        data={}
        for table in ["workspaces","content","contacts","campaigns","templates"]:
            cur=self.db.execute(f"select * from {table}"); data[table]={"columns":[x[0] for x in cur.description],"rows":cur.fetchall()}
        with open(path,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)
        QMessageBox.information(self,"Export complete","All local tables exported as JSON.")
    def rebuild(self):
        current=self.stack.currentWidget()
        name=next((k for k,v in self.page_map.items() if v==current),"Dashboard")
        idx=self.stack.indexOf(current); self.stack.removeWidget(current); current.deleteLater()
        page=self.build_page(name); self.page_map[name]=page; self.stack.insertWidget(idx,page); self.stack.setCurrentWidget(page)
    def toggle_theme(self): self.dark=not self.dark; self.set_theme()
    def set_theme(self):
        if self.dark:
            self.setStyleSheet("""QMainWindow,QWidget{background:#151A18;color:#E8EEE9;font-family:'Segoe UI';font-size:10pt} QFrame#card{background:#202722;border:1px solid #303B33;border-radius:12px;padding:14px} QLabel#heading{font-size:24pt;font-weight:700;color:#F2F6F2} QLabel#subtitle{color:#9BA99E} QLabel#metric{font-size:23pt;font-weight:700;color:#42B879} QLabel#brand{font-size:18pt;font-weight:800;color:#54C889;padding:10px} QFrame#sidebar{background:#101411} QPushButton{background:#20864F;color:white;border:0;border-radius:8px;padding:10px} QPushButton#nav{background:transparent;color:#C1CCC4;text-align:left;padding:10px} QPushButton#nav:hover{background:#26362B;color:white} QLineEdit,QTextEdit,QComboBox,QTableWidget,QListWidget,QCalendarWidget{background:#202722;color:#E8EEE9;border:1px solid #38453B;border-radius:6px;padding:5px} QHeaderView::section{background:#26332A;color:#E8EEE9;padding:6px} QLabel#section{font-size:13pt;font-weight:700}""")
        else:
            self.setStyleSheet("""QMainWindow,QWidget{background:#F5F7F5;color:#1D2A22;font-family:'Segoe UI';font-size:10pt} QFrame#card{background:#FFFFFF;border:1px solid #E2E8E2;border-radius:12px;padding:14px} QLabel#heading{font-size:24pt;font-weight:700;color:#18251D} QLabel#subtitle{color:#6D7C71} QLabel#metric{font-size:23pt;font-weight:700;color:#16864B} QLabel#brand{font-size:18pt;font-weight:800;color:#16864B;padding:10px} QFrame#sidebar{background:#EAF0EA} QPushButton{background:#16864B;color:white;border:0;border-radius:8px;padding:10px} QPushButton#nav{background:transparent;color:#33463A;text-align:left;padding:10px} QPushButton#nav:hover{background:#DCE8DE;color:#173C25} QLineEdit,QTextEdit,QComboBox,QTableWidget,QListWidget,QCalendarWidget{background:white;color:#1D2A22;border:1px solid #D9E2DA;border-radius:6px;padding:5px} QHeaderView::section{background:#E8EFE9;color:#25382B;padding:6px} QLabel#section{font-size:13pt;font-weight:700}""")

def main():
    app=QApplication(sys.argv); app.setApplicationName("SocialPilot AI Desktop")
    win=SocialPilot(); win.show(); sys.exit(app.exec())
if __name__=="__main__": main()
