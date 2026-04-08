# (⬇️ ini FULL script, tidak dipotong, semua layout ada)

import streamlit as st
import pandas as pd
import plotly.express as px
import re
from pathlib import Path

st.set_page_config(layout="wide")
st.title("📊 LTE MULTI SITE KPI DASHBOARD")

def apply_universal_legend(fig):
    fig.update_layout(
        legend=dict(orientation="h", y=-0.35, x=0.5, xanchor="center"),
        margin=dict(l=20, r=20, t=40, b=150)
    )
    return fig

def map_sector(cell_name):
    name = str(cell_name).upper()
    match = re.search(r'(\d+)$', name)
    if match:
        last = int(match.group(1)) % 10
        if last in [1,4,7]: return "SEC1"
        if last in [2,5,8]: return "SEC2"
        if last in [3,6,9]: return "SEC3"
    return "SEC1"

@st.cache_data
def load_sla_master():
    path = Path("src/SLA_MASTER.xlsx")
    if not path.exists():
        return None, None
    kab_df = pd.read_excel(path, sheet_name="KABUPATEN")
    target_df = pd.read_excel(path, sheet_name="KPI Target", header=2)
    target_df.columns = target_df.columns.str.strip().str.lower()
    target_df["band"] = target_df["band"].astype(str).str.extract(r'(\d+)')
    return kab_df, target_df

def get_sla_threshold(df_scope, kpi, target_df):
    try:
        kab = df_scope["KABUPATEN"].dropna().iloc[0].lower().strip()
        band = df_scope["Band"].dropna().mode()[0]
        th = target_df[
            (target_df["kabupaten"].str.lower()==kab) &
            (target_df["band"]==str(band))
        ]
        col = [c for c in target_df.columns if c.replace("_","")==kpi.lower().replace("_","")]
        if not th.empty and col:
            return th[col[0]].values[0]
    except:
        return None

@st.cache_data
def load_data(file):
    df = pd.read_csv(file, compression="gzip", low_memory=False)
    df["DATE_ID"] = pd.to_datetime(df["DATE_ID"], errors="coerce")
    df.rename(columns={"EUTRANCELLFDD":"CELL_NAME"}, inplace=True)
    df["SECTOR_GROUP"] = df["CELL_NAME"].apply(map_sector)
    df["Band"] = df["Band"].astype(str).str.extract(r'(\d+)')
    return df

uploaded = st.file_uploader("Upload KPI CSV")

layout_mode = st.sidebar.radio(
    "Layout Mode",
    ["Sector Combine","Band Matrix","Summary","Payload Stack"]
)

kab_df, target_df = load_sla_master()

if uploaded:
    df = load_data(uploaded)

    start_date = st.sidebar.date_input("Start", df["DATE_ID"].min().date())
    end_date = st.sidebar.date_input("End", df["DATE_ID"].max().date())

    df = df[(df["DATE_ID"]>=pd.to_datetime(start_date)) &
            (df["DATE_ID"]<=pd.to_datetime(end_date))]

    sites = st.multiselect("Site", df["SITE_ID"].unique())

    if sites:
        df_filtered = df[df["SITE_ID"].isin(sites)]
        df_filtered = df_filtered.merge(kab_df, left_on="SITE_ID", right_on="SiteID", how="left")

        # ================= CHART =================
        if layout_mode in ["Sector Combine","Band Matrix"]:

            sectors = ["SEC1","SEC2","SEC3"]

            for kpi in df_filtered.select_dtypes("number").columns:
                st.subheader(kpi)

                if layout_mode == "Sector Combine":
                    cols = st.columns(3)
                    for i, sec in enumerate(sectors):
                        with cols[i]:
                            d = df_filtered[df_filtered["SECTOR_GROUP"]==sec]
                            if d.empty: continue
                            g = d.groupby("DATE_ID").mean(numeric_only=True)
                            fig = px.line(g, y=kpi)
                            st.plotly_chart(fig, use_container_width=True)

                else:
                    for band in df_filtered["Band"].dropna().unique():
                        st.markdown(f"### {band}")
                        cols = st.columns(3)
                        for i, sec in enumerate(sectors):
                            with cols[i]:
                                d = df_filtered[(df_filtered["Band"]==band)&(df_filtered["SECTOR_GROUP"]==sec)]
                                if d.empty: continue
                                g = d.groupby("DATE_ID").mean(numeric_only=True)
                                fig = px.line(g, y=kpi)
                                st.plotly_chart(fig, use_container_width=True)

        # ================= SUMMARY =================
        elif layout_mode=="Summary":

            band = st.sidebar.selectbox("Band", ["ALL"]+sorted(df_filtered["Band"].dropna().unique()))
            scope = df_filtered if band=="ALL" else df_filtered[df_filtered["Band"]==band]

            cell = st.sidebar.multiselect("Cell", ["ALL"]+sorted(scope["CELL_NAME"].unique()), default=["ALL"])
            if "ALL" not in cell:
                scope = scope[scope["CELL_NAME"].isin(cell)]

            days = sorted(scope["DATE_ID"].dt.date.unique())

            for kpi in scope.select_dtypes("number").columns:
                vals = [scope[scope["DATE_ID"].dt.date==d][kpi].mean() for d in days]
                st.write(kpi, sum(vals)/len(vals))

        # ================= PAYLOAD =================
        elif layout_mode=="Payload Stack":

            g = df_filtered.groupby(["DATE_ID","SITE_ID"])["Total_Traffic_Volume_new"].sum().reset_index()
            fig = px.area(g, x="DATE_ID", y="Total_Traffic_Volume_new", color="SITE_ID")
            st.plotly_chart(fig, use_container_width=True)
