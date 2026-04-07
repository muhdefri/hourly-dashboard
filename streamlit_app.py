import streamlit as st
import pandas as pd
import plotly.express as px
import re
from pathlib import Path

st.set_page_config(layout="wide")
st.title("📊 LTE MULTI SITE KPI DASHBOARD")

# ================= LEGEND =================
def apply_universal_legend(fig):
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.35,
            xanchor="center",
            x=0.5,
            font=dict(size=9)
        ),
        margin=dict(l=20, r=20, t=40, b=150)
    )
    return fig


# ================= SECTOR MAP =================
def map_sector(cell_name):
    name = str(cell_name).upper()

    match_rl = re.search(r'RL(\d)', name)
    if match_rl:
        return f"SEC{match_rl.group(1)}"

    match_rr = re.search(r'RR(\d)', name)
    if match_rr:
        return f"SEC{match_rr.group(1)}"

    match = re.search(r'(\d+)$', name)
    if match:
        last_digit = int(match.group(1)) % 10
        if last_digit in [1,4,7]: return "SEC1"
        elif last_digit in [2,5,8]: return "SEC2"
        elif last_digit in [3,6,9]: return "SEC3"

    return "UNKNOWN"


# ================= LOAD DATA =================
@st.cache_data
def load_data(file):

    if file.name.endswith(".gz"):
        df = pd.read_csv(file, compression="gzip", low_memory=False)
    else:
        df = pd.read_csv(file, low_memory=False)

    # 🔥 CLEAN KPI (GLOBAL FIX)
    skip_cols = ["SITE_ID","CELL_NAME","Band","DATE_ID","Hour_id"]

    for col in df.columns:
        if col in skip_cols:
            continue

        if df[col].dtype == "object":
            df[col] = (
                df[col]
                .astype(str)
                .str.replace('%', '', regex=False)
                .str.replace(',', '.', regex=False)
                .replace(['', 'None', 'nan'], None)
            )
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df["DATE_ID"] = pd.to_datetime(df["DATE_ID"])

    if "Hour_id" in df.columns:
        df["DATETIME_ID"] = df["DATE_ID"] + pd.to_timedelta(df["Hour_id"], unit="h")
        df["DATA_RESOLUTION"] = "Hourly"
    else:
        df["DATETIME_ID"] = df["DATE_ID"]
        df["DATA_RESOLUTION"] = "Daily"

    df.rename(columns={"EUTRANCELLFDD":"CELL_NAME"}, inplace=True)
    df["SECTOR_GROUP"] = df["CELL_NAME"].apply(map_sector)

    return df


# ================= MAIN =================
uploaded = st.file_uploader("Upload KPI CSV", type=["csv","gz"])

layout_mode = st.sidebar.radio(
    "Layout Mode",
    ["Sector Combine","Band Matrix","Summary","Payload Stack"]
)

if uploaded:

    df = load_data(uploaded)

    summary_kpi = [
        "RRC Setup Success Rate (Service)",
        "ERAB_Setup_Success_Rate_All_New",
        "Session_Setup_Success_Rate_New",
        "Session_Abnormal_Release_New",
        "Intra-Frequency Handover Out Success Rate",
        "inter_freq_HO",
        "Radio_Network_Availability_Rate",
        "UL_INT_PUSCH",
        "Average_CQI_nonHOME",
        "SE_New"
    ]

    traffic_kpi = [
        "Total_Traffic_Volume_new",
        "DL_Resource_Block_Utilizing_Rate_New",
        "UL_Resource_Block_Utilizing_Rate_New",
        "Downlink_Traffic_Volume_New",
        "Uplink_Traffic_Volume_New",
        "Active User DL"
    ]

    kpi_list = summary_kpi + traffic_kpi

    selected_sites = st.multiselect(
        "Select Site ID",
        sorted(df["SITE_ID"].unique())
    )

    if selected_sites:

        df_filtered = df[df["SITE_ID"].isin(selected_sites)]

        # ==================================================
        # ================= SUMMARY ========================
        # ==================================================
        if layout_mode == "Summary":

            st.subheader("Summary View")

            for kpi in summary_kpi:

                if kpi not in df_filtered.columns:
                    continue

                df_temp = df_filtered.copy()
                df_temp[kpi] = pd.to_numeric(df_temp[kpi], errors='coerce')
                df_temp = df_temp.dropna(subset=[kpi])

                if df_temp.empty:
                    continue

                df_plot = df_temp.groupby("DATE_ID")[kpi].mean().reset_index()

                fig = px.line(df_plot, x="DATE_ID", y=kpi, markers=True)
                fig = apply_universal_legend(fig)

                st.plotly_chart(fig, use_container_width=True)

        # ==================================================
        # ================= PAYLOAD ========================
        # ==================================================
        elif layout_mode == "Payload Stack":

            st.header("📦 Total Traffic Volume")

            df_temp = df_filtered.copy()
            df_temp["Total_Traffic_Volume_new"] = pd.to_numeric(
                df_temp["Total_Traffic_Volume_new"], errors='coerce'
            )

            df_plot = (
                df_temp.groupby(["DATE_ID","SITE_ID"])["Total_Traffic_Volume_new"]
                .sum()
                .reset_index()
            )

            fig = px.area(df_plot, x="DATE_ID", y="Total_Traffic_Volume_new", color="SITE_ID")
            fig = apply_universal_legend(fig)

            st.plotly_chart(fig, use_container_width=True)

        # ==================================================
        # ================= CHART ==========================
        # ==================================================
        elif layout_mode in ["Sector Combine","Band Matrix"]:

            sectors = ["SEC1","SEC2","SEC3"]

            for kpi in kpi_list:

                st.markdown("---")
                st.subheader(kpi)

                cols = st.columns(3)

                for i, sec in enumerate(sectors):

                    with cols[i]:

                        df_sector = df_filtered[df_filtered["SECTOR_GROUP"] == sec]

                        if df_sector.empty:
                            continue

                        if kpi not in df_sector.columns:
                            continue

                        df_temp = df_sector.copy()
                        df_temp[kpi] = pd.to_numeric(df_temp[kpi], errors='coerce')
                        df_temp = df_temp.dropna(subset=[kpi])

                        if df_temp.empty:
                            continue

                        df_grouped = df_temp.groupby(
                            ["CELL_NAME","DATE_ID"]
                        )[kpi].mean().reset_index()

                        if kpi in traffic_kpi:
                            fig = px.area(df_grouped, x="DATE_ID", y=kpi, color="CELL_NAME")
                        else:
                            fig = px.line(df_grouped, x="DATE_ID", y=kpi, color="CELL_NAME", markers=True)

                        fig = apply_universal_legend(fig)

                        st.plotly_chart(fig, use_container_width=True)
