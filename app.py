import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from supabase import create_client
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chave_secreta_padrao")

# Configuração do Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configuração do Supabase
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_in = request.form.get('username')
        pass_in = request.form.get('password')
        try:
            response = supabase.table("usuarios").select("username, password").execute()
            for u in response.data:
                if u['username'].strip() == user_in.strip() and u['password'].strip() == pass_in.strip():
                    login_user(User(user_in))
                    return redirect(url_for('index'))
            flash('Usuário ou senha inválidos!')
        except Exception as e:
            print(f"Erro no login: {e}")
            flash('Erro de conexão!')
    return render_template('login.html')

@app.route('/')
@login_required
def index():
    try:
        response = supabase.table("agendamentos").select("*").execute()
        return render_template('index.html', agenda=response.data)
    except Exception as e:
        print(f"Erro ao carregar index: {e}")
        return render_template('index.html', agenda=[])

@app.route('/agendar', methods=['POST'])
@login_required
def agendar():
    try:
        # Tenta inserir no Supabase
        supabase.table("agendamentos").insert({
            "cliente": request.form.get('nome'), 
            "servico": request.form.get('servico'), 
            "horario": request.form.get('horario'),
            "status": "Pendente"
        }).execute()
        flash("Agendamento realizado!")
    except Exception as e:
        # Se falhar, printamos o erro nos logs do Render para você ver
        print(f"ERRO AO AGENDAR NO SUPABASE: {e}")
        flash("Erro ao salvar no banco. Verifique as permissões (RLS).")
    return redirect(url_for('index'))

@app.route('/excluir/<int:id>')
@login_required
def excluir(id):
    supabase.table("agendamentos").delete().eq("id", id).execute()
    return redirect(url_for('index'))

@app.route('/mudar_status/<int:id>/<novo_status>')
@login_required
def mudar_status(id, novo_status):
    supabase.table("agendamentos").update({"status": novo_status}).eq("id", id).execute()
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)