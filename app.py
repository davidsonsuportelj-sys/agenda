import os
from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chave_secreta_padrao")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, username, role):
        self.id = username
        self.role = role

def registrar_log(os_id, acao):
    try:
        supabase.table("logs_os").insert({
            "usuario": current_user.id, 
            "os_id": os_id, 
            "acao": acao
        }).execute()
    except Exception as e:
        print(f"Erro ao registrar log: {e}")

@login_manager.user_loader
def load_user(user_id):
    response = supabase.table("usuarios").select("username, role").eq("username", user_id).single().execute()
    if response.data: 
        return User(response.data['username'], response.data['role'])
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

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    query = supabase.table("agendamentos").select("*")
 
    if current_user.role == 'tecnico': 
        query = query.eq("tecnico", current_user.id)
    elif current_user.role == 'vendedor': 
        query = query.eq("vendedor", current_user.id)
        
    agenda = query.order("id", desc=True).execute().data
    clientes = supabase.table("clientes").select("*").execute().data
    tecnicos = supabase.table("usuarios").select("username").eq("role", "tecnico").execute().data
    vendedores = supabase.table("usuarios").select("username").eq("role", "vendedor").execute().data
    
    return render_template('index.html', 
                           agenda=agenda, 
                           clientes=clientes, 
                           tecnicos=tecnicos, 
                           vendedores=vendedores,
                           role=current_user.role, 
                           user=current_user)

@app.route('/cadastrar_cliente', methods=['POST'])
@login_required
def cadastrar_cliente():
    if current_user.role in ['admin', 'vendedor']:
        supabase.table("clientes").insert({
            "nome": request.form.get('nome'),
            "telefone": request.form.get('telefone'),
            "endereco": request.form.get('endereco')
        }).execute()
    return redirect(url_for('index'))

@app.route('/agendar', methods=['POST'])
@login_required
def agendar():
    if current_user.role in ['admin', 'vendedor']:
        vendedor_selecionado = request.form.get('vendedor') if current_user.role == 'admin' else current_user.id
        
        res = supabase.table("agendamentos").insert({
            "cliente": request.form.get('cliente_id'), 
            "servico": request.form.get('servico'),
            "horario": request.form.get('horario'),
            "tecnico": request.form.get('tecnico'),
            "prioridade": request.form.get('prioridade'),
            "obs": request.form.get('obs'),
            "vendedor": vendedor_selecionado,
            "status": "Pendente"
        }).execute()
        
        if res.data:
            registrar_log(res.data[0]['id'], "Criou nova OS")
    return redirect(url_for('index'))

@app.route('/reagendar/<id>', methods=['POST'])
@login_required
def reagendar(id):
    nova_data = request.form.get('nova_data')
    if nova_data:
        supabase.table("agendamentos").update({"horario": nova_data, "status": "Reagendado"}).eq("id", id).execute()
        registrar_log(id, f"Reagendou para {nova_data}")
    return redirect(url_for('index'))

@app.route('/mudar_status/<id>/<novo_status>')
@login_required
def mudar_status(id, novo_status):
    supabase.table("agendamentos").update({"status": novo_status}).eq("id", id).execute()
    registrar_log(id, f"Mudou status para {novo_status}")
    return redirect(url_for('index'))

@app.route('/cancelar/<id>')
@login_required
def cancelar(id):
    supabase.table("agendamentos").update({"status": "Cancelado"}).eq("id", id).execute()
    registrar_log(id, "Cancelou OS")
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)