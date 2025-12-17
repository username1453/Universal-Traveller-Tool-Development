// 🌓 INVERT BUTTON FUNCTIONALITY
const invertButton = document.getElementById('invert-btn');
let isInverted = true;

invertButton.addEventListener('click', () => {
    const tiles = document.querySelectorAll('.leaflet-tile');
    isInverted = !isInverted;

    tiles.forEach(tile => {
        tile.style.filter = isInverted ? 'invert(100%)' : 'none';
    });
});


// 🗺️ MAP INITIALIZATION
var map = L.map('map', {
    center: [-55.505, 3.09],
    zoom: 4,
    minZoom: 2,
    maxZoom: 6,
    maxBounds: [[72.55, -97.48], [-81.72, 107.5]],  // Map boundaries
    maxBoundsViscosity: 1.0  // Restrict panning
});

var backgroundtilelayer = L.tileLayer('tiles/main-map/{z}/{x}/{y}.jpg', {
    maxZoom: 6,
    tileSize: 256,
    attribution: 'Map data &copy; Your Attribution'
}).addTo(map);

// 📊 MARKER AND CIRCLE SCALING

// Base sizes for icons and circle markers at the initial zoom level
const baseIconSize = 32;       // Default size for map icons (e.g., planet markers)
const baseCircleRadius = 33;   // Default radius for circle markers (e.g., zone indicators)
const scaleFactor = 0.33;      // Scaling factor determining how much size changes per zoom level
const initialZoom = map.getZoom(); // Capture the map's initial zoom level for reference

/**
 * Calculate scaled icon size based on the current zoom level.
 * @param {number} zoom - Current zoom level of the map.
 * @returns {number} - The calculated icon size adjusted for zoom.
 */
function getScaledIconSize(zoom) {
    return baseIconSize * (1 + (zoom - initialZoom) * scaleFactor);
}

function getScaledCircleRadius(zoom) {
    return baseCircleRadius * (1 + (zoom - initialZoom) * scaleFactor);
}


// 🪐 CUSTOM ICON DEFINITIONS
var wetIcon = new L.Icon({
    iconUrl: 'images/wet-planet.png',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -32]
});

var dryIcon = new L.Icon({
    iconUrl: 'images/dry-planet.png',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -32]
});

var asteroidIcon = new L.Icon({
    iconUrl: 'images/asteroids.png',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -32]
});

var basicicon = new L.Icon({
    iconUrl: 'images/marker-icon.png'
});

// Setting Icon

var divicon = L.divIcon({className: 'iconsdiv', iconSize: null }); // Explicitly set to null or you will default to 12x12

var gasGiantIcon = L.divIcon({
    className: 'icon-gasgiant iconsdiv',
    iconSize: [12, 12],
    iconAnchor: [-24, 6],
    popupAnchor: [0, -24]
});

var imperialNavalIcon = L.divIcon({
    className: 'icon-naval iconsdiv',
    iconSize: [12, 12],
    iconAnchor: [6, -36],
    popupAnchor: [0, -24]
});

var scoutIcon = L.divIcon({
    className: 'icon-scout iconsdiv',
    iconSize: [12, 12],
    iconAnchor: [6, 36],
    popupAnchor: [0, -24]
});

var researchIcon = L.divIcon({
    className: 'icon-research iconsdiv',
    iconSize: [12, 12],
    iconAnchor: [36, 6],
    popupAnchor: [0, -24]
});

// 📍 PLANETARY FEATURES AND GEOJSON HANDLING
// 🗂️ Array to Store Tooltip References
const tooltips = []; // ✅ Global declaration

const subsectorNames = {
    "A": "Ultima", "B": "Suleiman", "C": "Concord", "D": "Harlequin",
    "E": "Alderamin", "F": "Esperance", "G": "Vega", "H": "Banasdan",
    "I": "Albadawi", "J": "Dingir", "K": "Sol", "L": "Arcturus",
    "M": "Jardin", "N": "Capella", "O": "Gemini", "P": "Kukulkan"
};

function planetaryfeatures(feature, layer) {
    // Call planetaryzones to add zone circles for each feature
    planetaryzones(feature, layer);
    var link = feature.properties.Link;
    var imageUrl = 'https://username1453.github.io/Universal-Traveller-Tool/' + encodeURIComponent(link);
    
    // Replace only problematic filename characters (leave spaces intact)
    var sanitizedName = feature.properties.Name.replace(/[<>:"\/\\|?*\']+/g, '_').trim();
    
    // Replace spaces with %20 for proper URL encoding
    var planetfilePath = encodeURIComponent(sanitizedName).replace(/%20/g, ' ');

    var popupContent = 
    "<h1>Planetary Data Access</h1>" +  // Popup header
    "<p>Core Planet Name: <a href='https://wiki.travellerrpg.com/" + feature.properties.Name + '_(world)' + "' target='_blank' style='color:inherit; text-decoration:none;'>" + feature.properties.Name + "</a></p>" +// Name of planet and link to Traveller wiki
    "<p>Universal World Profile: <a href='https://wiki.travellerrpg.com/Universal_World_Profile' target='_blank' style='color:inherit; text-decoration:none;'>" + feature.properties.UWP + "</a></p>" +// UWP of planet and link to UWP meaning
    "<p>" + "Subsector: " + (subsectorNames[feature.properties.SS] || 'Unknown') + "</p>" +   // Subsector located within
    "<p>";

    // Dynamically add icons if properties are 'Yes'
    let iconLine = [];

    if (feature.properties.gasgiant === 'Yes') {
        iconLine.push('<img src="images/gas_giant.png" alt="Gas Giant" title="Gas Giant" style="width: 24px; height: 24px; margin-right: 5px;" />');
    }
    if (feature.properties.imperial_naval === 'Yes') {
        iconLine.push('<img src="images/naval_base.png" alt="Naval Base" title="Naval Base" style="width: 24px; height: 24px; margin-right: 5px;" />');
    }
    if (feature.properties.other_naval === 'Yes') {
        iconLine.push('<img src="images/other_naval_base.png" alt="Naval Base" title="Naval Base" style="width: 24px; height: 24px; margin-right: 5px;" />');
    }
    if (feature.properties.scout === 'Yes') {
        iconLine.push('<img src="images/Scout_base.png" alt="Scout Base" title="Scout Base" style="width: 24px; height: 24px; margin-right: 5px;" />');
    }
    if (feature.properties.scout_waystation === 'Yes') {
        iconLine.push('<img src="images/Scout_waystation.png" alt="Scout Waystation" title="Scout Waystation" style="width: 24px; height: 24px; margin-right: 5px;" />');
    }
    if (feature.properties.military === 'Yes') {
        iconLine.push('<img src="images/military_base.png" alt="Military Base" title="Military Base" style="width: 24px; height: 24px; margin-right: 5px;" />');
    }
    if (feature.properties.research === 'Yes') {
        iconLine.push('<img src="images/research_station.png" alt="Research Facility" title="Research Facility" style="width: 24px; height: 24px; margin-right: 5px;" />');
    }
    if (feature.properties.prison === 'Yes') {
        iconLine.push('<img src="images/prison.png" alt="Prison" title="Prison" style="width: 24px; height: 24px; margin-right: 5px;" />');
    }

    // If there are icons to show, add them to the popup
    if (iconLine.length > 0) {
        popupContent += "<p>" + iconLine.join('') + "</p>";
    }

    popupContent += "<p>" + "<a href='sector_data/" + planetfilePath + ".pdf' target='_blank' style='color: #32CD32; text-decoration: underline;'>" + 
    "Planetary Profile" +  "</a></p>"  + 
    "<a href='" + imageUrl + "' target='_blank'>" +     // Link
    "<img src='" + imageUrl + "' alt='" + feature.properties.Name + "' style='width:100%; max-width: 300px;'/>" +   // Preview
    "</a>";

    layer.bindPopup(popupContent, { autoPan: true });

    switch (feature.properties.type) {
        case 'Water': layer.setIcon(wetIcon); break;
        case 'Dry': layer.setIcon(dryIcon); break;
        case 'Asteroid': layer.setIcon(asteroidIcon); break;
        default: layer.setIcon(basicicon); break;
    }

/*     let zoneCircle;
    switch (feature.properties.Zone) {
        case 'A':
            zoneCircle = L.circleMarker(layer.getLatLng(), {
                color: 'yellow', fillColor: 'transparent', opacity: 0.75, radius: baseCircleRadius
            }).addTo(map);
            break;
        case 'R':
            zoneCircle = L.circleMarker(layer.getLatLng(), {
                color: 'red', fillColor: 'transparent', opacity: 0.75, radius: baseCircleRadius
            }).addTo(map);
            break;
    } */

    // Show planet name
    if (feature.properties.Name) {
        const nameTooltip = L.tooltip({ permanent: true, direction: 'top', className: 'custom-tooltip' })
            .setContent(feature.properties.Name)
            .setLatLng(layer.getLatLng()).addTo(map);
        tooltips.push(nameTooltip); // ✅ Store tooltip reference
    }

    // Show planet UWP
    if (feature.properties.UWP) {
        const uwpTooltip = L.tooltip({ permanent: true, direction: 'bottom', className: 'custom-uwp-tooltip' })
            .setContent(feature.properties.UWP)
            .setLatLng(layer.getLatLng()).addTo(map);
        tooltips.push(uwpTooltip); // ✅ Store tooltip reference
    }

}

// Initialize the zoneCirclesLayer as a LayerGroup
let zoneCirclesLayer = L.layerGroup();

// Example function to add circle to the layer group based on feature data
function addZoneCircle(feature, layer) {
    let zoneCircle;

    // Make sure the 'feature' object has the necessary properties (Zone and LatLng)
    switch (feature.properties.Zone) {
        case 'A':
            zoneCircle = L.circleMarker(layer.getLatLng(), {
                color: 'yellow',
                fillColor: 'transparent',
                opacity: 0.75,
                radius: baseCircleRadius
            });
            break;
        case 'R':
            zoneCircle = L.circleMarker(layer.getLatLng(), {
                color: 'red',
                fillColor: 'transparent',
                opacity: 0.75,
                radius: baseCircleRadius
            });
            break;
    }

    // If zoneCircle was created, add it to the zoneCirclesLayer
    if (zoneCircle) {
        zoneCirclesLayer.addLayer(zoneCircle);
    }
}

// Define the onEachFeature function that is used for each feature in the geoJSON data
function planetaryzones(feature, layer) {
    // Add a zone circle to each feature
    addZoneCircle(feature, layer);
}

var planetarydatavar = L.geoJson(planetarydata, { onEachFeature: planetaryfeatures }).addTo(map);

// Add the zoneCirclesLayer to the map after it has been populated
zoneCirclesLayer.addTo(map);


// 🔍 Define the zoom threshold for tooltip visibility
const tooltipThreshold = 3; // Tooltips become permanent at zoom >= 3
let lastZoom = map.getZoom(); // Store the initial zoom level

map.on('zoomend', () => {
    const zoom = map.getZoom();
    const iconSize = getScaledIconSize(zoom);
    const circleRadius = getScaledCircleRadius(zoom);

    map.eachLayer(layer => {
        // Scale regular icon markers (planets, spaceship)
        if (layer instanceof L.Marker && 
            layer.options.icon && 
            layer.options.icon.options.iconUrl) {
            layer.setIcon(L.icon({
                iconUrl: layer.options.icon.options.iconUrl,
                iconSize: [iconSize, iconSize],
                iconAnchor: [iconSize / 2, iconSize / 2],
                popupAnchor: [0, -iconSize / 2]
            }));
        }
        
        // Scale DivIcon markers (tactical units) - update their container size
        else if (layer instanceof L.Marker && 
                 layer.options.icon && 
                 layer.options.icon.options.className === 'military-unit-icon') {
            // Tactical units use DivIcons - scale the container
            const currentIcon = layer.options.icon;
            layer.setIcon(L.divIcon({
                className: currentIcon.options.className,
                html: currentIcon.options.html,
                iconSize: [iconSize, iconSize],
                iconAnchor: [iconSize / 2, iconSize / 2],
                popupAnchor: [0, -iconSize / 2]
            }));
        }
        
        // Scale circle markers (zones)
        else if (layer instanceof L.CircleMarker) {
            layer.setRadius(circleRadius);
        }
        
        // Skip GeoJSON polygon layers - they scale automatically
        // (political boundaries, fog of war don't need manual scaling)
    });
    
    // Tooltip visibility
    if (zoom < tooltipThreshold && lastZoom >= tooltipThreshold) {
        tooltips.forEach(tooltip => map.removeLayer(tooltip));
    } else if (zoom >= tooltipThreshold && lastZoom < tooltipThreshold) {
        tooltips.forEach(tooltip => map.addLayer(tooltip));
    }
    lastZoom = zoom;
});

// 🏴 POLITICAL BOUNDARIES
function boundariespolygon(feature) {
    const styles = {
        'Terran Federation': '#1f77b4', 'Vegan Polity': '#ff7f0e',
        'Bootean Federation': '#2ca02c', 'Chinon Hives': '#5927d6',
        'Kryptonian States': '#9467bd', 'Xantippe States': '#8c564b',
        'Kukulcan Republic': '#e377c2', 'The Imperium': '#cc1d45',
        'default': '#cccccc'
    };

    return {
        fillColor: styles[feature.properties.Nation] || styles['default'],
        color: styles[feature.properties.Nation] || styles['default'],
        weight: 3,
        fillOpacity: 0.2
    };
}

var politicalboundariesvar = L.geoJSON(politicalboundaries, {
    style: boundariespolygon,
    onEachFeature: (feature, layer) => {
        const nation = feature.properties.Nation || 'Unknown';
        const link = 'https://username1453.github.io/Universal-Traveller-Tool/sector_data/' + encodeURIComponent(nation) + '.pdf';
        
        const popupHtml = `Nation: <a href="${link}" target="_blank" style="color:inherit; text-decoration:none;">${nation}</a>`;
        layer.bindPopup(popupHtml);
    }
}).addTo(map);


// Fog of War layer
map.createPane('fogPane');
map.getPane('fogPane').style.zIndex = 650; // Higher than overlayPane (default is 400)


const fogOfWarLayer = L.geoJSON(fog_of_war, {
    pane: 'fogPane',
    style: {
      color: "#000",
      fillColor: "#595959",
      fillOpacity: 0.95,
      weight: 0
    },
    className: 'fog-layer'
  });

// Add fog layer to map by default
fogOfWarLayer.addTo(map);

// 🌟 TRANSPARENT BACKGROUND
map.getContainer().style.backgroundColor = 'transparent';

//  DRAGGABLE MARKER

// Define a custom icon for the draggable marker
const yourSpaceship = L.icon({
    iconUrl: 'images/battleship.png', // Path to your icon
    iconSize: [50, 50], // Size of the icon
    iconAnchor: [16, 32], // Anchor point (bottom center)
    popupAnchor: [0, -32] // Popup anchor point
});

// Initialize the marker variable (empty for now)
let draggableMarker = null;

// Button toggle logic
const toggleMarkerBtn = document.getElementById('toggle-marker-btn');
let markerExists = false;

toggleMarkerBtn.addEventListener('click', function () {
    if (markerExists) {
        // Remove the marker from the map
        map.removeLayer(draggableMarker);
        draggableMarker = null; // Clear the marker reference
        toggleMarkerBtn.textContent = 'Add Spaceship';
    } else {
        // Add the marker to the map at a default location
        draggableMarker = L.marker([-55.505, 3.09], {
            icon: yourSpaceship,
            draggable: true,
            title: "Drag me!"
        }).addTo(map);

        // Log the marker's position on drag
        draggableMarker.on('dragend', function (e) {
            const position = draggableMarker.getLatLng();
            console.log(`Marker moved to: ${position.lat}, ${position.lng}`);
        });

        toggleMarkerBtn.textContent = 'Remove Spaceship';
    }

    // Toggle state
    markerExists = !markerExists;
});

// Create the custom legend control
var layerLegend = L.control({ position: 'bottomleft' });

layerLegend.onAdd = function(map) {
    var div = L.DomUtil.create('div', 'legend-control legend-hidden');
    div.innerHTML += '<strong>Map Layers</strong><br>';
    
    // Add checkboxes for each layer
    div.innerHTML += `<label><input type="checkbox" id="toggle-political" checked> Political Boundaries</label><br>`;
    div.innerHTML += `<label><input type="checkbox" id="toggle-zones" checked> Zones</label><br>`;
    div.innerHTML += `<label><input type="checkbox" id="toggle-planetary" checked> Planetary Data</label><br>`;
    div.innerHTML += `<label><input type="checkbox" id="toggle-fog" checked> Fog of War</label><br>`;
    
    return div;
};

layerLegend.addTo(map);

// Hook checkboxes to toggle layers
document.addEventListener('change', function(e) {
    if (e.target.id === 'toggle-political') {
        if (e.target.checked) map.addLayer(politicalboundariesvar);
        else map.removeLayer(politicalboundariesvar);
    } else if (e.target.id === 'toggle-zones') {
        if (e.target.checked) map.addLayer(zoneCirclesLayer);
        else map.removeLayer(zoneCirclesLayer);
    } else if (e.target.id === 'toggle-fog') {
        if (e.target.checked) map.addLayer(fogOfWarLayer);
        else map.removeLayer(fogOfWarLayer);
    } else if (e.target.id === 'toggle-planetary') {
        if (e.target.checked) map.addLayer(planetarydatavar);
        else map.removeLayer(planetarydatavar);
    }
});

// Toggle visibility of the legend via button
document.getElementById('toggleLegend').addEventListener('click', function() {
    const control = document.querySelector('.legend-control');
    control.classList.toggle('legend-hidden');
});


