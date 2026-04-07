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

    # fix numeric
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="ignore")

    df["DATE_ID"] = pd.to_datetime(df["DATE_ID"])

    if "Hour_id" in df.columns:
        df["DATETIME_ID"] = df["DATE_ID"] + pd.to_timedelta(df["Hour_id"], unit="h")
        df["DATA_RESOLUTION"] = "Hourly"
    else:
        df["DATETIME_ID"] = df["DATE_ID"]
        df["DATA_RESOLUTION"] = "Daily"

    df.rename(columns={"EUTRANCELLFDD":"CELL_NAME"}, inplace=True)
    df["SECTOR_GROUP"] = df["CELL_NAME"].apply(map_sector)

    df["Band"] = df["Band"].astype(str).str.upper().str.replace(" ","")

    return df


# ================= MAIN =================
uploaded = st.file_uploader("Upload KPI CSV", type=["csv","gz"])

layout_mode = st.sidebar.radio(
    "Layout Mode",
    ["Sector Combine","Band Matrix","Summary"]
)

kab_df, target_df = load_sla_master()

if uploaded:

    df = load_data(uploaded)

    kpi_list = [c for c in df.columns if c not in ["DATE_ID","CELL_NAME","SITE_ID","Band"]]

    selected_sites = st.multiselect("Select Site ID", sorted(df["SITE_ID"].unique()))

    if selected_sites:

        df_filtered = df[df["SITE_ID"].isin(selected_sites)]

        # ================= SUMMARY =================
        if layout_mode == "Summary":

            show_only_nok = st.checkbox("Show Only NOK KPI", value=False)

            unique_days = sorted(df_filtered["DATE_ID"].dt.date.unique())
            nok_found = False

            for kpi in kpi_list:

                avg = df_filtered[kpi].mean()
                th = get_sla_threshold(df_filtered, kpi, target_df)

                is_nok = False
                if th is not None and pd.notna(avg):
                    is_nok = avg < th

                if is_nok:
                    nok_found = True

                if show_only_nok and not is_nok:
                    continue

                st.write(("🔴" if is_nok else "🟢"), kpi, round(avg,2), "| SLA:", th)

            if show_only_nok and not nok_found:
                st.success("✅ All KPI Passed SLA")

        # ================= SECTOR COMBINE =================
        elif layout_mode == "Sector Combine":

            sectors = ["SEC1","SEC2","SEC3"]

            for kpi in kpi_list:
                st.subheader(kpi)
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
                            fig.add_hline(y=th, line_dash="dash", line_color="red")

                        st.plotly_chart(fig, use_container_width=True)

        # ================= BAND MATRIX =================
        elif layout_mode == "Band Matrix":

            bands = sorted(df_filtered["Band"].dropna().unique())
            sectors = ["SEC1","SEC2","SEC3"]

            for kpi in kpi_list:

                st.subheader(kpi)

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
                                fig.add_hline(y=th, line_dash="dash", line_color="red")

                            st.plotly_chart(fig, use_container_width=True)
