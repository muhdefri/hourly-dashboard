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
    return kab_df, target_df


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

    # FIX NUMERIC KPI (tetap seperti sebelumnya)
    for col in kpi_columns:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 🔥 FIX DATE (AUTO DETECT FORMAT)
    df["DATE_ID"] = pd.to_datetime(
        df["DATE_ID"],
        errors="coerce"
    )

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

    # 🔥 SAFE DATE HANDLING (FIX ERROR)
    min_date = df["DATE_ID"].min()
    max_date = df["DATE_ID"].max()

    if pd.isna(min_date) or pd.isna(max_date):
        st.error("❌ DATE_ID tidak terbaca. Cek format tanggal di CSV.")
        st.stop()

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

        # ================= CHART =================
        if layout_mode in ["Sector Combine","Band Matrix"]:

            sectors = ["SEC1","SEC2","SEC3"]

            for kpi in kpi_list:

                st.markdown("---")
                st.subheader(kpi)

                if layout_mode == "Sector Combine":

                    cols = st.columns(3)

                    for i, sec in enumerate(sectors):
                        with cols[i]:

                            df_sec = df_filtered[df_filtered["SECTOR_GROUP"] == sec]
                            if df_sec.empty:
                                continue

                            df_g = df_sec.groupby(["CELL_NAME","DATE_ID"]).mean(numeric_only=True).reset_index()
                            if kpi not in df_g.columns:
                                continue

                            fig = px.line(df_g, x="DATE_ID", y=kpi, color="CELL_NAME")

                            th = get_sla_threshold(df_sec, kpi, target_df)
                            if pd.notna(th):
                                fig.add_hline(
                                    y=float(th),
                                    line_dash="dash",
                                    line_color="red",
                                    annotation_text=f"{float(th):.2f}",
                                    annotation_position="top left"
                                )

                            st.plotly_chart(apply_universal_legend(fig), use_container_width=True)

                else:

                    bands = sorted(df_filtered["Band"].dropna().unique())

                    for band in bands:

                        st.markdown(f"### 📡 {band}")
                        cols = st.columns(3)

                        for i, sec in enumerate(sectors):
                            with cols[i]:

                                df_sec = df_filtered[
                                    (df_filtered["Band"] == band) &
                                    (df_filtered["SECTOR_GROUP"] == sec)
                                ]

                                if df_sec.empty:
                                    continue

                                df_g = df_sec.groupby(["CELL_NAME","DATE_ID"]).mean(numeric_only=True).reset_index()
                                if kpi not in df_g.columns:
                                    continue

                                fig = px.line(df_g, x="DATE_ID", y=kpi, color="CELL_NAME")

                                th = get_sla_threshold(df_sec, kpi, target_df)
                                if pd.notna(th):
                                    fig.add_hline(
                                        y=float(th),
                                        line_dash="dash",
                                        line_color="red",
                                        annotation_text=f"{float(th):.2f}",
                                        annotation_position="top left"
                                    )

                                st.plotly_chart(apply_universal_legend(fig), use_container_width=True)

        # ================= SUMMARY =================
        elif layout_mode == "Summary":

            show_only_nok = st.checkbox("Show Only NOK KPI", value=False)

            if df_filtered.empty:
                st.warning("⚠️ No data after filtering")
                st.stop()

            unique_days = sorted(df_filtered["DATE_ID"].dt.date.unique())

            if len(unique_days) == 0:
                st.warning("⚠️ No data in selected date range")
                st.stop()

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

            nok_found = False

            for kpi in summary_kpi:

                if kpi not in df_filtered.columns:
                    continue

                daily_values = []

                for d in unique_days:
                    val = df_filtered[df_filtered["DATE_ID"].dt.date == d][kpi].mean()
                    daily_values.append(val)

                avg_val = pd.Series(daily_values).mean()
                target = get_sla_threshold(df_filtered, kpi, target_df)

                is_nok = False
                if target is not None and pd.notna(avg_val):
                    if "Abnormal" in kpi:
                        is_nok = avg_val > target
                    else:
                        is_nok = avg_val < target

                if is_nok:
                    nok_found = True

                if show_only_nok and not is_nok:
                    continue

                html += "<tr>"
                html += f"<td><b>{kpi}</b></td>"

                for val in daily_values:
                    html += f"<td>{round(val,2) if pd.notna(val) else ''}</td>"

                html += f"<td>{round(avg_val,2) if pd.notna(avg_val) else ''}</td>"
                html += f"<td>{round(target,2) if target is not None else ''}</td>"

                if target is not None and pd.notna(avg_val):
                    if "Abnormal" in kpi:
                        passed = "Y" if avg_val <= target else "N"
                        delta = target - avg_val
                    else:
                        passed = "Y" if avg_val >= target else "N"
                        delta = avg_val - target

                    color = "#b7e1cd" if passed=="Y" else "#f4c7c3"

                    html += f"<td style='background:{color}; text-align:center'><b>{passed}</b></td>"
                    html += f"<td>{round(delta,2)}</td>"
                else:
                    html += "<td></td><td></td>"

                html += "</tr>"

            html += "</table>"

            if show_only_nok and not nok_found:
                st.success("✅ All KPI Passed SLA")

            st.markdown(html, unsafe_allow_html=True)

        # ================= PAYLOAD =================
        elif layout_mode == "Payload Stack":

            st.header("📦 Total Traffic Volume (GB)")

            df_grouped = (
                df_filtered.groupby(["DATE_ID","SITE_ID"])["Total_Traffic_Volume_new"]
                .sum()
                .reset_index()
            )

            df_grouped["Total_Traffic_Volume_new"] /= 1024

            fig = px.area(
                df_grouped,
                x="DATE_ID",
                y="Total_Traffic_Volume_new",
                color="SITE_ID"
            )

            st.plotly_chart(apply_universal_legend(fig), use_container_width=True)
