from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import random
from wlogio_app import db


ACCOUNT_TYPES = ('individual', 'company', 'employee')
ACCOUNT_TYPE_LABELS = {
    'individual': 'Indywidualne',
    'company':    'Firmowe',
    'employee':   'Pracownicze',
}
# Typy dostępne do wyboru podczas rejestracji — 'employee' nadawane jest
# wyłącznie ręcznie/niezależnie od samodzielnej rejestracji.
REGISTRATION_ACCOUNT_TYPES = ('individual', 'company')

# Wielkość firmy (konto 'company') -> maksymalna liczba kont pracowniczych.
COMPANY_SIZES = ('small', 'medium', 'large')
COMPANY_SIZE_LIMITS = {'small': 10, 'medium': 50, 'large': 100}
COMPANY_SIZE_LABELS = {'small': 'mała', 'medium': 'średnia', 'large': 'duża'}
DEFAULT_COMPANY_SIZE = 'small'


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    # Konta 'individual' / 'company' logują się emailem; konto 'employee'
    # nie ma (i nie wymaga) adresu email — stąd nullable=True.
    email = db.Column(db.String(255), unique=True, nullable=True, index=True)
    # Login — wyłącznie dla kont 'employee', nadawany przez administratora
    # konta firmowego (zamiast adresu email).
    login = db.Column(db.String(50), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    pin = db.Column(db.String(4), nullable=True)
    avatar = db.Column(db.Text, nullable=True)
    # 'individual' / 'company' — wybierane przy rejestracji;
    # 'employee' — konto pracownicze, nadawane niezależnie od rejestracji
    # (patrz ACCOUNT_TYPES / ACCOUNT_TYPE_LABELS).
    account_type = db.Column(db.String(20), nullable=False, default='employee')
    # Wyłącznie dla kont 'employee' — id konta 'company', do którego należą.
    company_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    # Wyłącznie dla kont 'company' — 'small' / 'medium' / 'large'
    # (limit pracowników: patrz COMPANY_SIZE_LIMITS). NULL traktowany jak 'small'.
    company_size = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Konto firmowe -> jego konta pracownicze (self-referencyjna relacja).
    employees = db.relationship(
        'User',
        backref=db.backref('company', remote_side=[id]),
        foreign_keys=[company_id],
        order_by='User.name',
    )

    work_entries = db.relationship('WorkEntry', backref='user', lazy='dynamic',
                                   cascade='all, delete-orphan')
    month_configs = db.relationship('MonthConfig', backref='user', lazy='dynamic',
                                    cascade='all, delete-orphan')
    vacation_balances = db.relationship('VacationBalance', backref='user', lazy='dynamic',
                                        cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_pin(self):
        self.pin = str(random.randint(1000, 9999))
        return self.pin

    @property
    def is_individual(self):
        return self.account_type == 'individual'

    @property
    def is_company(self):
        return self.account_type == 'company'

    @property
    def is_employee_account(self):
        return self.account_type == 'employee'

    @property
    def effective_company_size(self):
        if not self.is_company:
            return None
        return self.company_size if self.company_size in COMPANY_SIZE_LIMITS else DEFAULT_COMPANY_SIZE

    @property
    def employee_limit(self):
        """Maks. liczba pracowników dla konta firmowego (None dla pozostałych)."""
        size = self.effective_company_size
        return COMPANY_SIZE_LIMITS[size] if size else None

    @property
    def account_type_label(self):
        """Pełna nazwa rodzaju konta, np. 'konto firmowe - firma mała'."""
        if self.is_company:
            return 'konto firmowe - firma ' + COMPANY_SIZE_LABELS[self.effective_company_size]
        if self.is_employee_account:
            return 'konto pracownicze'
        return 'konto indywidualne'

    def __repr__(self):
        return f'<User {self.email or self.login}>'


class WorkEntry(db.Model):
    """
    Pojedynczy dzień w rejestrze.
    entry_type: 'work', 'vacation', 'on_demand', 'unpaid', 'holiday', 'sick_leave'

    Przerwy (breaks): format "HH:MM-HH:MM;HH:MM-HH:MM" — wiele przerw oddzielonych ';'.
    Każda przerwa musi mieścić się w przedziale time_start..time_end i nie nachodzić
    na inne przerwy. Suma czasu wszystkich przerw - 15 min = nadprogramowa przerwa.
    Patrz wlogio_app.calculator.parse_breaks() / format_breaks().
    """
    __tablename__ = 'work_entries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    billing_year = db.Column(db.Integer, nullable=False)
    billing_month = db.Column(db.Integer, nullable=False)
    entry_type = db.Column(db.String(20), nullable=False, default='work')

    time_start = db.Column(db.Time, nullable=True)
    time_end = db.Column(db.Time, nullable=True)

    # Wiele przerw jako string "HH:MM-HH:MM;HH:MM-HH:MM"
    breaks = db.Column(db.Text, nullable=True)

    extra_break_minutes = db.Column(db.Integer, default=0)
    hours_worked = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    hours_billed = db.Column(db.Numeric(5, 2), nullable=False, default=8)

    vacation_day_number = db.Column(db.Integer, nullable=True)
    is_remote = db.Column(db.Boolean, default=False)
    remote_trip_number = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'date', name='uq_user_date'),
        db.Index('ix_user_billing', 'user_id', 'billing_year', 'billing_month'),
    )

    def __repr__(self):
        return f'<WorkEntry {self.date} [{self.entry_type}] {self.hours_billed}h>'


class MonthConfig(db.Model):
    __tablename__ = 'month_configs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    billing_year = db.Column(db.Integer, nullable=False)
    billing_month = db.Column(db.Integer, nullable=False)
    hourly_rate = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    expected_hours = db.Column(db.Numeric(6, 2), nullable=True)
    bonus = db.Column(db.Numeric(10, 2), nullable=True, default=0)
    notes = db.Column(db.String(500), nullable=True)

    # Ustawienia okresu rozliczeniowego
    # Domyślnie: od 23. dnia poprzedniego miesiąca do 22. dnia bieżącego
    billing_start_day = db.Column(db.Integer, nullable=False, default=23)
    billing_end_day   = db.Column(db.Integer, nullable=False, default=22)

    # Zaokrąglanie godzin pracy: 1, 5, 10, 15 lub 30 minut
    round_minutes = db.Column(db.Integer, nullable=False, default=15)

    # Stawka za nadgodziny (% stawki godzinowej), domyślnie 100%
    overtime_rate = db.Column(db.Integer, nullable=False, default=100)

    # Dni robocze jako string CSV z numerami dni tygodnia (0=pon, 6=nie)
    # Domyślnie: pon-pt = '0,1,2,3,4'
    work_days = db.Column(db.String(20), nullable=False, default='0,1,2,3,4')

    # Stawka za pracę w dni poza roboczymi (% stawki godzinowej), domyślnie 100%
    offday_rate = db.Column(db.Integer, nullable=False, default=100)

    # Liczba godzin roboczych w dniu, domyślnie 8
    hours_per_day = db.Column(db.Numeric(4, 2), nullable=False, default=8.00)

    # Dozwolona płatna przerwa w ciągu dnia (minuty), domyślnie 15
    paid_break_minutes = db.Column(db.Integer, nullable=False, default=15)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'billing_year', 'billing_month',
                            name='uq_user_billing_period'),
    )

    def work_days_list(self):
        """Zwraca listę dni roboczych jako inty, np. [0, 1, 2, 3, 4]."""
        if not self.work_days:
            return [0, 1, 2, 3, 4]
        try:
            return [int(d.strip()) for d in self.work_days.split(',') if d.strip()]
        except ValueError:
            return [0, 1, 2, 3, 4]


class VacationBalance(db.Model):
    __tablename__ = 'vacation_balances'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    vacation_total = db.Column(db.Integer, nullable=False, default=26)
    on_demand_total = db.Column(db.Integer, nullable=False, default=4)
    remote_total = db.Column(db.Integer, nullable=False, default=0)

    # Osobne, roczne pule urlopowe — nie pomniejszają vacation_total
    care_leave_total = db.Column(db.Integer, nullable=False, default=5)      # Urlop opiekuńczy
    force_majeure_total = db.Column(db.Integer, nullable=False, default=2)   # Siła wyższa
    child_care_total = db.Column(db.Integer, nullable=False, default=2)      # Opieka nad dzieckiem

    __table_args__ = (
        db.UniqueConstraint('user_id', 'year', name='uq_user_year_balance'),
    )
