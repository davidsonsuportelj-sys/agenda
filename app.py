import os
import requests
from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chave_secreta_padrao")

ZAPI_INSTANCE_ID = os.getenv("ZAPI_INSTANCE_ID")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

class User(UserMixin):
    def __init__(self, username, role):
        self.id = username
        self.role = role

def registrar_log(os_id, acao):
    supabase.table("logs_os").insert({"usuario": current_user.id, "os_id": os_id, "acao": acao}).execute()

def enviar_whatsapp(telefone, mensagem):
    url_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-messages"
    requests.post(url_zapi, json={"phone": telefone, "message": mensagem}, headers={"Client-Token": ZAPI_TOKEN, "Content-Type": "application/json"})

@login_manager.user_loader
def load_user(user_id):
    response = supabase.table("usuarios").select("username, role").eq("username", user_id).single().execute()
    return User(response.data['username'], response.data['role']) if response.data else None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        response = supabase.table("usuarios").select("*").eq("username", request.form.get('username')).single().execute()
        if response.data and response.data['password'] == request.form.get('password'):
            login_user(User(response.data['username'], response.data['role']))
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/')
@login_required
def index():
    query = supabase.table("agendamentos").select("*")
    if current_user.role == 'tecnico': query = query.eq("tecnico", current_user.id)
    agenda = query.execute().data
    tecnicos = supabase.table("usuarios").select("username").eq("role", "tecnico").execute().data
    vendedores = supabase.table("usuarios").select("username").eq("role", "vendedor").execute().data
    return render_template('index.html', agenda=agenda, role=current_user.role, user_id=current_user.id, tecnicos=tecnicos, vendedores=vendedores)

@app.route('/agendar', methods=['POST'])
@login_required
def agendar():
    res = supabase.table("agendamentos").insert({
        "cliente": request.form.get('cliente'), "servico": request.form.get('servico'), "horario": request.form.get('horario'),
        "tecnico": request.form.get('tecnico'), "vendedor": request.form.get('vendedor') if current_user.role == 'admin' else current_user.id,
        "prioridade": request.form.get('prioridade'), "obs": request.form.get('obs'), "status": "Pendente"
    }).execute()
    registrar_log(res.data[0]['id'], "Criou nova OS")
    return redirect(url_for('index'))

@app.route('/reagendar/<id>', methods=['POST'])
@login_required
def reagendar(id):
    if current_user.role != 'admin': return "Acesso negado", 403
    supabase.table("agendamentos").update({"horario": request.form.get('nova_data')}).eq("id", id).execute()
    registrar_log(id, "Reagendou a OS")
    return redirect(url_for('index'))

@app.route('/mudar_status/<id>/<novo_status>')
@login_required
def mudar_status(id, novo_status):
    supabase.table("agendamentos").update({"status": novo_status}).eq("id", id).execute()
    registrar_log(id, f"Alterou status para {novo_status}")
    return redirect(url_for('index'))

@app.route('/cancelar/<id>')
@login_required
def cancelar(id):
    if current_user.role == 'tecnico': return "Acesso negado", 403
    supabase.table("agendamentos").update({"status": "Cancelado"}).eq("id", id).execute()
    registrar_log(id, "Cancelou a OS")
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)