import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-zmien-w-produkcji'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Normy czasu pracy
    WORK_HOURS_PER_DAY = 8.0   # godzin dziennie
    BREAK_MINUTES = 15          # odliczana przerwa programowa (min)

    # Miesiąc rozliczeniowy: 23 bieżącego → 22 następnego
    MONTH_START_DAY = 23
    MONTH_END_DAY = 22


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
