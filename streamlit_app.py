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


# ================= SECTOR =================
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
    try:
        kab = str(df_scope["KABUPATEN"].dropna().iloc[0]).lower().strip()
        band = str(df_scope["Band"].dropna().iloc[0]).lower().strip()

        df = target_df[
            (target_df["kabupaten"].str.lower() == kab) &
            (target_df["band"].str.lower() == band)
        ]

        col = [
            c for c in target_df.columns
            if c.replace("_","").replace(" ","") ==
            kpi.lower().replace("_","").replace(" ","")
        ]

        if not df.empty and col:
            return df[col[0]].values[0]
    except:
        return None

    return None


# ================= LOAD DATA =================
@st.cache_data
def load_data(file):

    df = pd.read_csv(
        file,
        compression="gzip" if file.name.endswith(".gz") else None,
        low_memory=False
    )

    # CLEAN KPI
    for col in df.columns:

        if df[col].dtype == "object":
            df[col] = (
                df[col]
                .astype(str)
                .str.replace('%','', regex=False)
                .str.replace(',','.', regex=False)
            )

            df[col] = pd.to_numeric(df[col], errors='coerce')

    df["DATE_ID"] = pd.to_datetime(df["DATE_ID"])

    if "Hour_id" in df.columns:
        df["DATETIME_ID"] = df["DATE_ID"] + pd.to_timedelta(df["Hour_id"], unit="h")
    else:
        df["DATETIME_ID"] = df["DATE_ID"]

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

    # ================= AUTO KPI =================
    exclude_cols = [
        "SITE_ID","CELL_NAME","Band",
        "DATE_ID","DATETIME_ID","Hour_id","SECTOR_GROUP"
    ]

    kpi_list = [
        col for col in df.columns
        if col not in exclude_cols and pd.api.types.is_numeric_dtype(df[col])
    ]

    # DEBUG
    st.sidebar.write("KPI Detected:", kpi_list)

    # ================= FILTER =================
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

        # ================= SECTOR COMBINE =================
        if layout_mode == "Sector Combine":

            sectors = ["SEC1","SEC2","SEC3"]

            for kpi in kpi_list:

                st.markdown("---")
                st.subheader(kpi)

                cols = st.columns(3)

                for i, sec in enumerate(sectors):

                    with cols[i]:

                        df_sec = df_filtered[df_filtered["SECTOR_GROUP"] == sec]

                        if df_sec.empty:
                            st.write("No Data")
                            continue

                        df_temp = df_sec.dropna(subset=[kpi])

                        if df_temp.empty:
                            st.write("No Data")
                            continue

                        df_plot = df_temp.groupby(["CELL_NAME", x_col])[kpi].mean().reset_index()

                        fig = px.line(df_plot, x=x_col, y=kpi, color="CELL_NAME")

                        th = get_sla_threshold(df_sec, kpi, target_df)
                        if pd.notna(th):
                            fig.add_hline(y=float(th), line_color="red", line_dash="dash")

                        st.plotly_chart(apply_universal_legend(fig), use_container_width=True)

        # ================= BAND MATRIX =================
        elif layout_mode == "Band Matrix":

            sectors = ["SEC1","SEC2","SEC3"]
            bands = ["LTE900","LTE1800","LTE2100","LTE2300"]

            for kpi in kpi_list:

                st.markdown("---")
                st.subheader(kpi)

                header = st.columns(3)
                for i, sec in enumerate(sectors):
                    header[i].markdown(f"### {sec}")

                for band in bands:

                    st.markdown(f"#### {band}")

                    cols = st.columns(3)

                    for i, sec in enumerate(sectors):

                        with cols[i]:

                            df_sec = df_filtered[
                                (df_filtered["SECTOR_GROUP"] == sec) &
                                (df_filtered["Band"] == band)
                            ]

                            if df_sec.empty:
                                st.write("-")
                                continue

                            df_temp = df_sec.dropna(subset=[kpi])

                            if df_temp.empty:
                                st.write("-")
                                continue

                            df_plot = df_temp.groupby(["CELL_NAME", x_col])[kpi].mean().reset_index()

                            fig = px.line(df_plot, x=x_col, y=kpi, color="CELL_NAME")

                            th = get_sla_threshold(df_sec, kpi, target_df)
                            if pd.notna(th):
                                fig.add_hline(y=float(th), line_color="red", line_dash="dash")

                            st.plotly_chart(apply_universal_legend(fig), use_container_width=True)

        # ================= SUMMARY =================
        elif layout_mode == "Summary":

            st.subheader("Summary KPI")

            unique_days = sorted(df_filtered["DATE_ID"].dt.date.unique())

            html = "<table style='border-collapse:collapse; width:100%;'>"
            html += "<tr><th>KPI</th>"

            for d in unique_days:
                html += f"<th>{pd.to_datetime(d).strftime('%d-%b')}</th>"

            html += "<th>AVG</th></tr>"

            for kpi in kpi_list:

                html += f"<tr><td>{kpi}</td>"

                vals = []
                for d in unique_days:
                    val = df_filtered[df_filtered["DATE_ID"].dt.date == d][kpi].mean()
                    vals.append(val)
                    html += f"<td>{round(val,2) if pd.notna(val) else ''}</td>"

                html += f"<td>{round(pd.Series(vals).mean(),2)}</td>"
                html += "</tr>"

            html += "</table>"
            st.markdown(html, unsafe_allow_html=True)

        # ================= PAYLOAD =================
        elif layout_mode == "Payload Stack":

            if "Total_Traffic_Volume_new" in df_filtered.columns:

                df_plot = df_filtered.groupby(["DATE_ID","SITE_ID"])["Total_Traffic_Volume_new"].sum().reset_index()

                fig = px.area(df_plot, x="DATE_ID", y="Total_Traffic_Volume_new", color="SITE_ID")
                st.plotly_chart(apply_universal_legend(fig), use_container_width=True)
