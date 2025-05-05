import streamlit as st
from streamlit_folium import st_folium
import folium
import requests
import json
import pandas as pd
from shapely.geometry import Point, shape
import io
import csv

# Configuration de la page
st.set_page_config(
    page_title="Zones accessibles sur carte",
    layout="wide"
)

# Initialisation des variables d'état dans la session
if 'geojson_data' not in st.session_state:
    st.session_state.geojson_data = None
if 'lat' not in st.session_state:
    st.session_state.lat = 48.858370  # Paris, Tour Eiffel par défaut
if 'lon' not in st.session_state:
    st.session_state.lon = 2.294481
if 'minutes' not in st.session_state:
    st.session_state.minutes = 10
if 'mode' not in st.session_state:
    st.session_state.mode = "foot-walking"
if 'calculation_done' not in st.session_state:
    st.session_state.calculation_done = False
if 'addresses' not in st.session_state:
    st.session_state.addresses = []
if 'start_point_method' not in st.session_state:
    st.session_state.start_point_method = "map"  # Méthode par défaut: map ou address
if 'map_center' not in st.session_state:
    st.session_state.map_center = [st.session_state.lat, st.session_state.lon]
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = 14
if 'map_height' not in st.session_state:
    st.session_state.map_height = 70  # Hauteur par défaut en pourcentage de la hauteur de la fenêtre

st.title("Zones accessibles sur carte")

# Configuration de la clé API
ORS_API_KEY = st.sidebar.text_input(
    "Clé API OpenRouteService",
    value="",  # Vous pouvez remplacer par votre propre clé
    type="password",
    help="Obtenez une clé API gratuite sur https://openrouteservice.org/dev/#/signup"
)

if not ORS_API_KEY:
    st.warning("Veuillez entrer une clé API OpenRouteService pour utiliser cette application")
    #st.stop()

# Fonction pour géocoder une adresse - version améliorée
def geocode_address(address):
    url = "https://api.openrouteservice.org/geocode/search"
    headers = {
        "Authorization": ORS_API_KEY,
        "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8"
    }
    params = {
        "text": address,
        "size": 1,  # Limiter à un seul résultat
        "boundary.country": "FR"  # Vous pouvez ajuster cela selon vos besoins
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("features") and len(data["features"]) > 0:
                feature = data["features"][0]
                coordinates = feature["geometry"]["coordinates"]
                
                # Extraire l'adresse complète des propriétés
                properties = feature["properties"]
                formatted_address = properties.get("label", "Adresse inconnue")
                
                return {
                    "lat": coordinates[1], 
                    "lon": coordinates[0],
                    "address": formatted_address,
                    "properties": properties
                }
            else:
                st.error(f"Aucun résultat trouvé pour l'adresse: {address}")
                return None
        else:
            st.error(f"Erreur lors du géocodage : {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Une erreur s'est produite lors du géocodage : {str(e)}")
        return None

# Fonction pour géocoder plusieurs adresses (avec gestion des erreurs individuelles)
def geocode_multiple_addresses(addresses_list):
    results = []
    
    with st.spinner(f"Géocodage de {len(addresses_list)} adresses..."):
        for address in addresses_list:
            address = address.strip()
            if address:  # Ignorer les lignes vides
                result = geocode_address(address)
                if result:
                    results.append({
                        "original_address": address,
                        "geocoded_address": result["address"],
                        "lat": result["lat"],
                        "lon": result["lon"],
                        "in_zone": None,
                        "travel_time": None
                    })
                else:
                    # Ajouter quand même l'adresse avec des valeurs nulles pour montrer qu'elle a échoué
                    results.append({
                        "original_address": address,
                        "geocoded_address": "Échec du géocodage",
                        "lat": None,
                        "lon": None,
                        "in_zone": None,
                        "travel_time": None
                    })
    
    return results

# Fonction pour géocoder une adresse et définir le point initial
def set_start_point_by_address():
    address_data = geocode_address(start_address_input)
    if address_data:
        st.session_state.lat = address_data["lat"]
        st.session_state.lon = address_data["lon"]
        # Centrer la carte sur le nouveau point
        st.session_state.map_center = [address_data["lat"], address_data["lon"]]
        st.session_state.calculation_done = False
        st.session_state.geojson_data = None
        # Réinitialiser les résultats des adresses précédentes
        if st.session_state.addresses:
            for addr in st.session_state.addresses:
                addr["in_zone"] = None
                addr["travel_time"] = None
        st.success(f"Point de départ défini à : {address_data['address']}")
        return True
    return False

# Fonction pour calculer le temps de trajet entre deux points
def calculate_travel_time(start_lat, start_lon, end_lat, end_lon, mode):
    url = f"https://api.openrouteservice.org/v2/directions/{mode}"
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json"
    }
    params = {
        "coordinates": [[start_lon, start_lat], [end_lon, end_lat]],
        "units": "m"
    }
    
    try:
        response = requests.post(url, json=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if "routes" in data and len(data["routes"]) > 0:
                # Extraire la durée en secondes
                duration_seconds = data["routes"][0]["summary"]["duration"]
                # Convertir en minutes
                duration_minutes = duration_seconds / 60
                return duration_minutes
            else:
                return None
        else:
            return None
    except Exception as e:
        return None

# Fonction pour vérifier si un point est dans la zone isochrone
def is_point_in_isochrone(point_lat, point_lon, geojson_data):
    if not geojson_data or "features" not in geojson_data:
        return None
    
    point = Point(point_lon, point_lat)
    
    # Parcourir toutes les features dans le GeoJSON
    for feature in geojson_data["features"]:
        polygon = shape(feature["geometry"])
        if polygon.contains(point):
            return True
    
    return False

# Fonction pour mettre à jour la carte et calculer les isochrones
def calculate_isochrone():
    st.session_state.calculation_done = True
    
    with st.spinner("Calcul des zones accessibles en cours..."):
        url = f"https://api.openrouteservice.org/v2/isochrones/{st.session_state.mode}"
        headers = {
            "Authorization": ORS_API_KEY,
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8"
        }
        params = {
            "locations": [[st.session_state.lon, st.session_state.lat]],
            "range": [st.session_state.minutes * 60],  # Conversion des minutes en secondes
            "units": "m",
            "location_type": "start"
        }
        
        try:
            response = requests.post(url, json=params, headers=headers)
            
            if response.status_code == 200:
                st.session_state.geojson_data = response.json()
                # Si des adresses ont été vérifiées, les vérifier à nouveau après recalcul
                if st.session_state.addresses:
                    check_all_addresses()
                return True
            else:
                st.error(f"Erreur lors de l'appel à l'API OpenRouteService : {response.status_code}")
                st.write(f"Détails de l'erreur : {response.text}")
                return False
        except Exception as e:
            st.error(f"Une erreur s'est produite : {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            return False

# Fonction pour vérifier toutes les adresses en une fois
def check_all_addresses():
    if not st.session_state.addresses or not st.session_state.geojson_data:
        return
        
    with st.spinner(f"Vérification de {len(st.session_state.addresses)} adresses..."):
        for addr in st.session_state.addresses:
            if addr["lat"] is not None and addr["lon"] is not None:
                # Vérifier si l'adresse est dans la zone
                addr["in_zone"] = is_point_in_isochrone(
                    addr["lat"], 
                    addr["lon"], 
                    st.session_state.geojson_data
                )
                
                # Calculer le temps de trajet
                addr["travel_time"] = calculate_travel_time(
                    st.session_state.lat,
                    st.session_state.lon,
                    addr["lat"],
                    addr["lon"],
                    st.session_state.mode
                )

# Fonction pour créer la carte interactive
def create_map():
    # Créer la carte de base
    m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom)
    
    # Ajouter un marqueur pour le point de départ
    folium.Marker(
        [st.session_state.lat, st.session_state.lon],
        popup="Point de départ",
        tooltip="Point de départ",
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)
    
    # Ajouter la zone isochrone si calculée
    if st.session_state.calculation_done and st.session_state.geojson_data:
        # Ajouter les isochrones avant les marqueurs pour une meilleure visibilité
        isochrone_layer = folium.GeoJson(
            data=st.session_state.geojson_data,
            name="Zone accessible",
            style_function=lambda x: {
                'fillColor': '#3388ff',
                'color': '#3388ff',
                'weight': 2,
                'fillOpacity': 0.4
            },
            highlight_function=lambda x: {
                'fillColor': '#3388ff',
                'color': '#0000ff',
                'fillOpacity': 0.6,
                'weight': 3
            }
        )
        isochrone_layer.add_to(m)
    
    # Ajouter des marqueurs pour les adresses vérifiées
    mode_texte = {"foot-walking": "à pied", "cycling-regular": "à vélo", "driving-car": "en voiture"}
    if st.session_state.addresses:
        for i, addr in enumerate(st.session_state.addresses):
            if addr["lat"] is not None and addr["lon"] is not None:
                # Choisir la couleur en fonction du résultat de la vérification
                icon_color = "green" if addr["in_zone"] else "black"
                
                # Préparer le contenu du popup avec les informations détaillées
                travel_time_text = ""
                if addr["travel_time"] is not None:
                    travel_time_text = f"<b>Temps de trajet estimé:</b> {addr['travel_time']:.1f} minutes<br>"
                
                popup_html = f"""
                <div style="width: 300px; max-width: 100%;">
                    <h4>{addr['geocoded_address']}</h4>
                    <p>
                    <b>Adresse d'origine:</b> {addr['original_address']}<br>
                    <b>Coordonnées:</b> {addr['lat']:.6f}, {addr['lon']:.6f}<br>
                    {travel_time_text}
                    <b>Statut:</b> {'Dans la zone accessible' if addr['in_zone'] else 'Hors de la zone accessible'}
                    </p>
                </div>
                """
                
                # Créer un popup iframe pour un meilleur affichage
                popup = folium.Popup(folium.Html(popup_html, script=True), max_width=350)
                
                # Préparer le texte pour le tooltip (infobulle au survol)
                tooltip_text = f"{addr['geocoded_address']}"
                if addr["travel_time"] is not None:
                    tooltip_text = f"{addr['geocoded_address']} - {addr['travel_time']:.1f} min {mode_texte.get(st.session_state.mode, st.session_state.mode)}"
                
                # Ajouter le marqueur avec les informations détaillées
                folium.Marker(
                    [addr["lat"], addr["lon"]],
                    popup=popup,
                    tooltip=tooltip_text,
                    icon=folium.Icon(color=icon_color, icon="home")
                ).add_to(m)
                
                # Si l'adresse est en dehors de la zone, tracer un itinéraire
                if addr["travel_time"] is not None and not addr["in_zone"]:
                    # Ajouter une ligne représentant l'itinéraire
                    folium.PolyLine(
                        locations=[[st.session_state.lat, st.session_state.lon], [addr["lat"], addr["lon"]]],
                        color=icon_color,
                        weight=3,
                        opacity=0.7,
                        dash_array='5, 5',
                        tooltip=f"Trajet: {addr['travel_time']:.1f} min {mode_texte.get(st.session_state.mode, st.session_state.mode)}"
                    ).add_to(m)
    
    return m

# Mise à jour des coordonnées lorsqu'un point est sélectionné sur la carte
def update_coordinates(clicked_data):
    if clicked_data and clicked_data.get("last_clicked"):
        # Sauvegarder le centre et le niveau de zoom actuels
        if clicked_data.get("center"):
            st.session_state.map_center = [clicked_data["center"]["lat"], clicked_data["center"]["lng"]]
        if clicked_data.get("zoom"):
            st.session_state.map_zoom = clicked_data["zoom"]
            
        # Mettre à jour les coordonnées du point seulement si en mode carte et un clic a eu lieu
        if st.session_state.start_point_method == "map":
            new_lat = clicked_data["last_clicked"]["lat"]
            new_lon = clicked_data["last_clicked"]["lng"]
            
            # Seulement mettre à jour si les coordonnées ont changé
            if new_lat != st.session_state.lat or new_lon != st.session_state.lon:
                st.session_state.lat = new_lat
                st.session_state.lon = new_lon
                # Réinitialiser le calcul si un nouveau point est sélectionné
                st.session_state.calculation_done = False
                st.session_state.geojson_data = None
                # Réinitialiser les résultats des adresses précédentes
                if st.session_state.addresses:
                    for addr in st.session_state.addresses:
                        addr["in_zone"] = None
                        addr["travel_time"] = None
                return True
    return False

# Obtenir les dimensions de l'écran pour adapter la carte
def get_screen_width_percentage(percentage=95):
    """Retourne une largeur en pixels basée sur un pourcentage de la largeur de l'écran"""
    return f"{percentage}%"

def get_screen_height_percentage(percentage=70):
    """Retourne une hauteur en pixels basée sur un pourcentage de la hauteur de l'écran"""
    return f"{percentage}vh"  # vh = viewport height, s'adapte à la hauteur de la fenêtre

# Sélection de la méthode pour définir le point de départ
st.sidebar.subheader("Choix du point de départ")
start_point_method = st.sidebar.radio(
    "Comment voulez-vous définir le point de départ ?",
    options=["Sélectionner sur la carte", "Saisir une adresse"],
    index=0 if st.session_state.start_point_method == "map" else 1,
    key="start_method_radio"
)

# Mise à jour de la méthode de sélection dans la session
st.session_state.start_point_method = "map" if start_point_method == "Sélectionner sur la carte" else "address"

# Création de colonnes pour une meilleure organisation
col1, col2 = st.columns([2, 1])

with col1:
    # Instructions pour l'utilisateur
    if st.session_state.start_point_method == "map":
        st.write("Cliquez sur la carte pour choisir un point de départ.")
    else:
        st.write("Point de départ défini par adresse.")
    
    # Créer et afficher la carte unique avec adaptation à l'écran
    map_object = create_map()
    
    # Définir une hauteur fixe en pixels pour garantir la visibilité de la carte
    fixed_height = 600
    
    # Afficher la carte avec une hauteur fixe
    clicked_data = st_folium(
        map_object, 
        width="100%", 
        height=fixed_height,
        key="unified_map",
        returned_objects=["last_clicked", "center", "zoom"]
    )
    
    # Mettre à jour les coordonnées si nécessaire et si en mode carte
    if update_coordinates(clicked_data) and st.session_state.start_point_method == "map":
        st.rerun()  # Actualiser pour refléter les changements

with col2:
    # Affichage des coordonnées sélectionnées
    st.write(f"Coordonnées sélectionnées : Latitude {st.session_state.lat:.6f}, Longitude {st.session_state.lon:.6f}")
    
    # Si la méthode est l'adresse, afficher le champ de saisie d'adresse
    if st.session_state.start_point_method == "address":
        st.subheader("Point de départ par adresse")
        start_address_input = st.text_input(
            "Entrez l'adresse du point de départ",
            key="start_address_input"
        )
        if st.button("Définir comme point de départ", key="set_start_btn"):
            if start_address_input:
                if set_start_point_by_address():
                    st.rerun()  # Actualiser pour refléter les changements
            else:
                st.warning("Veuillez entrer une adresse.")
    
    # Choix de la durée avec mise à jour de la session
    st.subheader("Paramètres")
    minutes = st.slider("Durée (minutes)", 1, 60, st.session_state.minutes, key="minutes_slider")
    st.session_state.minutes = minutes
    
    # Choix du mode de déplacement avec mise à jour de la session
    mode = st.selectbox(
        "Mode de déplacement", 
        ["foot-walking", "cycling-regular", "driving-car"],
        format_func=lambda x: {
            "foot-walking": "À pied", 
            "cycling-regular": "À vélo", 
            "driving-car": "En voiture"
        }.get(x, x),
        index=["foot-walking", "cycling-regular", "driving-car"].index(st.session_state.mode),
        key="mode_selector"
    )
    st.session_state.mode = mode

    # Option pour afficher la réponse brute
    show_raw_response = st.checkbox("Afficher la réponse brute de l'API", value=False, key="show_raw")
    
    # Bouton pour lancer le calcul
    if st.button("Afficher la zone accessible", key="calc_button"):
        calculate_isochrone()
        st.rerun()  # Actualiser pour afficher les résultats

    # Séparateur
    st.markdown("---")
    
    # Section pour vérifier une ou plusieurs adresses
    st.subheader("Vérifier des adresses")
    
    # Onglets pour choisir le mode de saisie des adresses
    address_tabs = st.tabs(["Adresse unique", "Plusieurs adresses", "Importer un fichier"])
    
    with address_tabs[0]:
        # Mode adresse unique
        single_address = st.text_input("Entrez une adresse à vérifier", key="single_address_input")
        
        if st.button("Vérifier cette adresse", key="check_single_btn"):
            if not st.session_state.calculation_done:
                st.warning("Veuillez d'abord calculer une zone accessible.")
            elif not single_address:
                st.warning("Veuillez entrer une adresse.")
            else:
                # Géocoder l'adresse
                address_data = geocode_address(single_address)
                if address_data:
                    # Créer une entrée pour cette adresse unique
                    new_address = {
                        "original_address": single_address,
                        "geocoded_address": address_data["address"],
                        "lat": address_data["lat"],
                        "lon": address_data["lon"],
                        "in_zone": None,
                        "travel_time": None
                    }
                    
                    # Vérifier si l'adresse est dans la zone
                    new_address["in_zone"] = is_point_in_isochrone(
                        new_address["lat"],
                        new_address["lon"],
                        st.session_state.geojson_data
                    )
                    
                    # Calculer le temps de trajet
                    new_address["travel_time"] = calculate_travel_time(
                        st.session_state.lat,
                        st.session_state.lon,
                        new_address["lat"],
                        new_address["lon"],
                        st.session_state.mode
                    )
                    
                    # Ajouter à la liste des adresses
                    st.session_state.addresses = [new_address]
                    st.rerun()  # Actualiser pour afficher les résultats
    
    with address_tabs[1]:
        # Mode plusieurs adresses (saisie manuelle)
        multi_addresses = st.text_area(
            "Entrez plusieurs adresses (une par ligne)",
            height=150,
            key="multi_address_input"
        )
        
        if st.button("Vérifier ces adresses", key="check_multi_btn"):
            if not st.session_state.calculation_done:
                st.warning("Veuillez d'abord calculer une zone accessible.")
            elif not multi_addresses:
                st.warning("Veuillez entrer au moins une adresse.")
            else:
                # Diviser le texte en lignes et nettoyer
                addresses_list = [addr.strip() for addr in multi_addresses.split("\n") if addr.strip()]
                
                if addresses_list:
                    # Géocoder toutes les adresses
                    st.session_state.addresses = geocode_multiple_addresses(addresses_list)
                    
                    # Vérifier toutes les adresses
                    check_all_addresses()
                    st.rerun()  # Actualiser pour afficher les résultats
    
    with address_tabs[2]:
        # Mode import de fichier CSV
        st.write("Importez un fichier CSV ou TXT contenant une liste d'adresses.")
        uploaded_file = st.file_uploader("Choisir un fichier", type=["csv", "txt"], key="file_uploader")
        
        col1, col2 = st.columns(2)
        with col1:
            delimiter = st.selectbox("Délimiteur", [",", ";", "\t", "|"], index=0, key="delimiter")
        with col2:
            has_header = st.checkbox("Le fichier a une en-tête", value=True, key="has_header")
        
        address_column = None
        preview_df = None
        
        if uploaded_file is not None:
            try:
                # Lire les premières lignes pour aperçu
                content = uploaded_file.read().decode()
                uploaded_file.seek(0)  # Revenir au début du fichier pour la lecture suivante
                
                # Convertir le contenu en DataFrame pandas
                if delimiter == "\t":
                    preview_df = pd.read_csv(io.StringIO(content), sep="\t", header=0 if has_header else None, nrows=5)
                else:
                    preview_df = pd.read_csv(io.StringIO(content), sep=delimiter, header=0 if has_header else None, nrows=5)
                
                st.write("Aperçu du fichier:")
                st.dataframe(preview_df.head(5))
                
                # Si le fichier a une en-tête, permettre de sélectionner la colonne des adresses
                if has_header and not preview_df.empty:
                    address_column = st.selectbox(
                        "Sélectionnez la colonne contenant les adresses",
                        options=preview_df.columns.tolist(),
                        key="address_column"
                    )
            except Exception as e:
                st.error(f"Erreur lors de la lecture du fichier: {str(e)}")
        
        if st.button("Vérifier les adresses du fichier", key="check_file_btn"):
            if not st.session_state.calculation_done:
                st.warning("Veuillez d'abord calculer une zone accessible.")
            elif uploaded_file is None:
                st.warning("Veuillez d'abord importer un fichier.")
            else:
                try:
                    addresses_list = []
                    
                    # Réinitialiser le curseur du fichier
                    uploaded_file.seek(0)
                    
                    # Lire le fichier
                    if delimiter == "\t":
                        df = pd.read_csv(uploaded_file, sep="\t", header=0 if has_header else None)
                    else:
                        df = pd.read_csv(uploaded_file, sep=delimiter, header=0 if has_header else None)
                    
                    # Extraire les adresses
                    if has_header and address_column:
                        addresses_list = df[address_column].dropna().tolist()
                    else:
                        # Si pas d'en-tête ou pas de colonne sélectionnée, prendre la première colonne
                        addresses_list = df.iloc[:, 0].dropna().tolist()
                    
                    if addresses_list:
                        # Géocoder toutes les adresses
                        st.session_state.addresses = geocode_multiple_addresses(addresses_list)
                        
                        # Vérifier toutes les adresses
                        check_all_addresses()
                        st.rerun()  # Actualiser pour afficher les résultats
                    else:
                        st.warning("Aucune adresse trouvée dans le fichier.")
                        
                except Exception as e:
                    st.error(f"Erreur lors du traitement du fichier: {str(e)}")

# Afficher la réponse brute si demandé et disponible
if show_raw_response and st.session_state.geojson_data:
    st.subheader("Réponse brute de l'API")
    st.json(st.session_state.geojson_data)

# Afficher un tableau avec les résultats des adresses vérifiées si des calculs ont été effectués
if st.session_state.calculation_done and st.session_state.addresses:
    st.subheader(f"Résultats pour {len(st.session_state.addresses)} adresses")
    
    # Créer un DataFrame à partir des adresses
    df = pd.DataFrame(st.session_state.addresses)
    
    # Formater le DataFrame pour l'affichage
    df_display = df.copy()
    if "travel_time" in df_display.columns:
        df_display["travel_time"] = df_display["travel_time"].apply(
            lambda x: f"{x:.1f} min" if pd.notnull(x) else "N/A"
        )
    if "in_zone" in df_display.columns:
        df_display["in_zone"] = df_display["in_zone"].apply(
            lambda x: "✅ Oui" if x else "❌ Non" if x is not None else "N/A"
        )
    
    # Renommer les colonnes pour l'affichage
    df_display = df_display.rename(columns={
        "original_address": "Adresse d'origine",
        "geocoded_address": "Adresse géocodée",
        "lat": "Latitude",
        "lon": "Longitude",
        "in_zone": "Dans la zone",
        "travel_time": "Temps de trajet"
    })
    
    # Afficher le tableau
    st.dataframe(df_display, use_container_width=True)
    
    # Option pour télécharger les résultats
    csv = df.to_csv(index=False)
    st.download_button(
        label="Télécharger les résultats (CSV)",
        data=csv,
        file_name="resultats_adresses.csv",
        mime="text/csv"
    )
    
    # Afficher un résumé
    in_zone_count = sum(1 for addr in st.session_state.addresses if addr["in_zone"] is True)
    out_zone_count = sum(1 for addr in st.session_state.addresses if addr["in_zone"] is False)
    error_count = sum(1 for addr in st.session_state.addresses if addr["in_zone"] is None)
    
    st.write(f"**Résumé:** {in_zone_count} adresses dans la zone, {out_zone_count} adresses hors zone, {error_count} erreurs de géocodage.")

# Ajouter des informations dans la barre latérale
st.sidebar.title("À propos")
st.sidebar.info(
    """
    Cette application vous permet de visualiser les zones accessibles en un certain temps depuis un point donné.
    
    Elle utilise l'API OpenRouteService pour calculer les isochrones.
    
    **Comment utiliser cette application:**
    1. Choisissez comment définir votre point de départ (carte ou adresse)
    2. Sélectionnez le point de départ sur la carte ou saisissez une adresse
    3. Choisissez la durée en minutes
    4. Sélectionnez votre mode de déplacement
    5. Cliquez sur "Afficher la zone accessible"
    6. Vérifiez une ou plusieurs adresses à la fois
    """
)
