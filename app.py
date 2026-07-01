import os
import requests
from flask import Flask, render_template, request, redirect, url_for, abort
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
    try:
        supabase.table("logs_os").insert({"usuario": current_user.id, "os_id": os_id, "acao": acao}).execute()
    except Exception as e:
        print(f"Erro ao registrar log: {e}")

def enviar_whatsapp(telefone, mensagem):
    url_zapi = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-messages"
    headers = {"Client-Token": ZAPI_TOKEN, "Content-Type": "application/json"}
    payload = {"phone": telefone, "message": mensagem}
    try:
        response = requests.post(url_zapi, json=payload, headers=headers)
        print(f"DEBUG Z-API Status: {response.status_code} | Resposta: {response.text}")
    except Exception as e:
        print(f"Erro ao comunicar com Z-API: {e}")

def notificar_conclusao(os_id, cliente, servico):
    usuarios_alvo = supabase.table("usuarios").select("telefone").in_("role", ["admin", "vendedor"]).execute().data
    msg = f"✅ *OS Finalizada!*\nID: {os_id}\nCliente: {cliente}\nServiço: {servico}"
    for user in usuarios_alvo:
        if user.get('telefone'):
            enviar_whatsapp(user['telefone'], msg)

@login_manager.user_loader
def load_user(user_id):
    response = supabase.table("usuarios").select("username, role").eq("username", user_id).single().execute()
    if response.data: return User(response.data['username'], response.data['role'])
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_in = request.form.get('username')
        pass_in = request.form.get('password')
        response = supabase.table("usuarios").select("*").eq("username", user_in).single().execute()
        if response.data and response.data['password'] == pass_in:
            login_user(User(response.data['username'], response.data['role']))
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/')
@login_required
def index():
    status_filtro = request.args.get('status', 'Todos')
    query = supabase.table("agendamentos").select("*")
    if current_user.role == 'tecnico': query = query.eq("tecnico", current_user.id)
    elif current_user.role == 'vendedor': query = query.eq("vendedor", current_user.id)
    agenda_full = query.execute().data
    agenda = [item for item in agenda_full if item['status'] == status_filtro] if status_filtro != 'Todos' else agenda_full
    tecnicos = supabase.table("usuarios").select("username").eq("role", "tecnico").execute().data
    vendedores = supabase.table("usuarios").select("username").eq("role", "vendedor").execute().data
    return render_template('index.html', agenda=agenda, role=current_user.role, user_id=current_user.id, tecnicos=tecnicos, vendedores=vendedores)

@app.route('/logs')
@login_required
def ver_logs():
    if current_user.role != 'admin': return "Acesso negado", 403
    logs = supabase.table("logs_os").select("*").order("id", desc=True).execute().data
    return render_template('logs.html', logs=logs)

@app.route('/agendar', methods=['POST'])
@login_required
def agendar():
    if current_user.role in ['admin', 'vendedor']:
        tec_nome = request.form.get('tecnico')
        res = supabase.table("agendamentos").insert({
            "cliente": request.form.get('cliente'), "servico": request.form.get('servico'), "horario": request.form.get('horario'),
            "tecnico": tec_nome, "vendedor": request.form.get('vendedor') if current_user.role == 'admin' else current_user.id,
            "prioridade": request.form.get('prioridade'), "obs": request.form.get('obs'), "status": "Pendente"
        }).execute()
        registrar_log(res.data[0]['id'], "Criou nova OS")
        tec_data = supabase.table("usuarios").select("telefone").eq("username", tec_nome).single().execute()
        if tec_data.data and tec_data.data.get('telefone'):
            msg = f"🔔 *Nova OS!*\nCliente: {request.form.get('cliente')}\nServiço: {request.form.get('servico')}"
            enviar_whatsapp(tec_data.data['telefone'], msg)
    return redirect(url_for('index'))

@app.route('/reagendar/<id>', methods=['POST'])
@login_required
def reagendar(id):
    nova_data = request.form.get('nova_data')
    if nova_data:
        supabase.table("agendamentos").update({"horario": nova_data, "status": "Reagendado"}).eq("id", id).execute()
        registrar_log(id, f"Reagendou a OS para {nova_data}")
    return redirect(url_for('index'))

@app.route('/mudar_status/<id>/<novo_status>')
@login_required
def mudar_status(id, novo_status):
    if novo_status == 'Concluído':
        os_data = supabase.table("agendamentos").select("cliente, servico").eq("id", id).single().execute()
        if os_data.data: notificar_conclusao(id, os_data.data['cliente'], os_data.data['servico'])
    supabase.table("agendamentos").update({"status": novo_status}).eq("id", id).execute()
    registrar_log(id, f"Alterou status para {novo_status}")
    return redirect(url_for('index'))

@app.route('/cancelar/<id>')
@login_required
def cancelar(id):
    if current_user.role == 'tecnico': return "Acesso negado", 403
    os_data = supabase.table("agendamentos").select("tecnico, cliente, servico").eq("id", id).single().execute()
    supabase.table("agendamentos").update({"status": "Cancelado"}).eq("id", id).execute()
    registrar_log(id, "Cancelou a OS")
    if os_data.data:
        tec_nome = os_data.data.get('tecnico')
        tec_data = supabase.table("usuarios").select("telefone").eq("username", tec_nome).single().execute()
        if tec_data.data and tec_data.data.get('telefone'):
            msg = f"🚫 *Aviso de Cancelamento*\n\nA OS do cliente *{os_data.data.get('cliente')}* ({os_data.data.get('servico')}) foi cancelada."
            enviar_whatsapp(tec_data.data['telefone'], msg)
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)