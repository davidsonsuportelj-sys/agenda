from flask import Flask, render_template, request, redirect
from supabase import create_client
import os

app = Flask(__name__)

# Configurações do Supabase (use as que você encontrou no painel)
url = "SUA_URL_AQUI"
key = "SUA_API_KEY_AQUI"
supabase = create_client(url, key)

@app.route('/')
def index():
    # Busca todos os agendamentos da tabela 'agendamentos'
    response = supabase.table("agendamentos").select("*").execute()
    agenda = response.data
    return render_template('index.html', agenda=agenda)

@app.route('/agendar', methods=['POST'])
def agendar():
    nome = request.form['nome']
    horario = request.form['horario']
    
    # Insere no Supabase
    supabase.table("agendamentos").insert({"cliente": nome, "horario": horario}).execute()
    
    return redirect('/')

if __name__ == '__main__':
    app.run()