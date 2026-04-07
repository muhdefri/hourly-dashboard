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
        df = pd.read_csv(file, compression="gzip", low_memory=False)
    else:
        df = pd.read_csv(file, low_memory=False)

    # ===== CLEAN KPI =====
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

    # ================= DATE =================
    start_date = st.sidebar.date_input("Start Date", df["DATE_ID"].min().date())
    end_date = st.sidebar.date_input("End Date", df["DATE_ID"].max().date())

    df = df[
        (df["DATE_ID"] >= pd.to_datetime(start_date)) &
        (df["DATE_ID"] <= pd.to_datetime(end_date))
    ]

    selected_sites = st.multiselect("Select Site ID", sorted(df["SITE_ID"].unique()))

    if selected_sites:

        df_filtered = df[df["SITE_ID"].isin(selected_sites)]

        if kab_df is not None:
            df_filtered = df_filtered.merge(
                kab_df,
                left_on="SITE_ID",
                right_on="SiteID",
                how="left"
            )

        x_col = "DATE_ID"

        # ================= SUMMARY =================
        if layout_mode == "Summary":

            st.markdown("## Site Level Performance")

            unique_days = sorted(df_filtered["DATE_ID"].dt.date.unique())

            html = "<table style='border-collapse:collapse; width:100%;'>"

            html += "<tr style='background:#a5d6a7;'>"
            html += "<th rowspan='2'>KPI</th>"
            for i in range(len(unique_days)):
                html += f"<th>DAY {i+1}</th>"
            html += "<th rowspan='2'>Average</th><th rowspan='2'>Target</th><th rowspan='2'>Passed</th>"
            html += "</tr>"

            html += "<tr style='background:#c8e6c9;'>"
            for d in unique_days:
                html += f"<th>{pd.to_datetime(d).strftime('%d-%b')}</th>"
            html += "</tr>"

            for kpi in summary_kpi:

                if kpi not in df_filtered.columns:
                    continue

                html += f"<tr><td><b>{kpi}</b></td>"

                vals = []

                for d in unique_days:
                    val = df_filtered[df_filtered["DATE_ID"].dt.date==d][kpi].mean()
                    vals.append(val)
                    html += f"<td>{round(val,2) if pd.notna(val) else ''}</td>"

                avg = pd.Series(vals).mean()
                html += f"<td>{round(avg,2) if pd.notna(avg) else ''}</td>"

                target = get_sla_threshold(df_filtered, kpi, target_df)
                html += f"<td>{round(target,2) if target else ''}</td>"

                if target and pd.notna(avg):
                    passed = "Y" if avg >= target else "N"
                    color = "#b7e1cd" if passed=="Y" else "#f4c7c3"
                    html += f"<td style='background:{color}'>{passed}</td>"
                else:
                    html += "<td></td>"

                html += "</tr>"

            html += "</table>"
            st.markdown(html, unsafe_allow_html=True)

        # ================= PAYLOAD =================
        elif layout_mode == "Payload Stack":

            df_plot = df_filtered.groupby(["DATE_ID","SITE_ID"])["Total_Traffic_Volume_new"].sum().reset_index()

            fig = px.area(df_plot, x="DATE_ID", y="Total_Traffic_Volume_new", color="SITE_ID")
            st.plotly_chart(apply_universal_legend(fig), use_container_width=True)

        # ================= SECTOR =================
        elif layout_mode == "Sector Combine":

            sectors = ["SEC1","SEC2","SEC3"]

            for kpi in kpi_list:

                st.markdown("---")
                st.subheader(kpi)

                cols = st.columns(3)

                for i, sec in enumerate(sectors):

                    with cols[i]:

                        df_sec = df_filtered[df_filtered["SECTOR_GROUP"]==sec]

                        if df_sec.empty:
                            continue

                        df_plot = df_sec.groupby(["CELL_NAME",x_col])[kpi].mean().reset_index()

                        fig = px.line(df_plot, x=x_col, y=kpi, color="CELL_NAME")

                        th = get_sla_threshold(df_sec, kpi, target_df)
                        if pd.notna(th):
                            fig.add_hline(y=float(th), line_color="red", line_dash="dash")

                        st.plotly_chart(apply_universal_legend(fig), use_container_width=True)

        # ================= BAND MATRIX =================
        elif layout_mode == "Band Matrix":

            sectors = ["SEC1","SEC2","SEC3"]
            bands = df_filtered["Band"].dropna().unique()

            for kpi in kpi_list:

                st.markdown("---")
                st.subheader(kpi)

                for sec in sectors:

                    st.markdown(f"### {sec}")

                    df_sec = df_filtered[df_filtered["SECTOR_GROUP"]==sec]

                    cols = st.columns(len(bands))

                    for i, b in enumerate(bands):

                        with cols[i]:

                            df_band = df_sec[df_sec["Band"]==b]

                            if df_band.empty:
                                continue

                            df_plot = df_band.groupby(["CELL_NAME",x_col])[kpi].mean().reset_index()

                            fig = px.line(df_plot, x=x_col, y=kpi, color="CELL_NAME")

                            th = get_sla_threshold(df_band, kpi, target_df)
                            if pd.notna(th):
                                fig.add_hline(y=float(th), line_color="red", line_dash="dash")

                            st.plotly_chart(apply_universal_legend(fig), use_container_width=True)
