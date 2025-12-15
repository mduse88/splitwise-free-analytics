# Splitwise Expense Dashboard

Un'applicazione per monitorare le spese da Splitwise, visualizzarle in un dashboard interattivo e ricevere report automatici via email.

> **Personalizzabile**: Puoi configurare il titolo del dashboard tramite la variabile d'ambiente `DASHBOARD_TITLE`.

## Funzionalità

- **Dashboard Interattivo**: Grafici mensili e per categoria, filtri dinamici e ricerca
- **Backup Completo**: JSON e CSV con tutti i dati Splitwise (inclusi pagamenti, utenti, repayments)
- **Storico Completo**: Recupera TUTTE le spese dalla prima all'ultima tramite paginazione automatica
- **Automazione Mensile**: Report inviato il 1° di ogni mese via email
- **Backup su Google Drive**: Salvataggio automatico di dati e report nel cloud
- **Export Dati**: Possibilità di scaricare tutti i dati in formato CSV

## Struttura del Progetto

```
family_expenses/
├── family_expenses.py      # Entry point CLI
├── src/
│   ├── config.py           # Configurazione e env vars
│   ├── splitwise_client.py # API Splitwise
│   ├── dashboard.py        # Generazione dashboard
│   ├── email_sender.py     # Invio email
│   └── gdrive.py           # Upload Google Drive
├── templates/
│   └── dashboard.html      # Template Jinja2
├── Requirements.txt
└── .github/workflows/
    └── expense_report.yml  # Automazione GitHub Actions
```

## Setup Locale

### 1. Requisiti
- Python 3.11+
- Account Splitwise
- Account Google (per Drive e Gmail)

### 2. Installazione

```bash
# Clona il repository
git clone https://github.com/tuo-user/family_expenses.git
cd family_expenses

# Crea ambiente virtuale
python3 -m venv venv
source venv/bin/activate

# Installa dipendenze
pip install -r Requirements.txt
```

### 3. Configurazione

Copia il file `.env.example` e rinominalo in `.env`:

```bash
cp .env.example .env
```

Poi configura i valori:

```env
# Branding (opzionale)
DASHBOARD_TITLE=Family Expenses  # Titolo del dashboard (default: "Family Expenses")

# Splitwise (richiesto)
api_key=la_tua_api_key
group_id=il_tuo_group_id  # Opzionale: se omesso, recupera spese da TUTTI i gruppi (non testato senza group_id)

# Google Drive (opzionale per uso locale)
GDRIVE_CLIENT_ID=
GDRIVE_CLIENT_SECRET=
GDRIVE_REFRESH_TOKEN=
GDRIVE_FOLDER_ID=

# Email (opzionale per uso locale)
GMAIL_ADDRESS=
GMAIL_APP_PASSWORD=
RECIPIENT_EMAIL=
```

| Variabile | Richiesta | Descrizione |
|-----------|-----------|-------------|
| `DASHBOARD_TITLE` | No | Titolo personalizzato per il dashboard |
| `api_key` | **Sì** | API Key di Splitwise ([ottienila qui](https://secure.splitwise.com/apps)) |
| `group_id` | No | ID del gruppo Splitwise (URL: splitwise.com/groups/**XXXXX**) |
| `GDRIVE_*` | No | Credenziali OAuth per upload su Google Drive |
| `GMAIL_*` | No | Credenziali per invio email automatiche |

### 4. Utilizzo

```bash
# Genera dashboard e carica su Google Drive
python family_expenses.py

# Genera dashboard e invia anche email
python family_expenses.py --email

# Genera dashboard senza upload su Drive (usa file temporanei)
python family_expenses.py --no-upload

# Genera dashboard localmente nella cartella output/ (per test/debug)
python family_expenses.py --local
```

Con `--local`, i file vengono salvati in `output/` e puoi aprire il dashboard nel browser:
```bash
open output/2025-12-10_expenses_dashboard.html
```

## Automazione con GitHub Actions

Il progetto include un workflow GitHub che esegue automaticamente lo script:
- **Quando**: Il 1° di ogni mese alle 8:00 CET
- **Comando**: `python family_expenses.py --email`
- **Cosa fa**: 
  1. Scarica le nuove spese da Splitwise
  2. Genera il dashboard aggiornato
  3. Carica i file (JSON, CSV, HTML) su Google Drive
  4. Invia il dashboard via email

### Esecuzione Manuale

Puoi eseguire il workflow manualmente da GitHub Actions con opzioni configurabili:

1. Vai su **Actions** → **Monthly Expense Report** → **Run workflow**
2. Configura le opzioni:
   - **Upload files to Google Drive**: ✅ default attivo
   - **Send email notification**: ✅ default attivo
3. Clicca **Run workflow**

Utile per test: disattiva "Send email" per verificare solo l'upload su Drive.

### Configurazione GitHub Secrets

Per far funzionare l'automazione, aggiungi questi secret nel repository GitHub (Settings > Secrets and variables > Actions > tab **Secrets**):

| Secret | Descrizione |
|--------|-------------|
| `SPLITWISE_API_KEY` | La tua API Key di Splitwise |
| `SPLITWISE_GROUP_ID` | (Opzionale) L'ID del gruppo Splitwise. Se omesso, recupera da tutti i gruppi |
| `GMAIL_ADDRESS` | Il tuo indirizzo Gmail mittente |
| `GMAIL_APP_PASSWORD` | Password per le app di Gmail (16 caratteri) |
| `GDRIVE_CLIENT_ID` | Client ID OAuth Google Cloud |
| `GDRIVE_CLIENT_SECRET` | Client Secret OAuth Google Cloud |
| `GDRIVE_REFRESH_TOKEN` | Refresh Token per accesso offline |
| `GDRIVE_FOLDER_ID` | ID della cartella Google Drive di destinazione |

### Configurazione GitHub Variables

Aggiungi queste variabili nel repository GitHub (Settings > Secrets and variables > Actions > tab **Variables**):

| Variable | Descrizione |
|----------|-------------|
| `RECIPIENT_EMAIL` | Destinatari separati da virgola (es. `email1@gmail.com,email2@gmail.com`) |
| `DASHBOARD_TITLE` | (Opzionale) Titolo personalizzato per il dashboard |

## Output

I file vengono caricati direttamente su Google Drive (nessun salvataggio locale):

| File | Contenuto |
|------|-----------|
| `YYYY-MM-DD_expenses.json` | **Backup completo**: tutti i record Splitwise con tutti i campi (categoria, utenti, repayments, etc.) |
| `YYYY-MM-DD_expenses.csv` | **Backup completo**: stessi dati in formato tabellare |
| `YYYY-MM-DD_expenses_dashboard.html` | **Dashboard**: solo spese (no pagamenti), campi selezionati per visualizzazione |

### Struttura Dati

**JSON/CSV (backup completo)** includono:
- Tutti i record (spese + pagamenti/settlements)
- Tutti i campi Splitwise: `id`, `description`, `cost`, `date`, `category`, `repayments`, `users`, `created_by`, `receipt`, etc.
- Oggetti nested completamente deserializzati (es. `category: {id, name, subcategories}`)

**HTML (dashboard)** include solo:
- Spese (esclusi pagamenti)
- Campi per visualizzazione: `id`, `description`, `cost`, `currency_code`, `date`, `category_name`
