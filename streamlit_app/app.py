import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import json
import math
from pathlib import Path

st.set_page_config(
    page_title="Manufacturing Cluster Intelligence",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif !important; }

.metric-card {
    background: #111827; border: 1px solid #1e2d4a;
    border-radius: 10px; padding: 14px 16px; text-align: center;
}
.metric-val {
    font-size: 26px; font-weight: 700; color: #00d4ff;
    font-family: 'JetBrains Mono', monospace; line-height: 1.1;
}
.metric-lbl { font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-top: 3px; }
.metric-sub { font-size: 10px; color: #22d3ee; margin-top: 2px; }
.section-title {
    font-size: 11px; color: #64748b; text-transform: uppercase;
    letter-spacing: 1.5px; margin-bottom: 7px; padding-bottom: 5px;
    border-bottom: 1px solid #1e2d4a;
}
.pc-card {
    background: #0d1f35; border: 1px solid #00ff88;
    border-radius: 8px; padding: 11px 13px; margin: 7px 0;
}
.rank-card {
    background: #111827; border: 1px solid #1e2d4a;
    border-radius: 7px; padding: 9px 11px; margin-bottom: 6px;
}
.rank-card:hover { border-color: #00d4ff; }
.bar-wrap { background: #1a2235; border-radius: 2px; height: 5px; margin-top: 2px; }
.badge {
    display: inline-block; padding: 1px 8px; border-radius: 20px;
    font-size: 10px; font-weight: 600; margin-right: 4px;
}
div[data-testid="stTabs"] button { font-size: 13px !important; }
</style>
""", unsafe_allow_html=True)

# ─── Paths ──────────────────────────────────────────────────────────────────
APP_DIR  = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parent

PARTY_COLORS = {
    'Bharatiya Janata Party': '#ff9500',
    'Indian National Congress': '#19a7ce',
    'Samajwadi Party': '#e63946',
    'All India Trinamool Congress': '#28a745',
    'Trinamool Congress': '#28a745',
    'Telugu Desam Party': '#ffd700',
    'Telugu Desam': '#ffd700',
    'Janata Dal  (United)': '#9b59b6',
    'Dravida Munnetra Kazhagam': '#dc3545',
    'YSR Congress Party': '#0d6efd',
    'Yuvajana Sramika Rythu Congress Party': '#1a6ef5',
    'Biju Janata Dal': '#20c997',
    'Shiv Sena': '#fd7e14',
    'Janasena Party': '#e91e63',
    'Communist Party of India': '#cc0000',
    'Nationalist Congress Party - Sharadchandra Pawar': '#5f2eea',
    'Rashtriya Lok Dal': '#8bc34a',
    'Independent': '#888888',
}

IND_COLORS = [
    '#00d4ff','#00ff88','#ff6b35','#ffd700','#a855f7','#f472b6','#34d399',
    '#fb923c','#60a5fa','#f87171','#4ade80','#facc15','#818cf8','#e879f9',
    '#2dd4bf','#fb7185','#a3e635','#38bdf8','#c084fc','#fdba74','#67e8f9',
    '#86efac','#fca5a5','#d8b4fe','#fde68a','#a7f3d0','#bfdbfe','#fecaca',
    '#ddd6fe','#fed7aa','#6ee7b7','#93c5fd','#fda4af','#c4b5fd','#fcd34d',
    '#6edff6','#a3e635','#f9a8d4',
]

def get_party_color(party):
    return PARTY_COLORS.get(str(party).strip(), '#64748b')

def get_dist_km(lat1, lon1, lat2, lon2):
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dLon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ─── Data Loading ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading industrial data...")
def load_data():
    # ── units_enriched: unit-level lat/lon data ───
    eu = pd.read_csv(REPO_DIR / 'units_enriched.csv')
    eu.rename(columns={' District Name': 'District Name'}, inplace=True)
    for col in ['State name','District Name','PC name','place','Winner Name','Winner Party']:
        eu[col] = eu[col].astype(str).str.strip()
    eu['latitude']  = pd.to_numeric(eu['latitude'],  errors='coerce')
    eu['longitude'] = pd.to_numeric(eu['longitude'], errors='coerce')
    eu['employees'] = pd.to_numeric(eu['employees'], errors='coerce').fillna(0).astype(int)
    eu = eu.dropna(subset=['latitude','longitude'])
    eu = eu[(eu['latitude'].between(6,38)) & (eu['longitude'].between(68,98))]

    # ── Annexure: district-level industry breakdown ───
    df_raw = pd.read_csv(REPO_DIR / 'Annexure_with_3digit_Sheet1.csv')
    sub_hdr = df_raw.iloc[0]
    df_ann  = df_raw.iloc[1:].reset_index(drop=True).copy()
    df_ann.columns = df_raw.columns
    df_ann['Latitude']  = pd.to_numeric(df_ann['Latitude'],  errors='coerce')
    df_ann['Longitude'] = pd.to_numeric(df_ann['Longitude'], errors='coerce')

    industry_cols = [c for c in df_ann.columns if c not in ['State','District','Latitude','Longitude']]
    base_industries = {}
    for col in industry_cols:
        base = col.split('.')[0].strip()
        base_industries.setdefault(base, []).append(col)

    def safe_num(v):
        try:
            f = float(str(v).replace('-','0').replace(',',''))
            return 0 if math.isnan(f) else f
        except:
            return 0

    annex_map = {}
    for _, row in df_ann.iterrows():
        dist_key = str(row['District']).strip().upper()
        ind = {}
        for base, cols in base_industries.items():
            t = sum(safe_num(row[c]) for c in cols)
            if t > 0:
                ind[base] = int(t)
        annex_map[dist_key] = {'industries': ind, 'total_annex': sum(ind.values())}

    # ── PC-level aggregation ───
    pc_grp = eu.groupby(['State name','District Name','PC name','Winner Name','Winner Party']).agg(
        units=('unit_id','count'),
        total_employees=('employees','sum'),
        places=('place', lambda x: x.nunique())
    ).reset_index()

    pc_coords = eu.groupby('PC name').agg(lat=('latitude','mean'), lon=('longitude','mean')).reset_index()
    pc_grp = pc_grp.merge(pc_coords, on='PC name', how='left')

    # Attach industry data from annexure
    def get_industries(row):
        k = row['District Name'].upper().strip()
        return annex_map.get(k, {}).get('industries', {})

    pc_grp['industries'] = pc_grp.apply(get_industries, axis=1)
    pc_grp = pc_grp.dropna(subset=['lat','lon'])

    # ── Lok Sabha for margin data ───
    df_lok = pd.read_excel(REPO_DIR / 'Lok_Sabha_Elections_Winners_2024.xlsx')
    lok_map = {}
    for _, r in df_lok.iterrows():
        try:
            margin = int(r['Margin Votes'])
        except:
            margin = 0
        lok_map[str(r['PC Name']).strip().upper()] = {
            'margin': margin,
            'runner_up': str(r['Runner-up Canddiate']),
            'runner_party': str(r['Runner-up Party']),
        }
    def get_margin(pc_name):
        d = lok_map.get(str(pc_name).upper().strip(), {})
        return d.get('margin', 0), d.get('runner_up','N/A'), d.get('runner_party','N/A')

    pc_grp['margin'], pc_grp['runner_up'], pc_grp['runner_party'] = zip(*pc_grp['PC name'].map(get_margin))

    all_industries = sorted(set(k for ind in pc_grp['industries'] for k in ind))
    ind_color_map = {ind: IND_COLORS[i % len(IND_COLORS)] for i, ind in enumerate(all_industries)}

    return pc_grp, eu, all_industries, ind_color_map

pc_df, eu, all_industries, ind_color_map = load_data()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏭 MCI Dashboard")
    st.markdown("<span style='color:#64748b;font-size:12px'>Manufacturing Cluster Intelligence · Lok Sabha 2024</span>", unsafe_allow_html=True)
    st.divider()

    st.markdown("#### 🔍 Filters")
    states = ['All States'] + sorted(pc_df['State name'].dropna().unique())
    sel_state = st.selectbox("State", states)

    if sel_state != 'All States':
        districts = ['All Districts'] + sorted(pc_df[pc_df['State name']==sel_state]['District Name'].dropna().unique())
    else:
        districts = ['All Districts'] + sorted(pc_df['District Name'].dropna().unique())
    sel_district = st.selectbox("District", districts)

    if sel_state != 'All States' and sel_district != 'All Districts':
        pcs_avail = sorted(pc_df[(pc_df['State name']==sel_state)&(pc_df['District Name']==sel_district)]['PC name'].dropna().unique())
    elif sel_state != 'All States':
        pcs_avail = sorted(pc_df[pc_df['State name']==sel_state]['PC name'].dropna().unique())
    else:
        pcs_avail = sorted(pc_df['PC name'].dropna().unique())
    sel_pc = st.selectbox("Parliamentary Constituency", ['All PCs'] + pcs_avail)

    st.divider()
    ind_list = ['All Industries'] + all_industries
    sel_industry = st.selectbox("Industry Sector", ind_list)

    all_parties = ['All Parties'] + sorted(pc_df['Winner Party'].dropna().unique())
    sel_party = st.selectbox("Winning Party", all_parties)

    min_units = st.slider("Min. Units in PC", 0, int(pc_df['units'].max()), 0, step=5)

    st.divider()
    st.markdown("#### 🗺️ Map")
    view_mode = st.radio("Color By", ['Units Count', 'Top Industry', 'Winning Party'])
    show_clusters = st.checkbox("Cluster markers", value=True)

    st.divider()
    st.markdown("#### 📍 Radius Search")
    radius_km = st.slider("Radius (km)", 50, 500, 150, 25)
    radius_center = st.text_input("Center lat,lon", placeholder="28.6, 77.2")

    st.divider()
    total_u  = int(pc_df['units'].sum())
    total_em = int(pc_df['total_employees'].sum())
    st.caption(f"**{len(pc_df):,}** PC entries · **{total_u:,}** units · **{total_em:,}** employees")

# ─── Apply Filters ────────────────────────────────────────────────────────────
filt = pc_df.copy()
if sel_state    != 'All States':    filt = filt[filt['State name']    == sel_state]
if sel_district != 'All Districts': filt = filt[filt['District Name'] == sel_district]
if sel_pc       != 'All PCs':       filt = filt[filt['PC name']       == sel_pc]
if sel_party    != 'All Parties':   filt = filt[filt['Winner Party']  == sel_party]
if sel_industry != 'All Industries':
    filt = filt[filt['industries'].apply(lambda x: isinstance(x, dict) and x.get(sel_industry, 0) > 0)]
if min_units > 0:
    filt = filt[filt['units'] >= min_units]

radius_
