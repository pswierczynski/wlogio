# Wlogio — Work Hours Registry

A web application for tracking work hours, calculating salaries, managing vacation balances, and monitoring team presence in real time.

**Live app:** [wlogio.onrender.com](https://wlogio.onrender.com)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+ / Flask |
| Database | PostgreSQL on Supabase (Transaction Pooler, port 6543) |
| ORM | SQLAlchemy + Flask-SQLAlchemy |
| Frontend | Tailwind CSS + DaisyUI + Alpine.js |
| Avatar Storage | Supabase Storage (bucket: `avatars`, public) |
| Auth | Flask-Login, passwords hashed with `pbkdf2:sha256` |
| Hosting | Render.com (free tier, Python 3.14, gunicorn) |

---

## Project Structure

```
wlogio/
├── run.py                  # Entry point; sys.path.insert for Render compatibility
├── config.py               # Config from .env; rewrites postgres:// → postgresql+psycopg://
├── requirements.txt
├── render.yaml
├── reimport_xlsx.py        # Data importer from .xlsx file
└── wlogio_app/             # Main module (NOT app/ — conflicts with a package on Render)
    ├── __init__.py         # create_app(); explicit template_folder and static_folder
    ├── models.py
    ├── calculator.py
    └── routes/
        ├── auth.py
        ├── dashboard.py
        ├── entries.py
        ├── settings.py
        └── welcome.py
```

> **Important:** The main module is named `wlogio_app/` (not `app/`) because Render has a pre-installed package called `app` that causes a naming conflict. `run.py` uses `sys.path.insert(0, ...)` to handle this.

---

## Environment Variables

```env
SECRET_KEY=...              # Random string, min. 32 characters
DATABASE_URL=postgresql://postgres.[ref]:[PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
FLASK_ENV=production
SUPABASE_URL=https://[ref].supabase.co
SUPABASE_SERVICE_KEY=...    # service_role key from Supabase → Project Settings → API
```

Avatar uploads use the REST API directly (`requests` library), not the supabase-py SDK.

---

## Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/pswierczynski/wlogio.git
cd wlogio

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
# or: venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env — fill in DATABASE_URL, SECRET_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY

# 5. Run the app
python run.py
```

App available at: http://localhost:5000

---

## Database Migrations (Supabase SQL Editor)

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS pin VARCHAR(4);
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar TEXT;
ALTER TABLE work_entries ADD COLUMN IF NOT EXISTS clock_in TIME;
ALTER TABLE work_entries ADD COLUMN IF NOT EXISTS clock_out TIME;
ALTER TABLE work_entries ADD COLUMN IF NOT EXISTS break_clock_start TIME;
ALTER TABLE work_entries ADD COLUMN IF NOT EXISTS break_clock_end TIME;
```

---

## Key Features

### Billing Period Logic
The billing month runs from the **23rd of the previous month** to the **22nd of the current month**.

- Entry on 24.03 → `billing_month = 4` (April)
- Entry on 22.04 → `billing_month = 4` (April)
- Entry on 23.04 → `billing_month = 5` (May)

### Entry Types
| Type | Description |
|---|---|
| `work` | Regular work day |
| `vacation` | Paid vacation (deducted from vacation pool) |
| `on_demand` | On-demand leave (deducted from both on-demand and vacation pools) |
| `unpaid` | Unpaid leave (0h, does not affect vacation pool) |
| `holiday` | Public holiday |
| `sick_leave` | Sick leave |

### Hour Calculation
- Built-in break: **15 min** (deducted when a break longer than 15 min is logged)
- Extra break = total break time − 15 min
- Rounding: `round(hours * 4) / 4` (to nearest 0.25h)
- Overnight work supported: if `end < start`, adds 24h to end time
- Timezone: `Europe/Warsaw` via `zoneinfo.ZoneInfo`

### Overtime
Calculated as the sum of daily deviations from 8h (not from monthly total).
Example: 6.5h → −1.5, 8.25h → +0.25, total = −1.25h

### Vacation Balance
- Global balance (not split by year in the UI)
- January 1st reset: on-demand and remote reset to zero; unused vacation days carry over
- Example: 5 unused vacation days from 2026 → 2027 pool = 26 + 5 = 31

### Welcome Screen (`/welcome/`)
Real-time presence board showing all active users with their current status:

| Status | Condition | Border color |
|---|---|---|
| `working` | Current time is within work hours | Green |
| `break` | Within work hours AND within break hours | Orange |
| `idle` | All other cases | Grey (50% opacity) |

Status data is polled every 10 seconds. Clock-in/out buttons on the welcome screen (`clock_*` fields) take priority over dashboard-set times (`time_*` fields).

---

## Deployment (Render.com)

1. Push the project to GitHub
2. Create a new **Web Service** on Render.com
3. Set environment variables (see above)
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn run:app`

> Use the **Transaction Pooler** connection (port 6543), not Direct Connection (port 5432 — blocked on free tier).

---

## Technical Notes

- **psycopg3** (`psycopg[binary]==3.2.10`) — psycopg2 is incompatible with Python 3.14 on Render.
- **Connection string** must start with `postgresql+psycopg://`. `config.py` handles the rewrite automatically.
- **Password hashing** uses `pbkdf2:sha256` — default `scrypt` is incompatible with Python 3.9 on macOS.
- **Hour rounding** uses `round(hours * 4) / 4`, not `Decimal.quantize('0.25')` (which rounds to 2 decimal places, not to multiples of 0.25).
- **Alpine.js + Jinja2** — never use `onclick="func('{{ var }}')"` — quote escaping breaks. Use `data-*` attributes and `addEventListener` in JS instead.
