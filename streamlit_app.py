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


# ================= SMART SECTOR MAP =================
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

    hash_val = sum(ord(c) for c in name)
    return f"SEC{(hash_val % 3) + 1}"


# ================= SLA =================
@st.cache_data
def load_sla_master():
    path = Path("src/SLA_MASTER.xlsx")
    if not path.exists():
        return None, None

    kab_df = pd.read_excel(path, sheet_name="KABUPATEN")
    target_df = pd.read_excel(path, sheet_name="KPI Target", header=2)
    target_df.columns = target_df.columns.str.strip().str.lower()

    if "band" in target_df.columns:
        target_df["band"] = target_df["band"].astype(str).str.extract(r'(\d+)')

    return kab_df, target_df


# 🔥 FIX FINAL (SLA PASTI MUNCUL)
def get_sla_threshold(df_scope, kpi, target_df):
    if target_df is None or df_scope.empty:
        return None

    try:
        kab = str(df_scope["KABUPATEN"].dropna().iloc[0]).lower().strip()

        # 🔥 ambil band paling dominan (bukan random)
        band = (
            df_scope["Band"]
            .dropna()
            .mode()
        )

        if band.empty:
            return None

        band = str(band.iloc[0]).strip()

        th = target_df[
            (target_df["kabupaten"].str.lower().str.strip() == kab) &
            (target_df["band"].astype(str).str.strip() == band)
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
        df = pd.read_csv(file, compression="gzip", low_memory=False)
    else:
        df = pd.read_csv(file, low_memory=False)

    df.replace(["-", "NIL", "None", ""], pd.NA, inplace=True)

    kpi_columns = [
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

    for col in kpi_columns:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["DATE_ID"] = pd.to_datetime(df["DATE_ID"], errors="coerce")

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

    df["Band"] = df["Band"].str.extract(r'(\d+)')

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

    min_date = df["DATE_ID"].min()
    max_date = df["DATE_ID"].max()

    start_date = st.sidebar.date_input("Start Date", min_date.date())
    end_date = st.sidebar.date_input("End Date", max_date.date())

    df = df[
        (df["DATE_ID"] >= pd.to_datetime(start_date)) &
        (df["DATE_ID"] <= pd.to_datetime(end_date))
    ]

    selected_sites = st.multiselect("Select Site ID", sorted(df["SITE_ID"].unique()))

    if selected_sites:

        df_filtered = df[df["SITE_ID"].isin(selected_sites)]

        if kab_df is not None:
            df_filtered = df_filtered.merge(
                kab_df, left_on="SITE_ID", right_on="SiteID", how="left"
            )

        # ================= SUMMARY =================
        if layout_mode == "Summary":

            show_only_nok = st.checkbox("Show Only NOK KPI", value=False)

            band_options = ["ALL"] + sorted(df_filtered["Band"].dropna().unique())
            selected_band = st.sidebar.selectbox("Filter Band", band_options)

            if selected_band != "ALL":
                df_scope = df_filtered[df_filtered["Band"] == selected_band]
            else:
                df_scope = df_filtered.copy()

            cell_options = ["ALL"] + sorted(df_scope["CELL_NAME"].dropna().unique())
            selected_cells = st.sidebar.multiselect("Filter Cell", cell_options, default=["ALL"])

            if "ALL" not in selected_cells:
                df_scope = df_scope[df_scope["CELL_NAME"].isin(selected_cells)]

            if df_scope.empty:
                st.warning("⚠️ No data after filtering")
                st.stop()

            unique_days = sorted(df_scope["DATE_ID"].dt.date.unique())

            st.markdown("## Site Level Performance")

            html = "<table style='border-collapse:collapse; width:100%;'>"

            html += "<tr style='background:#a5d6a7;'>"
            html += "<th rowspan='2'>KPI</th>"

            for i in range(len(unique_days)):
                html += f"<th>DAY {i+1}</th>"

            html += "<th rowspan='2'>Average</th>"
            html += "<th rowspan='2'>Target KPI</th>"
            html += "<th rowspan='2'>Passed</th>"
            html += "<th rowspan='2'>Delta</th>"
            html += "</tr>"

            html += "<tr style='background:#c8e6c9;'>"
            for d in unique_days:
                html += f"<th>{pd.to_datetime(d).strftime('%d-%b-%y')}</th>"
            html += "</tr>"

            for kpi in summary_kpi:

                if kpi not in df_scope.columns:
                    continue

                daily_values = [
                    df_scope[df_scope["DATE_ID"].dt.date == d][kpi].mean()
                    for d in unique_days
                ]

                avg_val = pd.Series(daily_values).mean()
                target = get_sla_threshold(df_scope, kpi, target_df)

                html += "<tr>"
                html += f"<td><b>{kpi}</b></td>"

                for val in daily_values:
                    html += f"<td>{round(val,2) if pd.notna(val) else ''}</td>"

                html += f"<td>{round(avg_val,2) if pd.notna(avg_val) else ''}</td>"
                html += f"<td>{round(target,2) if target else ''}</td>"
                html += "</tr>"

            html += "</table>"

            st.markdown(html, unsafe_allow_html=True)
