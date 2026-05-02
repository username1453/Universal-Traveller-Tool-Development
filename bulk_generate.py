import json
import os
import re
from starport_generator import generate # verbatim import
import pyjson5  # pip install pyjson5

# 1. Load and clean the JavaScript file
with open('js/PlanetaryData.js', 'r') as f:
    raw_content = f.read()
    # Strip the JS variable assignment
    import re
    js_obj = re.sub(r'var\s+\w+\s*=\s*', '', raw_content).strip().rstrip(';')
    data = pyjson5.loads(js_obj)

# 2. Create the specific directory you requested
output_dir = "starportmaps"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# 3. Iterate through the features and generate maps
for feature in data['features']:
    props = feature['properties']
    name = props['Name']
    uwp = props['UWP']
    
    # Clean the name for filesystem safety (replaces spaces with underscores)
    safe_name = name.replace(" ", "_")
    filename = f"{output_dir}/{safe_name}.png"
    
    print(f"Generating: {name} (UWP: {uwp}) -> {filename}")
    
    try:
        # Call the existing generation function from starport_generator.py
        generate(uwp, output_path=filename)
    except Exception as e:
        print(f"Error generating {name}: {e}")

print(f"\nBatch complete. Maps saved in /{output_dir}/")
