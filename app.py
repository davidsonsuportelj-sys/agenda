import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from supabase import create_client
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

app = Flask(__name__)
app.secret_key = 'uma_chave_muito_secreta' # Troque por algo aleatório e seguro

# Configuração do Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configuração do Supabase
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# Classe de Usuário para o Flask-Login
class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# --- ROTAS ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Exemplo simples: você pode mudar para verificar no Supabase
        if username == 'admin' and password == 'admin123':
            user = User(1)
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha inválidos!')
            
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
        print(f"Erro ao buscar dados: {e}")
        agenda = []
    
    return render_template('index.html', agenda=agenda)

@app.route('/agendar', methods=['POST'])
def agendar():
    nome = request.form['nome']
    servico = request.form['servico']
    horario = request.form['horario']
    
    supabase.table("agendamentos").insert({
        "cliente": nome, 
        "servico": servico, 
        "horario": horario
    }).execute()
    
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)