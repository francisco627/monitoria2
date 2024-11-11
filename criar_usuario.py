from app import db, app  # Importe tanto o banco de dados quanto a aplicação Flask
from app import Usuario  # Certifique-se de ajustar o nome conforme o arquivo do modelo
from werkzeug.security import generate_password_hash

# Dados do usuário administrador
email = "adm@fivenet.com.br"
senha = generate_password_hash("1234")  # Gera o hash da senha "1234"
nome = "Administrador"
grupo = "administrador"
matricula = "ADM123"

# Inicie o contexto da aplicação
with app.app_context():
    # Verifique se o usuário já existe no banco de dados
    usuario_existente = Usuario.query.filter_by(email=email).first()
    if not usuario_existente:
        novo_usuario = Usuario(
            email=email,
            senha=senha,
            nome=nome,
            grupo=grupo,
            matricula=matricula
        )
        db.session.add(novo_usuario)
        db.session.commit()
        print("Usuário administrador criado com sucesso!")
    else:
        print("Usuário administrador já existe.")
