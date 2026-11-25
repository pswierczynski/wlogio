"""
scope.py — mechanizm "aktualnie przeglądanego/edytowanego konta" dla kont
firmowych.

Konto firmowe samo nie ma wpisów dni/konfiguracji (patrz models.User) —
wszystkie dane (panel pracy, ustawienia, eksport) dotyczą zawsze konkretnego
pracownika, wybranego z listy i zapamiętanego w sesji przeglądarki
(session['viewing_employee_id']).

Dla konta indywidualnego i konta pracowniczego "efektywnym użytkownikiem"
jest zawsze ono samo.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import session, flash, redirect, url_for
from flask_login import current_user


def get_effective_user():
    """
    Zwraca User, którego dane aktualnie przeglądamy:
    - individual / employee: zawsze siebie,
    - company: wybranego pracownika (albo None, jeśli żaden nie jest
      jeszcze wybrany — wtedy routy powinny pokazać listę pracowników).
    """
    if current_user.account_type != 'company':
        return current_user

    employee_id = session.get('viewing_employee_id')
    if not employee_id:
        return None

    from wlogio_app.models import User
    employee = User.query.get(employee_id)
    if not employee or not employee.is_employee_account or employee.company_id != current_user.id:
        session.pop('viewing_employee_id', None)
        return None
    return employee


def require_effective_user():
    """
    Do użytku w routach, które MODYFIKUJĄ dane (dodawanie/edycja wpisów,
    zmiana konfiguracji miesiąca, bilansu urlopowego itd.).

    Zwraca (target_user, None) gdy wolno kontynuować, albo (None, response)
    gdy trzeba przerwać i zwrócić `response` — w dwóch przypadkach:
    - zalogowane konto pracownicze (ma tylko podgląd własnych danych,
      zmiany wprowadza wyłącznie administrator konta firmowego),
    - konto firmowe bez wybranego pracownika z listy.
    """
    if current_user.account_type == 'employee':
        flash('Twoje konto ma tylko podgląd — zmiany wprowadza administrator konta firmowego.', 'error')
        return None, redirect(url_for('dashboard.index'))

    target = get_effective_user()
    if target is None:
        flash('Najpierw wybierz pracownika z listy.', 'error')
        return None, redirect(url_for('dashboard.index'))

    return target, None


def set_viewing_employee(employee_id):
    session['viewing_employee_id'] = employee_id


def clear_viewing_employee():
    session.pop('viewing_employee_id', None)


# --- Konto pracownicze: zakres zapisu w panelu pracy zależy od ustawień konta firmowego ---


def local_today():
    """Dzisiejsza data w strefie Europe/Warsaw (tak samo jak w terminalu)."""
    return datetime.now(ZoneInfo('Europe/Warsaw')).date()


def _employee_day_allowed(user, day, new_type, existing_type=None):
    """
    Czy konto pracownicze może ustawić na dzień `day` wpis typu `new_type`
    (istniejący wpis ma typ `existing_type`, brak = None) — wg ustawień firmy:
      full     - zawsze,
      today    - tylko bieżący dzień; dodatkowo (opcja) dni inne niż praca od dziś w przyszłość,
      terminal - nic w panelu; (opcja) dni inne niż praca od dziś w przyszłość.
    """
    mode, future_leave = user.entry_policy
    if mode == 'full':
        return True
    today = local_today()
    if mode == 'today' and day == today:
        return True
    # Praca zdalna w bieżącym dniu (opcja firmy; ma sens w trybie "tylko terminal")
    if day == today and new_type == 'remote' and existing_type in (None, 'remote') and user.remote_today_allowed:
        return True
    work_like = ('work', 'remote')
    if future_leave and day >= today and new_type not in work_like and existing_type not in work_like:
        return True
    return False


def entry_policy_type(entry_type, is_remote=False):
    """Typ do oceny uprawnień: praca zdalna ('work' + is_remote) to osobny rodzaj 'remote'."""
    return 'remote' if entry_type == 'work' and is_remote else entry_type


def employee_set_error(entry_date, new_type, existing_type=None):
    """Komunikat błędu, jeśli zalogowany pracownik NIE może ustawić takiego wpisu; None gdy wolno."""
    if new_type == 'holiday' and existing_type != 'holiday':
        return 'Pracownik nie może dodawać świąt — są dodawane automatycznie.'
    if _employee_day_allowed(current_user, entry_date, new_type, existing_type):
        return None
    if new_type == 'remote' and current_user.remote_today_allowed:
        return 'Pracę zdalną możesz dodać tylko w bieżącym dniu.'
    mode, future_leave = current_user.entry_policy
    if mode == 'today':
        if future_leave:
            return 'Możesz zmieniać tylko bieżący dzień oraz dodawać urlopy i zwolnienia od dziś w przyszłość.'
        return 'Pracownik może zmieniać tylko bieżący dzień.'
    if future_leave:
        return 'Możesz dodawać tylko urlopy i zwolnienia od dziś w przyszłość. Pracę rejestrujesz w terminalu.'
    return 'Firma zezwala na rejestrowanie czasu pracy wyłącznie w terminalu.'


def employee_can_delete(entry):
    t = entry_policy_type(entry.entry_type, entry.is_remote)
    return _employee_day_allowed(current_user, entry.date, t, t)


def employee_can_modify(entry):
    """Czy bieżący pracownik może edytować/usunąć ten wpis (używane w szablonach)."""
    if current_user.account_type != 'employee':
        return True
    t = entry_policy_type(entry.entry_type, entry.is_remote)
    return _employee_day_allowed(current_user, entry.date, t, t)


def employee_can_note(entry):
    """Czy pracownik może zmienić WYŁĄCZNIE notatkę tego wpisu (zawsze, ale tylko w bieżącym dniu)."""
    return current_user.account_type == 'employee' and entry.date == local_today()


def employee_can_add_any():
    """Czy w panelu ma być widoczny przycisk dodawania dnia."""
    if current_user.account_type != 'employee':
        return True
    mode, future_leave = current_user.entry_policy
    return mode in ('full', 'today') or future_leave or current_user.remote_today_allowed


def require_entry_user():
    """
    Jak require_effective_user(), ale dopuszcza konto pracownicze (zapis
    własnych wpisów) — szczegółowe ograniczenia dni/typów egzekwują routy
    przez employee_set_error() / employee_can_delete().
    """
    if current_user.account_type == 'employee':
        return current_user, None
    return require_effective_user()
