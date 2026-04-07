import streamlit as st
import pandas as pd
import plotly.express as px
import re
from pathlib import Path

st.set_page_config(layout="wide")
st.title("📊 LTE MULTI SITE KPI DASHBOARD")

# ================= PATCH KPI =================
problem_kpi = [
    "Intra-Frequency Handover Out Success Rate",
    "inter_freq_HO",
    "UL_INT_PUSCH",
    "Average_CQI_nonHOME",
    "Total_Traffic_Volume_new",
    "DL_Resource_Block_Utilizing_Rate_New",
    "UL_Resource_Block_Utilizing_Rate_New",
    "Downlink_Traffic_Volume_New",
    "Uplink_Traffic_Volume_New"
]

def clean_kpi(series):
    return pd.to_numeric(
        series.astype(str)
        .str.replace("%", "")
        .str.replace("NIL", "")
        .str.replace("-", "")
        .str.replace(",", "")
        .str.strip(),
        errors="coerce"
    )

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
        df = pd.read_csv(file, compression="gzip")
    else:
        df = pd.read_csv(file)

    df["DATE_ID"] = pd.to_datetime(df["DATE_ID"])

    if "Hour_id" in df.columns:
        df["DATETIME_ID"] = df["DATE_ID"] + pd.to_timedelta(df["Hour_id"], unit="h")
        df["DATA_RESOLUTION"] = "Hourly"
    else:
        df["DATETIME_ID"] = df["DATE_ID"]
        df["DATA_RESOLUTION"] = "Daily"

    df.rename(columns={"EUTRANCELLFDD":"CELL_NAME"}, inplace=True)
    df["SECTOR_GROUP"] = df["CELL_NAME"].apply(map_sector)

    df["Band"] = (
        df["Band"].astype(str)
        .str.upper()
        .str.replace(" ","", regex=False)
        .str.replace("-","", regex=False)
    )

    return df

# ================= MAIN =================
uploaded = st.file_uploader("Upload KPI CSV", type=["csv","gz"])

layout_mode = st.sidebar.radio(
    "Layout Mode",
    ["Sector Combine","Band Matrix","Summary","Payload Stack"]
)

if uploaded:

    df = load_data(uploaded)

    kpi_list = [
        "UL_INT_PUSCH",
        "Average_CQI_nonHOME",
        "Total_Traffic_Volume_new",
        "DL_Resource_Block_Utilizing_Rate_New",
        "UL_Resource_Block_Utilizing_Rate_New",
        "Downlink_Traffic_Volume_New",
        "Uplink_Traffic_Volume_New"
    ]

    x_col = "DATE_ID"

    if layout_mode in ["Sector Combine","Band Matrix"]:

        sectors = ["SEC1","SEC2","SEC3"]

        for kpi in kpi_list:

            st.subheader(kpi)
            cols = st.columns(3)

            for i, sec in enumerate(sectors):

                with cols[i]:

                    df_sector = df[df["SECTOR_GROUP"] == sec]

                    if df_sector.empty:
                        continue

                    # ===== PATCH ONLY HERE =====
                    if kpi in problem_kpi:
                        df_sector[kpi] = clean_kpi(df_sector[kpi])
                        df_grouped = df_sector.groupby(["CELL_NAME", x_col])[kpi].mean().reset_index()
                    else:
                        df_grouped = df_sector.groupby(["CELL_NAME",x_col]).mean(numeric_only=True).reset_index()

                        if kpi not in df_grouped.columns:
                            continue

                    fig = px.line(df_grouped, x=x_col, y=kpi, color="CELL_NAME", markers=True)
                    fig = apply_universal_legend(fig)
                    st.plotly_chart(fig, use_container_width=True)
