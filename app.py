import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chave_padrao_segura")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configuração do Supabase com tratamento de erro básico
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Variáveis de ambiente SUPABASE_URL ou SUPABASE_KEY não foram encontradas!")

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
        username_input = request.form.get('username')
        password_input = request.form.get('password')
        
        try:
            response = supabase.table("usuarios").select("*").eq("username", username_input).eq("password", password_input).execute()
            if response.data:
                user = User(username_input)
                login_user(user)
                return redirect(url_for('index'))
            else:
                flash('Usuário ou senha inválidos!')
        except Exception as e:
            flash(f'Erro de conexão com o banco: {str(e)}')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    try:
        response = supabase.table("agendamentos").select("*").execute()
        agenda = response.data
    except Exception as e:
        print(f"Erro ao buscar agendamentos: {e}")
        agenda = []
    return render_template('index.html', agenda=agenda)

@app.route('/agendar', methods=['POST'])
@login_required
def agendar():
    try:
        supabase.table("agendamentos").insert({
            "cliente": request.form.get('nome'), 
            "servico": request.form.get('servico'), 
            "horario": request.form.get('horario')
        }).execute()
    except Exception as e:
        print(f"Erro ao agendar: {e}")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)