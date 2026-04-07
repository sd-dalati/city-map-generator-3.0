import osmnx as ox
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import matplotlib.colors as mcolors
import numpy as np
from geopy.geocoders import Nominatim
from tqdm import tqdm
import time
import json
import os
import sys
from datetime import datetime
import argparse

THEMES_DIR = "../themes"
FONTS_DIR = "../fonts"
POSTERS_DIR = "../posters"

def load_fonts():
    fonts = {
        'bold': os.path.join(FONTS_DIR, 'Roboto-Bold.ttf'),
        'regular': os.path.join(FONTS_DIR, 'Roboto-Regular.ttf'),
        'light': os.path.join(FONTS_DIR, 'Roboto-Light.ttf')
    }
    for weight, path in fonts.items():
        if not os.path.exists(path):
            print(f"⚠ Font not found: {path}")
            return None
    return fonts

FONTS = load_fonts()

def generate_output_filename(city, theme_name):
    if not os.path.exists(POSTERS_DIR):
        os.makedirs(POSTERS_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    city_slug = city.lower().replace(' ', '_')
    filename = f"{city_slug}_{theme_name}_{timestamp}.png"
    return os.path.join(POSTERS_DIR, filename)

def get_available_themes():
    if not os.path.exists(THEMES_DIR):
        os.makedirs(THEMES_DIR)
        return []
    themes = []
    for file in sorted(os.listdir(THEMES_DIR)):
        if file.endswith('.json'):
            theme_name = file[:-5]
            themes.append(theme_name)
    return themes

def load_theme(theme_name="feature_based"):
    theme_file = os.path.join(THEMES_DIR, f"{theme_name}.json")
    if not os.path.exists(theme_file):
        print(f"⚠ Theme file '{theme_file}' not found. Using default.")
        return {
            "name": "Feature-Based Shading", "bg": "#FFFFFF", "text": "#000000",
            "gradient_color": "#FFFFFF", "water": "#C0C0C0", "parks": "#F0F0F0",
            "road_motorway": "#0A0A0A", "road_primary": "#1A1A1A", "road_secondary": "#2A2A2A",
            "road_tertiary": "#3A3A3A", "road_residential": "#4A4A4A", "road_default": "#3A3A3A"
        }
    with open(theme_file, 'r') as f:
        theme = json.load(f)
    print(f"✓ Loaded theme: {theme.get('name', theme_name)}")
    return theme

THEME = None

def create_gradient_fade(ax, color, location='bottom', zorder=10):
    vals = np.linspace(0, 1, 256).reshape(-1, 1)
    gradient = np.hstack((vals, vals))
    rgb = mcolors.to_rgb(color)
    my_colors = np.zeros((256, 4))
    my_colors[:, 0:3] = rgb
    if location == 'bottom':
        my_colors[:, 3] = np.linspace(1, 0, 256)
        extent_y = [0, 0.25]
    else:
        my_colors[:, 3] = np.linspace(0, 1, 256)
        extent_y = [0.75, 1.0]
    custom_cmap = mcolors.ListedColormap(my_colors)
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    y_range = ylim[1] - ylim[0]
    ax.imshow(gradient, extent=[xlim[0], xlim[1], ylim[0] + y_range * extent_y[0], ylim[0] + y_range * extent_y[1]], 
              aspect='auto', cmap=custom_cmap, zorder=zorder, origin='lower')

def get_edge_colors_by_type(G):
    edge_colors = []
    for u, v, data in G.edges(data=True):
        highway = data.get('highway', 'unclassified')
        if isinstance(highway, list): highway = highway[0]
        if highway in ['motorway', 'motorway_link']: color = THEME['road_motorway']
        elif highway in ['trunk', 'trunk_link', 'primary', 'primary_link']: color = THEME['road_primary']
        elif highway in ['secondary', 'secondary_link']: color = THEME['road_secondary']
        elif highway in ['tertiary', 'tertiary_link']: color = THEME['road_tertiary']
        elif highway in ['residential', 'living_street', 'unclassified']: color = THEME['road_residential']
        else: color = THEME['road_default']
        edge_colors.append(color)
    return edge_colors

def get_edge_widths_by_type(G):
    edge_widths = []
    for u, v, data in G.edges(data=True):
        highway = data.get('highway', 'unclassified')
        if isinstance(highway, list): highway = highway[0]
        if highway in ['motorway', 'motorway_link']: width = 1.2
        elif highway in ['trunk', 'trunk_link', 'primary', 'primary_link']: width = 1.0
        elif highway in ['secondary', 'secondary_link']: width = 0.8
        elif highway in ['tertiary', 'tertiary_link']: width = 0.6
        else: width = 0.4
        edge_widths.append(width)
    return edge_widths

def get_coordinates(city, country):
    print("Looking up coordinates...")
    geolocator = Nominatim(user_agent="city_map_poster_3")
    time.sleep(1)
    location = geolocator.geocode(f"{city}, {country}")
    if location:
        print(f"✓ Found: {location.address}")
        return (location.latitude, location.longitude)
    raise ValueError(f"Could not find coordinates for {city}, {country}")

def create_poster(city, country, point, dist, output_file, orientation='portrait'):
    print(f"Generating map for {city}, {country}...")
    with tqdm(total=3, desc="Fetching map data", unit="step") as pbar:
        G = ox.graph_from_point(point, dist=dist, dist_type='bbox', network_type='all')
        pbar.update(1)
        try: water = ox.features_from_point(point, tags={'natural': 'water', 'waterway': 'riverbank'}, dist=dist)
        except: water = None
        pbar.update(1)
        try: parks = ox.features_from_point(point, tags={'leisure': 'park', 'landuse': 'grass'}, dist=dist)
        except: parks = None
        pbar.update(1)
    
    fig, ax = plt.subplots(figsize=(12, 16) if orientation == 'portrait' else (20, 12), facecolor=THEME['bg'])
    ax.set_facecolor(THEME['bg'])
    ax.set_position([0, 0, 1, 1])

    if water is not None and not water.empty: water.plot(ax=ax, facecolor=THEME['water'], edgecolor='none', zorder=1)
    if parks is not None and not parks.empty: parks.plot(ax=ax, facecolor=THEME['parks'], edgecolor='none', zorder=2)

    ox.plot_graph(G, ax=ax, bgcolor=THEME['bg'], node_size=0, edge_color=get_edge_colors_by_type(G), 
                  edge_linewidth=get_edge_widths_by_type(G), show=False, close=False)

    create_gradient_fade(ax, THEME['gradient_color'], location='bottom', zorder=10)
    create_gradient_fade(ax, THEME['gradient_color'], location='top', zorder=10)

    font_main = FontProperties(fname=FONTS['bold'], size=60) if FONTS else FontProperties(family='monospace', weight='bold', size=60)
    ax.text(0.5, 0.14, " ".join(list(city.upper())), transform=ax.transAxes, color=THEME['text'], ha='center', fontproperties=font_main, zorder=11)
    
    plt.savefig(output_file, dpi=300, facecolor=THEME['bg'])
    plt.close()
    print(f"✓ Done! Poster saved as {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--city', '-c', type=str)
    parser.add_argument('--country', '-C', type=str)
    parser.add_argument('--theme', '-t', type=str, default='feature_based')
    parser.add_argument('--distance', '-d', type=int, default=10000)
    parser.add_argument('--lat', type=float)
    parser.add_argument('--lng', type=float)
    parser.add_argument('--orientation', '-o', choices=['portrait', 'landscape'], default='portrait')
    args = parser.parse_args()

    if len(sys.argv) == 1: sys.exit(0)
    if not (args.lat and args.lng) and not (args.city and args.country): sys.exit(1)

    try:
        THEME = load_theme(args.theme)
        coords = (args.lat, args.lng) if args.lat and args.lng else get_coordinates(args.city, args.country)
        city_name = args.city if args.city else f"{args.lat}_{args.lng}"
        create_poster(city_name, args.country or "custom", coords, args.distance, generate_output_filename(city_name, args.theme), args.orientation)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

