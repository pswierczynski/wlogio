from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from decimal import Decimal
from datetime import date

from app import db
from app.models import MonthConfig, VacationBalance

settings_bp = Blueprint('settings', __name__)

MONTH_NAMES = {
    1: 'Styczeń', 2: 'Luty', 3: 'Marzec', 4: 'Kwiecień',
    5: 'Maj', 6: 'Czerwiec', 7: 'Lipiec', 8: 'Sierpień',
    9: 'Wrzesień', 10: 'Październik', 11: 'Listopad', 12: 'Grudzień'
}


@settings_bp.route('/')
@login_required
def index():
    current_year = date.today().year

    # Konfiguracje miesięcy
    configs = (
        MonthConfig.query
        .filter_by(user_id=current_user.id)
        .order_by(MonthConfig.billing_year.desc(), MonthConfig.billing_month.desc())
        .all()
    )

    # Bilanse urlopowe
    balances = (
        VacationBalance.query
        .filter_by(user_id=current_user.id)
        .order_by(VacationBalance.year.desc())
        .all()
    )

    return render_template(
        'settings/index.html',
        configs=configs,
        balances=balances,
        current_year=current_year,
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

    if request.method == 'POST':
        try:
            config.hourly_rate = Decimal(request.form.get('hourly_rate', '0').replace(',', '.'))
            config.expected_hours = Decimal(request.form.get('expected_hours', '0').replace(',', '.'))
            config.bonus = Decimal(request.form.get('bonus', '0').replace(',', '.'))
            config.notes = request.form.get('notes', '').strip() or None
            db.session.commit()
            flash('Konfiguracja miesiąca zapisana.', 'success')
        except Exception as e:
            flash(f'Błąd: {e}', 'error')

        return redirect(url_for('settings.index'))

    return render_template(
        'settings/month_config.html',
        config=config,
        MONTH_NAMES=MONTH_NAMES,
    )


@settings_bp.route('/vacation/<int:year>', methods=['GET', 'POST'])
@login_required
def vacation_balance(year):
    balance = VacationBalance.query.filter_by(
        user_id=current_user.id,
        year=year
    ).first()

    if not balance:
        balance = VacationBalance(
            user_id=current_user.id,
            year=year,
            vacation_total=26,
            on_demand_total=4,
            remote_total=0,
        )
        db.session.add(balance)
        db.session.commit()

    if request.method == 'POST':
        try:
            balance.vacation_total = int(request.form.get('vacation_total', 26))
            balance.on_demand_total = int(request.form.get('on_demand_total', 4))
            balance.remote_total = int(request.form.get('remote_total', 0))
            db.session.commit()
            flash(f'Bilans urlopowy na {year} rok zapisany.', 'success')
        except Exception as e:
            flash(f'Błąd: {e}', 'error')

        return redirect(url_for('settings.index'))

    return render_template(
        'settings/vacation_balance.html',
        balance=balance,
        year=year,
    )
