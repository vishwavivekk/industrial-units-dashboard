# ── KPI Row (continued) ────────────────────────────────────────────────────────
k1, k2, k3, k4, k5, k6 = st.columns(6)

_n          = len(filt)
total_units = int(filt['units'].sum())
total_emp   = int(filt['total_employees'].sum())
avg_units   = round(filt['units'].mean(), 1) if _n else 0
top_state   = filt.groupby('State name')['units'].sum().idxmax() if _n else "—"
top_party   = filt.groupby('Winner Party')['units'].sum().idxmax() if _n else "—"

def kpi(col, val, label, sub=""):
    col.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-val">{val}</div>'
        f'<div class="metric-lbl">{label}</div>'
        f'<div class="metric-sub">{sub}</div>'
        f'</div>', unsafe_allow_html=True
    )

kpi(k1, f"{_n:,}",          "PC Constituencies", "filtered")
kpi(k2, f"{total_units:,}", "Industrial Units",  "registered")
kpi(k3, f"{total_emp:,}",   "Employees",         "total")
kpi(k4, f"{avg_units}",     "Avg Units/PC",      "mean")
kpi(k5, top_state[:12],     "Top State",         "by units")
kpi(k6, top_party[:12],     "Top Party",         "by units")

st.markdown("<br>", unsafe_allow_html=True)

# ── Map ────────────────────────────────────────────────────────────────────────
map_col, detail_col = st.columns([3, 1])

with map_col:
    st.markdown('<div class="section-title">🗺️ Industrial Cluster Map</div>', unsafe_allow_html=True)

    if filt.empty:
        st.warning("No data matches the current filters.")
    else:
        center_lat = filt['lat'].mean()
        center_lon = filt['lon'].mean()

        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=5,
            tiles='CartoDB dark_matter',
            width='100%'
        )

        # Optional radius circle
        if radius_center_coords:
            folium.Circle(
                location=list(radius_center_coords),
                radius=radius_km * 1000,
                color='#00d4ff',
                fill=True,
                fill_opacity=0.05,
                weight=1.5
            ).add_to(m)

        # Color scale for units count
        max_units_val = filt['units'].max() if _n else 1

        for _, row in filt.iterrows():
            # Determine marker color
            if view_mode == 'Winning Party':
                color = get_party_color(row['Winner Party'])
            elif view_mode == 'Top Industry':
                inds = row['industries']
                if isinstance(inds, dict) and inds:
                    top_ind = max(inds, key=inds.get)
                    color   = ind_color_map.get(top_ind, '#64748b')
                else:
                    color = '#64748b'
            else:  # Units Count
                intensity = row['units'] / max_units_val if max_units_val else 0
                r = int(0   + intensity * 255)
                g = int(212 - intensity * 150)
                b = int(255 - intensity * 200)
                color = f'#{r:02x}{g:02x}{b:02x}'

            radius = max(5, min(18, 5 + (row['units'] / max_units_val) * 13))

            # Tooltip
            inds_str = ', '.join(
                f"{k}({v})" for k, v in
                sorted((row['industries'] or {}).items(), key=lambda x: -x[1])[:3]
            )
            tooltip = (
                f"<b>{row['PC name']}</b><br>"
                f"{row['State name']} · {row['District Name']}<br>"
                f"Units: {row['units']:,} | Employees: {row['total_employees']:,}<br>"
                f"Winner: {row['Winner Name']} ({row['Winner Party']})<br>"
                f"Top Industries: {inds_str or 'N/A'}"
            )

            popup_html = f"""
            <div style='font-family:sans-serif;min-width:200px'>
                <h4 style='margin:0 0 6px;color:#00d4ff'>{row['PC name']}</h4>
                <b>State:</b> {row['State name']}<br>
                <b>District:</b> {row['District Name']}<br>
                <b>Units:</b> {row['units']:,}<br>
                <b>Employees:</b> {row['total_employees']:,}<br>
                <b>Winner:</b> {row['Winner Name']}<br>
                <b>Party:</b> {row['Winner Party']}<br>
                <b>Margin:</b> {row['margin']:,}<br>
                <b>Runner-up:</b> {row['runner_up']} ({row['runner_party']})<br>
                <b>Industries:</b> {inds_str or 'N/A'}
            </div>"""

            if show_clusters:
                folium.CircleMarker(
                    location=[row['lat'], row['lon']],
                    radius=radius,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.75,
                    weight=1,
                    tooltip=folium.Tooltip(tooltip, sticky=True),
                    popup=folium.Popup(popup_html, max_width=280)
                ).add_to(m)
            else:
                folium.Marker(
                    location=[row['lat'], row['lon']],
                    tooltip=folium.Tooltip(tooltip, sticky=True),
                    popup=folium.Popup(popup_html, max_width=280),
                    icon=folium.Icon(color='blue', icon='industry', prefix='fa')
                ).add_to(m)

        st_folium(m, use_container_width=True, height=580, returned_objects=[])

# ── Detail Panel ───────────────────────────────────────────────────────────────
with detail_col:
    st.markdown('<div class="section-title">🏆 Top PCs by Units</div>', unsafe_allow_html=True)
    top_pcs = filt.nlargest(10, 'units')[
        ['PC name', 'State name', 'units', 'total_employees', 'Winner Party']
    ].reset_index(drop=True)

    for _, r in top_pcs.iterrows():
        pct  = int(r['units'] / max(filt['units'].max(), 1) * 100)
        pclr = get_party_color(r['Winner Party'])
        st.markdown(
            f'<div class="rank-card">'
            f'<div style="font-size:12px;font-weight:600;color:#e2e8f0">{r["PC name"]}</div>'
            f'<div style="font-size:10px;color:#64748b">{r["State name"]}</div>'
            f'<div style="font-size:11px;color:#00d4ff;margin-top:2px">'
            f'{r["units"]:,} units · {r["total_employees"]:,} emp</div>'
            f'<div class="bar-wrap">'
            f'<div style="width:{pct}%;height:5px;background:{pclr};border-radius:2px"></div>'
            f'</div></div>',
            unsafe_allow_html=True
        )

    st.markdown('<div class="section-title" style="margin-top:14px">🏭 Industry Breakdown</div>',
                unsafe_allow_html=True)
    all_ind_counts = {}
    for inds in filt['industries']:
        if isinstance(inds, dict):
            for k, v in inds.items():
                all_ind_counts[k] = all_ind_counts.get(k, 0) + v
    for ind, cnt in sorted(all_ind_counts.items(), key=lambda x: -x[1])[:8]:
        clr  = ind_color_map.get(ind, '#64748b')
        ipct = int(cnt / max(sum(all_ind_counts.values()), 1) * 100)
        st.markdown(
            f'<div class="rank-card">'
            f'<div style="font-size:11px;font-weight:600;color:#e2e8f0">{ind[:28]}</div>'
            f'<div style="font-size:10px;color:{clr}">{cnt:,} establishments</div>'
            f'<div class="bar-wrap">'
            f'<div style="width:{ipct}%;height:5px;background:{clr};border-radius:2px"></div>'
            f'</div></div>',
            unsafe_allow_html=True
        )
