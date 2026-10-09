import sys
sys.path.insert(0, '.')
from app.services.district_centroids import CENTROIDS, centroid_for
print(f"Total centroids: {len(CENTROIDS)}")
print(f"Feni: {centroid_for('Feni')}")
print(f"Dhaka: {centroid_for('Dhaka')}")
print(f"Chattogram: {centroid_for('Chattogram')}")
print(f"feni (lowercase): {centroid_for('feni')}")
print(f"Unknown: {centroid_for('Atlantis')}")
