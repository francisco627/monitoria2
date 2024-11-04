from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask import send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'chave-secreta-para-sessao'

# Configuração do banco de dados SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///monitorias.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)


# Modelo de usuário para o banco de dados
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    grupo = db.Column(db.String(20), nullable=False, default='analista')
    matricula = db.Column(db.String(100), unique=True, nullable=True)  # Novo campo de matrícula
    monitorias = db.relationship('Monitoria', backref='usuario', lazy=True)

class Monitoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_analista = db.Column(db.String(100), nullable=False)
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

# Verifica se a pasta de uploads existe
UPLOAD_FOLDER = 'upload'
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

    if usuario and check_password_hash(usuario.senha, password):
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
    session.pop('usuario', None)
    session.pop('usuario_id', None)
    session.pop('grupo', None)
    return redirect(url_for('index'))

# Rota para o formulário de monitoria
@app.route('/monitoria', methods=['GET', 'POST'])
def monitoria_form():
    if request.method == 'POST':
        arquivo_pdf = request.files.get('arquivo_pdf')
        gravacao = request.files.get('gravacao')

        # Salvar arquivos se existirem na pasta 'upload'
        arquivo_pdf_path = None
        if arquivo_pdf:
            try:
                arquivo_pdf.save(os.path.join(UPLOAD_FOLDER, arquivo_pdf.filename))
                arquivo_pdf_path = arquivo_pdf.filename
            except Exception as e:
                flash(f'Erro ao salvar o arquivo PDF: {str(e)}', 'error')

        gravacao_path = None
        if gravacao:
            try:
                gravacao.save(os.path.join(UPLOAD_FOLDER, gravacao.filename))
                gravacao_path = gravacao.filename
            except Exception as e:
                flash(f'Erro ao salvar a gravação: {str(e)}', 'error')

        total_points = 100
        penalties = {
            'se_apresentou': 10,
            'atendeu_prontidao': 15,
            'ouviu_demanda': 10,
            'demonstrou_empatia': 10,
            'realizou_sondagem': 15
        }

        nome_analista = request.form.get('nome_analista')
        matricula = request.form.get('matricula')
        id_atendimento = request.form.get('id_atendimento')
        descritivo = request.form.get('descritivo')

        penalidades_aplicadas = []

        # Cálculo de penalidades
        for question, penalty in penalties.items():
            if request.form.get(question) == 'Não':
                total_points -= penalty
                penalidades_aplicadas.append(question)

        total_points = max(total_points, 0)

        # Verificações de penalidades adicionais
        additional_penalties = [
            'argumentou_cancelamento',
            'respeitou_cliente',
            'confirmacao_cadastral',
            'contornou_odc',
            'seguiu_procedimentos'
        ]
        for penalty in additional_penalties:
            if request.form.get(penalty) == 'Não':
                total_points = 0
                penalidades_aplicadas.append(penalty)

        nova_monitoria = Monitoria(
            nome_analista=nome_analista,
            matricula=matricula,
            id_atendimento=id_atendimento,
            nota=total_points,
            status='pendente',
            descritivo=descritivo,
            arquivo_pdf=arquivo_pdf_path,
            gravacao=gravacao_path,
            penalidades=', '.join(penalidades_aplicadas),
            data_monitoria=datetime.now(),
            usuario_id=session['usuario_id']
        )

        db.session.add(nova_monitoria)
        db.session.commit()
        flash('Monitoria criada com sucesso!', 'success')
        return redirect(url_for('monitoria_sucesso'))
    
    return render_template('monitoria_form.html')

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
    monitoria = Monitoria.query.get_or_404(index)  # Obtém a monitoria pelo ID
    
    if request.method == 'POST':
        assinatura = request.form.get('assinatura')  # Obtém a assinatura do formulário
        print(f"Assinatura fornecida: '{assinatura}', Matrícula monitorada: '{monitoria.matricula}'")  # Debug
        print(f"Status atual da monitoria: '{monitoria.status}'")  # Debug
        
        # Valida a assinatura
        if assinatura != monitoria.matricula:
            flash('A assinatura deve ser a matrícula do analista monitorado.', 'error')
            return render_template('aplicar_feedback.html', monitoria=monitoria, arquivo_pdf=monitoria.arquivo_pdf, gravacao=monitoria.gravacao)
        
        # Registra a assinatura e atualiza a monitoria
        monitoria.assinatura = assinatura
        monitoria.data_assinatura = datetime.now()  # Armazena a data/hora da assinatura
        monitoria.status = 'aplicada'  # Atualiza o status da monitoria
        db.session.commit()  # Salva as mudanças no banco de dados
        
        flash('Feedback aplicado com sucesso!', 'success')
        return redirect(url_for('feedback_sucesso'))  # Redireciona para a página de sucesso

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
    return render_template('visualizar_monitoria.html', monitoria=monitoria)

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

# Rota para exibir relatórios
@app.route('/relatorio', methods=['GET', 'POST'])
def relatorio():
    # Obtem a lista de analistas do grupo
    analistas = Usuario.query.filter_by(grupo='analista').all()
    
    # Dicionários para armazenar médias e quantidades de monitorias por analista
    media_notas = {}
    media_pontuacao_por_analista = {}
    nota_media_por_analista = {}

    # Verifica se há filtro na requisição POST
    if request.method == 'POST':
        analista_selecionado = request.form.get('analista')
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')

        # Filtra as monitorias com base no analista e nas datas
        query = Monitoria.query

        if analista_selecionado:
            query = query.filter_by(matricula=analista_selecionado)

        if data_inicio and data_fim:
            query = query.filter(Monitoria.data_monitoria.between(data_inicio, data_fim))

        monitorias = query.all()

        # Cálculo da média de notas por analista e contagem de monitorias
        for monitoria in monitorias:
            media_notas.setdefault(monitoria.nome_analista, []).append(monitoria.nota)

        # Calcula a média geral de notas e quantidade de monitorias por analista
        for analista, notas in media_notas.items():
            nota_media_por_analista[analista] = {
                'media': sum(notas) / len(notas),
                'quantidade': len(notas)
            }

        # Estrutura para calcular média de pontuação por item para cada analista
        for monitoria in monitorias:
            media_pontuacao_por_analista.setdefault(monitoria.nome_analista, {
                'se_apresentou': [],
                'atendeu_prontidao': [],
                'ouviu_demanda': [],
                'demonstrou_empatia': [],
                'realizou_sondagem': []
            })

            # Para cada item, verifica se houve penalidade e atribui pontuação
            for item in media_pontuacao_por_analista[monitoria.nome_analista].keys():
                if item in monitoria.penalidades:
                    media_pontuacao_por_analista[monitoria.nome_analista][item].append(0)  # Penalidade
                else:
                    media_pontuacao_por_analista[monitoria.nome_analista][item].append(10)  # Sem penalidade

        # Calcula a média de pontuação para cada item por analista
        for analista, items in media_pontuacao_por_analista.items():
            for item, pontuacoes in items.items():
                if pontuacoes:
                    media_pontuacao_por_analista[analista][item] = sum(pontuacoes) / len(pontuacoes)
                else:
                    media_pontuacao_por_analista[analista][item] = 0

    # Renderiza o template com as variáveis necessárias
    return render_template(
        'relatorio.html',
        analistas=analistas,
        media_notas=media_notas,
        media_pontuacao_por_analista=media_pontuacao_por_analista,
        nota_media_por_analista=nota_media_por_analista
    )

    return render_template(
        'relatorio.html',
        analistas=analistas,
        media_notas=media_notas,
        media_pontuacao_por_analista=media_pontuacao_por_analista,
        nota_media_por_analista=nota_media_por_analista
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


@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)