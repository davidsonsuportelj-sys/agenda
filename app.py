import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "uma_chave_muito_segura_para_sessao")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

url = "https://oeqqjyhgtrfexbsaufuo.supabase.co"
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
        username_input = request.form.get('username').strip() # .strip() remove espaços extras
        password_input = request.form.get('password').strip()
        
        try:
            # Buscamos APENAS pelo usuário
            response = supabase.table("usuarios").select("*").eq("username", username_input).execute()
            
            # Verificamos se encontramos o usuário E se a senha confere
            if response.data:
                user_db = response.data[0]
                if user_db['password'] == password_input:
                    user = User(username_input)
                    login_user(user)
                    return redirect(url_for('index'))
                else:
                    print(f"DEBUG: Senha incorreta. Esperada: '{user_db['password']}', Recebida: '{password_input}'")
            else:
                print(f"DEBUG: Usuário '{username_input}' não encontrado no banco.")
                
            flash('Usuário ou senha inválidos!')
        except Exception as e:
            print(f"DEBUG: Erro de banco: {e}")
            flash('Erro ao conectar ao banco.')
            
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
    except:
        agenda = []
    return render_template('index.html', agenda=agenda)

@app.route('/agendar', methods=['POST'])
@login_required
def agendar():
    supabase.table("agendamentos").insert({
        "cliente": request.form.get('nome'), 
        "servico": request.form.get('servico'), 
        "horario": request.form.get('horario')
    }).execute()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)