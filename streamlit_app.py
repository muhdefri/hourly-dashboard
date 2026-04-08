# ================= CHART FIX =================

# SECTOR COMBINE
df_g = df_sec.groupby(["CELL_NAME","DATE_ID"]).mean(numeric_only=True).reset_index()

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


# ================= BAND MATRIX FIX =================

df_g = df_sec.groupby(["CELL_NAME","DATE_ID"]).mean(numeric_only=True).reset_index()

fig = px.line(df_g, x="DATE_ID", y=kpi, color="CELL_NAME")

th = get_sla_threshold(df_sec, kpi, target_df)
if pd.notna(th):
    fig.add_hline(
        y=float(th),
        line_dash="dash",
        line_color="red"
    )


# ================= SUMMARY FIX (BALIK TABLE) =================

st.markdown("## Site Level Performance")

unique_days = sorted(df_scope["DATE_ID"].dt.date.unique())

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

    daily_values = []

    for d in unique_days:
        val = df_scope[df_scope["DATE_ID"].dt.date == d][kpi].mean()
        daily_values.append(val)

    avg_val = pd.Series(daily_values).mean()
    target = get_sla_threshold(df_scope, kpi, target_df)

    html += "<tr>"
    html += f"<td><b>{kpi}</b></td>"

    for val in daily_values:
        html += f"<td>{round(val,2) if pd.notna(val) else ''}</td>"

    avg_show = round(avg_val,2) if pd.notna(avg_val) else ""
    target_show = round(target,2) if target is not None else ""

    html += f"<td>{avg_show}</td>"
    html += f"<td>{target_show}</td>"

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

st.markdown(html, unsafe_allow_html=True)
