import os
import sys

# Upewnij się że lokalny folder app/ ma pierwszeństwo przed zainstalowanymi paczkami
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db

config_name = os.environ.get('FLASK_ENV', 'production')
app = create_app(config_name)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print('[INFO] Tabele bazy danych gotowe.')
    app.run(host='0.0.0.0', port=5000, debug=(config_name == 'development'))