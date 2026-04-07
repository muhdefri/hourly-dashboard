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

    # 🔥 CLEAN KPI
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
    else:
        df["DATETIME_ID"] = df["DATE_ID"]

    df.rename(columns={"EUTRANCELLFDD":"CELL_NAME"}, inplace=True)
    df["SECTOR_GROUP"] = df["CELL_NAME"].apply(map_sector)

    return df


# ================= MAIN =================
uploaded = st.file_uploader("Upload KPI CSV", type=["csv","gz"])

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

        sectors = ["SEC1","SEC2","SEC3"]

        for kpi in kpi_list:

            st.markdown("---")
            st.subheader(kpi)

            cols = st.columns(3)

            for i, sec in enumerate(sectors):

                with cols[i]:

                    st.markdown(f"### 📡 {sec}")

                    df_sector = df_filtered[df_filtered["SECTOR_GROUP"] == sec]

                    if df_sector.empty:
                        st.info("No data")
                        continue

                    if kpi not in df_sector.columns:
                        st.warning("KPI not found")
                        continue

                    df_temp = df_sector.copy()

                    # 🔥 FORCE NUMERIC (ANTI ERROR FINAL)
                    df_temp[kpi] = pd.to_numeric(df_temp[kpi], errors='coerce')
                    df_temp = df_temp.dropna(subset=[kpi])

                    if df_temp.empty:
                        st.warning("No valid data")
                        continue

                    df_grouped = (
                        df_temp.groupby(["CELL_NAME","DATE_ID"])[kpi]
                        .mean()
                        .reset_index()
                    )

                    if kpi in traffic_kpi:
                        fig = px.area(
                            df_grouped,
                            x="DATE_ID",
                            y=kpi,
                            color="CELL_NAME"
                        )
                    else:
                        fig = px.line(
                            df_grouped,
                            x="DATE_ID",
                            y=kpi,
                            color="CELL_NAME",
                            markers=True
                        )

                    fig = apply_universal_legend(fig)

                    st.plotly_chart(fig, use_container_width=True)
