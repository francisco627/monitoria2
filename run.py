from waitress import serve
from app import app  # Certifique-se de que 'app' é o nome correto da sua aplicação Flask

serve(app, host='0.0.0.0', port=8000)
