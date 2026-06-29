from flask import Flask, render_template, request, redirect
from supabase import create_client
import os

app = Flask(__name__)

# Substitua pelas suas credenciais reais
url = "https://oeqqjyhgtrfexbsaufuo.supabase.co/rest/v1/"
key = "sb_publishable_WV3acm1S8cRtgdzeSLGjKQ_GJA58uZr"
supabase = create_client(url, key)

@app.route('/')
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
    horario = request.form['horario']
    supabase.table("agendamentos").insert({"cliente": nome, "horario": horario}).execute()
    return redirect('/')

if __name__ == '__main__':
    app.run()