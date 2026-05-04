import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or '4f9d2c7a8e1b6f0c9d3a7e5b1c8f2d6a'
    SQLALCHEMY_DATABASE_URI = os.environ.get('mysql+pymysql://przemeks_wlogio:Przemek121!@hosting-206.host1.eu:2222/przemeks_wlogio')
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
