import datetime

import plotly.express as px
import streamlit as st
import pandas as pd
from auth import check_login
from crud import *


def clear_form_state():
    keys_to_delete = [
        key for key in st.session_state.keys()
        if "_" in key  # your form keys are table_column format
    ]

    for key in keys_to_delete:
        del st.session_state[key]

st.set_page_config(layout="wide")


def restore_draft_to_session(table, columns, user_id):

    draft_data = get_user_draft(table, user_id)

    if not draft_data:
        return

    for col_info in columns:

        col = col_info["column_name"]
        dtype = col_info["data_type"]

        key = f"{table}_{col}"

        # Skip if already set
        if key in st.session_state:
            continue

        if col not in draft_data:
            continue

        value = draft_data[col]

        if value is None:
            continue

        # Integer types
        if dtype in ("integer", "bigint", "smallint"):
            try:
                st.session_state[key] = int(value)
            except:
                st.session_state[key] = 0

        # Numeric types
        elif dtype in ("numeric", "double precision", "real"):
            try:
                st.session_state[key] = float(value)
            except:
                st.session_state[key] = 0.0

        # Date type
        elif dtype == "date":
            if isinstance(value, datetime.date):
                st.session_state[key] = value
            elif isinstance(value, str):
                try:
                    st.session_state[key] = datetime.datetime.strptime(
                        value, "%Y-%m-%d"
                    ).date()
                except:
                    st.session_state[key] = datetime.date.today()

        # Default → string
        else:
            st.session_state[key] = str(value)

# ================= SESSION =================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ================= LOGIN =================
if not st.session_state.logged_in:

    st.title("Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        user = check_login(u, p)
        if user:
            st.session_state.logged_in = True
            st.session_state.user_id = user["id"]
            st.session_state.username = user["username"]
            st.session_state.role = user["role"]
            st.rerun()
        else:
            st.error("Invalid login")

    st.stop()

# ================= USER INFO =================
user_id = st.session_state.user_id
is_admin = st.session_state.role == "admin"

# ================= TOP BAR =================
top_col1, top_col2, top_col3 = st.columns([7, 2, 1])

with top_col1:
    st.title("Canal Management Dashboard")

with top_col2:
    st.markdown(
        f"""
        <div style='text-align: right; font-weight: 600; padding-top: 8px;'>
            👤 {st.session_state.username}
        </div>
        """,
        unsafe_allow_html=True
    )

with top_col3:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

# =====================================================
# ================= USER SIDE =================
# =====================================================


can_edit = can_user_edit(user_id)

if not is_admin:

    tables = get_all_tables()

    # Section Tabs
    tabs = st.tabs(tables)

    # Progress
    percentage, completed, total = get_user_progress(user_id)
    st.progress(percentage / 100)
    st.info(f"Sections Completed: {completed} / {total}")

    for i, table in enumerate(tables):

        with tabs[i]:

            st.header(table)

            columns = get_table_columns(table, is_admin=False)
            restore_draft_to_session(table, columns, user_id)
            form_data = {}
            filled_fields = 0

            for col_info in columns:

                col = col_info["column_name"]
                dtype = col_info["data_type"]

                key = f"{table}_{col}"

                if dtype in ("integer", "bigint", "smallint"):
                    value = st.number_input(col, step=1, key=key)

                elif dtype in ("numeric", "double precision", "real"):
                    value = st.number_input(col, key=key)

                elif dtype == "date":
                    value = st.date_input(col, key=key)

                else:
                    value = st.text_input(col, key=key)

                form_data[col] = value

                if value not in ("", None):
                    filled_fields += 1

            if st.button(f"💾 Save {table}", key=f"save_{table}"):
                if not can_edit:
                    st.warning("You cannot edit this application unless it is rejected.")

                if filled_fields == 0:
                    st.warning("Section is empty.")
                else:
                    save_draft_record(table, form_data, user_id)
                    st.success("Section saved.")
                    st.rerun()

    # ---------- FINAL SUBMIT ----------
    st.markdown("---")
    st.subheader("Final Master Submission")

    if st.button("🚀 Submit Complete Application"):

        incomplete_sections = get_incomplete_forms(user_id)

        if incomplete_sections:
            st.error("All sections must be completed.")
            for sec in incomplete_sections:
                st.write(f"• {sec}")
        else:
            create_master_submission(user_id)
            st.success("Application submitted successfully.")
            st.rerun()

    # ---------- USER SUBMISSIONS ----------
    st.markdown("---")
    st.subheader("Your Submitted Applications")

    submissions = get_user_master_submissions(user_id)

    if submissions:
        for idx, sub in enumerate(submissions):
            with st.expander(

                f"Cycle {sub['cycle']} - {sub['status']} - {sub['submitted_at']}"
            ):
                if sub["status"] == "REJECTED" and sub.get("rejection_reason"):
                    st.error(f"Rejection Reason: {sub['rejection_reason']}")
                full_data = get_full_submission_data(sub["id"])

                for section_name, df_section in full_data.items():
                    st.write(f"### {section_name}")

                    # USER should NOT see system fields
                    cleaned_df = df_section.drop(
                        columns=[c for c in [
                            "submitted_at", "approval_status",
                            "approved_at", "submission_cycle",
                            "master_id", "created_by", "is_draft"
                        ] if c in df_section.columns]
                    )

                    st.dataframe(cleaned_df, use_container_width=True)
    else:
        st.info("No submissions yet.")

# =====================================================
# ================= ADMIN SIDE ========================
# =====================================================

if is_admin:

    st.markdown("---")
    st.subheader("📋 Master Submission Admin Panel")

    users_df = get_users_with_data()

    selected_user = st.selectbox("Select User", users_df["username"])

    user_row = users_df[users_df["username"] == selected_user].iloc[0]
    selected_user_id = int(user_row["id"])

    # -------- Status Metrics --------
    approved, rejected, pending = get_user_master_status_counts(selected_user_id)

    c1, c2, c3 = st.columns(3)
    c1.metric("🟢 Approved", approved)
    c2.metric("🔴 Rejected", rejected)
    c3.metric("🟡 Pending", pending)

    # ---------------- Status Pie Chart ----------------
    status_df = pd.DataFrame({
        "Status": ["Approved", "Rejected", "Pending"],
        "Count": [approved, rejected, pending]
    })

    color_map = {
        "Approved": "green",
        "Rejected": "red",
        "Pending": "orange"
    }

    fig_pie = px.pie(
        status_df,
        names="Status",
        values="Count",
        color="Status",
        color_discrete_map=color_map,
        title="Status Distribution",
        hole=0.4
    )

    st.plotly_chart(fig_pie, use_container_width=True)



    submissions = get_user_master_submissions(selected_user_id)

    if submissions:

        for idx, sub in enumerate(submissions):

            icon = "🟢" if sub["status"] == "APPROVED" else \
                   "🔴" if sub["status"] == "REJECTED" else "🟡"

            with st.expander(
                f"{icon} Cycle {sub['cycle']} - {sub['status']} - {sub['submitted_at']}"
            ):

                full_data = get_full_submission_data(sub["id"])

                for section_name, df_section in full_data.items():
                    st.write(f"### {section_name}")

                    # ADMIN sees EVERYTHING
                    st.dataframe(df_section, use_container_width=True)

                colA, colB = st.columns(2)



                rejection_reason = st.text_area(
                    "Rejection Reason",
                    key=f"reason_{sub['id']}_{idx}"
                )

                # 🔥 Approve button
                if colA.button(
                        f"Approve Form",
                        key=f"approve_{sub['id']}_{idx}"
                ):
                    approve_master_submission(sub["id"])
                    st.success("Application approved.")
                    st.rerun()

                # 🔥 Reject button
                if colB.button(
                        f"Reject Form ",
                        key=f"reject_{sub['id']}_{idx}"
                ):

                    if not rejection_reason.strip():
                        st.error("Rejection reason is mandatory.")
                    else:
                        reject_master_submission(sub["id"], rejection_reason)
                        st.warning("Application rejected.")
                        st.rerun()

                pdf = export_master_submission_pdf(sub["id"])

                st.download_button(
                    "Download Full Application PDF",
                    pdf,
                    file_name=f"{selected_user}_cycle_{sub['cycle']}.pdf",
                    mime="application/pdf"
                )

    else:
        st.info("No submissions found for this user.")
