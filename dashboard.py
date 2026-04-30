#!/usr/bin/env python3
"""Streamlit dashboard for Job Tracker."""

import streamlit as st
import pandas as pd
from pathlib import Path

DATA_FILE = Path(__file__).parent / 'jobs.xlsx'

STATUSES = ['Applied', 'Interview', 'Offer', 'Rejected', 'Unknown']

st.set_page_config(
    page_title="Job Tracker",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📋 Job Tracker")


# ── Data ─────────────────────────────────────────────────────────────────────
@st.cache_data
def load_data() -> pd.DataFrame:
    if not DATA_FILE.exists():
        return pd.DataFrame()
    df = pd.read_excel(DATA_FILE, engine='openpyxl')
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    return df


def save_data(df: pd.DataFrame) -> None:
    out = df.copy()
    out['Date'] = out['Date'].dt.strftime('%Y-%m-%d')
    out.to_excel(DATA_FILE, index=False, engine='openpyxl')
    st.cache_data.clear()


df = load_data()

if df.empty:
    st.warning("No data found. Run `python3 job_tracker.py` first.")
    st.stop()


# ── Metrics ───────────────────────────────────────────────────────────────────
counts = df['Status'].value_counts()
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total",     len(df))
c2.metric("Applied",   counts.get('Applied',   0))
c3.metric("Interview", counts.get('Interview', 0))
c4.metric("Offer",     counts.get('Offer',     0))
c5.metric("Rejected",  counts.get('Rejected',  0))
c6.metric("Unknown",   counts.get('Unknown',   0))

# Conversion rate: Applied → Interview
applied_n  = counts.get('Applied',   0)
interview_n = counts.get('Interview', 0)
total_n    = applied_n + interview_n + counts.get('Offer', 0) + counts.get('Rejected', 0)
if total_n > 0:
    rate = round(interview_n / total_n * 100, 1)
    st.caption(f"Interview rate: **{rate}%** of tracked applications reached interview stage")

st.divider()


# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")

    sel_status = st.multiselect(
        "Status",
        options=STATUSES,
        default=STATUSES,
    )

    sources = sorted(df['Source'].dropna().unique().tolist())
    sel_source = st.multiselect("Source", options=sources, default=sources)

    company_query = st.text_input("Search company", placeholder="e.g. Google")

    valid_dates = df['Date'].dropna()
    if not valid_dates.empty:
        min_d = valid_dates.min().date()
        max_d = valid_dates.max().date()
        date_range = st.date_input(
            "Date range",
            value=(min_d, max_d),
            min_value=min_d,
            max_value=max_d,
        )
    else:
        date_range = ()

    st.divider()
    st.caption("Edit Status cells in the table below, then hit **Save changes**.")


# ── Apply filters ─────────────────────────────────────────────────────────────
mask = df['Status'].isin(sel_status) & df['Source'].isin(sel_source)
filtered = df[mask].copy()

if company_query:
    filtered = filtered[
        filtered['Company'].str.contains(company_query, case=False, na=False)
    ]

if len(date_range) == 2:
    start = pd.Timestamp(date_range[0])
    end   = pd.Timestamp(date_range[1])
    filtered = filtered[filtered['Date'].between(start, end)]


# ── Charts ────────────────────────────────────────────────────────────────────
col_bar, col_source = st.columns(2)

with col_bar:
    st.subheader("Status breakdown")
    chart_df = (
        filtered['Status']
        .value_counts()
        .reindex(STATUSES, fill_value=0)
        .rename_axis('Status')
        .reset_index(name='Count')
    )
    st.bar_chart(chart_df.set_index('Status')['Count'])

with col_source:
    st.subheader("Source breakdown")
    source_df = (
        filtered['Source']
        .value_counts()
        .rename_axis('Source')
        .reset_index(name='Count')
    )
    st.bar_chart(source_df.set_index('Source')['Count'])

st.divider()


# ── Editable table ────────────────────────────────────────────────────────────
st.subheader(f"Applications — {len(filtered)} shown")

DISPLAY_COLS = ['Date', 'Company', 'Role', 'Status', 'Source', 'Subject', 'Sender']
show_cols    = [c for c in DISPLAY_COLS if c in filtered.columns]

# Track original df indices so we can write edits back
orig_indices = filtered.index.tolist()

edited = st.data_editor(
    filtered[show_cols].reset_index(drop=True),
    column_config={
        'Status': st.column_config.SelectboxColumn(
            'Status',
            options=STATUSES,
            required=True,
            width='small',
        ),
        'Date': st.column_config.DateColumn('Date', width='small'),
        'Company': st.column_config.TextColumn('Company', width='medium'),
        'Role': st.column_config.TextColumn('Role', width='medium'),
        'Source': st.column_config.TextColumn('Source', width='small'),
        'Subject': st.column_config.TextColumn('Subject', width='large'),
        'Sender': st.column_config.TextColumn('Sender', width='medium'),
    },
    disabled=[c for c in show_cols if c != 'Status'],  # only Status editable
    hide_index=True,
    use_container_width=True,
)

if st.button("💾 Save changes", type="primary"):
    for pos, orig_idx in enumerate(orig_indices):
        df.at[orig_idx, 'Status'] = edited.at[pos, 'Status']
    save_data(df)
    st.success("Saved!")
    st.rerun()
