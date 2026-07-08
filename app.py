import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect
from supabase import create_client
from dotenv import load_dotenv
from werkzeug.exceptions import BadRequest
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)

# SEGURANÇA: SECRET_KEY é obrigatória para produção, sem fallback fraco.
app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError(
        "A variável de ambiente SECRET_KEY não está configurada. "
        "Defina uma chave secreta forte no arquivo .env antes de iniciar a aplicação."
    )

csrf = CSRFProtect(app)

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    raise RuntimeError(
        "As variáveis SUPABASE_URL e SUPABASE_KEY são obrigatórias."
    )

supabase = create_client(url, key)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configuração de logging estruturado para produção
logging.basicConfig(level=logging.INFO)
app_logger = logging.getLogger(__name__)


class User(UserMixin):
    def __init__(self, username, role):
        self.id = username
        self.role = role


def get_os_ou_none(os_id):
    """Busca uma OS pelo id. Retorna None se não existir."""
    try:
        response = supabase.table("agendamentos").select("*").eq("id", os_id).single().execute()
        return response.data
    except Exception:
        return None


def usuario_pode_gerenciar(item, incluir_tecnico=True):
    """Regras de autorização para ações sobre uma OS:
    - admin: sempre pode
    - vendedor: só na OS que ele mesmo criou/vendeu
    - tecnico: só na OS em que ele é o técnico designado (quando incluir_tecnico=True)
    """
    if current_user.role == 'admin':
        return True
    if current_user.role == 'vendedor' and item.get('vendedor') == current_user.id:
        return True
    if incluir_tecnico and current_user.role == 'tecnico' and item.get('tecnico') == current_user.id:
        return True
    return False


def registrar_log(os_id, acao):
    try:
        supabase.table("logs_os").insert({
            "usuario": current_user.id,
            "os_id": os_id,
            "acao": acao
        }).execute()
    except Exception as e:
        app_logger.error(f"Erro ao registrar log: {e}")


def validar_texto_simples(valor, nome_campo, obrigatorio=True, tamanho_max=255):
    """
    Valida campos de texto simples. Retorna o valor sanitizado (strip)
    ou levanta BadRequest.
    """
    valor = (valor or "").strip()

    if obrigatorio and not valor:
        raise BadRequest(f"O campo '{nome_campo}' é obrigatório.")

    if len(valor) > tamanho_max:
        raise BadRequest(f"O campo '{nome_campo}' excede o tamanho máximo de {tamanho_max} caracteres.")

    return valor


def validar_cliente_id(cliente_id_raw):
    """Converte e valida o id do cliente. Retorna int ou levanta BadRequest."""
    try:
        cliente_id = int(cliente_id_raw)
        if cliente_id <= 0:
            raise ValueError
        return cliente_id
    except (TypeError, ValueError):
        raise BadRequest("O campo 'cliente_id' deve ser um número positivo válido.")


def validar_prioridade(prioridade):
    """Valida se a prioridade está dentro das opções permitidas."""
    opcoes_validas = {'Baixa', 'Média', 'Alta'}
    return prioridade if prioridade in opcoes_validas else 'Média'


def cliente_nome_por_id(cliente_id):
    """Busca o nome do cliente pelo id. Retorna None se não encontrado."""
    try:
        response = supabase.table("clientes").select("nome").eq("id", cliente_id).single().execute()
        if response.data and response.data.get("nome"):
            return response.data["nome"]
    except Exception:
        pass
    return None


# FILTRO CUSTOMIZADO PARA FORMATAÇÃO DE DATAS NO JINJA2
@app.template_filter('formatar_data')
def formatar_data(valor):
    """Formata uma string ISO 8601 (datetime) para 'dd/mm/yyyy às HH:MM'."""
    if not valor:
        return "N/A"
    try:
        from datetime import datetime
        # Supabase geralmente retorna no formato ISO 8601 completo
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return dt.strftime('%d/%m/%Y às %H:%M')
    except (ValueError, TypeError):
        return valor


# FILTRO PARA NORMALIZAR STATUS EM CLASSES CSS
@app.template_filter('slug_status')
def slug_status(value):
    """Converte um status em um slug seguro para usar em classes CSS."""
    if not value:
        return ''
    mapa = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a',
        'é': 'e', 'ê': 'e',
        'í': 'i',
        'ó': 'o', 'ô': 'o', 'õ': 'o',
        'ú': 'u',
        'ç': 'c'
    }
    slug = ''.join(mapa.get(c.lower(), c.lower()) for c in value)
    slug = slug.replace(' ', '-').replace('_', '-')
    return slug


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

        try:
            response = supabase.table("usuarios").select("*").eq("username", user_in).single().execute()
            user_data = response.data
        except Exception:
            user_data = None

        if user_data:
            senha_armazenada = user_data.get('password', '')
            senha_valida = False

            if senha_armazenada.startswith(('pbkdf2:', 'scrypt:')):
                # Senha já está no formato hash (fluxo normal)
                senha_valida = check_password_hash(senha_armazenada, pass_in)
            elif senha_armazenada == pass_in:
                # Senha legada em texto puro: valida e migra para hash automaticamente
                senha_valida = True
                novo_hash = generate_password_hash(pass_in)
                supabase.table("usuarios").update({"password": novo_hash}).eq("username", user_in).execute()

            if senha_valida:
                login_user(User(user_data['username'], user_data['role']))
                return redirect(url_for('index'))

        flash("Usuário ou senha inválidos.", "danger")
    return render_template('login.html')


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    # CAPTURA DOS FILTROS
    busca = request.args.get('busca', '').strip()
    status = request.args.get('status', '').strip()
    tecnico_filtro = request.args.get('tecnico', '').strip()
    vendedor_filtro = request.args.get('vendedor', '').strip()
    data_inicio = request.args.get('data_inicio', '').strip()
    data_fim = request.args.get('data_fim', '').strip()

    # NOVO: parâmetros de ordenação
    ordenar_por = request.args.get('ordenar_por', 'horario').strip()
    direcao = request.args.get('direcao', 'desc').strip()

    # Whitelist de colunas permitidas para ordenação (segurança contra injeção SQL/template)
    colunas_validas = {
        'vendedor', 'tecnico', 'horario', 'servico',
        'prioridade', 'status', 'obs'
    }
    if ordenar_por not in colunas_validas:
        ordenar_por = 'horario'

    if direcao not in ['asc', 'desc']:
        direcao = 'desc'

    query = supabase.table("agendamentos").select("*, clientes(nome)")

    # FILTROS POR PERFIL (existentes)
    if current_user.role == 'tecnico':
        query = query.eq("tecnico", current_user.id)
    elif current_user.role == 'vendedor':
        query = query.eq("vendedor", current_user.id)

    # FILTRO POR STATUS
    if status:
        query = query.eq("status", status)

    # FILTRO POR TÉCNICO (disponível para admin e vendedor)
    if tecnico_filtro and current_user.role in ['admin', 'vendedor']:
        query = query.eq("tecnico", tecnico_filtro)

    # FILTRO POR VENDEDOR (disponível apenas para admin)
    if vendedor_filtro and current_user.role == 'admin':
        query = query.eq("vendedor", vendedor_filtro)

    # FILTRO POR PERÍODO
    if data_inicio:
        query = query.gte("horario", data_inicio)

    if data_fim:
        # Inclui o dia inteiro (até 23:59:59)
        if len(data_fim) == 10:
            data_fim_completo = data_fim + "T23:59:59"
        else:
            data_fim_completo = data_fim
        query = query.lte("horario", data_fim_completo)

    # NOVO: aplica ordenação dinâmica
    agenda = query.order(ordenar_por, desc=(direcao == 'desc')).order("id", desc=True).execute().data

    # BUSCA POR NOME DO CLIENTE (filtra em memória após enriquecimento)
    if busca:
        termo = busca.lower()
        agenda_filtrada = []
        for item in agenda:
            # Tenta buscar o nome no relacionamento
            nome_relacionamento = ''
            if item.get('clientes') and item['clientes'].get('nome'):
                nome_relacionamento = item['clientes']['nome']

            # Tenta buscar por id do cliente
            nome_cache = ''
            if item.get('cliente'):
                nome_cache = cliente_nome_por_id(item['cliente']) or ''

            if termo in (nome_relacionamento.lower() or '') or termo in (nome_cache.lower() or ''):
                # Garante que o nome do cliente seja preenchido se encontrado por cache
                if not item.get('clientes'):
                    item['clientes'] = {}
                item['clientes']['nome'] = nome_relacionamento or nome_cache
                agenda_filtrada.append(item)
        agenda = agenda_filtrada
    else:
        # Enriquece os itens da agenda com o nome do cliente caso o relacionamento falhe
        for item in agenda:
            if (not item.get('clientes') or not item['clientes'].get('nome')) and item.get('cliente'):
                nome_cliente = cliente_nome_por_id(item['cliente'])
                if nome_cliente:
                    item['clientes'] = {'nome': nome_cliente}

    clientes = supabase.table("clientes").select("*").execute().data
    tecnicos = supabase.table("usuarios").select("username").eq("role", "tecnico").execute().data
    vendedores = supabase.table("usuarios").select("username").eq("role", "vendedor").execute().data

    filtros = {
        'busca': busca,
        'status': status,
        'tecnico': tecnico_filtro,
        'vendedor': vendedor_filtro,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        # NOVO
        'ordenar_por': ordenar_por,
        'direcao': direcao
    }

    return render_template(
        'index.html',
        agenda=agenda,
        clientes=clientes,
        tecnicos=tecnicos,
        vendedores=vendedores,
        role=current_user.role,
        user=current_user,
        filtros=filtros
    )


@app.route('/cadastrar_cliente', methods=['POST'])
@login_required
def cadastrar_cliente():
    if current_user.role not in ['admin', 'vendedor']:
        flash("Você não tem permissão para cadastrar clientes.", "danger")
        return redirect(url_for('index'))

    try:
        nome = validar_texto_simples(request.form.get('nome'), "Nome", obrigatorio=True, tamanho_max=200)
        telefone = validar_texto_simples(request.form.get('telefone'), "Telefone", obrigatorio=False, tamanho_max=30)
        endereco = validar_texto_simples(request.form.get('endereco'), "Endereço", obrigatorio=False, tamanho_max=255)

        supabase.table("clientes").insert({
            "nome": nome,
            "telefone": telefone,
            "endereco": endereco
        }).execute()

        flash("Cliente cadastrado com sucesso!", "success")

    except BadRequest as e:
        flash(str(e), "danger")
    except Exception as e:
        app_logger.error(f"Erro ao cadastrar cliente: {e}")
        flash("Ocorreu um erro ao cadastrar o cliente. Tente novamente.", "danger")

    return redirect(url_for('index'))


@app.route('/agendar', methods=['POST'])
@login_required
def agendar():
    if current_user.role not in ['admin', 'vendedor']:
        flash("Você não tem permissão para agendar ordens de serviço.", "danger")
        return redirect(url_for('index'))

    try:
        cliente_id = validar_cliente_id(request.form.get('cliente_id'))
        servico = validar_texto_simples(request.form.get('servico'), "Serviço", obrigatorio=True, tamanho_max=200)
        horario = validar_texto_simples(request.form.get('horario'), "Data/Hora", obrigatorio=True, tamanho_max=30)
        prioridade = validar_prioridade(request.form.get('prioridade'))
        obs = validar_texto_simples(request.form.get('obs'), "Observação", obrigatorio=False, tamanho_max=500)
        tecnico = request.form.get('tecnico')

        if not tecnico:
            raise BadRequest("O campo 'Técnico' é obrigatório.")

        vendedor_selecionado = request.form.get('vendedor') if current_user.role == 'admin' else current_user.id

        if current_user.role == 'admin':
            if not vendedor_selecionado:
                raise BadRequest("O campo 'Vendedor' é obrigatório para administradores.")

        res = supabase.table("agendamentos").insert({
            "cliente": cliente_id,
            "servico": servico,
            "horario": horario,
            "tecnico": tecnico,
            "prioridade": prioridade,
            "obs": obs,
            "vendedor": vendedor_selecionado,
            "status": "Pendente"
        }).execute()

        if res.data:
            registrar_log(res.data[0]['id'], "Criou nova OS")

        flash("Ordem de serviço agendada com sucesso!", "success")

    except BadRequest as e:
        flash(str(e), "danger")
    except Exception as e:
        app_logger.error(f"Erro ao agendar OS: {e}")
        flash("Ocorreu um erro ao agendar a ordem de serviço.", "danger")

    return redirect(url_for('index'))


@app.route('/reagendar/<id>', methods=['POST'])
@login_required
def reagendar(id):
    item = get_os_ou_none(id)
    if not item or not usuario_pode_gerenciar(item):
        flash("Você não tem permissão para reagendar esta OS.", "danger")
        return redirect(url_for('index'))

    try:
        nova_data = validar_texto_simples(request.form.get('nova_data'), "Nova Data/Hora", obrigatorio=True, tamanho_max=30)

        supabase.table("agendamentos").update({"horario": nova_data, "status": "Reagendado"}).eq("id", id).execute()
        registrar_log(id, f"Reagendou para {nova_data}")
        flash("OS reagendada com sucesso!", "success")

    except BadRequest as e:
        flash(str(e), "danger")
    except Exception as e:
        app_logger.error(f"Erro ao reagendar OS {id}: {e}")
        flash("Ocorreu um erro ao reagendar a OS.", "danger")

    return redirect(url_for('index'))


@app.route('/mudar_status/<id>/<novo_status>')
@login_required
def mudar_status(id, novo_status):
    # Validação básica do status recebido via URL
    status_permitidos = {'Pendente', 'Em andamento', 'Concluído', 'Reagendado', 'Cancelado'}
    if novo_status not in status_permitidos:
        flash("Status informado não é válido.", "danger")
        return redirect(url_for('index'))

    item = get_os_ou_none(id)
    if not item or not usuario_pode_gerenciar(item):
        flash("Você não tem permissão para alterar o status desta OS.", "danger")
        return redirect(url_for('index'))

    try:
        supabase.table("agendamentos").update({"status": novo_status}).eq("id", id).execute()
        registrar_log(id, f"Mudou status para {novo_status}")
        flash(f"Status da OS atualizado para '{novo_status}'.", "success")
    except Exception as e:
        app_logger.error(f"Erro ao mudar status da OS {id}: {e}")
        flash("Ocorreu um erro ao atualizar o status da OS.", "danger")

    return redirect(url_for('index'))


@app.route('/cancelar/<id>')
@login_required
def cancelar(id):
    item = get_os_ou_none(id)
    # Técnico não pode cancelar, apenas finalizar/reagendar suas próprias OS
    if not item or not usuario_pode_gerenciar(item, incluir_tecnico=False):
        flash("Você não tem permissão para cancelar esta OS.", "danger")
        return redirect(url_for('index'))

    try:
        # Impede cancelar uma OS já concluída ou cancelada
        if item.get("status") in ['Concluído', 'Cancelado']:
            flash("Esta OS já está finalizada ou cancelada.", "warning")
            return redirect(url_for('index'))

        supabase.table("agendamentos").update({"status": "Cancelado"}).eq("id", id).execute()
        registrar_log(id, "Cancelou OS")
        flash("OS cancelada com sucesso!", "success")
    except Exception as e:
        app_logger.error(f"Erro ao cancelar OS {id}: {e}")
        flash("Ocorreu um erro ao cancelar a OS.", "danger")

    return redirect(url_for('index'))


@app.route('/logs')
@login_required
def logs():
    if current_user.role != 'admin':
        flash("Apenas administradores podem acessar o histórico de logs.", "danger")
        return redirect(url_for('index'))

    try:
        logs_list = supabase.table("logs_os").select("*").order("data", desc=True).execute().data
    except Exception as e:
        app_logger.error(f"Erro ao carregar logs: {e}")
        logs_list = []
        flash("Ocorreu um erro ao carregar o histórico de logs.", "danger")

    return render_template('logs.html', logs=logs_list)


@app.route('/logout')
def logout():
    logout_user()
    flash("Você saiu do sistema com segurança.", "info")
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
