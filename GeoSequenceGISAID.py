import argparse
import collections
import json
import requests
import pandas as pd
import folium
import branca.colormap as cm

def extract_state_from_header(header_line):
    header_line = header_line.strip().lstrip(">")
    main_part = header_line.split("|")[0]
    
    tokens = [token.strip().replace("_", " ").title() for token in main_part.split("/")]
    
    synonyms = {
        "Usa": "United States of America",
        "Antigua And Bermuda": "Antigua and Barbuda",
        "Trinidad And Tobago": "Trinidad and Tobago",
        "Turks And Caicos Islands": "Turks and Caicos Islands",
        "U.S. Virgin Islands": "United States Virgin Islands"
    }
    tokens = [synonyms.get(token, token) for token in tokens]
    
    banned = {"Chikv", "Hchikv", "Un", "Monkey", "Mosquito", "Mouse"}
    
    candidate = None
    if len(tokens) > 1 and tokens[1] not in banned and not any(ch.isdigit() for ch in tokens[1]):
        candidate = tokens[1]
    elif len(tokens) > 2 and tokens[2] not in banned and not any(ch.isdigit() for ch in tokens[2]):
        candidate = tokens[2]
    else:

        for token in tokens[1:]:
            if token not in banned and not any(ch.isdigit() for ch in token):
                candidate = token
                break
    if candidate is None:
        candidate = "unknown"
    return candidate

def load_fasta_counts(fasta_file):

    counts = collections.Counter()
    with open(fasta_file, "r") as f:
        for line in f:
            if line.startswith(">"):
                state = extract_state_from_header(line)
                counts[state] += 1
    return counts

def get_country_property(feature):

    props = feature.get("properties", {})
    return props.get("NAME") or props.get("ADMIN") or props.get("name")

def tooltip_function(feature, counts_dict_norm):
    country_name = get_country_property(feature)
    if not country_name:
        return "N/A"
    value = counts_dict_norm.get(country_name.lower(), None)
    if value is not None:
        return f"{country_name}: {value} sequence(s)"
    else:
        return country_name

def main():
    parser = argparse.ArgumentParser(
        description="Genera una mappa Choropleth e una tabella Excel dai titoli FASTA."
    )
    parser.add_argument(
        "-i", "--input", default="sequences.fasta",
        help="File FASTA di input (default: sequences.fasta)"
    )
    parser.add_argument(
        "-e", "--excel", default="sequence_counts.xlsx",
        help="Nome del file Excel di output (default: sequence_counts.xlsx)"
    )
    parser.add_argument(
        "-m", "--map", default="country_map.html",
        help="Nome del file HTML della mappa di output (default: country_map.html)"
    )
    parser.add_argument(
        "-g", "--geojson", default="https://raw.githubusercontent.com/python-visualization/folium/master/examples/data/world-countries.json",
        help="URL o percorso al file GeoJSON dei confini dei paesi"
    )
    args = parser.parse_args()
    
    counts = load_fasta_counts(args.input)
    
    data = [(state, count) for state, count in counts.items() if state != "unknown"]
    df = pd.DataFrame(data, columns=["Country", "Sequence_Count"])
    print("Sequence Counts per Country:")
    print(df)
    
    df.to_excel(args.excel, index=False)
    print(f"Tabella Excel salvata in: {args.excel}")
    
    try:
        if args.geojson.startswith("http"):
            response = requests.get(args.geojson)
            world_geo = response.json()
        else:
            with open(args.geojson, "r", encoding="utf-8") as f:
                world_geo = json.load(f)
    except Exception as e:
        print(f"Errore nel caricamento del GeoJSON: {e}")
        return
    
    m = folium.Map(location=[20, 0], zoom_start=2)
    
    counts_dict = dict(df.values)
    # Crea un dizionario normalizzato (chiavi in minuscolo) per il matching con il GeoJSON
    counts_norm = {k.lower(): v for k, v in counts_dict.items()}
    
    min_count = df["Sequence_Count"].min() if not df.empty else 0
    max_count = df["Sequence_Count"].max() if not df.empty else 1
    colormap = cm.LinearColormap(colors=["green", "red"], vmin=min_count, vmax=max_count)
    colormap.caption = "Sequence Count"
    colormap.add_to(m)
    
    def style_function(feature):
        country_name = get_country_property(feature)
        if not country_name:
            return {"fillOpacity": 0.1, "weight": 0.5, "color": "black"}
        value = counts_norm.get(country_name.lower(), None)
        if value is None:
            return {"fillOpacity": 0.1, "weight": 0.5, "color": "black"}
        return {"fillColor": colormap(value), "fillOpacity": 0.7, "weight": 0.5, "color": "black"}
    
    for feature in world_geo.get("features", []):
        feature["properties"]["tooltip"] = tooltip_function(feature, counts_norm)
    
    folium.GeoJson(
        world_geo,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=["tooltip"],
            aliases=["Country:"],
            labels=True,
            sticky=True,
            style=("background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 5px;")
        )
    ).add_to(m)
    
    m.save(args.map)
    print(f"Mappa salvata in: {args.map}")

if __name__ == "__main__":
    main()
