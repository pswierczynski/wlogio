from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


# ---------------------------------------------------------------------------
# USER
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    """
    Użytkownik aplikacji.
    Rejestracja przez email + hasło.
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacje
    work_entries = db.relationship('WorkEntry', backref='user', lazy='dynamic',
                                   cascade='all, delete-orphan')
    month_configs = db.relationship('MonthConfig', backref='user', lazy='dynamic',
                                    cascade='all, delete-orphan')
    vacation_balances = db.relationship('VacationBalance', backref='user', lazy='dynamic',
                                        cascade='all, delete-orphan')
    hourly_rates = db.relationship('HourlyRate', backref='user', lazy='dynamic',
                                   cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'


# ---------------------------------------------------------------------------
# WORK ENTRY
# ---------------------------------------------------------------------------

class WorkEntry(db.Model):
    """
    Pojedynczy dzień w rejestrze.

    entry_type:
        'work'        - normalny dzień pracy
        'vacation'    - urlop zwykły
        'on_demand'   - urlop na żądanie
        'holiday'     - święto ustawowe
        'sick_leave'  - zwolnienie lekarskie

    Miesiąc rozliczeniowy liczony od 23 do 22 następnego miesiąca.
    billing_year i billing_month określają do którego okresu należy wpis.
    Np. wpis z 24.03 należy do miesiąca rozliczeniowego KWIECIEŃ (billing_month=4).
    """
    __tablename__ = 'work_entries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Data wpisu
    date = db.Column(db.Date, nullable=False)

    # Okres rozliczeniowy (23 prev → 22 curr)
    billing_year = db.Column(db.Integer, nullable=False)
    billing_month = db.Column(db.Integer, nullable=False)  # 1-12

    # Typ wpisu
    entry_type = db.Column(db.String(20), nullable=False, default='work')

    # Godziny pracy (tylko dla entry_type='work')
    time_start = db.Column(db.Time, nullable=True)
    time_end = db.Column(db.Time, nullable=True)
    break_start = db.Column(db.Time, nullable=True)
    break_end = db.Column(db.Time, nullable=True)

    # Nadprogramowa przerwa ponad 15 minut (minuty)
    extra_break_minutes = db.Column(db.Integer, default=0)

    # Obliczone wartości
    # hours_worked  = rzeczywiste minuty / 60 (przed zaokrągleniem)
    # hours_billed  = po odjęciu nadprogramowej przerwy, zaokrąglone do 0.25
    hours_worked = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    hours_billed = db.Column(db.Numeric(5, 2), nullable=False, default=8)

    # Metadane
    vacation_day_number = db.Column(db.Integer, nullable=True)  # który urlop w roku
    is_remote = db.Column(db.Boolean, default=False)            # praca zdalna
    remote_trip_number = db.Column(db.Integer, nullable=True)   # numer wyjazdu
    notes = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'date', name='uq_user_date'),
        db.Index('ix_user_billing', 'user_id', 'billing_year', 'billing_month'),
    )

    def __repr__(self):
        return f'<WorkEntry {self.date} [{self.entry_type}] {self.hours_billed}h>'


# ---------------------------------------------------------------------------
# MONTH CONFIG
# ---------------------------------------------------------------------------

class MonthConfig(db.Model):
    """
    Konfiguracja okresu rozliczeniowego.

    Przechowuje:
    - stawkę godzinową (dziedziczoną z poprzedniego miesiąca)
    - premię
    - oczekiwaną liczbę godzin (dni robocze * 8)
    - ustawienia urlopów i pracy zdalnej (sumy roczne, ręcznie)

    Jeden rekord = jeden okres rozliczeniowy (billing_year, billing_month).
    """
    __tablename__ = 'month_configs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    billing_year = db.Column(db.Integer, nullable=False)
    billing_month = db.Column(db.Integer, nullable=False)  # 1-12

    # Stawka godzinowa dla tego okresu (PLN)
    hourly_rate = db.Column(db.Numeric(8, 2), nullable=False, default=0)

    # Oczekiwana liczba godzin w okresie (dni_robocze * 8)
    expected_hours = db.Column(db.Numeric(6, 2), nullable=True)

    # Premia za ten miesiąc
    bonus = db.Column(db.Numeric(10, 2), nullable=True, default=0)

    # Roczne sumy urlopów (ręcznie ustawiane przez użytkownika)
    # Przechowywane tylko w rekordach danego roku (aktualne na dany rok)
    vacation_total = db.Column(db.Integer, nullable=True)       # np. 26
    on_demand_total = db.Column(db.Integer, nullable=True)      # np. 4
    remote_total = db.Column(db.Integer, nullable=True)         # np. 24

    notes = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'billing_year', 'billing_month',
                            name='uq_user_billing_period'),
    )

    def __repr__(self):
        return f'<MonthConfig {self.billing_year}-{self.billing_month:02d} {self.hourly_rate} PLN/h>'


# ---------------------------------------------------------------------------
# HOURLY RATE HISTORY (opcjonalna historia zmian stawki)
# ---------------------------------------------------------------------------

class HourlyRate(db.Model):
    """
    Historia zmian stawki godzinowej.
    Używana do audytu — główna stawka jest w MonthConfig.
    """
    __tablename__ = 'hourly_rates'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rate = db.Column(db.Numeric(8, 2), nullable=False)
    valid_from = db.Column(db.Date, nullable=False)
    valid_to = db.Column(db.Date, nullable=True)  # NULL = aktualnie obowiązuje
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<HourlyRate {self.rate} PLN od {self.valid_from}>'


# ---------------------------------------------------------------------------
# VACATION BALANCE
# ---------------------------------------------------------------------------

class VacationBalance(db.Model):
    """
    Bilans urlopowy per rok.

    used_days i used_on_demand są obliczane dynamicznie
    z wpisów WorkEntry dla danego roku kalendarzowego.
    Reset następuje automatycznie z dniem 1 stycznia.

    vacation_total, on_demand_total, remote_total
    są przepisywane z MonthConfig (ręczne ustawienia użytkownika).
    """
    __tablename__ = 'vacation_balances'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)

    # Pule roczne (ręcznie ustawiane)
    vacation_total = db.Column(db.Integer, nullable=False, default=26)
    on_demand_total = db.Column(db.Integer, nullable=False, default=4)
    remote_total = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'year', name='uq_user_year_balance'),
    )

    def __repr__(self):
        return f'<VacationBalance {self.year} user={self.user_id}>'
