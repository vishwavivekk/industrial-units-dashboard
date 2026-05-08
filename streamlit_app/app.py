import streamlit as st
import pandas as pd
import json
import os
import folium
from streamlit_folium import st_folium
from pathlib import Path

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Industrial Units Dashboard",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #f7f6f2; }
[data-testid="stSidebar"] { background: #f0ede8; }
[data-testid="stMetricValue"] { font-size: 2rem !important; font-weight: 700; color: #01696f; }
[data-testid="stMetricLabel"] { color: #6e6c66; font-size: 0.85rem; }
.unit-card {
    background: white;
    border: 1px solid #e8e4de;
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 8px;
}
.unit-title { font-weight: 700; font-size: 0.95rem; color: #28251d; margin: 0 0 6px; }
.unit-meta { font-size: 0.8rem; color: #6e6c66; }
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 700;
    margin-right: 6px;
}
.badge-pc { background: #d6eef0; color: #01696f; }
.badge-party { background: #e0eef8; color: #006494; }
h1 { color: #28251d !important; }
</style>
""", unsafe_allow_html=True)

# ─── Data loading (cached) ────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent

@st.cache_data(show_spinner="Loading industrial units...")
def load_units():
    df = pd.read_csv(DATA_DIR / "units_enriched.csv")
    df.rename(columns={' District Name': 'District Name'}, inplace=True)
    df['State name']    = df['State name'].str.strip()
    df['District Name'] = df['District Name'].str.strip()
    df['PC name']       = df['PC name'].str.strip()
    df['place']         = df['place'].str.strip()
    df = df.dropna(subset=['latitude', 'longitude'])
    df = df[(df['latitude'].between(-90, 90)) & (df['longitude'].between(30, 100))]
    df['PC ID'] = df['PC ID'].fillna(0).astype(int)
    return df

@st.cache_data(show_spinner="Loading GeoJSON boundaries...")
def load_geojson():
    with open(DATA_DIR / "india_pc_2019.json") as f:
        return json.load(f)

# ─── Load data ────────────────────────────────────────────────────────────────
df     = load_units()
geojson = load_geojson()

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("# 🏭 Industrial Units Dashboard")
st.markdown("Map industrial units across Indian parliamentary constituency boundaries")
st.divider()

# ─── Sidebar filters ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔎 Filters")

    states = sorted(df['State name'].dropna().unique().tolist())
    selected_state = st.selectbox("State", ["All states"] + states)

    if selected_state != "All states":
        districts = sorted(df[df['State name'] == selected_state]['District Name'].dropna().unique().tolist())
    else:
        districts = sorted(df['District Name'].dropna().unique().tolist())
    selected_district = st.selectbox("District", ["All districts"] + districts)

    if selected_state != "All states" and selected_district != "All districts":
        pcs = sorted(df[(df['State name'] == selected_state) & (df['District Name'] == selected_district)]['PC name'].dropna().unique().tolist())
    elif selected_state != "All states":
        pcs = sorted(df[df['State name'] == selected_state]['PC name'].dropna().unique().tolist())
    else:
        pcs = sorted(df['PC name'].dropna().unique().tolist())
    selected_pc = st.selectbox("Principal Constituency", ["All PCs"] + pcs)

    st.markdown("---")
    search_query = st.text_input("🔍 Search place / unit", placeholder="Type to search...")

    st.markdown("---")
    max_markers = st.slider("Max map markers", 100, 5000, 2000, 100,
        help="Limit markers for map performance")

    st.markdown("---")
    show_boundary = st.checkbox("Show PC boundary", value=True)
    show_markers  = st.checkbox("Show unit markers", value=True)

# ─── Filter logic ─────────────────────────────────────────────────────────────
filtered = df.copy()
if selected_state    != "All states":    filtered = filtered[filtered['State name']    == selected_state]
if selected_district != "All districts": filtered = filtered[filtered['District Name'] == selected_district]
if selected_pc       != "All PCs":       filtered = filtered[filtered['PC name']       == selected_pc]
if search_query:
    q = search_query.lower()
    filtered = filtered[
        filtered['place'].str.lower().str.contains(q, na=False) |
        filtered['PC name'].str.lower().str.contains(q, na=False) |
        filtered['District Name'].str.lower().str.contains(q, na=False)
    ]

# ─── KPI row ──────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🏭 Industrial Units", f"{len(filtered):,}")
c2.metric("🏛 States",           filtered['State name'].nunique())
c3.metric("📍 Districts",        filtered['District Name'].nunique())
c4.metric("🗳 PCs",              filtered['PC name'].nunique())
c5.metric("👷 Total Employees",  f"{filtered['employees'].sum():,}")

st.divider()

# ─── Map + List layout ────────────────────────────────────────────────────────
map_col, list_col = st.columns([1.4, 0.6])

# ── Map ──────────────────────────────────────────────────────────────────────
with map_col:
    st.markdown("### 🗺 Map View")

    # Determine map center
    if selected_pc != "All PCs":
        pc_feat = next(
            (f for f in geojson['features']
             if f['properties'].get('pc_name', '').strip().lower() == selected_pc.lower()
             and (selected_state == "All states" or
                  f['properties'].get('st_name','').strip().lower() == selected_state.lower())),
            None
        )
    else:
        pc_feat = None

    if len(filtered) > 0:
        center_lat = filtered['latitude'].mean()
        center_lon = filtered['longitude'].mean()
    else:
        center_lat, center_lon = 22.8, 79.5

    zoom = 5 if selected_state == "All states" else (7 if selected_district == "All districts" else (9 if selected_pc == "All PCs" else 10))
    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom,
                   tiles='CartoDB positron', control_scale=True)

    # PC boundary
    if show_boundary and pc_feat:
        folium.GeoJson(
            pc_feat,
            name="PC Boundary",
            style_function=lambda x: {
                'color': '#01696f', 'weight': 3,
                'fillColor': '#01696f', 'fillOpacity': 0.07
            },
            tooltip=f"{pc_feat['properties']['pc_name']} | {pc_feat['properties']['st_name']}"
        ).add_to(m)

    # Unit markers
    if show_markers and len(filtered) > 0:
        sample = filtered.head(max_markers)
        from folium.plugins import MarkerCluster
        mc = MarkerCluster(
            options={'maxClusterRadius': 40, 'disableClusteringAtZoom': 12}
        ).add_to(m)
        for _, row in sample.iterrows():
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=5,
                color='#d9485f',
                fill=True,
                fill_color='#d9485f',
                fill_opacity=0.75,
                tooltip=f"{row['place']} | {row['PC name']} | Employees: {row['employees']}",
                popup=folium.Popup(
                    f"<b>{row['place']}</b><br>"
                    f"PC: {row['PC name']}<br>"
                    f"District: {row['District Name']}<br>"
                    f"State: {row['State name']}<br>"
                    f"Employees: {row['employees']}<br>"
                    f"Winner: {row.get('Winner Name', 'NA')} ({row.get('Winner Party', 'NA')})",
                    max_width=260
                )
            ).add_to(mc)

    st_folium(m, use_container_width=True, height=580, returned_objects=[])

# ── Unit list ─────────────────────────────────────────────────────────────────
with list_col:
    st.markdown(f"### 📋 Unit List <small style='color:#6e6c66; font-size:0.8rem'>({len(filtered):,} found, showing 250)</small>", unsafe_allow_html=True)

    if len(filtered) == 0:
        st.info("No units match your current filters.")
    else:
        display = filtered.head(250)
        for _, row in display.iterrows():
            st.markdown(f"""
            <div class="unit-card">
                <div class="unit-title">{row['place'] or 'Industrial Unit'}</div>
                <div>
                    <span class="badge badge-pc">{row['PC name']}</span>
                    <span class="badge badge-party">{row.get('Winner Party','NA')}</span>
                </div>
                <div class="unit-meta" style="margin-top:8px;">
                    📍 {row['District Name']} &nbsp;|&nbsp; {row['State name']}<br>
                    👷 Employees: {row['employees']} &nbsp;|&nbsp;
                    🌐 {row['latitude']:.4f}, {row['longitude']:.4f}
                </div>
            </div>
            """, unsafe_allow_html=True)

st.divider()

# ─── Summary table ────────────────────────────────────────────────────────────
with st.expander("📊 Summary Table — PC-wise unit count", expanded=False):
    summary = (
        filtered.groupby(['State name', 'District Name', 'PC name', 'Winner Party'])
        .agg(Units=('unit_id', 'count'), Total_Employees=('employees', 'sum'))
        .reset_index()
        .sort_values('Units', ascending=False)
    )
    st.dataframe(summary, use_container_width=True, hide_index=True)
    csv = summary.to_csv(index=False).encode('utf-8')
    st.download_button("⬇ Download summary CSV", csv, "pc_summary.csv", "text/csv")

# ─── Raw data download ────────────────────────────────────────────────────────
with st.expander("📥 Download filtered units", expanded=False):
    st.info(f"{len(filtered):,} units match current filters.")
    raw_csv = filtered.to_csv(index=False).encode('utf-8')
    st.download_button("⬇ Download filtered units CSV", raw_csv, "filtered_units.csv", "text/csv")
