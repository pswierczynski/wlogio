"""
badges.py - ikony i kolory badge'y statusu dnia (te same co w Terminalu pracy).

Używane na liście pracowników. Kolejność i znaczenie kodów:
P praca zdalna, W praca, U urlop, N urlop na żądanie, B urlop bezpłatny,
H święto, Z zwolnienie lekarskie, O urlop opiekuńczy, S siła wyższa,
D opieka nad dzieckiem.
"""

BADGE_ICONS = {
    'B': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="8" y1="12" x2="16" y2="12"/></svg>',
    'D': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="6" r="2.6"/><path d="M4.5 17c0-3 2-5 4.5-5s4.5 2 4.5 5"/><circle cx="18" cy="10" r="2"/><path d="M14.7 17c.2-2.2 1.6-3.6 3.3-3.6s3.1 1.4 3.3 3.6"/></svg>',
    'H': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.5 14.7 9 21.5 9.5 16.3 14 18 20.5 12 16.8 6 20.5 7.7 14 2.5 9.5 9.3 9Z"/></svg>',
    'N': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z"/></svg>',
    'O': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 1 0-7.8 7.8l1 1L12 21l7.8-7.8 1-1a5.5 5.5 0 0 0 0-7.8Z"/></svg>',
    'P': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><circle cx="12" cy="20" r="1" fill="#fff" stroke="none"/></svg>',
    'S': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    'U': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="5" r="3"/><path d="M3 12 Q6 8 9 12 Q12 16 15 12 Q18 8 21 12"/><path d="M3 18 Q6 14 9 18 Q12 22 15 18 Q18 14 21 18"/></svg>',
    'W': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M3 13h18"/></svg>',
    'Z': '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3"/><path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4"/><circle cx="20" cy="10" r="2"/></svg>',
}

BADGE_COLORS = {
    'B': '#9ca3af',
    'D': '#3abff8',
    'H': '#9ca3af',
    'N': '#f59e0b',
    'O': '#3abff8',
    'P': '#22c55e',
    'S': '#f59e0b',
    'U': '#3abff8',
    'W': '#22c55e',
    'Z': '#ff5861',
}
