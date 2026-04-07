import streamlit as st
import pandas as pd
import plotly.express as px
import re
from pathlib import Path

st.set_page_config(layout="wide")
st.title("📊 LTE MULTI SITE KPI DASHBOARD")

# ================= PATCH KPI BERMASALAH =================
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

# ================= SLA LOAD =================
@st.cache_data
def load_sla_master():
    path = Path("src/SLA_MASTER.xlsx")
    if not path.exists():
        return None, None

    kab_df = pd.read_excel(path, sheet_name="KABUPATEN")
    target_df = pd.read_excel(path, sheet_name="KPI Target", header=2)
    target_df.columns = target_df.columns.str.strip().str.lower()
    return kab_df, target_df

# ================= SLA LOOKUP =================
def get_sla_threshold(df_scope, kpi, target_df):
    if target_df is None or df_scope.empty:
        return None

    try:
        kab = str(df_scope["KABUPATEN"].dropna().iloc[0]).lower().strip()
        band = str(df_scope["Band"].dropna().unique()[0]).lower().strip()

        th = target_df[
            (target_df["kabupaten"].str.lower().str.strip() == kab) &
            (target_df["band"].str.lower().str.strip() == band)
        ]

        col_match = [
            c for c in target_df.columns
            if c.replace("_","").replace(" ","") ==
            kpi.lower().replace("_","").replace(" ","")
        ]

        if not th.empty and col_match:
            return th[col_match[0]].values[0]

    except:
        return None

    return None

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

kab_df, target_df = load_sla_master()

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

    if df["DATA_RESOLUTION"].iloc[0] == "Hourly":
        time_resolution = st.sidebar.radio("Time Resolution", ["Hourly","Daily"])
    else:
        time_resolution = "Daily"
        st.sidebar.info("📅 Daily File Detected")

    start_date = st.sidebar.date_input("Start Date", df["DATE_ID"].min().date())
    end_date = st.sidebar.date_input("End Date", df["DATE_ID"].max().date())

    df = df[
        (df["DATE_ID"] >= pd.to_datetime(start_date)) &
        (df["DATE_ID"] <= pd.to_datetime(end_date))
    ]

    selected_sites = st.multiselect(
        "Select Site ID",
        sorted(df["SITE_ID"].unique())
    )

    if selected_sites:

        df_filtered = df[df["SITE_ID"].isin(selected_sites)]

        if layout_mode in ["Sector Combine","Band Matrix"]:

            sectors = ["SEC1","SEC2","SEC3"]

            for kpi in kpi_list:

                st.markdown("---")
                st.subheader(kpi)

                cols = st.columns(len(sectors))

                for i, sec in enumerate(sectors):

                    with cols[i]:

                        df_sector = df_filtered[df_filtered["SECTOR_GROUP"] == sec]

                        if df_sector.empty:
                            continue

                        x_col = "DATE_ID" if time_resolution=="Daily" else "DATETIME_ID"

                        # ================= PATCH LOGIC =================
                        if kpi in problem_kpi:

                            if kpi not in df_sector.columns:
                                st.warning(f"{kpi} tidak ada di file")
                                continue

                            df_sector[kpi] = clean_kpi(df_sector[kpi])

                            if df_sector[kpi].notna().sum() == 0:
                                st.warning(f"{kpi} kosong (all NaN)")
                                continue

                            df_grouped = (
                                df_sector.groupby(["CELL_NAME", x_col])[kpi]
                                .mean()
                                .reset_index()
                            )

                        else:
                            df_grouped = df_sector.groupby(["CELL_NAME",x_col]).mean(numeric_only=True).reset_index()

                            if kpi not in df_grouped.columns:
                                continue

                        if kpi in traffic_kpi:
                            fig = px.area(df_grouped, x=x_col, y=kpi, color="CELL_NAME")
                        else:
                            fig = px.line(df_grouped, x=x_col, y=kpi, color="CELL_NAME", markers=True)

                        fig = apply_universal_legend(fig)
                        st.plotly_chart(fig, use_container_width=True)
