"""
Geolocalización detallada para España
"""
import plotly.graph_objects as go

SPAIN_COORDS = {
    'Madrid': {'lat': 40.4168, 'lon': -3.7038},
    'Barcelona': {'lat': 41.3851, 'lon': 2.1734},
    'Valencia': {'lat': 39.4699, 'lon': -0.3763},
    'Sevilla': {'lat': 37.3891, 'lon': -5.9845},
    'Bilbao': {'lat': 43.2630, 'lon': -2.9350},
    'Málaga': {'lat': 36.7213, 'lon': -4.4214},
    'Zaragoza': {'lat': 41.6488, 'lon': -0.8891},
}

PROVINCIA_KEYWORDS = {
    'Madrid': ['madrid'],
    'Barcelona': ['barcelona', 'cataluña'],
    'Valencia': ['valencia'],
    'Sevilla': ['sevilla', 'andalucia'],
}

def get_coords_from_region(region):
    region_lower = region.lower()
    for provincia, coords in SPAIN_COORDS.items():
        if provincia.lower() in region_lower:
            return coords['lat'], coords['lon']
    return 40.4168, -3.7038

def build_spain_map(df):
    spain_df = df[df.get('region', '').str.contains('España|Madrid|Barcelona', case=False, na=False)]
    if spain_df.empty:
        return None
    
    spain_df['lat'], spain_df['lon'] = zip(*spain_df['region'].apply(get_coords_from_region))
    
    fig = go.Figure()
    fig.add_trace(go.Scattergeo(
        lat=spain_df['lat'],
        lon=spain_df['lon'],
        mode='markers',
        marker=dict(
            size=spain_df['risk'].map({'Crítico': 25, 'Alto': 20, 'Medio': 15}),
            color=spain_df['risk'].map({'Crítico': '#ff4757', 'Alto': '#ffa502', 'Medio': '#00d4ff'}),
            opacity=0.7
        ),
        text=spain_df['title'],
        name='Amenazas España'
    ))
    
    fig.update_layout(
        title='📍 Amenazas en España',
        geo=dict(
            scope='europe',
            lonaxis_range=[-10, 5],
            lataxis_range=[35, 44],
            landcolor='#1a1f2e'
        ),
        height=400
    )
    return fig
