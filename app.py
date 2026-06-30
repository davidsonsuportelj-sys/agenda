import os
from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chave_secreta_padrao")

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

@app.route('/')
@login_required
def index():
    # Se for admin, vê tudo. Se for técnico, vê apenas as suas OS.
    if current_user.role == 'admin':
        agenda = supabase.table("agendamentos").select("*").order("horario").execute().data
    else:
        agenda = supabase.table("agendamentos").select("*").eq("tecnico", current_user.id).execute().data
        
    return render_template('index.html', agenda=agenda, role=current_user.role, user_id=current_user.id)

@app.route('/agendar', methods=['POST'])
@login_required
def agendar():
    if current_user.role == 'admin':
        supabase.table("agendamentos").insert({
            "cliente": request.form.get('cliente'), 
            "servico": request.form.get('servico'), 
            "horario": request.form.get('horario'),
            "tecnico": request.form.get('tecnico'),
            "status": "Pendente"
        }).execute()
    return redirect(url_for('index'))

@app.route('/mudar_status/<id>/<novo_status>')
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