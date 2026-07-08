import os
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from supabase import create_client
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

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

def get_os_ou_none(os_id):
    """Busca uma OS pelo id. Retorna None se não existir."""
    try:
        response = supabase.table("agendamentos").select("*").eq("id", os_id).single().execute()
        return response.data
    except Exception:
        return None

def usuario_pode_gerenciar(item, incluir_tecnico=True):
    """Regras de autorização para ações sobre uma OS:
    - admin: sempre pode
    - vendedor: só na OS que ele mesmo criou/vendeu
    - tecnico: só na OS em que ele é o técnico designado (quando incluir_tecnico=True)
    """
    if current_user.role == 'admin':
        return True
    if current_user.role == 'vendedor' and item.get('vendedor') == current_user.id:
        return True
    if incluir_tecnico and current_user.role == 'tecnico' and item.get('tecnico') == current_user.id:
        return True
    return False

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

        try:
            response = supabase.table("usuarios").select("*").eq("username", user_in).single().execute()
            user_data = response.data
        except Exception:
            user_data = None

        if user_data:
            senha_armazenada = user_data.get('password', '')
            senha_valida = False

            if senha_armazenada.startswith(('pbkdf2:', 'scrypt:')):
                # Senha já está no formato hash (fluxo normal)
                senha_valida = check_password_hash(senha_armazenada, pass_in)
            elif senha_armazenada == pass_in:
                # Senha legada em texto puro: valida e migra para hash automaticamente
                senha_valida = True
                novo_hash = generate_password_hash(pass_in)
                supabase.table("usuarios").update({"password": novo_hash}).eq("username", user_in).execute()

            if senha_valida:
                login_user(User(user_data['username'], user_data['role']))
                return redirect(url_for('index'))

        flash("Usuário ou senha inválidos.")
    return render_template('login.html')

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    # CORREÇÃO AQUI: Agora incluímos o relacionamento com a tabela clientes
    # O Supabase retornará o objeto de clientes dentro de cada item de agendamento
    query = supabase.table("agendamentos").select("*, clientes(nome)")
 
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
        
        # Certifique-se de que cliente_id seja enviado como inteiro (int)
        res = supabase.table("agendamentos").insert({
            "cliente": int(request.form.get('cliente_id')), 
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
    item = get_os_ou_none(id)
    if not item or not usuario_pode_gerenciar(item):
        flash("Você não tem permissão para reagendar esta OS.")
        return redirect(url_for('index'))

    nova_data = request.form.get('nova_data')
    if nova_data:
        supabase.table("agendamentos").update({"horario": nova_data, "status": "Reagendado"}).eq("id", id).execute()
        registrar_log(id, f"Reagendou para {nova_data}")
    return redirect(url_for('index'))

@app.route('/mudar_status/<id>/<novo_status>')
@login_required
def mudar_status(id, novo_status):
    item = get_os_ou_none(id)
    if not item or not usuario_pode_gerenciar(item):
        flash("Você não tem permissão para alterar o status desta OS.")
        return redirect(url_for('index'))

    supabase.table("agendamentos").update({"status": novo_status}).eq("id", id).execute()
    registrar_log(id, f"Mudou status para {novo_status}")
    return redirect(url_for('index'))

@app.route('/cancelar/<id>')
@login_required
def cancelar(id):
    item = get_os_ou_none(id)
    # Técnico não pode cancelar, apenas finalizar/reagendar suas próprias OS
    if not item or not usuario_pode_gerenciar(item, incluir_tecnico=False):
        flash("Você não tem permissão para cancelar esta OS.")
        return redirect(url_for('index'))

    supabase.table("agendamentos").update({"status": "Cancelado"}).eq("id", id).execute()
    registrar_log(id, "Cancelou OS")
    return redirect(url_for('index'))

@app.route('/logs')
@login_required
def logs():
    if current_user.role != 'admin':
        flash("Apenas administradores podem acessar o histórico de logs.")
        return redirect(url_for('index'))
    logs = supabase.table("logs_os").select("*").order("data", desc=True).execute().data
    return render_template('logs.html', logs=logs)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)