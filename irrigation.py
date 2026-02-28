import streamlit as st
import pandas as pd
import io
from reportlab.platypus import SimpleDocTemplate, Table

from auth import check_login
from crud import *

# --------------------------------
# PAGE CONFIG
# --------------------------------
st.set_page_config(
    page_title="Irrigation Management Dashboard",
    page_icon="📊",
    layout="wide"
)

if st.session_state.get("insert_success"):
    st.toast("Inserted successfully")
    del st.session_state["insert_success"]


# --------------------------------
# SESSION INIT
# --------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = None

if "role" not in st.session_state:
    st.session_state.role = None

if "sheets" not in st.session_state:
    st.session_state.sheets = None


# --------------------------------
# ROLE HELPERS
# --------------------------------
def is_admin():
    return st.session_state.role == "admin"

def is_user():
    return st.session_state.role == "user"


# --------------------------------
# DOWNLOAD HELPERS
# --------------------------------
def to_excel_bytes(df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buffer.getvalue()

def to_csv_bytes(df):
    return df.to_csv(index=False).encode()

def to_pdf_bytes(df):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    table = Table([df.columns.tolist()] + df.values.tolist())
    doc.build([table])
    return buffer.getvalue()


# --------------------------------
# LOGIN
# --------------------------------
if not st.session_state.logged_in:

    st.title("Login")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        user = check_login(u, p)

        if user:
            st.session_state.logged_in = True
            st.session_state.username = user["username"]
            st.session_state.role = user["role"]
            st.rerun()
        else:
            st.error("Invalid login")

    st.stop()


# --------------------------------
# SIDEBAR
# --------------------------------
st.sidebar.write(f"User: {st.session_state.username}")
st.sidebar.write(f"Role: {st.session_state.role}")

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()


# --------------------------------
# LOAD TABLES FROM DATABASE
# --------------------------------
if not st.session_state.sheets:
    st.session_state.sheets = get_all_tables()

if not st.session_state.sheets:
    st.error("No tables found in database")
    st.stop()


# --------------------------------
# SELECT TABLE
# --------------------------------
sheet = st.sidebar.radio("Select Table", st.session_state.sheets)


# --------------------------------
# LOAD DATA
# --------------------------------
df = get_table_data(sheet)
columns = [c for c in df.columns if c != "id"]

st.title(f"Table - {sheet}")


# --------------------------------
# SEARCH
# --------------------------------
search = st.text_input("Search")

if search:
    df = search_data(sheet, search)


# --------------------------------
# VIEW DATA (ADMIN)
# --------------------------------
if is_admin():
    st.subheader("All Records")
    st.data_editor(df, use_container_width=True, height=600, disabled=True)


# --------------------------------
# DOWNLOAD
# --------------------------------
if is_admin():
    st.subheader("Download Data")

    c1, c2, c3 = st.columns(3)
    c1.download_button("Excel", to_excel_bytes(df), f"{sheet}.xlsx")
    c2.download_button("CSV", to_csv_bytes(df), f"{sheet}.csv")
    c3.download_button("PDF", to_pdf_bytes(df), f"{sheet}.pdf")


# --------------------------------
# INSERT FORM
# --------------------------------
st.subheader("Add Record")

if "form_key" not in st.session_state:
    st.session_state.form_key = 0

form_data = {}

with st.form(key=f"form_{st.session_state.form_key}"):

    for col in columns:

        if "date" in col.lower():
            form_data[col] = st.date_input(col, value=None)

        elif "year" in col.lower():
            form_data[col] = st.number_input(col, 2000, 2100, step=1)

        else:
            form_data[col] = st.text_input(col)

    if st.form_submit_button("Insert"):
        insert_record(sheet, form_data)
        st.session_state.form_key += 1
        st.session_state.insert_success = True
        st.rerun()


# --------------------------------
# EDIT DELETE
# --------------------------------
if is_admin():

    st.subheader("Edit / Delete")

    row_id = st.number_input("Row ID", step=1)

    col1, col2 = st.columns(2)

    if col1.button("Delete"):
        delete_record(sheet, row_id)
        st.rerun()

    if col2.button("Load for Edit"):
        rec = df[df["id"] == row_id]
        if not rec.empty:
            st.session_state.edit_data = rec.iloc[0]

    if "edit_data" in st.session_state:

        st.subheader("Update Record")
        updated = {}

        for col in columns:
            updated[col] = st.text_input(
                col,
                str(st.session_state.edit_data.get(col, ""))
            )

        if st.button("Update"):
            update_record(sheet, row_id, updated)
            del st.session_state.edit_data
            st.rerun()