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
