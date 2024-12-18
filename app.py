from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import func
from datetime import datetime
import pytz
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from waitress import serve  # Importação do waitress
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'

app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:Mika%40102030@172.16.49.68:5432/postgres"



app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicialização do SQLAlchemy e Migrate
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Modelo de usuário para o banco de dados
class Usuario(db.Model):
    __tablename__ = 'usuario'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    grupo = db.Column(db.String(20), nullable=False, default='analista')
    matricula = db.Column(db.String(100), unique=True, nullable=True)  # Novo campo de matrícula
    monitorias = db.relationship('Monitoria', backref='usuario', lazy=True)


# Modelo de monitoria para o banco de dados
class Monitoria(db.Model):
    __tablename__ = 'monitoria'

    id = db.Column(db.Integer, primary_key=True)
    link_incluso = db.Column(db.String(255), nullable=True)
    nome_analista = db.Column(db.String(100), nullable=False)
    nome_administrador = db.Column(db.String(100))  # Novo campo para o nome do administrador
    nome_monitor = db.Column(db.String(100), nullable=False)  # Novo campo para o nome do monitor
    matricula = db.Column(db.String(100), nullable=False)
    id_atendimento = db.Column(db.String(100), nullable=False)
    nota = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    descritivo = db.Column(db.Text, nullable=True)
    arquivo_pdf = db.Column(db.String(200), nullable=True)
    gravacao = db.Column(db.String(200), nullable=True)
    penalidades = db.Column(db.Text, nullable=True)
    data_monitoria = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    assinatura = db.Column(db.String(100))  # Adiciona a coluna assinatura
    data_assinatura = db.Column(db.DateTime)  # Adiciona a coluna para data da assinatura
    # Adicionando as pontuações específicas para cada item de monitoria
    se_apresentou = db.Column(db.Integer, nullable=True)  # 15 pontos
    atendeu_prontidao = db.Column(db.Integer, nullable=True)  # 25 pontos
    ouviu_demanda = db.Column(db.Integer, nullable=True)  # 20 pontos
    demonstrou_empatia = db.Column(db.Integer, nullable=True)  # 25 pontos
    realizou_sondagem = db.Column(db.Integer, nullable=True)  # 15 pontos

    # Itens críticos que, se houver erro, anulam a nota
    argumentou_cancelamento = db.Column(db.Integer, nullable=True)
    respeitou_cliente = db.Column(db.Integer, nullable=True)
    confirmacao_cadastral = db.Column(db.Integer, nullable=True)
    contornou_odc = db.Column(db.Integer, nullable=True)
    seguiu_procedimentos = db.Column(db.Integer, nullable=True)



 # Defina o caminho absoluto da pasta de upload (alterado conforme seu sistema)
UPLOAD_FOLDER = r'C:\Users\User\Desktop\Quality Monitory\upload'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Cria a pasta se não existir
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Rota inicial
@app.route('/')
def index():
    return render_template('index.html')

# Rota do dashboard
@app.route('/dashboard')
def dashboard():
    if 'usuario' in session:
        nome_usuario = session['usuario']
        hora_atual = datetime.now().hour
        saudacao = "Ótimo dia" if hora_atual < 12 else "Ótima tarde"

        # Verifica o grupo do usuário e filtra as monitorias
        if session.get('grupo') == 'analista':
            # Para analistas, exibe apenas as monitorias associadas à sua matrícula
            monitorias = Monitoria.query.filter_by(matricula=session['matricula']).all()
        else:
            # Para administradores, exibe todas as monitorias
            monitorias = Monitoria.query.all()

        # Renderiza o dashboard com as monitorias filtradas
        return render_template('dashboard.html', nome_usuario=nome_usuario, saudacao=saudacao, monitorias=monitorias)
    
    # Se o usuário não estiver logado, redireciona para a página de login
    return redirect(url_for('index'))



# Rota para login
@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    usuario = Usuario.query.filter_by(email=email).first()

    if usuario and usuario.senha == password:  # Compara a senha diretamente
        session['usuario'] = usuario.nome
        session['usuario_id'] = usuario.id
        session['grupo'] = usuario.grupo
        session['matricula'] = usuario.matricula  # Adiciona matrícula à sessão
        return redirect(url_for('dashboard'))
    
    erro = "E-mail ou senha inválidos. Tente novamente."
    return render_template('index.html', erro=erro)

# Rota para logout
@app.route('/logout')
def logout():
    # Remove as chaves de sessão
    session.pop('usuario', None)
    session.pop('usuario_id', None)
    session.pop('grupo', None)
    
    # Redireciona para a página de login
    return redirect(url_for('index'))



# Rota para o formulário de monitoria


@app.route('/monitoria', methods=['GET', 'POST'])
def monitoria_form():
    nome_administrador = session.get('nome_administrador', 'Administrador')  # Garantir valor padrão
    nome_monitor = request.form.get('nome_monitor', 'Nome Padrão')  # Valor padrão, caso o campo não seja preenchido

    if request.method == 'POST':
        # Obter os links fornecidos pelo administrador
        arquivo_pdf_link = request.form.get('arquivo_pdf')
        gravacao_link = request.form.get('gravacao')
        link_incluso = request.form.get('link_incluso')  # Obtenha o campo link_incluso do formulário

        total_points = 100
        penalties = {
            'se_apresentou': 15,
            'atendeu_prontidao': 25,
            'ouviu_demanda': 20,
            'demonstrou_empatia': 25,
            'realizou_sondagem': 15
        }

        nome_analista = request.form.get('nome_analista')
        matricula = request.form.get('matricula')
        id_atendimento = request.form.get('id_atendimento')
        descritivo = request.form.get('descritivo')

        penalidades_aplicadas = []

        # Adicionar variáveis de pontuação diretamente para os itens de avaliação
        item_pontuacao = {
            'se_apresentou': 15,
            'atendeu_prontidao': 25,
            'ouviu_demanda': 20,
            'demonstrou_empatia': 25,
            'realizou_sondagem': 15,
            'argumentou_cancelamento': 10,
            'respeitou_cliente': 10,
            'confirmacao_cadastral': 5,
            'contornou_odc': 5,
            'seguiu_procedimentos': 5
        }

        # Cálculo de penalidades
        for question, penalty in penalties.items():
            if request.form.get(question) == 'Não':
                total_points -= penalty
                penalidades_aplicadas.append(question)

        # Verificando os campos de penalidades adicionais
        additional_penalties = [
            'argumentou_cancelamento',
            'respeitou_cliente',
            'confirmacao_cadastral',
            'contornou_odc',
            'seguiu_procedimentos'
        ]
        for penalty in additional_penalties:
            if request.form.get(penalty) == 'Não':
                total_points = 0  # Se qualquer um desses for 'Não', a nota é zerada
                penalidades_aplicadas.append(penalty)
                break

        total_points = max(total_points, 0)

        # Inicializando a nova monitoria com as variáveis gerais
        nova_monitoria = Monitoria(
            nome_analista=nome_analista,
            matricula=matricula,
            id_atendimento=id_atendimento,
            nota=total_points,
            status='pendente',
            descritivo=descritivo,
            link_incluso=link_incluso,  # Salve o valor do link_incluso no banco de dados
            penalidades=', '.join(penalidades_aplicadas),
            data_monitoria=datetime.now(),
            usuario_id=session['usuario_id'],
            nome_administrador=nome_administrador,  # Use o nome do administrador da variável
            nome_monitor=nome_monitor  # Definindo o valor de nome_monitor com valor padrão, se necessário
        ) 

        # Atribuindo as pontuações diretamente aos campos da monitoria
        for item, pontos in item_pontuacao.items():
            if request.form.get(item) == 'Sim':  # Se marcado 'Sim', atribui a pontuação
                setattr(nova_monitoria, item, pontos)
            else:
                setattr(nova_monitoria, item, 0)  # Se não for marcado 'Sim', atribui 0

        db.session.add(nova_monitoria)
        db.session.commit()
        flash('Monitoria criada com sucesso!', 'success')
        return redirect(url_for('monitoria_sucesso'))
    
    return render_template('monitoria_form.html', nome_monitor=request.form.get('nome_monitor', 'Valor Padrão'))


# Rota de sucesso após submeter monitoria
@app.route('/monitoria_sucesso', methods=['GET'])
def monitoria_sucesso():
    return render_template('monitoria_sucesso.html')

# Rota para feedback aplicado com sucesso
@app.route('/feedback_sucesso')
def feedback_sucesso():
    return render_template('feedback_sucesso.html')

# Rota para exibir feedbacks
@app.route('/feedback_form')
def feedback_form():
    if session.get('grupo') == 'analista':
        usuario_atual = Usuario.query.get(session['usuario_id'])
        monitorias = Monitoria.query.filter_by(matricula=usuario_atual.matricula).all()
    else:
        monitorias = Monitoria.query.all()
    return render_template('feedback_form.html', monitorias=monitorias)

# Rota para aplicar feedback

@app.route('/aplicar_feedback/<int:index>', methods=['GET', 'POST'])
def aplicar_feedback(index):
    # Obtém a monitoria do banco de dados
    monitoria = Monitoria.query.get_or_404(index)
    
    if request.method == 'POST':
        # Obtém a assinatura (matrícula) do analista monitorado
        assinatura = request.form.get('assinatura')
        
        # Valida a assinatura, deve ser igual à matrícula do analista monitorado
        if assinatura != monitoria.matricula:
            flash('A assinatura deve ser a matrícula do analista monitorado.', 'error')
            # Se a assinatura for inválida, renderiza novamente a página de feedback
            return render_template('aplicar_feedback.html', monitoria=monitoria, arquivo_pdf=monitoria.arquivo_pdf, gravacao=monitoria.gravacao)
        
        # Se a assinatura for válida, registra a assinatura e altera o status da monitoria
        monitoria.assinatura = assinatura
        monitoria.data_assinatura = datetime.now()  # Armazena a data/hora da assinatura
        monitoria.status = 'aplicada'  # Atualiza o status para 'aplicada'
        
        # Comita as mudanças no banco de dados
        db.session.commit()
        
        flash('Feedback aplicado com sucesso!', 'success')
        return redirect(url_for('feedback_sucesso'))  # Redireciona para página de sucesso após aplicar o feedback
    
    return render_template('aplicar_feedback.html', monitoria=monitoria, arquivo_pdf=monitoria.arquivo_pdf, gravacao=monitoria.gravacao)


# Rota para visualizar usuários
@app.route('/usuarios')
def listar_usuarios():
    usuarios = Usuario.query.all()
    return render_template('listar_usuarios.html', usuarios=usuarios)

# Rota para visualizar monitorias
@app.route('/monitorias')
def listar_monitorias():
    if session.get('grupo') == 'analista':
        # Exibe apenas monitorias associadas ao analista logado
        monitorias = Monitoria.query.filter_by(matricula=session['matricula']).all()
    else:
        monitorias = Monitoria.query.all()
    return render_template('listar_monitorias.html', monitorias=monitorias)


# Rota para visualizar detalhes de uma monitoria
@app.route('/monitoria/<int:id>')
def visualizar_monitoria(id):
    monitoria = Monitoria.query.get_or_404(id)
    
    # Se o nome do administrador já estiver diretamente na tabela Monitoria
    nome_administrador = monitoria.nome_administrador  # Ajuste conforme necessário
    
    return render_template('visualizar_monitoria.html', monitoria=monitoria, nome_administrador=nome_administrador)



# Rota para pesquisar monitorias
@app.route('/pesquisar_monitoria', methods=['POST'])
def pesquisar_monitoria():
    termo = request.form['termo']
    monitorias = Monitoria.query.filter(Monitoria.descritivo.contains(termo)).all()
    return render_template('listar_monitorias.html', monitorias=monitorias)

# Rota para editar uma monitoria
@app.route('/editar_monitoria/<int:id>', methods=['GET', 'POST'])
def editar_monitoria(id):
    monitoria = Monitoria.query.get_or_404(id)
    if request.method == 'POST':
        # Atualizar monitoria com os dados do formulário
        monitoria.nome_analista = request.form['nome_analista']
        monitoria.matricula = request.form['matricula']
        monitoria.id_atendimento = request.form['id_atendimento']
        monitoria.descritivo = request.form['descritivo']
        
        # Verifica se novos arquivos foram enviados
        if 'arquivo_pdf' in request.files:
            arquivo_pdf = request.files['arquivo_pdf']
            if arquivo_pdf.filename:
                arquivo_pdf.save(os.path.join(UPLOAD_FOLDER, arquivo_pdf.filename))
                monitoria.arquivo_pdf = arquivo_pdf.filename
        
        if 'gravacao' in request.files:
            gravacao = request.files['gravacao']
            if gravacao.filename:
                gravacao.save(os.path.join(UPLOAD_FOLDER, gravacao.filename))
                monitoria.gravacao = gravacao.filename
        
        db.session.commit()
        flash('Monitoria editada com sucesso!', 'success')
        return redirect(url_for('listar_monitorias'))

    return render_template('editar_monitoria.html', monitoria=monitoria)


# Rota para excluir uma monitoria
@app.route('/deletar_monitoria/<int:id>', methods=['POST'])
def deletar_monitoria(id):
    monitoria = Monitoria.query.get_or_404(id)
    db.session.delete(monitoria)
    db.session.commit()
    flash('Monitoria excluída com sucesso!', 'success')
    return redirect(url_for('listar_monitorias'))

# Rota para excluir um usuário
@app.route('/deletar_usuario/<int:id>', methods=['POST'])
def deletar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    flash('Usuário excluído com sucesso!', 'success')
    return redirect(url_for('listar_usuarios'))

# Rota para editar um usuário
@app.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
def editar_usuario(id):
    usuario = Usuario.query.get(id)

    if request.method == 'POST':
        usuario.nome = request.form['nome']
        usuario.matricula = request.form['matricula']
        usuario.email = request.form['email']
        senha = request.form['senha']
        if senha:
            usuario.senha = generate_password_hash(senha)
        usuario.grupo = request.form['grupo']

        db.session.commit()
        flash('Usuário editado com sucesso!', 'success')
        return redirect(url_for('registrar_usuario'))  # Use o nome correto aqui

    return render_template('editar_usuario.html', usuario=usuario)

# Rota Relatório
@app.route('/relatorio_analista', methods=['GET', 'POST'])
def relatorio_analista():
    analistas = Monitoria.query.with_entities(Monitoria.nome_analista).distinct()
    monitorias = []
    mensagem_erro = None
    media_consolidada = 0
    pontuacao_media_itens = {}
    pontuacao_ideal = {}
    pontuacao_por_item = {}

    fuso_horario_local = pytz.timezone('America/Sao_Paulo')

    if request.method == 'POST':
        analista_nome = request.form.get('analista')
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')

        query = Monitoria.query
        if analista_nome:
            query = query.filter(Monitoria.nome_analista == analista_nome)

        if data_inicio:
            try:
                data_inicio_formatada = datetime.strptime(data_inicio, '%Y-%m-%d')
                query = query.filter(Monitoria.data_monitoria >= data_inicio_formatada)
            except ValueError:
                mensagem_erro = "Data de início inválida."

        if data_fim:
            try:
                data_fim_formatada = datetime.strptime(data_fim, '%Y-%m-%d')
                query = query.filter(Monitoria.data_monitoria <= data_fim_formatada)
            except ValueError:
                mensagem_erro = "Data de fim inválida."

        try:
            monitorias = query.all()

            # Ajustar as datas para o fuso horário local
            for monitoria in monitorias:
                monitoria.data_monitoria = monitoria.data_monitoria.astimezone(fuso_horario_local)
                if monitoria.data_assinatura:
                    monitoria.data_assinatura = monitoria.data_assinatura.astimezone(fuso_horario_local)

        except Exception as e:
            mensagem_erro = f"Ocorreu um erro ao buscar monitorias: {str(e)}"

    if monitorias:
        total_notas = sum(monitoria.nota for monitoria in monitorias)
        total_monitorias = len(monitorias)

        pontuacao_itens_totais = { 
            'se_apresentou': 0,
            'atendeu_prontidao': 0,
            'ouviu_demanda': 0,
            'demonstrou_empatia': 0,
            'realizou_sondagem': 0,
            'argumentou_cancelamento': 0,
            'respeitou_cliente': 0,
            'confirmacao_cadastral': 0,
            'contornou_odc': 0,
            'seguiu_procedimentos': 0,
        }

        pontuacao_por_item = {
            'se_apresentou': 15,
            'atendeu_prontidao': 25,
            'ouviu_demanda': 20,
            'demonstrou_empatia': 25,
            'realizou_sondagem': 15,
            'argumentou_cancelamento': 10,
            'respeitou_cliente': 10,
            'confirmacao_cadastral': 5,
            'contornou_odc': 5,
            'seguiu_procedimentos': 5
        }

        for monitoria in monitorias:
            for item in pontuacao_itens_totais:
                valor_item = getattr(monitoria, item, None)
                if valor_item:
                    pontuacao_itens_totais[item] += pontuacao_por_item[item]

        media_consolidada = total_notas / total_monitorias if total_monitorias > 0 else 0

        pontuacao_media_itens = {
            item: (valor / total_monitorias) if total_monitorias > 0 else 0
            for item, valor in pontuacao_itens_totais.items()
        }

        pontuacao_ideal = {
            item: pontuacao_por_item[item] * total_monitorias
            for item in pontuacao_por_item
        }

    return render_template(
        'relatorio_analista.html',
        analistas=analistas,
        monitorias=monitorias,
        media_consolidada=media_consolidada,
        pontuacao_media_itens=pontuacao_media_itens,
        pontuacao_ideal=pontuacao_ideal,
        pontuacao_por_item=pontuacao_por_item,
        mensagem_erro=mensagem_erro,
        itens=pontuacao_por_item.keys()  # Passando as chaves como lista de itens
    )


# Rota para registrar um novo usuário
@app.route('/registrar_usuario', methods=['GET', 'POST'])
def registrar_usuario():
    if request.method == 'POST':
        email = request.form['email']
        senha = generate_password_hash(request.form['senha'])
        nome = request.form['nome']
        grupo = request.form['grupo']
        matricula = request.form['matricula']  # Recebe a matrícula do formulário

        novo_usuario = Usuario(email=email, senha=senha, nome=nome, grupo=grupo, matricula=matricula)
        db.session.add(novo_usuario)
        db.session.commit()
        flash('Usuário criado com sucesso!', 'success')

        # Após salvar, redireciona para a mesma página e inclui a lista de usuários
        usuarios = Usuario.query.all()  # Busca todos os usuários cadastrados
        return render_template('registrar_usuario.html', usuarios=usuarios)

    # Caso a requisição seja GET, retorna a lista de usuários
    usuarios = Usuario.query.all()  # Busca todos os usuários cadastrados
    return render_template('registrar_usuario.html', usuarios=usuarios)

@app.route('/download/<filename>')
def download_file(filename):
    try:
        # Verifica se o arquivo existe no diretório UPLOAD_FOLDER
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.isfile(file_path):
            abort(404)  # Retorna erro 404 se o arquivo não for encontrado

        # Envia o arquivo como anexo, com o tipo MIME correto
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except Exception as e:
        # Exibe o erro, se necessário
        print(f"Erro ao tentar baixar o arquivo: {e}")
        abort(500)  # Retorna erro 500 para falhas inesperadas

    # Define o tipo MIME com base na extensão do arquivo
    if filename.lower().endswith('.pdf'):
        mimetype = 'application/pdf'
    elif filename.lower().endswith('.mp4'):
        mimetype = 'video/mp4'
    else:
        mimetype = 'application/octet-stream'  # Tipo genérico para outros arquivos

    return send_from_directory(directory, filename, as_attachment=True, mimetype=mimetype)


if __name__ == "__main__":
    serve(app, host='0.0.0.0', port=8080)  # Usando waitress 