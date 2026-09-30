"""Validated deployment settings and a small illustrative Delhi camera network."""
from dataclasses import dataclass
from datetime import timezone, timedelta
import os

IST = timezone(timedelta(hours=5, minutes=30))
MAX_SPEED_KMH = 110.0
RECENT_SECONDS = 1800
STATES = frozenset('AN AP AR AS BR CG CH DD DL DN GA GJ HP HR JH JK KA KL LA LD MH ML MN MP MZ NL OD OR PB PY RJ SK TN TR TS TG UK UP UT WB'.split())


@dataclass(frozen=True)
class Camera:
    id: str
    name: str
    lat: float
    lon: float
    restricted: bool = False
    restricted_start: int = 22
    restricted_end: int = 6


CAMERAS = [
    Camera('C01', 'Kashmere Gate', 28.667, 77.228),
    Camera('C02', 'Civil Lines', 28.681, 77.220),
    Camera('C03', 'Karol Bagh', 28.651, 77.190),
    Camera('C04', 'Connaught Place', 28.632, 77.219),
    Camera('C05', 'ITO Junction', 28.628, 77.242),
    Camera('C06', 'India Gate', 28.613, 77.229),
    Camera('C07', 'Dhaula Kuan', 28.592, 77.163),
    Camera('C08', 'Defence Enclave', 28.574, 77.227, True),
]
# Undirected illustrative road lengths; C01 -> C08 is exactly 13 km.
ROADS = [
    ('C01', 'C02', 2.4, 45), ('C01', 'C03', 5.0, 50),
    ('C01', 'C04', 4.0, 50), ('C02', 'C03', 5.8, 45),
    ('C03', 'C04', 3.5, 45), ('C04', 'C05', 3.0, 45),
    ('C04', 'C06', 3.0, 50), ('C05', 'C06', 2.8, 45),
    ('C03', 'C07', 8.0, 60), ('C06', 'C07', 8.5, 60),
    ('C06', 'C08', 6.0, 55), ('C07', 'C08', 8.0, 60),
]


@dataclass(frozen=True)
class Settings:
    database: str = os.getenv('ANPR_DATABASE', 'data/nexus.sqlite3')
    api_key: str = os.getenv('ANPR_API_KEY', '')
    demo_mode: bool = os.getenv('ANPR_DEMO_MODE', 'true').lower() == 'true'
