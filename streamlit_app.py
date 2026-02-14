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


# ================= SECTOR MAP FINAL =================
def map_sector(cell_name):
    name = str(cell_name).upper()

    # Ambil RLxx / RRxx di akhir string
    match = re.search(r'(RL|RR)(\d{2})$', name)
    if match:
        sector_digit = match.group(2)[0]
        if sector_digit in ["1", "2", "3"]:
            return f"SEC{sector_digit}"

    # fallback lama
    match_last = re.search(r'(\d+)$', name)
    if match_last:
        last_digit = int(match_last.group(1)) % 10
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

    band_order = ["LTE900","LTE1800","LTE2100","LTE2300"]

    df["Band"] = (
        df["Band"].astype(str)
        .str.upper()
        .str.replace(" ","", regex=False)
        .str.replace("-","", regex=False)
    )

    df["Band"] = pd.Categorical(df["Band"], categories=band_order, ordered=True)

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

    if not selected_sites:
        st.stop()

    df_filtered = df[df["SITE_ID"].isin(selected_sites)]

    if kab_df is not None:
        df_filtered = df_filtered.merge(
            kab_df,
            left_on="SITE_ID",
            right_on="SiteID",
            how="left"
        )

    # ================= PAYLOAD STACK =================
    if layout_mode == "Payload Stack":

        st.header("📦 Total Traffic Volume (GB)")

        x_col = "DATE_ID" if time_resolution=="Daily" else "DATETIME_ID"

        df_grouped = (
            df_filtered.groupby([x_col,"SITE_ID"])["Total_Traffic_Volume_new"]
            .sum()
            .reset_index()
        )

        df_grouped["Total_Traffic_Volume_new"] /= 1024

        min_date = df_grouped[x_col].min().date()
        max_date = df_grouped[x_col].max().date()

        before_range = st.date_input("Before Period", (min_date, min_date))
        after_range = st.date_input("After Period", (max_date, max_date))

        before_total = df_grouped[
            (df_grouped[x_col].dt.date >= before_range[0]) &
            (df_grouped[x_col].dt.date <= before_range[1])
        ]["Total_Traffic_Volume_new"].sum()

        after_total = df_grouped[
            (df_grouped[x_col].dt.date >= after_range[0]) &
            (df_grouped[x_col].dt.date <= after_range[1])
        ]["Total_Traffic_Volume_new"].sum()

        delta = after_total - before_total
        growth = (delta / before_total * 100) if before_total != 0 else 0

        col1,col2,col3,col4 = st.columns(4)
        col1.metric("Before (GB)", f"{before_total:,.2f}")
        col2.metric("After (GB)", f"{after_total:,.2f}")
        col3.metric("Delta (GB)", f"{delta:,.2f}")
        col4.metric("Growth %", f"{growth:.2f}%")

        fig = px.area(
            df_grouped,
            x=x_col,
            y="Total_Traffic_Volume_new",
            color="SITE_ID",
            labels={"Total_Traffic_Volume_new":"Total Traffic (GB)"}
        )

        fig = apply_universal_legend(fig)
        st.plotly_chart(fig, use_container_width=True)

        st.stop()


    # ================= SUMMARY =================
    if layout_mode == "Summary":

        st.markdown("## Site Level Performance")

        unique_days = sorted(df_filtered["DATE_ID"].dt.date.unique())

        df_summary = []

        for kpi in summary_kpi:

            row = {"KPI": kpi}
            daily_values = []

            for idx, d in enumerate(unique_days):
                val = df_filtered[df_filtered["DATE_ID"].dt.date == d][kpi].mean()
                row[f"DAY {idx+1}"] = round(val,2) if pd.notna(val) else None
                daily_values.append(val)

            avg_val = pd.Series(daily_values).mean()
            row["Average"] = round(avg_val,2)

            target = get_sla_threshold(df_filtered, kpi, target_df)
            row["Target KPI"] = target

            if target is not None and pd.notna(avg_val):
                if "Abnormal" in kpi:
                    status = "Y" if avg_val <= target else "N"
                    delta = target - avg_val
                else:
                    status = "Y" if avg_val >= target else "N"
                    delta = avg_val - target

                row["Passed"] = status
                row["Delta"] = round(delta,2)
            else:
                row["Passed"] = "-"
                row["Delta"] = "-"

            df_summary.append(row)

        summary_df = pd.DataFrame(df_summary)

        def highlight_pass(val):
            if val == "Y":
                return "background-color:#b7e1cd"
            elif val == "N":
                return "background-color:#f4c7c3"
            return ""

        st.dataframe(
            summary_df.style.applymap(highlight_pass, subset=["Passed"]),
            use_container_width=True
        )

        st.stop()


    # ================= SECTOR COMBINE & BAND MATRIX =================
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

                if layout_mode == "Sector Combine":

                    df_grouped = df_sector.groupby(["CELL_NAME",x_col]).mean(numeric_only=True).reset_index()

                    if kpi not in df_grouped.columns:
                        continue

                    if kpi in traffic_kpi:
                        fig = px.area(df_grouped, x=x_col, y=kpi, color="CELL_NAME")
                    else:
                        fig = px.line(df_grouped, x=x_col, y=kpi, color="CELL_NAME", markers=True)

                    th = get_sla_threshold(df_sector, kpi, target_df)

                    if pd.notna(th):
                        fig.add_hline(
                            y=float(th),
                            line_color="red",
                            line_dash="dash",
                            annotation_text=f"{float(th):.2f}"
                        )

                    fig = apply_universal_legend(fig)
                    st.plotly_chart(fig, use_container_width=True)

                elif layout_mode == "Band Matrix":

                    bands = ["LTE900","LTE1800","LTE2100","LTE2300"]

                    for band_val in bands:

                        df_band = df_sector[df_sector["Band"] == band_val]

                        if df_band.empty:
                            continue

                        st.markdown(f"📡 {band_val}")

                        df_grouped = df_band.groupby(["CELL_NAME",x_col]).mean(numeric_only=True).reset_index()

                        if kpi not in df_grouped.columns:
                            continue

                        if kpi in traffic_kpi:
                            fig = px.area(df_grouped, x=x_col, y=kpi, color="CELL_NAME")
                        else:
                            fig = px.line(df_grouped, x=x_col, y=kpi, color="CELL_NAME", markers=True)

                        th = get_sla_threshold(df_band, kpi, target_df)

                        if pd.notna(th):
                            fig.add_hline(
                                y=float(th),
                                line_color="red",
                                line_dash="dash",
                                annotation_text=f"{float(th):.2f}"
                            )

                        fig = apply_universal_legend(fig)
                        st.plotly_chart(fig, use_container_width=True)
