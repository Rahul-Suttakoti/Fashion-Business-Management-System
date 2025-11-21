# app.py
"""
Streamlit GUI for Fashion Business DB (patched + additions)
- Robust datetime handling
- Collections & Designers and Suppliers & Fabrics pages fixed for empty DBs
- Inventory removal (set to 0 / delete) added
- Purchase Orders expected_delivery fixed
- ProcessSale caller adapts to 4- or 5-arg procedure in DB
- st.rerun used (with shim for older Streamlit)
- Added: GetDesignerPortfolio, MonthlySalesReport (Procedures & Functions)
- Added: Complete Product Info and Sales Performance by Store (Reports)
Requirements:
 pip install streamlit mysql-connector-python python-dotenv pandas matplotlib
Run:
 streamlit run app.py
"""

import streamlit as st
import mysql.connector
from mysql.connector import errorcode
import pandas as pd
import os
from dotenv import load_dotenv
import hashlib
import binascii
import os as pyos
import matplotlib.pyplot as plt
import datetime as _dt

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASS", ""),
    "database": os.getenv("DB_NAME", "fashion_business"),
    "port": int(os.getenv("DB_PORT", "3306"))
}

# ---------------- DB helpers ----------------
@st.cache_resource(ttl=600)
def get_db_conn():
    try:
        cnx = mysql.connector.connect(**DB_CONFIG)
        return cnx
    except mysql.connector.Error as err:
        st.error(f"DB connection error: {err}")
        return None

def run_query(query, params=None):
    cnx = get_db_conn()
    if not cnx:
        return pd.DataFrame()
    cur = cnx.cursor(dictionary=True)
    try:
        cur.execute(query, params or ())
        if cur.description:
            cols = [c[0] for c in cur.description]
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=cols)
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Query error: {e}")
        return pd.DataFrame()
    finally:
        cur.close()

def run_modification(query, params=None):
    cnx = get_db_conn()
    if not cnx:
        st.error("No DB connection.")
        return False
    cur = cnx.cursor()
    try:
        cur.execute(query, params or ())
        cnx.commit()
        return True
    except Exception as e:
        st.error(f"Execution error: {e}")
        try:
            cnx.rollback()
        except:
            pass
        return False
    finally:
        cur.close()

def call_proc(proc_name, params=()):
    cnx = get_db_conn()
    if not cnx:
        st.error("No DB connection.")
        return None
    cur = cnx.cursor()
    try:
        cur.callproc(proc_name, params)
        results = []
        for result in cur.stored_results():
            results.append(pd.DataFrame(result.fetchall(), columns=[c[0] for c in result.description]))
        return results
    except Exception as e:
        st.error(f"Stored procedure error: {e}")
        return None
    finally:
        cur.close()

def call_function_sql_scalar(func_sql, params=()):
    cnx = get_db_conn()
    if not cnx:
        st.error("No DB connection.")
        return None
    cur = cnx.cursor()
    try:
        cur.execute(func_sql, params)
        res = cur.fetchone()
        return res[0] if res else None
    except Exception as e:
        st.error(f"Function call error: {e}")
        return None
    finally:
        cur.close()

def get_proc_param_count(proc_name):
    """Return number of IN parameters for a stored procedure in the current DB.
       This uses information_schema.parameters; if unavailable, returns None."""
    q = """
    SELECT COUNT(*) AS cnt
    FROM information_schema.parameters
    WHERE specific_schema = %s AND specific_name = %s
      AND parameter_mode IN ('IN','INOUT')
    """
    df = run_query(q, (DB_CONFIG['database'], proc_name))
    if df is None or df.empty:
        return None
    try:
        return int(df['cnt'].iloc[0])
    except:
        return None

# ---------------- support tables creation ----------------
def column_exists(table_name, column_name):
    q = """
    SELECT COUNT(*) cnt FROM information_schema.columns
    WHERE table_schema = %s AND table_name = %s AND column_name = %s
    """
    df = run_query(q, (DB_CONFIG['database'], table_name, column_name))
    if df.empty:
        return False
    return int(df['cnt'].iloc[0]) > 0

def ensure_app_users_table():
    q = """
    CREATE TABLE IF NOT EXISTS app_users (
        app_user_id INT PRIMARY KEY AUTO_INCREMENT,
        username VARCHAR(100) UNIQUE,
        role VARCHAR(50),
        password_hash VARCHAR(128),
        salt VARCHAR(64),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    run_modification(q)

def ensure_purchase_orders_table():
    q = """
    CREATE TABLE IF NOT EXISTS Purchase_Orders (
        po_id INT PRIMARY KEY AUTO_INCREMENT,
        item_id INT,
        supplier_id INT,
        quantity_ordered INT,
        status VARCHAR(50) DEFAULT 'OPEN',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expected_delivery DATE,
        notes TEXT,
        FOREIGN KEY (item_id) REFERENCES Clothing_Items(item_id),
        FOREIGN KEY (supplier_id) REFERENCES Suppliers(supplier_id)
    );
    """
    run_modification(q)

def ensure_audit_log_table():
    q = """
    CREATE TABLE IF NOT EXISTS audit_log (
        audit_id INT PRIMARY KEY AUTO_INCREMENT,
        app_user_id INT,
        username VARCHAR(100),
        action VARCHAR(100),
        table_name VARCHAR(100),
        row_id VARCHAR(100),
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    run_modification(q)

ensure_app_users_table()
ensure_purchase_orders_table()
ensure_audit_log_table()

# ---------------- security: password hashing ----------------
def make_salt():
    return binascii.hexlify(pyos.urandom(16)).decode()

def hash_password(password, salt):
    return hashlib.sha256((salt + password).encode()).hexdigest()

def create_app_user(username, role, password):
    salt = make_salt()
    phash = hash_password(password, salt)
    return run_modification("INSERT INTO app_users (username, role, password_hash, salt) VALUES (%s,%s,%s,%s)", (username, role, phash, salt))

def authenticate_user(username, password):
    df = run_query("SELECT * FROM app_users WHERE username = %s", (username,))
    if df is None or df.empty:
        return None
    row = df.iloc[0]
    salt = row.get('salt')
    stored = row.get('password_hash')
    if salt is None or stored is None:
        return None
    if hash_password(password, salt) == stored:
        return row.to_dict()
    return None

# ---------------- audit logging ----------------
def audit_log(app_user_id, username, action, table_name, row_id, details):
    run_modification(
        "INSERT INTO audit_log (app_user_id, username, action, table_name, row_id, details) VALUES (%s,%s,%s,%s,%s,%s)",
        (app_user_id, username, action, table_name, str(row_id), details)
    )

# ---------------- session & login ----------------
if "app_user" not in st.session_state:
    st.session_state["app_user"] = None

def login_user(username, password):
    user = authenticate_user(username, password)
    if user:
        st.session_state["app_user"] = user
        st.success(f"Logged in as {username} ({user['role']})")
        return True
    else:
        st.error("Invalid username or password")
        return False

def logout():
    st.session_state["app_user"] = None

# backward-compatible rerun shim
if not hasattr(st, "rerun") and hasattr(st, "experimental_rerun"):
    st.rerun = st.experimental_rerun

# ---------------- sidebar & navigation ----------------
st.sidebar.title("FashionDB App (patched + additions)")
st.sidebar.markdown("**DB**: " + DB_CONFIG['database'])
st.sidebar.divider()

if st.session_state["app_user"]:
    st.sidebar.info(f"User: {st.session_state['app_user']['username']}\nRole: {st.session_state['app_user']['role']}")
    if st.sidebar.button("Logout"):
        logout()
else:
    st.sidebar.markdown("**Login**")
    login_username = st.sidebar.text_input("Username", key="username_input")
    login_password = st.sidebar.text_input("Password", type="password", key="password_input")
    if st.sidebar.button("Login"):
        login_user(login_username.strip(), login_password)

st.sidebar.markdown("---")
page = st.sidebar.selectbox("Page", [
    "Dashboard", "Items", "Inventory", "Sales", "Suppliers & Fabrics",
    "Collections & Designers", "Alerts & Triggers", "Procedures & Functions",
    "Reports", "Admin (App Users)", "Purchase Orders", "Audit Log", "SQL Runner"
])

def current_role():
    user = st.session_state.get("app_user")
    return user['role'] if user else None

def current_user_id():
    user = st.session_state.get("app_user")
    return int(user['app_user_id']) if user else None

# ---------------- main app ----------------
st.title("Fashion Business — Management GUI (patched + additions)")

# ---------- Dashboard ----------
if page == "Dashboard":
    st.header("Dashboard")
    df_rev = run_query("SELECT IFNULL(SUM(total_amount),0) AS total_revenue FROM Sales")
    total_revenue = float(df_rev['total_revenue'].iloc[0]) if not df_rev.empty else 0.0
    df_low = run_query("SELECT COUNT(*) AS low_count FROM Inventory WHERE quantity_in_stock <= reorder_level")
    low_count = int(df_low['low_count'].iloc[0]) if not df_low.empty else 0
    col1, col2 = st.columns(2)
    col1.metric("Total Revenue", f"₹{total_revenue:,.2f}")
    col2.metric("Low Stock Items", f"{low_count}")
    st.markdown("### Recent Sales")
    df_sales = run_query("SELECT s.sale_id, s.sale_date, st.name as store_name, ci.name as item_name, s.quantity_sold, s.total_amount, s.payment FROM Sales s JOIN Stores st ON st.store_id = s.store_id JOIN Clothing_Items ci ON ci.item_id = s.item_id ORDER BY s.sale_date DESC LIMIT 10")
    st.dataframe(df_sales)

    st.markdown("### Monthly Revenue Trend (last 12 months)")
    q = """
    SELECT YEAR(sale_date) AS yr, MONTH(sale_date) AS mon, IFNULL(SUM(total_amount),0) AS revenue
    FROM Sales
    WHERE sale_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
    GROUP BY YEAR(sale_date), MONTH(sale_date)
    ORDER BY YEAR(sale_date), MONTH(sale_date);
    """
    df_month = run_query(q)
    if df_month is not None and not df_month.empty:
        today_dt = _dt.datetime.now()
        months = []
        revs = []
        for i in range(11, -1, -1):
            d = today_dt - pd.DateOffset(months=i)
            y = d.year; m = d.month
            months.append(f"{y}-{m:02d}")
            match = df_month[(df_month['yr'] == y) & (df_month['mon'] == m)]
            revs.append(float(match['revenue'].iloc[0]) if not match.empty else 0.0)
        fig, ax = plt.subplots()
        ax.plot(months, revs, marker='o')
        ax.set_title("Monthly Revenue (last 12 months)")
        ax.set_xlabel("Month")
        ax.set_ylabel("Revenue (₹)")
        plt.xticks(rotation=45)
        st.pyplot(fig)
    else:
        st.info("Not enough sales data to show monthly trend.")

# ---------- Items ----------
elif page == "Items":
    st.header("Clothing Items — CRUD (Admin/Manager)")
    role = current_role()
    st.info("Only admin can create/delete items; manager can update.")
    if role == "admin":
        with st.form("create_item"):
            st.subheader("Create new item")
            name = st.text_input("Name")
            size = st.text_input("Size")
            color = st.text_input("Color")
            price = st.number_input("Price", min_value=0.0, step=1.0)
            cols = run_query("SELECT collection_id, name FROM Collections")
            collection_id = None
            if not cols.empty:
                col_map = dict(zip(cols['collection_id'], cols['name']))
                collection_id = st.selectbox("Collection", options=list(col_map.keys()), format_func=lambda x: col_map[x])
            submitted = st.form_submit_button("Create Item")
            if submitted:
                q = "INSERT INTO Clothing_Items (name, size, color, price, collection_id) VALUES (%s,%s,%s,%s,%s)"
                ok = run_modification(q, (name, size, color, price, collection_id))
                if ok:
                    st.success("Item created.")
                    audit_log(current_user_id(), st.session_state['app_user']['username'], "CREATE_ITEM", "Clothing_Items", "", f"{name}")
                    st.rerun()
    df = run_query("SELECT ci.item_id, ci.name, ci.size, ci.color, ci.price, c.name AS collection FROM Clothing_Items ci LEFT JOIN Collections c ON ci.collection_id = c.collection_id")
    if df is None or df.empty:
        st.info("No clothing items found. Create items using the form above.")
    else:
        st.dataframe(df)
    if role in ("admin", "manager"):
        st.subheader("Update item")
        items = run_query("SELECT item_id, name FROM Clothing_Items")
        if not items.empty:
            item_map = dict(zip(items['item_id'], items['name']))
            sel = st.selectbox("Item to update", list(item_map.keys()), format_func=lambda x: item_map[x])
            current = run_query("SELECT * FROM Clothing_Items WHERE item_id = %s", (sel,))
            if not current.empty:
                row = current.iloc[0]
                new_name = st.text_input("Name", row['name'])
                new_price = st.number_input("Price", value=float(row['price']), step=1.0)
                if st.button("Apply update"):
                    ok = run_modification("UPDATE Clothing_Items SET name=%s, price=%s WHERE item_id=%s", (new_name, new_price, sel))
                    if ok:
                        st.success("Updated.")
                        audit_log(current_user_id(), st.session_state['app_user']['username'], "UPDATE_ITEM", "Clothing_Items", sel, f"name->{new_name},price->{new_price}")
                        st.rerun()
    if role == "admin":
        st.subheader("Delete item")
        del_items = run_query("SELECT item_id, name FROM Clothing_Items")
        if not del_items.empty:
            del_map = dict(zip(del_items['item_id'], del_items['name']))
            to_del = st.selectbox("Item to delete", list(del_map.keys()), format_func=lambda x: del_map[x])
            if st.button("Delete item"):
                ok = run_modification("DELETE FROM Clothing_Items WHERE item_id=%s", (to_del,))
                if ok:
                    st.success("Deleted.")
                    audit_log(current_user_id(), st.session_state['app_user']['username'], "DELETE_ITEM", "Clothing_Items", to_del, "deleted")
                    st.rerun()

# ---------- Inventory ----------
elif page == "Inventory":
    st.header("Inventory Management")
    inv = run_query("SELECT i.inventory_id, i.item_id, ci.name AS item_name, i.quantity_in_stock, i.reorder_level FROM Inventory i JOIN Clothing_Items ci ON i.item_id = ci.item_id")
    if inv is None or inv.empty:
        st.info("No inventory rows. Add inventory via Items/Admin pages.")
    else:
        st.dataframe(inv)

    st.subheader("Update stock (increase/decrease)")
    items = run_query("SELECT inventory_id, item_id, quantity_in_stock, reorder_level FROM Inventory")
    if items is not None and not items.empty:
        inv_map = dict(zip(items['inventory_id'], items['item_id']))
        chosen_inv = st.selectbox("Select inventory row", list(inv_map.keys()))
        cur_row = items[items['inventory_id'] == chosen_inv].iloc[0]
        cur_qty = int(cur_row['quantity_in_stock'])
        st.write(f"Current quantity: {cur_qty}  |  Reorder level: {int(cur_row['reorder_level'])}")
        delta = st.number_input("Change (positive to add, negative to remove)", value=0, step=1)
        if st.button("Apply stock change"):
            ok = run_modification("UPDATE Inventory SET quantity_in_stock = quantity_in_stock + %s WHERE inventory_id = %s", (delta, chosen_inv))
            if ok:
                st.success("Inventory updated.")
                audit_log(current_user_id(), st.session_state['app_user']['username'], "UPDATE_INVENTORY", "Inventory", chosen_inv, f"delta={delta}")
                st.rerun()

        st.markdown("**Remove / Delete inventory (admin only)**")
        if current_role() == "admin":
            if st.button("Set quantity to 0 (Mark as empty)"):
                ok = run_modification("UPDATE Inventory SET quantity_in_stock = 0 WHERE inventory_id = %s", (chosen_inv,))
                if ok:
                    st.success("Inventory quantity set to 0.")
                    audit_log(current_user_id(), st.session_state['app_user']['username'], "ZERO_INVENTORY", "Inventory", chosen_inv, "set to 0")
                    st.rerun()
            if st.button("Delete inventory row"):
                ok = run_modification("DELETE FROM Inventory WHERE inventory_id = %s", (chosen_inv,))
                if ok:
                    st.success("Inventory row deleted.")
                    audit_log(current_user_id(), st.session_state['app_user']['username'], "DELETE_INVENTORY", "Inventory", chosen_inv, "deleted")
                    st.rerun()
    else:
        st.info("No inventory rows to update. Add inventory via Items page.")

# ---------- Sales ----------
elif page == "Sales":
    st.header("Sales - ProcessSale and recent sales")
    st.markdown("Use ProcessSale (stored proc) to process sales. App will adapt to procedure signature (4 or 5 params).")
    items = run_query("SELECT item_id, name FROM Clothing_Items")
    stores = run_query("SELECT store_id, name FROM Stores")
    if not items.empty and not stores.empty:
        item_map = dict(zip(items['item_id'], items['name']))
        store_map = dict(zip(stores['store_id'], stores['name']))
        with st.form("proc_sale"):
            sel_item = st.selectbox("Item", list(item_map.keys()), format_func=lambda x: item_map[x])
            sel_store = st.selectbox("Store", list(store_map.keys()), format_func=lambda x: store_map[x])
            qty = st.number_input("Quantity", min_value=1, step=1)
            payment = st.selectbox("Payment method", ["Cash", "Credit Card", "Debit Card", "UPI", "Net Banking"])
            submit = st.form_submit_button("Process Sale")
            if submit:
                # adapt to procedure signature
                cnt = get_proc_param_count("ProcessSale")
                if cnt is None:
                    st.warning("Could not determine ProcessSale parameter count; attempting 4-arg call.")
                    params = (sel_item, sel_store, qty, payment)
                elif cnt >= 5:
                    # assume signature: (p_sale_date, p_store_id, p_item_id, p_quantity, p_payment)
                    sale_date = _dt.datetime.now().date()
                    params = (sale_date, sel_store, sel_item, qty, payment)
                else:
                    # assume signature: (p_item_id, p_store_id, p_quantity, p_payment)
                    params = (sel_item, sel_store, qty, payment)
                res = call_proc("ProcessSale", params)
                if res is not None:
                    st.success("ProcessSale invoked. Check Sales and Inventory.")
                    audit_log(current_user_id(), st.session_state['app_user']['username'], "PROCESS_SALE", "Sales", "", f"item={sel_item},store={sel_store},qty={qty}")
                    st.rerun()
    else:
        st.info("Ensure Clothing_Items and Stores exist.")
    st.subheader("Recent Sales")
    df = run_query("SELECT s.sale_id, s.sale_date, st.name as store_name, ci.name as item_name, s.quantity_sold, s.total_amount, s.payment FROM Sales s JOIN Stores st ON st.store_id = s.store_id JOIN Clothing_Items ci ON ci.item_id = s.item_id ORDER BY s.sale_date DESC LIMIT 50")
    if df is None or df.empty:
        st.info("No sales yet.")
    else:
        st.dataframe(df)

# ---------- Purchase Orders ----------
elif page == "Purchase Orders":
    st.header("Purchase Orders (auto-create from Inventory_Alerts)")
    st.markdown("Auto-create a Purchase Order (PO) for an alert. The app attempts to pick a supplier by looking up fabrics used for that item and choosing the supplier with the lowest cost_per_meter.")
    alerts = run_query("SELECT * FROM Inventory_Alerts ORDER BY alert_date DESC LIMIT 100")
    st.subheader("Inventory Alerts")
    if alerts is None or alerts.empty:
        st.info("No inventory alerts found.")
    else:
        st.dataframe(alerts)

    st.subheader("Create PO from an alert")
    if alerts is not None and not alerts.empty:
        alert_map = dict(zip(alerts['alert_id'], alerts['item_id']))
        sel_alert = st.selectbox("Select alert", list(alert_map.keys()), format_func=lambda x: f"Alert {x} - item {alert_map[x]}")
        if st.button("Auto-create PO for selected alert"):
            item_id = alert_map[sel_alert]
            q_supplier = """
            SELECT f.supplier_id, s.name AS supplier_name, MIN(f.cost_per_meter) AS min_cost
            FROM Clothing_Item_Fabrics cif
            JOIN Fabrics f ON cif.fabric_id = f.fabric_id
            JOIN Suppliers s ON f.supplier_id = s.supplier_id
            WHERE cif.item_id = %s
            GROUP BY f.supplier_id, s.name
            ORDER BY min_cost ASC
            LIMIT 1
            """
            sup_df = run_query(q_supplier, (item_id,))
            if sup_df.empty:
                st.error("No supplier found for this item (no fabrics mapped). Create fabric mappings first.")
            else:
                supplier_id = int(sup_df['supplier_id'].iloc[0])
                inv_row = run_query("SELECT inventory_id, quantity_in_stock, reorder_level FROM Inventory WHERE item_id = %s", (item_id,))
                if inv_row.empty:
                    qty_order = 10
                else:
                    rq = int(inv_row['reorder_level'].iloc[0])
                    qty_order = max(10, rq * 2)
                # robust expected_delivery calculation
                expected_delivery = (_dt.datetime.now() + _dt.timedelta(days=7)).date()
                ok = run_modification(
                    "INSERT INTO Purchase_Orders (item_id, supplier_id, quantity_ordered, expected_delivery, notes) VALUES (%s,%s,%s,%s,%s)",
                    (item_id, supplier_id, qty_order, expected_delivery, f"Auto PO from alert {sel_alert}")
                )
                if ok:
                    st.success(f"Purchase Order created: item {item_id}, supplier {supplier_id}, qty {qty_order}")
                    po_df = run_query("SELECT po_id FROM Purchase_Orders ORDER BY created_at DESC LIMIT 1")
                    if not po_df.empty:
                        po_id = int(po_df['po_id'].iloc[0])
                        run_modification("UPDATE Inventory_Alerts SET message = CONCAT(message, ' | PO_CREATED:', %s) WHERE alert_id = %s", (str(po_id), sel_alert))
                        audit_log(current_user_id(), st.session_state['app_user']['username'], "CREATE_PO", "Purchase_Orders", po_id, f"from alert {sel_alert}, qty={qty_order}, supplier={supplier_id}")
                        st.rerun()
    else:
        st.info("No alerts to create PO from.")

    st.subheader("PO list")
    po_df = run_query("SELECT po_id, item_id, supplier_id, quantity_ordered, status, created_at, expected_delivery FROM Purchase_Orders ORDER BY created_at DESC LIMIT 100")
    if po_df is None or po_df.empty:
        st.info("No purchase orders.")
    else:
        st.dataframe(po_df)

# ---------- Suppliers & Fabrics ----------
elif page == "Suppliers & Fabrics":
    st.header("Suppliers & Fabrics")

    sup = run_query("SELECT * FROM Suppliers")
    if sup is None or sup.empty:
        st.info("No suppliers yet. Add a supplier below.")
    else:
        st.subheader("Suppliers")
        st.dataframe(sup)

    if current_role() in ("admin", "procurement"):
        with st.form("add_supplier"):
            st.markdown("**Add Supplier**")
            name = st.text_input("Supplier name")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            addr = st.text_area("Address")
            if st.form_submit_button("Add Supplier"):
                ok = run_modification("INSERT INTO Suppliers (name, email, phone, address) VALUES (%s,%s,%s,%s)", (name, email, phone, addr))
                if ok:
                    st.success("Supplier added.")
                    audit_log(current_user_id(), st.session_state['app_user']['username'], "CREATE_SUPPLIER", "Suppliers", "", f"{name}")
                    st.rerun()

    fabrics = run_query("SELECT f.fabric_id, f.material, f.cost_per_meter, s.name as supplier FROM Fabrics f LEFT JOIN Suppliers s ON f.supplier_id = s.supplier_id")
    if fabrics is None or fabrics.empty:
        st.info("No fabrics yet. Add fabrics below.")
    else:
        st.subheader("Fabrics")
        st.dataframe(fabrics)

    if current_role() in ("admin", "procurement"):
        with st.form("add_fabric"):
            st.markdown("**Add Fabric**")
            mat = st.text_input("Material")
            supplier_df = run_query("SELECT supplier_id, name FROM Suppliers")
            supplied = None
            if supplier_df is not None and not supplier_df.empty:
                sup_map = dict(zip(supplier_df['supplier_id'], supplier_df['name']))
                supplied = st.selectbox("Supplier", list(sup_map.keys()), format_func=lambda x: sup_map[x])
            else:
                st.info("Create a supplier first.")
            cost = st.number_input("Cost per meter", min_value=0.0)
            if st.form_submit_button("Add Fabric"):
                if supplied is None:
                    st.error("Select a supplier.")
                else:
                    ok = run_modification("INSERT INTO Fabrics (material, supplier_id, cost_per_meter) VALUES (%s,%s,%s)", (mat, supplied, cost))
                    if ok:
                        st.success("Fabric added.")
                        audit_log(current_user_id(), st.session_state['app_user']['username'], "CREATE_FABRIC", "Fabrics", "", f"{mat}")
                        st.rerun()

# ---------- Collections & Designers ----------
elif page == "Collections & Designers":
    st.header("Designers & Collections")

    # Designers section
    st.subheader("Designers")
    designers = run_query("SELECT * FROM Designers")
    if designers is None or designers.empty:
        st.info("No designers found. Create a new designer below.")
    else:
        st.dataframe(designers)

    # Create designer form (always visible for Admin)
    if current_role() == "admin":
        with st.form("add_designer"):
            st.markdown("**Add new Designer**")
            name = st.text_input("Name")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            style = st.text_input("Style")
            if st.form_submit_button("Add Designer"):
                ok = run_modification("INSERT INTO Designers (name, email, phone, style) VALUES (%s,%s,%s,%s)", (name, email, phone, style))
                if ok:
                    st.success("Designer added.")
                    audit_log(current_user_id(), st.session_state['app_user']['username'], "CREATE_DESIGNER", "Designers", "", f"{name}")
                    st.rerun()

    # Collections section
    st.subheader("Collections")
    cols = run_query("SELECT c.collection_id, c.name, c.season, c.year, d.name AS designer FROM Collections c LEFT JOIN Designers d ON c.designer_id = d.designer_id")
    if cols is None or cols.empty:
        st.info("No collections found. Create a new collection below.")
    else:
        st.dataframe(cols)

    # Create collection form (visible to admin or manager)
    if current_role() in ("admin", "manager"):
        with st.form("add_collection"):
            st.markdown("**Add new Collection**")
            colname = st.text_input("Collection name")
            season = st.text_input("Season")
            year = st.number_input("Year", min_value=2000, max_value=2100, value=_dt.datetime.now().year)
            designers_df = run_query("SELECT designer_id, name FROM Designers")
            designer_choice = None
            if designers_df is not None and not designers_df.empty:
                dm = dict(zip(designers_df['designer_id'], designers_df['name']))
                designer_choice = st.selectbox("Designer", list(dm.keys()), format_func=lambda x: dm[x])
            else:
                st.info("Create a designer first.")
            if st.form_submit_button("Add Collection"):
                if designer_choice is None:
                    st.error("You must select a designer.")
                else:
                    ok = run_modification("INSERT INTO Collections (name, season, year, designer_id) VALUES (%s,%s,%s,%s)", (colname, season, year, designer_choice))
                    if ok:
                        st.success("Collection added.")
                        audit_log(current_user_id(), st.session_state['app_user']['username'], "CREATE_COLLECTION", "Collections", "", f"{colname}")
                        st.rerun()

    # Designer Portfolio viewer
    st.subheader("Designer Portfolio")
    if designers is None or designers.empty:
        st.info("No designer portfolio to display. Create designers first.")
    else:
        designer_map = dict(zip(designers['designer_id'], designers['name']))
        sel = st.selectbox("Select designer to view portfolio", list(designer_map.keys()), format_func=lambda x: designer_map[x])
        if sel:
            d_info = run_query("SELECT * FROM Designers WHERE designer_id=%s", (sel,))
            d_cols = run_query("SELECT * FROM Collections WHERE designer_id=%s", (sel,))
            d_items = run_query("SELECT ci.* FROM Clothing_Items ci JOIN Collections c ON ci.collection_id = c.collection_id WHERE c.designer_id = %s", (sel,))
            st.subheader("Designer Info")
            st.dataframe(d_info)
            st.subheader("Collections")
            st.dataframe(d_cols)
            st.subheader("Items")
            st.dataframe(d_items)

# ---------- Alerts & Triggers ----------
elif page == "Alerts & Triggers":
    st.header("Inventory Alerts & Triggers")
    alerts = run_query("SELECT * FROM Inventory_Alerts ORDER BY alert_date DESC LIMIT 200")
    if alerts is None or alerts.empty:
        st.info("No inventory alerts.")
    else:
        st.dataframe(alerts)

    st.subheader("Simulate update to fire reorder trigger")
    inv = run_query("SELECT inventory_id, item_id, quantity_in_stock, reorder_level FROM Inventory")
    if inv is not None and not inv.empty:
        inv_map = dict(zip(inv['inventory_id'], inv['item_id']))
        choose = st.selectbox("Select inventory row", list(inv_map.keys()))
        rlevel = int(inv[inv['inventory_id'] == choose]['reorder_level'].iloc[0])
        new_qty = st.number_input("Set new quantity (≤ reorder_level to create alert)", value=rlevel, step=1)
        if st.button("Set quantity and trigger alert"):
            ok = run_modification("UPDATE Inventory SET quantity_in_stock = %s WHERE inventory_id = %s", (new_qty, choose))
            if ok:
                st.success("Inventory updated. Trigger will insert alert if condition met.")
                audit_log(current_user_id(), st.session_state['app_user']['username'], "SIMULATE_REORDER_TRIGGER", "Inventory", choose, f"set_qty={new_qty}")
                st.rerun()
    else:
        st.info("No inventory rows to simulate.")

# ---------- Procedures & Functions ----------
elif page == "Procedures & Functions":
    st.header("Call Procedures and Functions")
    st.subheader("GetItemFabricCost")
    items = run_query("SELECT item_id, name FROM Clothing_Items")
    if items is None or items.empty:
        st.info("No items found.")
    else:
        item_map = dict(zip(items['item_id'], items['name']))
        sel_item = st.selectbox("Item", list(item_map.keys()), format_func=lambda x: item_map[x])
        if st.button("Compute fabric cost"):
            val = call_function_sql_scalar("SELECT GetItemFabricCost(%s)", (sel_item,))
            st.write(f"Fabric cost for '{item_map[sel_item]}': ₹{val}")

    st.subheader("GetProfitMargin")
    if items is not None and not items.empty:
        sel_item2 = st.selectbox("Item for margin", list(item_map.keys()), key="margin_item", format_func=lambda x: item_map[x])
        if st.button("Compute profit margin"):
            val = call_function_sql_scalar("SELECT GetProfitMargin(%s)", (sel_item2,))
            st.write(f"Profit margin for '{item_map[sel_item2]}': {val}%")

    st.subheader("GetDesignerRevenue")
    designers = run_query("SELECT designer_id, name FROM Designers")
    if designers is None or designers.empty:
        st.info("No designers found.")
    else:
        dmap = dict(zip(designers['designer_id'], designers['name']))
        sel_d = st.selectbox("Designer", list(dmap.keys()), format_func=lambda x: dmap[x])
        if st.button("Compute designer revenue"):
            val = call_function_sql_scalar("SELECT GetDesignerRevenue(%s)", (sel_d,))
            st.write(f"Revenue for designer '{dmap[sel_d]}': ₹{val}")

    # ---------------------------------------------------
    # Extra Procedures: GetDesignerPortfolio & MonthlySalesReport
    # ---------------------------------------------------
    st.divider()
    st.subheader("Extra Stored Procedures")

    # ---- GetDesignerPortfolio ----
    st.markdown("**GetDesignerPortfolio (designer_id)**")
    designers_df = run_query("SELECT designer_id, name FROM Designers")
    if designers_df is None or designers_df.empty:
        st.info("No designers found.")
    else:
        dmap = dict(zip(designers_df['designer_id'], designers_df['name']))
        sel_d = st.selectbox("Select Designer (for portfolio)", list(dmap.keys()), format_func=lambda x: dmap[x])
        if st.button("Show Designer Portfolio"):
            # Call the stored procedure
            res = call_proc("GetDesignerPortfolio", (sel_d,))
            if res and len(res) >= 1:
                st.success(f"Portfolio for Designer: {dmap[sel_d]}")
                # Procedure may return multiple result sets: Designer info, Collections, Items
                labels = ["Designer Info", "Collections", "Items"]
                for i, dfp in enumerate(res):
                    st.markdown(f"#### {labels[i] if i < len(labels) else f'Result {i+1}'}")
                    st.dataframe(dfp)
            else:
                st.warning("No data returned for this designer.")

    # ---- MonthlySalesReport ----
    st.markdown("**MonthlySalesReport (store_id, month, year)**")
    stores_df = run_query("SELECT store_id, name FROM Stores")
    if stores_df is None or stores_df.empty:
        st.info("No stores found.")
    else:
        smap = dict(zip(stores_df['store_id'], stores_df['name']))
        sel_store = st.selectbox("Select Store", list(smap.keys()), format_func=lambda x: smap[x])
        col_m, col_y = st.columns(2)
        month = col_m.number_input("Month (1-12)", min_value=1, max_value=12, value=_dt.datetime.now().month)
        year = col_y.number_input("Year", min_value=2000, max_value=2100, value=_dt.datetime.now().year)
        if st.button("Generate Monthly Sales Report"):
            res = call_proc("MonthlySalesReport", (sel_store, month, year))
            if res and len(res) >= 1:
                st.success(f"Monthly Sales Report for {smap[sel_store]} ({month}/{year})")
                st.dataframe(res[0])
            else:
                st.warning("No data found for this period.")

# ---------- Reports ----------
elif page == "Reports":
    st.header("Reports (Nested / Join / Aggregate queries)")
    st.markdown("Run example queries required by rubric: nested query, join query, aggregate query.")
    if st.button("Nested: Items more expensive than collection average"):
        df = run_query("""
        SELECT ci.item_id, ci.name, ci.price, c.name AS collection_name
        FROM Clothing_Items ci
        JOIN Collections c ON ci.collection_id = c.collection_id
        WHERE ci.price > (
            SELECT AVG(ci2.price) FROM Clothing_Items ci2 WHERE ci2.collection_id = ci.collection_id
        ) ORDER BY c.name, ci.price DESC
        """)
        if df is None or df.empty:
            st.info("No results.")
        else:
            st.dataframe(df)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV (Nested)", csv, "nested_items.csv")
    if st.button("Join: Full product info (item + designer + supplier)"):
        df = run_query("""
        SELECT ci.item_id, ci.name AS item_name, ci.price, c.name AS collection_name, d.name AS designer_name, f.material AS fabric, s.name AS supplier
        FROM Clothing_Items ci
        LEFT JOIN Collections c ON ci.collection_id = c.collection_id
        LEFT JOIN Designers d ON c.designer_id = d.designer_id
        LEFT JOIN Uses u ON ci.item_id = u.item_id
        LEFT JOIN Fabrics f ON u.fabric_id = f.fabric_id
        LEFT JOIN Suppliers s ON f.supplier_id = s.supplier_id
        """)
        if df is None or df.empty:
            st.info("No results.")
        else:
            st.dataframe(df)
            st.download_button("Download CSV (Join)", df.to_csv(index=False).encode('utf-8'), "join_products.csv")
    if st.button("Aggregate: Top Selling Items"):
        df = run_query("""
        SELECT ci.item_id, ci.name, IFNULL(SUM(s.quantity_sold),0) AS qty_sold, IFNULL(SUM(s.total_amount),0) AS revenue
        FROM Clothing_Items ci
        LEFT JOIN Sales s ON ci.item_id = s.item_id
        GROUP BY ci.item_id, ci.name
        ORDER BY qty_sold DESC LIMIT 10
        """)
        if df is None or df.empty:
            st.info("No results.")
        else:
            st.dataframe(df)
            st.download_button("Download CSV (Aggregate)", df.to_csv(index=False).encode('utf-8'), "top_sellers.csv")

    # ---------------------------------------------------
    # Extra Join Queries
    # ---------------------------------------------------
    st.divider()
    st.subheader("Extra Join Queries")

    # ---- Join Query 1: Complete Product Information ----
    st.markdown("**Join Query 1: Complete Product Information (Item + Designer + Supplier)**")
    if st.button("Run Complete Product Info Query"):
        q = """
        SELECT ci.item_id, ci.name AS item_name, ci.price, 
               c.name AS collection_name, d.name AS designer_name, 
               f.material AS fabric, s.name AS supplier_name
        FROM Clothing_Items ci
        LEFT JOIN Collections c ON ci.collection_id = c.collection_id
        LEFT JOIN Designers d ON c.designer_id = d.designer_id
        LEFT JOIN Clothing_Item_Fabrics cif ON ci.item_id = cif.item_id
        LEFT JOIN Fabrics f ON cif.fabric_id = f.fabric_id
        LEFT JOIN Suppliers s ON f.supplier_id = s.supplier_id;
        """
        df = run_query(q)
        if df is None or df.empty:
            st.warning("No data found for this join.")
        else:
            st.dataframe(df)
            st.download_button("Download CSV (Complete Product Info)", df.to_csv(index=False).encode('utf-8'), "complete_product_info.csv")

    # ---- Join Query 2: Sales Performance by Store ----
    st.markdown("**Join Query 2: Sales Performance by Store with Item Details**")
    if st.button("Run Sales Performance Query"):
        q = """
        SELECT st.name AS store_name, ci.name AS item_name, 
               SUM(s.quantity_sold) AS total_quantity, 
               SUM(s.total_amount) AS total_revenue
        FROM Sales s
        JOIN Stores st ON s.store_id = st.store_id
        JOIN Clothing_Items ci ON s.item_id = ci.item_id
        GROUP BY st.name, ci.name
        ORDER BY store_name, total_revenue DESC;
        """
        df = run_query(q)
        if df is None or df.empty:
            st.warning("No data found for this join.")
        else:
            st.dataframe(df)
            st.download_button("Download CSV (Sales Performance)", df.to_csv(index=False).encode('utf-8'), "sales_performance_by_store.csv")

# ---------- Admin (App Users) ----------
elif page == "Admin (App Users)":
    st.header("App Users (create / assign roles) — Admin only")
    role = current_role()
    if role != "admin":
        st.warning("Only Admins can manage app users. Login as an admin to create app users.")
    df = run_query("SELECT app_user_id, username, role, created_at FROM app_users ORDER BY created_at DESC")
    if df is None or df.empty:
        st.info("No app users found.")
    else:
        st.dataframe(df)
    if role == "admin":
        st.subheader("Create app user with password")
        with st.form("create_app_user"):
            uname = st.text_input("Username")
            role_sel = st.selectbox("Role", ["admin", "manager", "cashier", "procurement", "analyst"])
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Create user"):
                if len(uname.strip()) == 0 or len(pw.strip()) < 4:
                    st.error("Username non-empty and password >= 4 chars")
                else:
                    ok = create_app_user(uname.strip(), role_sel, pw.strip())
                    if ok:
                        st.success("App user created.")
                        audit_log(current_user_id(), st.session_state['app_user']['username'], "CREATE_APP_USER", "app_users", "", f"{uname}")
                        st.rerun()

# ---------- Audit Log ----------
elif page == "Audit Log":
    st.header("Audit Log (actions performed via GUI)")
    logs = run_query("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 500")
    if logs is None or logs.empty:
        st.info("No audit logs yet.")
    else:
        st.dataframe(logs)
        if st.button("Export audit log to CSV"):
            csv = logs.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "audit_log.csv")

# ---------- SQL Runner ----------
elif page == "SQL Runner":
    st.header("SQL Runner (SELECT only)")
    st.markdown("Use for read-only testing. Only SELECT queries are allowed from GUI.")
    q = st.text_area("Write SELECT query here (read-only):", height=200)
    if st.button("Run SELECT"):
        q_trim = q.strip().lower()
        if not q_trim.startswith("select"):
            st.error("Only SELECT queries are allowed.")
        else:
            df = run_query(q)
            if df is None or df.empty:
                st.info("No results.")
            else:
                st.dataframe(df)

# ---------- footer ----------
st.markdown("---")
st.text("Patched Streamlit GUI for Fashion Business DB — use responsibly.")
