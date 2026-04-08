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

    # ================= KPI LIST =================
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

    # ================= FILTER =================
    min_date = df["DATE_ID"].min()
    max_date = df["DATE_ID"].max()

    start = st.sidebar.date_input("Start", min_date.date())
    end = st.sidebar.date_input("End", max_date.date())

    df = df[(df["DATE_ID"] >= pd.to_datetime(start)) &
            (df["DATE_ID"] <= pd.to_datetime(end))]

    sites = st.multiselect("Site", sorted(df["SITE_ID"].unique()))

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

                            d = df_filtered[df_filtered["SECTOR_GROUP"] == sec]
                            if d.empty:
                                continue

                            g = d.groupby("DATE_ID")[kpi].mean().reset_index()
                            fig = px.line(g, x="DATE_ID", y=kpi)

                            th = get_sla_threshold(d, kpi, target_df)
                            if th:
                                fig.add_hline(y=float(th), line_dash="dash", line_color="red")

                            st.plotly_chart(
                                apply_universal_legend(fig),
                                use_container_width=True,
                                key=f"{kpi}_{sec}"
                            )

                else:

                    for band in sorted(df_filtered["Band"].dropna().unique()):

                        st.markdown(f"### 📡 {band}")
                        cols = st.columns(3)

                        for i, sec in enumerate(sectors):
                            with cols[i]:

                                d = df_filtered[
                                    (df_filtered["Band"] == band) &
                                    (df_filtered["SECTOR_GROUP"] == sec)
                                ]

                                if d.empty:
                                    continue

                                g = d.groupby("DATE_ID")[kpi].mean().reset_index()
                                fig = px.line(g, x="DATE_ID", y=kpi)

                                th = get_sla_threshold(d, kpi, target_df)
                                if th:
                                    fig.add_hline(y=float(th), line_dash="dash", line_color="red")

                                st.plotly_chart(
                                    apply_universal_legend(fig),
                                    use_container_width=True,
                                    key=f"{kpi}_{band}_{sec}"
                                )

        # ================= SUMMARY =================
        elif layout_mode == "Summary":

            band_opt = ["ALL"] + sorted(df_filtered["Band"].dropna().unique())
            band_sel = st.sidebar.selectbox("Filter Band", band_opt)

            scope = df_filtered if band_sel == "ALL" else df_filtered[df_filtered["Band"] == band_sel]

            cell_opt = ["ALL"] + sorted(scope["CELL_NAME"].unique())
            cell_sel = st.sidebar.multiselect("Filter Cell", cell_opt, default=["ALL"])

            if "ALL" not in cell_sel:
                scope = scope[scope["CELL_NAME"].isin(cell_sel)]

            if scope.empty:
                st.warning("No data")
                st.stop()

            st.markdown("## Site Level Performance")

            for kpi in summary_kpi:
                if kpi not in scope.columns:
                    continue

                val = scope[kpi].mean()
                target = get_sla_threshold(scope, kpi, target_df)

                st.write(f"{kpi} | Avg: {round(val,2)} | SLA: {target}")

        # ================= PAYLOAD =================
        elif layout_mode == "Payload Stack":

            g = df_filtered.groupby(["DATE_ID","SITE_ID"])["Total_Traffic_Volume_new"].sum().reset_index()

            fig = px.area(
                g,
                x="DATE_ID",
                y="Total_Traffic_Volume_new",
                color="SITE_ID"
            )

            st.plotly_chart(
                apply_universal_legend(fig),
                use_container_width=True,
                key="payload_chart"
            )
