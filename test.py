from pyrosm import OSM
import matplotlib.pyplot as plt

PBF_FILE = "utils/data/philippines-latest.osm.pbf"

# Define bounding box:
# (west, south, east, north)
bbox = [125.45, 7.00, 125.65, 7.15]

# Pass bbox INTO OSM()
osm = OSM(PBF_FILE, bounding_box=bbox)

roads = osm.get_network(network_type="driving")

print(roads.head())
print(f"Road segments: {len(roads)}")

roads.plot(figsize=(8, 8), linewidth=0.3)

plt.show()