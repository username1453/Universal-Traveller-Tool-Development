// This script runs AFTER the global 'map' variable has been initialized in index.js.

// --- STATE MANAGEMENT ---
// This array holds your unit data in memory (Conceptually separate from the map)
let tacticalUnits = [];

// Create a separate layer group just for units so they sit on top of all other layers
const unitLayerGroup = L.layerGroup().addTo(map);

// --- UTILITIES & RENDERING ---

/**
 * Creates a custom DivIcon using SVG for the unit markers.
 * @param {string} type - 'spaceship' or 'soldier'
 * @param {string} color - 'red' or 'blue'
 * @returns {L.DivIcon} Leaflet DivIcon instance
 */
function getUnitIcon(type, color) {
    const c = color === 'red' ? '#ef4444' : '#3b82f6'; // Icon fill color
    const s = color === 'red' ? '#991b1b' : '#1e40af'; // Icon stroke color
    
    let svgHtml = '';
    if (type === 'spaceship') {
        // Rocket/Spaceship SVG
        svgHtml = `<svg viewBox="0 0 24 24" fill="${c}" stroke="${s}" stroke-width="2" stroke-linejoin="round"><path d="M12 2l7 19-7-4-7 4 7-19z" /></svg>`;
    } else {
        // Soldier/User SVG
        svgHtml = `<svg viewBox="0 0 24 24" fill="${c}" stroke="${s}" stroke-width="2"><circle cx="12" cy="8" r="5" /><path d="M3 21v-2a7 7 0 0 1 7-7h4a7 7 0 0 1 7 7v2" /></svg>`;
    }

    return L.divIcon({
        className: 'leaflet-div-icon',
        html: `<div class="unit-icon" style="width: 32px; height: 32px;">${svgHtml}</div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 16], 
        popupAnchor: [0, -20]
    });
}

/**
 * Creates a Leaflet marker for a single unit and adds it to the layer group.
 * @param {object} unitData - The unit object from the tacticalUnits array.
 */
function renderUnit(unitData) {
    const icon = getUnitIcon(unitData.type, unitData.color);
    
    // Create Marker
    const marker = L.marker([unitData.lat, unitData.lng], {
        icon: icon,
        draggable: true 
    });

    // Bind Popup (The "Edit" interface)
    // We use helper functions (updateUnitProp, removeUnit) defined on the window object 
    // to interact with the unit data from inside the popup HTML.
    const popupContent = `
        <div class="p-3 font-sans" style="min-width: 200px;">
            <h3 class="font-bold text-lg mb-1" style="color:${unitData.color === 'red' ? '#dc2626' : '#2563eb'}">
                ${unitData.properties.name}
            </h3>
            <div class="text-sm text-gray-600 mb-2">
                <strong>HP:</strong> <input type="number" value="${unitData.properties.hp}" 
                    onchange="window.updateUnitProp('${unitData.id}', 'name', this.value)"
                    class="border rounded px-1 w-24 text-sm">
            </div>
            <div class="text-sm text-gray-600 mb-2">
                <strong>HP:</strong> <input type="number" value="${unitData.properties.hp}" 
                    onchange="window.updateUnitProp('${unitData.id}', 'hp', this.value)" 
                    class="border rounded px-1 w-16 text-sm">
            </div>
            <div class="text-sm text-gray-600 mb-2">
                <strong>Status:</strong> 
                <select onchange="window.updateUnitProp('${unitData.id}', 'status', this.value)" class="border rounded text-sm">
                    <option value="Active" ${unitData.properties.status === 'Active' ? 'selected' : ''}>Active</option>
                    <option value="Engaged" ${unitData.properties.status === 'Engaged' ? 'selected' : ''}>Engaged</option>
                    <option value="Destroyed" ${unitData.properties.status === 'Destroyed' ? 'selected' : ''}>Destroyed</option>
                </select>
            </div>
            <button onclick="window.removeUnit('${unitData.id}')" class="text-xs text-red-500 hover:underline mt-2">Delete Unit</button>
        </div>
    `;
    
    marker.bindPopup(popupContent, { className: 'tactical-popup' });

    // Event Listener: Update unit data when marker is dragged
    marker.on('dragend', function(e) {
        const newPos = e.target.getLatLng();
        unitData.lat = newPos.lat;
        unitData.lng = newPos.lng;
        // Optionally update popup content if it shows coordinates
        e.target.getPopup().setContent(popupContent);
        console.log(`Unit ${unitData.id} moved to Lat: ${newPos.lat.toFixed(4)}, Lng: ${newPos.lng.toFixed(4)}`);
    });

    // Store marker reference and add to map
    unitData._marker = marker;
    unitLayerGroup.addLayer(marker);
}

// --- GLOBAL HELPER FUNCTIONS (Used by inline popup HTML) ---

window.updateUnitProp = function(id, key, value) {
    const unit = tacticalUnits.find(u => u.id === id);
    if (unit) {
        unit.properties[key] = value;
        // Rebind popup to refresh content (important for name/HP changes)
        if (unit._marker) {
             renderUnit(unit);
             unit._marker.openPopup();
        }
    }
};

window.removeUnit = function(id) {
    const index = tacticalUnits.findIndex(u => u.id === id);
    if (index > -1) {
        const unit = tacticalUnits[index];
        if (unit._marker) unitLayerGroup.removeLayer(unit._marker);
        tacticalUnits.splice(index, 1);
    }
    // Instead of alert(), use console.log or a custom UI message
    console.log(`Unit ${id} removed.`);
};


// --- EVENT LISTENERS (MAIN LOGIC) ---

document.addEventListener('DOMContentLoaded', () => {

    // 1. ADD UNIT LOGIC
    document.getElementById('add-unit-btn').addEventListener('click', () => {
        const selection = document.getElementById('unit-type-select').value;
        const [type, color] = selection.split('-');
        
        // Default location: Center of current map view
        const center = map.getCenter();
        
        const newUnit = {
            id: 'u_' + Date.now(),
            type: type,
            color: color,
            lat: center.lat,
            lng: center.lng,
            properties: {
                name: `${color.toUpperCase()} ${type === 'spaceship' ? 'Ship' : 'Soldier'}`,
                hp: 100,
                status: 'Active',
                notes: ''
            }
        };
        
        tacticalUnits.push(newUnit);
        renderUnit(newUnit);
        if (newUnit._marker) {
            newUnit._marker.openPopup(); // Open popup immediately for editing
        }
        console.log("New unit added.");
    });

    // 2. SAVE ARMY LOGIC (Downloads JSON file)
    document.getElementById('save-units-btn').addEventListener('click', () => {
        // Prepare data for saving: Strip out the internal Leaflet marker reference
        const dataToSave = tacticalUnits.map(u => {
            const { _marker, ...cleanUnit } = u; 
            return cleanUnit;
        });
        
        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(dataToSave, null, 2));
        const dlAnchorElem = document.createElement('a');
        dlAnchorElem.setAttribute("href", dataStr);
        dlAnchorElem.setAttribute("download", "my_army_data.json");
        document.body.appendChild(dlAnchorElem);
        dlAnchorElem.click();
        document.body.removeChild(dlAnchorElem);
        console.log(`Saved ${dataToSave.length} units to my_army_data.json`);
    });

    // 3. LOAD ARMY LOGIC (Uploads JSON file)
    document.getElementById('unit-upload').addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = function(evt) {
            try {
                const loadedUnits = JSON.parse(evt.target.result);
                
                // Clear existing units from map and memory
                unitLayerGroup.clearLayers();
                tacticalUnits = [];
                
                // Render and store new units
                loadedUnits.forEach(u => {
                    tacticalUnits.push(u);
                    renderUnit(u);
                });
                console.log(`Successfully loaded ${tacticalUnits.length} units.`);

            } catch (err) {
                console.error("Error parsing Unit JSON:", err);
                // In a real app, display an error message in a modal or status bar
            }
        };
        reader.readAsText(file);
        this.value = ''; // Reset input
    });
});
