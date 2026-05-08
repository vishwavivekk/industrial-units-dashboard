import streamlit as st
import pandas as pd
import json
import os
from pathlib import Path

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Industrial Units Dashboard",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #f7f6f2; }
[data-testid="stSidebar"] { background: #f0ede8; }
[data-testid="stMetricValue"] { font-size: 2rem !important; font-weight: 700; color: #01696f; }
[data-testid="stMetricLabel"] { color: #6e6c66; font-size: 0.85rem; }
.unit-card { background: white; border: 1px solid #e8e4de; border-radius: 10px; padding: 12px 16px; margin-bottom: 8px; }
.unit-title { font-weight: 700; font-size: 0.95rem; color: #28251d; margin: 0 0 6px; }
.unit-meta { font-size: 0.8rem; color: #6e6c66; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 700; margin-right: 6px; }
.badge-pc { background: #d6eef0; color: #01696f; }
.badge-party { background: #e0eef8; color: #006494; }
</style>
""", unsafe_allow_html=True)

# ─── Resolve data paths ───────────────────────────────────────────────────────
# Works both locally and on Streamlit Cloud
# On Streamlit Cloud: repo root is /mount/src/industrial-units-dashboard/
# streamlit_app/app.py lives inside streamlit_app/, so parent = streamlit_app, parent.parent = repo root

APP_DIR  = Path(__file__).parent            # streamlit_app/
REPO_DIR = APP_DIR.parent                   # repo root

# Data files are at repo_root/processed/ and repo_root/
UNITS_JSON  = REPO_DIR / "processed" / "units_data.json"
GEOJSON     = REPO_DIR / "india_pc_2019.json"
FILTER_JSON = REPO_DIR / "processed" / "filter_data.json"

# ─── Data loading ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading industrial units...")
def load_units():
    with open(UNITS_JSON) as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df['State name']    = df['State name'].astype(str).str.strip()
    df['District Name'] = df['District Name'].astype(str).str.strip()
    df['PC name']       = df['PC name'].astype(str).str.strip()
    df['place']         = df['place'].astype(str).str.strip()
    df['latitude']      = pd.to_numeric(df['latitude'],  errors='coerce')
    df['longitude']     = pd.to_numeric(df['longitude'], errors='coerce')
    df['employees']     = pd.to_numeric(df['employees'], errors='coerce').fillna(0).astype(int)
    df = df.dropna(subset=['latitude','longitude'])
    df = df[(df['latitude'].between(-90,90)) & (df['longitude'].between(30,100))]
    return df

@st.cache_data(show_spinner="Loading GeoJSON boundaries...")
def load_geojson():
    with open(GEOJSON) as f:
        return json.load(f)

@st.cache_data(show_spinner="Loading filters...")
def load_filters():
    with open(FILTER_JSON) as f:
        return json.load(f)

df      = load_units()
geojson = load_geojson()
filters = load_filters()

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("# 🏭 Industrial Units Dashboard")
st.markdown("Map industrial units across Indian parliamentary constituency boundaries")
st.divider()

# ─── Sidebar filters ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔎 Filters")

    states = sorted(filters.keys())
    selected_state = st.selectbox("State", ["All states"] + states)

    if selected_state != "All states":
        districts = sorted(filters[selected_state].keys())
    else:
        districts = sorted(df['District Name'].dropna().unique().tolist())
    selected_district = st.selectbox("District", ["All districts"] + districts)

    if selected_state != "All states" and selected_district != "All districts":
        pcs = sorted([p['name'] for p in filters[selected_state].get(selected_district, [])])
    elif selected_state != "All states":
        pcs = sorted(set(p['name'] for d in filters[selected_state].values() for p in d))
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
c1.metric("🏭 Units",            f"{len(filtered):,}")
c2.metric("🏛 States",           filtered['State name'].nunique())
c3.metric("📍 Districts",        filtered['District Name'].nunique())
c4.metric("🗳 PCs",              filtered['PC name'].nunique())
c5.metric("👷 Total Employees",  f"{filtered['employees'].sum():,}")

st.divider()

# ─── Map + List layout ────────────────────────────────────────────────────────
map_col, list_col = st.columns([1.4, 0.6])

with map_col:
    st.markdown("### 🗺 Map View")
    try:
        import folium
        from streamlit_folium import st_folium

        pc_feat = None
        if selected_pc != "All PCs" and geojson:
            pc_feat = next(
                (f for f in geojson['features']
                 if f['properties'].get('pc_name','').strip().lower() == selected_pc.lower()
                 and (selected_state == "All states" or
                      f['properties'].get('st_name','').strip().lower() == selected_state.lower())),
                None
            )

        center_lat = filtered['latitude'].mean()  if len(filtered) > 0 else 22.8
        center_lon = filtered['longitude'].mean() if len(filtered) > 0 else 79.5
        zoom = 5 if selected_state == "All states" else (7 if selected_district == "All districts" else (9 if selected_pc == "All PCs" else 10))

        m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom,
                       tiles='CartoDB positron', control_scale=True)

        if show_boundary and pc_feat:
            folium.GeoJson(
                pc_feat,
                style_function=lambda x: {'color':'#01696f','weight':3,'fillColor':'#01696f','fillOpacity':0.07},
                tooltip=f"{pc_feat['properties']['pc_name']} | {pc_feat['properties']['st_name']}"
            ).add_to(m)

        if show_markers and len(filtered) > 0:
            from folium.plugins import MarkerCluster
            mc = MarkerCluster(options={'maxClusterRadius':40,'disableClusteringAtZoom':12}).add_to(m)
            for _, row in filtered.head(max_markers).iterrows():
                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    radius=5, color='#d9485f', fill=True,
                    fill_color='#d9485f', fill_opacity=0.75,
                    tooltip=f"{row['place']} | {row['PC name']} | Emp: {row['employees']}",
                    popup=folium.Popup(
                        f"<b>{row['place']}</b><br>PC: {row['PC name']}<br>"
                        f"District: {row['District Name']}<br>State: {row['State name']}<br>"
                        f"Employees: {row['employees']}<br>"
                        f"Winner: {row.get('Winner Name','NA')} ({row.get('Winner Party','NA')})",
                        max_width=260)
                ).add_to(mc)

        st_folium(m, use_container_width=True, height=560, returned_objects=[])

    except Exception as e:
        st.error(f"Map error: {e}")

with list_col:
    st.markdown(f"### 📋 Units <small style='color:#6e6c66;font-size:.8rem'>({len(filtered):,} found, showing 250)</small>", unsafe_allow_html=True)
    if len(filtered) == 0:
        st.info("No units match the current filters.")
    else:
        for _, row in filtered.head(250).iterrows():
            st.markdown(f"""
            <div class="unit-card">
                <div class="unit-title">{row['place'] or 'Industrial Unit'}</div>
                <div>
                    <span class="badge badge-pc">{row['PC name']}</span>
                    <span class="badge badge-party">{row.get('Winner Party','NA')}</span>
                </div>
                <div class="unit-meta" style="margin-top:8px;">
                    📍 {row['District Name']} | {row['State name']}<br>
                    👷 {row['employees']} employees &nbsp;|&nbsp; 🌐 {row['latitude']:.4f}, {row['longitude']:.4f}
                </div>
            </div>""", unsafe_allow_html=True)

st.divider()

with st.expander("📊 PC-wise Summary Table", expanded=False):
    summary = (
        filtered.groupby(['State name','District Name','PC name','Winner Party'])
        .agg(Units=('unit_id','count'), Total_Employees=('employees','sum'))
        .reset_index().sort_values('Units', ascending=False)
    )
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.download_button("⬇ Download CSV", summary.to_csv(index=False).encode(), "pc_summary.csv", "text/csv")

with st.expander("📥 Download filtered units", expanded=False):
    st.info(f"{len(filtered):,} units match current filters.")
    st.download_button("⬇ Download CSV", filtered.to_csv(index=False).encode(), "filtered_units.csv", "text/csv")
