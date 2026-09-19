# Fashion Business Management System

A Streamlit + MySQL application for managing a fashion business — designers, collections, fabrics, suppliers, inventory, sales, and reporting, with role-based app users, stored procedures, functions, and triggers.

**Repo:** https://github.com/Rahul-Suttakoti/Fashion-Business-Management-System

---

## Project Structure

```
Fashion_Business_Management_System/
├── app.py                              # Main Streamlit application
├── create_admin.py                     # Script to create the first admin app-user
├── DB_schema.sql                       # Table definitions + sample data
├── Triggers_Functions_procedures.sql   # Triggers, functions, stored procedures
├── requirements.txt                    # Python dependencies
├── .env                                # DB credentials (NOT committed — see below)
└── .gitignore
```

## Tech Stack

- **Frontend/App:** Streamlit
- **Database:** MySQL
- **Language:** Python 3
- **Libraries:** `streamlit`, `mysql-connector-python`, `python-dotenv`, `pandas`, `matplotlib`

---

## Prerequisites

- Python 3.9+ installed
- MySQL Server installed and running (MySQL Workbench / MySQL Command Line Client recommended alongside it)
- Git
- VS Code (or any editor)

---

## Full Setup Guide

### 1. Install MySQL Server

Download and install **MySQL Server** (not just Workbench) from https://dev.mysql.com/downloads/mysql/. During installation:
- Choose a **Custom** setup and make sure **MySQL Server**, **MySQL Workbench**, and **MySQL Command Line Client** are all selected.
- Set and remember a **root password** — you'll need it throughout this project.

Verify install by opening **MySQL Command Line Client** from the Start menu and logging in with the root password.

### 2. Clone or open the project

```bash
git clone https://github.com/Rahul-Suttakoti/Fashion-Business-Management-System.git
cd Fashion-Business-Management-System
```

Open the folder in VS Code.

### 3. Create and activate a virtual environment

Open a terminal in VS Code (`` Ctrl+` ``):

```powershell
python -m venv venv
venv\Scripts\Activate.ps1      # Windows PowerShell
# source venv/bin/activate     # Mac/Linux
```

Your terminal prompt should now be prefixed with `(venv)`.

### 4. Install Python dependencies

```powershell
pip install -r requirements.txt
```

### 5. Create the MySQL database

Open **MySQL Command Line Client**, log in with your root password, then run:

```sql
CREATE DATABASE fashion_business;
```

### 6. Create a `.env` file

In the project root, create a file named exactly `.env`:

```
DB_HOST=localhost
DB_USER=root
DB_PASS=your_mysql_root_password
DB_NAME=fashion_business
DB_PORT=3306
```

> ⚠️ This file contains your database password. It is excluded from git via `.gitignore` — never commit it.

### 7. Load the schema and sample data

From the VS Code (PowerShell) terminal, using the full path to `mysql.exe` (adjust the version folder if yours differs):

```powershell
Get-Content .\DB_schema.sql | & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p fashion_business
```

This creates all core tables (`Designers`, `Collections`, `Suppliers`, `Fabrics`, `Clothing_Items`, `Stores`, `Sales`, `Inventory`, and junction tables) and inserts sample data.

**Known MySQL syntax quirk:** the file ends with four `CREATE INDEX IF NOT EXISTS ...` statements, which MySQL doesn't support (`IF NOT EXISTS` isn't valid there). These will error out — run them manually without that clause if you want the indexes:

```sql
CREATE INDEX idx_ci_collection_id ON Clothing_Items(collection_id);
CREATE INDEX idx_fabrics_supplier_id ON Fabrics(supplier_id);
CREATE INDEX idx_inv_item_id ON Inventory(item_id);
CREATE INDEX idx_cif_item_fabric ON Clothing_Item_Fabrics(item_id, fabric_id);
```

### 8. Load triggers, functions, and procedures

```powershell
Get-Content .\Triggers_Functions_procedures.sql | & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p fashion_business
```

This adds triggers, `GetDesignerRevenue` (function), `GetDesignerPortfolio` and `MonthlySalesReport` (procedures), plus an `Inventory_Alerts` table + trigger.

**Same quirk again:** one `ADD CONSTRAINT IF NOT EXISTS fk_inventoryalerts_item ...` statement will fail. Run it manually without `IF NOT EXISTS`:

```sql
ALTER TABLE Inventory_Alerts
  ADD CONSTRAINT fk_inventoryalerts_item
    FOREIGN KEY (item_id) REFERENCES Clothing_Items(item_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE;
```

If it says the constraint already exists, that's fine — it means an earlier run already added it.

### 9. Create an admin app-user

This is a **login for the Streamlit app itself**, separate from your MySQL root account:

```powershell
python create_admin.py
```

Enter a username and a password (minimum 4 characters) when prompted.

### 10. Run the app

```powershell
streamlit run app.py
```

This opens the app automatically at **http://localhost:8501**. Log in with the admin credentials from step 9.

---

## Features

- **Designers / Collections / Suppliers / Fabrics** — CRUD management pages
- **Clothing Items / Inventory** — stock tracking, reorder levels, inventory alerts
- **Sales** — record sales, tied to stores and items
- **Reports** — nested query, join query, aggregate query, plus extra join queries (Complete Product Info, Sales Performance by Store)
- **Stored Procedures** — `GetDesignerPortfolio(designer_id)`, `MonthlySalesReport(store_id, month, year)`
- **Functions** — `GetDesignerRevenue(designer_id)`
- **Admin panel** — create app users with roles (admin, manager, cashier, procurement, analyst)
- **Audit Log** — tracks actions performed via the GUI
- **SQL Runner** — sandboxed, read-only `SELECT`-only query tool

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `mysql` not recognized in terminal | Use the full path to `mysql.exe`, or add `C:\Program Files\MySQL\MySQL Server 8.0\bin` to your system PATH and restart the terminal |
| `<` redirection error in PowerShell | PowerShell doesn't support `<` — use `Get-Content file.sql \| mysql ...` instead, or switch to Command Prompt |
| `ERROR 1064` near `IF NOT EXISTS` on `CREATE INDEX` / `ADD CONSTRAINT` | MySQL doesn't support `IF NOT EXISTS` for those statements — run them without that clause |
| `Duplicate entry` error re-running `DB_schema.sql` | The data's already loaded — don't re-run it, or `DROP DATABASE fashion_business; CREATE DATABASE fashion_business;` first for a clean reload |
| `git push` gives `403` / permission denied | Your `origin` remote is likely pointing to the wrong repo — check with `git remote -v` and fix with `git remote set-url origin <your-repo-url>` |
| `DB connection error` in the Streamlit app | Check `.env` values match your actual MySQL credentials, and confirm the MySQL service is running |

---

## Setting Up on a New Machine (Quick Reference)

```powershell
git clone https://github.com/Rahul-Suttakoti/Fashion-Business-Management-System.git
cd Fashion-Business-Management-System
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
# create .env manually (see step 6 above — it's not in the repo)
# create the DB and load DB_schema.sql + Triggers_Functions_procedures.sql (see steps 5, 7, 8)
python create_admin.py
streamlit run app.py
```

## Security Notes

- `.env` is git-ignored and must never be committed — it holds your MySQL root password.
- Passwords for app users (`app_users` table) are stored as salted SHA-256 hashes, not plaintext.
