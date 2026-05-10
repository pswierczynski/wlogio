from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import random
from wlogio_app import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    pin = db.Column(db.String(4), nullable=True)      # 4-cyfrowy PIN do ekranu powitalnego
    avatar = db.Column(db.Text, nullable=True)         # URL do Supabase Storage
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_entries = db.relationship('WorkEntry', backref='user', lazy='dynamic',
                                   cascade='all, delete-orphan')
    month_configs = db.relationship('MonthConfig', backref='user', lazy='dynamic',
                                    cascade='all, delete-orphan')
    vacation_balances = db.relationship('VacationBalance', backref='user', lazy='dynamic',
                                        cascade='all, delete-orphan')
    hourly_rates = db.relationship('HourlyRate', backref='user', lazy='dynamic',
                                   cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_pin(self):
        """Generuje losowy 4-cyfrowy PIN."""
        self.pin = str(random.randint(1000, 9999))
        return self.pin

    def __repr__(self):
        return f'<User {self.email}>'


class WorkEntry(db.Model):
    """
    Pojedynczy dzień w rejestrze.
    entry_type: 'work', 'vacation', 'on_demand', 'unpaid', 'holiday', 'sick_leave'
    """
    __tablename__ = 'work_entries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    billing_year = db.Column(db.Integer, nullable=False)
    billing_month = db.Column(db.Integer, nullable=False)
    entry_type = db.Column(db.String(20), nullable=False, default='work')

    # Godziny z formularza (ręcznie)
    time_start = db.Column(db.Time, nullable=True)
    time_end = db.Column(db.Time, nullable=True)
    break_start = db.Column(db.Time, nullable=True)
    break_end = db.Column(db.Time, nullable=True)

    # Godziny z ekranu powitalnego (automatyczne)
    clock_in = db.Column(db.Time, nullable=True)
    clock_out = db.Column(db.Time, nullable=True)
    break_clock_start = db.Column(db.Time, nullable=True)
    break_clock_end = db.Column(db.Time, nullable=True)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'billing_year', 'billing_month',
                            name='uq_user_billing_period'),
    )


class HourlyRate(db.Model):
    __tablename__ = 'hourly_rates'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rate = db.Column(db.Numeric(8, 2), nullable=False)
    valid_from = db.Column(db.Date, nullable=False)
    valid_to = db.Column(db.Date, nullable=True)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class VacationBalance(db.Model):
    __tablename__ = 'vacation_balances'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    vacation_total = db.Column(db.Integer, nullable=False, default=26)
    on_demand_total = db.Column(db.Integer, nullable=False, default=4)
    remote_total = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'year', name='uq_user_year_balance'),
    )
