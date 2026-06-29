import os
from flask import Flask, render_template, request, redirect
from supabase import create_client
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

app = Flask(__name__)

# --- CONFIGURAÇÃO SEGURA DO SUPABASE ---
# O sistema buscará as chaves do arquivo .env localmente
# ou das Variáveis de Ambiente configuradas no Render
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)

@app.route('/')
def index():
    try:
        # Busca todos os agendamentos da tabela 'agendamentos'
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
    
    # Insere no Supabase
    supabase.table("agendamentos").insert({
        "cliente": nome, 
        "servico": servico, 
        "horario": horario
    }).execute()
    
    return redirect('/')

if __name__ == '__main__':
    # Host e porta para rodar no Render
    app.run(host='0.0.0.0', port=5000)