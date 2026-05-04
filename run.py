import os
from app import create_app, db

config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config_name)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print('[INFO] Tabele bazy danych gotowe.')
    app.run(host='0.0.0.0', port=5000, debug=(config_name == 'development'))
