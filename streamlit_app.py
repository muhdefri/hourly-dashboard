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


# ================= SMART SECTOR =================
def map_sector(cell_name):
    name = str(cell_name).upper()
    match = re.search(r'(\d+)$', name)
    if match:
        d = int(match.group(1)) % 10
        if d in [1,4,7]: return "SEC1"
        if d in [2,5,8]: return "SEC2"
        if d in [3,6,9]: return "SEC3"
    return "SEC1"


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


def get_sla_threshold(df_scope, kpi, target_df):
    try:
        kab = df_scope["KABUPATEN"].dropna().iloc[0].lower().strip()
        band = df_scope["Band"].dropna().mode()[0]

        th = target_df[
            (target_df["kabupaten"].str.lower() == kab) &
            (target_df["band"] == str(band))
        ]

        col = [
            c for c in target_df.columns
            if c.replace("_","") == kpi.lower().replace("_","")
        ]

        if not th.empty and col:
            return th[col[0]].values[0]

    except:
        return None


# ================= LOAD =================
@st.cache_data
def load_data(file):

    if file.name.endswith(".gz"):
        df = pd.read_csv(file, compression="gzip", low_memory=False)
    else:
        df = pd.read_csv(file, low_memory=False)

    df.replace(["-", "NIL", "None", ""], pd.NA, inplace=True)

    # KPI LIST (dipakai juga untuk numeric conversion)
    kpi_columns = [
        "RRC Setup Success Rate (Service)",
        "ERAB_Setup_Success_Rate_All_New",
        "Session_Setup_Success_Rate_New",
        "Session_Abnormal_Release_New",
        "Intra-Frequency Handover Out Success Rate",
        "inter_freq_HO",
        "Radio_Network_Availability_Rate",
        "UL_INT_PUSCH",
        "Average_CQI_nonHOME",
        "SE_New",
        "Total_Traffic_Volume_new",
        "DL_Resource_Block_Utilizing_Rate_New",
        "UL_Resource_Block_Utilizing_Rate_New",
        "Downlink_Traffic_Volume_New",
        "Uplink_Traffic_Volume_New",
        "Active User DL"
    ]

    # 🔥 FIX: numeric conversion
    for col in kpi_columns:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["DATE_ID"] = pd.to_datetime(df["DATE_ID"], errors="coerce")

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

    # FILTER
    start = st.sidebar.date_input("Start", df["DATE_ID"].min().date())
    end = st.sidebar.date_input("End", df["DATE_ID"].max().date())

    df = df[(df["DATE_ID"] >= pd.to_datetime(start)) &
            (df["DATE_ID"] <= pd.to_datetime(end))]

    sites = st.multiselect("Select Site ID", sorted(df["SITE_ID"].unique()))

    if sites:

        df_filtered = df[df["SITE_ID"].isin(sites)]

        if kab_df is not None:
            df_filtered = df_filtered.merge(
                kab_df, left_on="SITE_ID", right_on="SiteID", how="left"
            )

        # ================= CHART =================
        if layout_mode in ["Sector Combine","Band Matrix"]:

            sectors = ["SEC1","SEC2","SEC3"]

            for kpi in kpi_list:

                if kpi not in df_filtered.columns:
                    continue

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

                            fig = px.line(df_g, x="DATE_ID", y=kpi, color="CELL_NAME")

                            th = get_sla_threshold(df_sec, kpi, target_df)
                            if pd.notna(th):
                                fig.add_hline(y=float(th), line_dash="dash", line_color="red")

                            st.plotly_chart(fig, use_container_width=True, key=f"{kpi}_{sec}")

                else:

                    for band in sorted(df_filtered["Band"].dropna().unique()):

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

                                fig = px.line(df_g, x="DATE_ID", y=kpi, color="CELL_NAME")

                                th = get_sla_threshold(df_sec, kpi, target_df)
                                if pd.notna(th):
                                    fig.add_hline(y=float(th), line_dash="dash", line_color="red")

                                st.plotly_chart(fig, use_container_width=True, key=f"{kpi}_{band}_{sec}")

        # ================= SUMMARY =================
        elif layout_mode == "Summary":

            band_opt = ["ALL"] + sorted(df_filtered["Band"].dropna().unique())
            band_sel = st.sidebar.selectbox("Filter Band", band_opt)

            df_scope = df_filtered if band_sel == "ALL" else df_filtered[df_filtered["Band"] == band_sel]

            cell_opt = ["ALL"] + sorted(df_scope["CELL_NAME"].unique())
            selected_cells = st.sidebar.multiselect("Filter Cell", cell_opt, default=["ALL"])

            if "ALL" not in selected_cells:
                df_scope = df_scope[df_scope["CELL_NAME"].isin(selected_cells)]

            st.markdown("## Site Level Performance")

            unique_days = sorted(df_scope["DATE_ID"].dt.date.unique())

            html = "<table style='border-collapse:collapse; width:100%;'>"
            html += "<tr style='background:#a5d6a7;'><th rowspan='2'>KPI</th>"

            for i in range(len(unique_days)):
                html += f"<th>DAY {i+1}</th>"

            html += "<th rowspan='2'>Average</th><th rowspan='2'>Target KPI</th><th rowspan='2'>Passed</th><th rowspan='2'>Delta</th></tr>"

            html += "<tr style='background:#c8e6c9;'>"
            for d in unique_days:
                html += f"<th>{pd.to_datetime(d).strftime('%d-%b-%y')}</th>"
            html += "</tr>"

            for kpi in summary_kpi:

                if kpi not in df_scope.columns:
                    continue

                daily_values = []

                for d in unique_days:
                    val = df_scope[df_scope["DATE_ID"].dt.date == d][kpi].mean()
                    daily_values.append(val)

                avg_val = pd.Series(daily_values).mean()
                target = get_sla_threshold(df_scope, kpi, target_df)

                html += "<tr><td><b>{}</b></td>".format(kpi)

                for val in daily_values:
                    html += f"<td>{round(val,2) if pd.notna(val) else ''}</td>"

                html += f"<td>{round(avg_val,2) if pd.notna(avg_val) else ''}</td>"
                html += f"<td>{round(target,2) if target is not None else ''}</td>"

                if target is not None and pd.notna(avg_val):
                    passed = "Y" if avg_val >= target else "N"
                    color = "#b7e1cd" if passed=="Y" else "#f4c7c3"
                    html += f"<td style='background:{color}'>{passed}</td>"
                    html += f"<td>{round(avg_val-target,2)}</td>"
                else:
                    html += "<td></td><td></td>"

                html += "</tr>"

            html += "</table>"

            st.markdown(html, unsafe_allow_html=True)

        # ================= PAYLOAD =================
        elif layout_mode == "Payload Stack":

            g = df_filtered.groupby(["DATE_ID","SITE_ID"])["Total_Traffic_Volume_new"].sum().reset_index()

            fig = px.area(g, x="DATE_ID", y="Total_Traffic_Volume_new", color="SITE_ID")

            st.plotly_chart(fig, use_container_width=True, key="payload_chart")
