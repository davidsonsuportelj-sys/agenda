import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from supabase import create_client
from dotenv import load_dotenv

# Carrega do .env (localmente ou no Render)
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Busca as configurações das variáveis de ambiente
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
            # Busca no Supabase
            response = supabase.table("usuarios").select("username, password").execute()
            
            # Verifica credenciais
            encontrado = False
            for u in response.data:
                if u['username'].strip() == user_in.strip() and u['password'].strip() == pass_in.strip():
                    encontrado = True
                    break
            
            if encontrado:
                login_user(User(user_in))
                return redirect(url_for('index'))
            else:
                flash('Usuário ou senha inválidos!')
        except Exception as e:
            print(f"Erro: {e}")
            flash('Erro ao conectar ao banco!')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', agenda=[])

@app.route('/agendar', methods=['POST'])
@login_required
def agendar():
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)