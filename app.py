from flask import Flask, render_template, request, redirect
from supabase import create_client
import os

app = Flask(__name__)

# --- CONFIGURAÇÃO DO SUPABASE ---
# Cole aqui sua URL e sua Chave (mantendo as aspas)
url = "https://oeqqjyhgtrfexbsaufuo.supabase.co/rest/v1/"
key = "sb_publishable_WV3acm1S8cRtgdzeSLGjKQ_GJA58uZr"

# Inicializa o cliente do Supabase
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
    # O host 0.0.0.0 é obrigatório para o Render acessar seu app
    app.run(host='0.0.0.0', port=5000)