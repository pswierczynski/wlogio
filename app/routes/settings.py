from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from decimal import Decimal
from datetime import date

from app import db
from app.models import MonthConfig, VacationBalance
from app.calculator import get_working_days_in_billing_period, get_or_create_vacation_balance

settings_bp = Blueprint('settings', __name__)

MONTH_NAMES = {
    1: 'Styczeń', 2: 'Luty', 3: 'Marzec', 4: 'Kwiecień',
    5: 'Maj', 6: 'Czerwiec', 7: 'Lipiec', 8: 'Sierpień',
    9: 'Wrzesień', 10: 'Październik', 11: 'Listopad', 12: 'Grudzień'
}


@settings_bp.route('/')
@login_required
def index():
    configs = (
        MonthConfig.query
        .filter_by(user_id=current_user.id)
        .order_by(MonthConfig.billing_year.desc(), MonthConfig.billing_month.desc())
        .all()
    )

    balance = get_or_create_vacation_balance(current_user.id, db.session)

    return render_template(
        'settings/index.html',
        configs=configs,
        balance=balance,
        MONTH_NAMES=MONTH_NAMES,
    )


@settings_bp.route('/month/<int:year>/<int:month>', methods=['GET', 'POST'])
@login_required
def month_config(year, month):
    config = MonthConfig.query.filter_by(
        user_id=current_user.id,
        billing_year=year,
        billing_month=month
    ).first_or_404()

    working_days = get_working_days_in_billing_period(year, month)
    expected_hours = working_days * 8

    if request.method == 'POST':
        try:
            config.hourly_rate = Decimal(request.form.get('hourly_rate', '0').replace(',', '.'))
            # expected_hours zawsze z kalendarza - użytkownik nie może zmieniać
            config.expected_hours = Decimal(str(expected_hours))
            bonus_str = request.form.get('bonus', '0').replace(',', '.').strip()
            config.bonus = Decimal(bonus_str) if bonus_str else Decimal('0')
            config.notes = request.form.get('notes', '').strip() or None
            db.session.commit()
            flash('Konfiguracja miesiąca zapisana.', 'success')
        except Exception as e:
            flash(f'Błąd: {e}', 'error')
        return redirect(url_for('settings.index'))

    return render_template(
        'settings/month_config.html',
        config=config,
        expected_hours=expected_hours,
        working_days=working_days,
        MONTH_NAMES=MONTH_NAMES,
    )


@settings_bp.route('/vacation', methods=['GET', 'POST'])
@login_required
def vacation_balance():
    balance = get_or_create_vacation_balance(current_user.id, db.session)

    if request.method == 'POST':
        try:
            balance.vacation_total = int(request.form.get('vacation_total', 26))
            balance.on_demand_total = int(request.form.get('on_demand_total', 4))
            balance.remote_total = int(request.form.get('remote_total', 24))
            db.session.commit()
            flash('Bilans urlopowy zapisany.', 'success')
        except Exception as e:
            flash(f'Błąd: {e}', 'error')
        return redirect(url_for('settings.index'))

    return render_template('settings/vacation_balance.html', balance=balance)
