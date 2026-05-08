# Industrial Units Dashboard — Streamlit App

## Files Required
Place all these files in the **same folder** as `app.py`:

| File | Description |
|------|-------------|
| `app.py` | Main Streamlit app |
| `units_enriched.csv` | Industrial units dataset (your original file) |
| `india_pc_2019.json` | PC boundaries GeoJSON (your original file) |

## Setup & Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
streamlit run app.py
```

Then open **http://localhost:8501** in your browser.

## Features
- Cascade filters: State → District → PC
- Interactive Leaflet map via Folium with cluster markers
- PC constituency boundary polygon overlay
- Summary KPI cards (units, states, districts, PCs, total employees)
- Unit list panel (first 250 matches)
- PC-wise summary table
- CSV download for filtered data
- Marker count slider for performance control
