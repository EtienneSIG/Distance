# Application Zones Accessibles sur Carte

## Description

Cette application web, développée avec Streamlit et Folium, permet de visualiser les zones géographiques accessibles en un temps donné depuis un point de départ. Elle utilise l'API OpenRouteService pour calculer les isochrones (zones atteignables en un temps défini) et offre plusieurs fonctionnalités pour analyser l'accessibilité de différentes adresses.

## Fonctionnalités principales

### 1. Définition du point de départ
- **Sélection sur la carte** : Cliquez directement sur la carte interactive pour définir le point de départ
- **Saisie d'adresse** : Entrez une adresse textuelle qui sera géocodée automatiquement

### 2. Paramètres de calcul des zones accessibles
- **Durée** : Définissez le temps maximum de déplacement (1 à 60 minutes)
- **Mode de déplacement** : Choisissez entre trois options :
  - À pied
  - À vélo
  - En voiture

### 3. Affichage cartographique
- Carte interactive basée sur Folium
- Visualisation du point de départ (marqueur rouge)
- Visualisation de la zone accessible (zone bleue)
- Hauteur de carte fixe pour une meilleure expérience utilisateur

### 4. Vérification d'adresses
L'application permet de vérifier si des adresses sont situées dans la zone accessible :

- **Adresse unique** : Vérifiez une seule adresse
- **Plusieurs adresses** : Entrez une liste d'adresses (une par ligne)
- **Import de fichier** : Chargez un fichier CSV ou TXT contenant des adresses

Pour chaque adresse vérifiée, l'application :
- Détermine si elle est dans la zone accessible (✅ Oui / ❌ Non)
- Calcule le temps de trajet estimé depuis le point de départ
- Affiche un marqueur sur la carte (vert si dans la zone, noir si hors zone)
- Pour les adresses hors zone, trace une ligne en pointillés vers le point de départ

### 5. Analyse des résultats
- Tableau récapitulatif de toutes les adresses vérifiées
- Statistiques sur le nombre d'adresses dans/hors de la zone
- Possibilité de télécharger les résultats au format CSV

## Prérequis techniques

- Une clé API OpenRouteService (gratuite, obtenue sur https://openrouteservice.org/dev/#/signup)
- Python avec les bibliothèques suivantes :
  - streamlit
  - streamlit_folium
  - folium
  - requests
  - pandas
  - shapely

## Comment utiliser l'application

1. **Configurez votre clé API** dans la barre latérale (une clé par défaut est fournie mais avec des limites)
2. **Choisissez la méthode** pour définir votre point de départ (carte ou adresse)
3. **Définissez le point de départ** en cliquant sur la carte ou en saisissant une adresse
4. **Ajustez les paramètres** (durée et mode de déplacement)
5. **Cliquez sur "Afficher la zone accessible"** pour calculer et visualiser l'isochrone
6. **Vérifiez des adresses** pour savoir si elles sont accessibles dans le temps défini
7. **Analysez les résultats** dans le tableau et sur la carte

## Cas d'utilisation

Cette application est utile pour :
- Rechercher un logement en fonction du temps de trajet vers votre lieu de travail
- Planifier l'emplacement d'un commerce en fonction de sa zone de chalandise
- Optimiser la distribution de services en fonction de l'accessibilité
- Analyser l'équité d'accès à des services publics (écoles, hôpitaux, etc.)
- Planifier des visites en fonction du temps de déplacement

## Limitations

- Les calculs d'isochrones et le géocodage sont limités par les quotas de l'API OpenRouteService
- Les temps de trajet sont des estimations qui ne prennent pas en compte les conditions de circulation en temps réel
- L'application est optimisée pour des recherches en France (paramètre par défaut pour le géocodage)
