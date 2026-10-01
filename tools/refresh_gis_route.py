"""Optional: refresh one camera leg with OSRM, retaining the offline fallback."""
import argparse
from anpr.gis import GISStore

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('from_id');parser.add_argument('to_id')
    args=parser.parse_args()
    route=GISStore().route(args.from_id,args.to_id,refresh=True)
    print('Cached road fallback' if route['cached'] else 'OSRM route cached locally')
    print(f"{route['road_distance_km']:.2f} km · {len(route['coordinates'])} road vertices")
