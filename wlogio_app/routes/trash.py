"""
trash.py - Kosz: usunięte dni (tabela trash_entries) z możliwością przywrócenia
lub trwałego usunięcia. Wpisy starsze niż 30 dni są kasowane automatycznie
(przy każdym otwarciu kosza i przy każdym usunięciu dnia).

Dostępny dla kont 'individual' (własne dni) i 'company' (dni wszystkich
pracowników, grupowane: pracownik → rok → miesiąc). Konto 'employee' nie ma dostępu.
"""
from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from wlogio_app import db
from wlogio_app.models import TrashEntry, WorkEntry, MonthConfig, User, TRASH_RETENTION_DAYS
from wlogio_app.routes.dashboard import get_company_employees, MONTH_NAMES
from wlogio_app.routes.entries import renumber_vacations

trash_bp = Blueprint('trash', __name__)


def drop_orphan_month_configs(pairs):
    """
    Kasuje konfigurację miesiąca (bez commita), jeśli dla (user_id, rok, miesiąc)
    nie zostało już ani jednego dnia — ani w panelu, ani w koszu. Wywoływane po
    TRWAŁYM usunięciu dni z kosza (ręcznie, przez opróżnienie lub po 30 dniach).
    """
    db.session.flush()
    for uid, y, m in set(pairs):
        has_entry = WorkEntry.query.filter_by(user_id=uid, billing_year=y, billing_month=m).first()
        has_trash = TrashEntry.query.filter_by(user_id=uid, billing_year=y, billing_month=m).first()
        if has_entry or has_trash:
            continue
        cfg = MonthConfig.query.filter_by(user_id=uid, billing_year=y, billing_month=m).first()
        if cfg:
            db.session.delete(cfg)


def _pairs(items):
    return [(t.user_id, t.billing_year, t.billing_month) for t in items]


def purge_expired_trash():
    """Kasuje z kosza wpisy starsze niż TRASH_RETENTION_DAYS (z commitem)."""
    limit = datetime.utcnow() - timedelta(days=TRASH_RETENTION_DAYS)
    expired = TrashEntry.query.filter(TrashEntry.deleted_at < limit).all()
    if expired:
        pairs = _pairs(expired)
        for t in expired:
            db.session.delete(t)
        drop_orphan_month_configs(pairs)
        db.session.commit()


def _scope_users():
    """Użytkownicy, których kosz widzi bieżące konto: [(User, ...)]."""
    if current_user.account_type == 'individual':
        return [current_user]
    if current_user.account_type == 'company':
        return get_company_employees(current_user.id)
    abort(403)


def _scope_query():
    ids = [u.id for u in _scope_users()]
    if not ids:
        return TrashEntry.query.filter(db.false())
    return TrashEntry.query.filter(TrashEntry.user_id.in_(ids))


def _selected_entries():
    ids = [int(x) for x in request.form.getlist('entry_ids') if x.isdigit()]
    if not ids:
        return []
    return _scope_query().filter(TrashEntry.id.in_(ids)).all()


@trash_bp.route('/')
@login_required
def index():
    users = _scope_users()
    purge_expired_trash()
    rows = _scope_query().order_by(TrashEntry.date.desc()).all()

    by_user = {}
    for r in rows:
        by_user.setdefault(r.user_id, {}).setdefault(r.billing_year, {}).setdefault(r.billing_month, []).append(r)

    groups = []      # [{user, years: [{year, months: [{key, name, entries}]}]}]
    month_ids = {}   # klucz miesiąca -> lista id (do zaznaczania wszystkich)
    for u in users:
        years = []
        for y in sorted(by_user.get(u.id, {}), reverse=True):
            months = []
            for m in sorted(by_user[u.id][y], reverse=True):
                entries = by_user[u.id][y][m]
                key = f'{u.id}-{y}-{m}'
                month_ids[key] = [e.id for e in entries]
                months.append({'key': key, 'name': MONTH_NAMES.get(m, str(m)), 'entries': entries})
            years.append({'year': y, 'count': sum(len(mm['entries']) for mm in months), 'months': months})
        if years:
            groups.append({'user': u, 'years': years})

    first = None
    if groups:
        g = groups[0]
        first = {'user': g['user'].id, 'year': g['years'][0]['year'], 'month': g['years'][0]['months'][0]['key']}

    return render_template(
        'trash/index.html', groups=groups, month_ids=month_ids, first=first,
        is_company=current_user.account_type == 'company', total=len(rows),
        retention_days=TRASH_RETENTION_DAYS, now=datetime.utcnow(),
    )


@trash_bp.route('/restore', methods=['POST'])
@login_required
def restore():
    items = _selected_entries()
    restored, conflicts, years = 0, 0, set()
    for t in items:
        exists = WorkEntry.query.filter_by(user_id=t.user_id, date=t.date).first()
        if exists:
            conflicts += 1
            continue
        db.session.add(t.to_entry())
        if t.entry_type in ('vacation', 'on_demand'):
            years.add((t.user_id, t.date.year))
        db.session.delete(t)
        restored += 1
    db.session.flush()
    for uid, y in years:
        renumber_vacations(uid, y)
    db.session.commit()

    if restored:
        flash(f'Przywrócono dni: {restored}.', 'success')
    if conflicts:
        flash(f'Pominięto dni, które mają już nowy wpis w tej dacie: {conflicts}.', 'error')
    return redirect(url_for('trash.index'))


@trash_bp.route('/purge', methods=['POST'])
@login_required
def purge():
    items = _selected_entries()
    pairs = _pairs(items)
    for t in items:
        db.session.delete(t)
    drop_orphan_month_configs(pairs)
    db.session.commit()
    if items:
        flash(f'Trwale usunięto dni: {len(items)}.', 'success')
    return redirect(url_for('trash.index'))


@trash_bp.route('/empty', methods=['POST'])
@login_required
def empty():
    items = _scope_query().all()
    pairs = _pairs(items)
    for t in items:
        db.session.delete(t)
    drop_orphan_month_configs(pairs)
    count = len(items)
    db.session.commit()
    flash(f'Opróżniono kosz (usunięto dni: {count}).', 'success')
    return redirect(url_for('trash.index'))
