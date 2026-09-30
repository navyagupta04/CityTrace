"""Explicitly synthetic registry adapter. No access to government registries."""
from hashlib import sha256
from typing import Protocol


class RegistryProvider(Protocol):
    def lookup(self, plate: str) -> dict: ...


class MockRegistry:
    def lookup(self, plate: str) -> dict:
        seed = int(sha256(plate.encode()).hexdigest()[:8], 16)
        makes = [('Maruti Suzuki', 'Baleno'), ('Hyundai', 'i20'), ('Tata', 'Nexon'), ('Honda', 'City'), ('Mahindra', 'XUV300')]
        make, model = makes[seed % len(makes)]
        return {'provider': 'mock', 'demo': True, 'registration': {
            'make': make, 'model': model, 'colour': ['White', 'Silver', 'Red', 'Blue', 'Black'][seed % 5],
            'fuel_type': ['Petrol', 'Diesel', 'CNG'][seed % 3], 'registration_date': f'202{seed%4}-04-12',
            'rto': 'Delhi · DL-01', 'insurance_valid_until': '2027-04-30',
            'puc_valid_until': '2026-08-31', 'fitness_valid_until': '2034-04-12'},
            'owner': {'name': 'Demo Registered Owner', 'address': f'{seed%300+1}, Demonstration Colony, New Delhi',
                      'contact': '+91 00000 00000'},
            'challans': [
                {'number': f'DEMO-{seed%100000:05}-01', 'timestamp': '2026-09-12T09:20:00+05:30', 'violation': 'Signal violation', 'location': 'ITO Junction', 'amount': 1000, 'status': 'Pending'},
                {'number': f'DEMO-{seed%100000:05}-02', 'timestamp': '2026-08-18T14:35:00+05:30', 'violation': 'Parking violation', 'location': 'Connaught Place', 'amount': 500, 'status': 'Paid'}]}


class AuthorizedRegistry:
    def lookup(self, plate: str) -> dict:
        raise NotImplementedError('Official VAHAN/e-Challan integration requires an authorized provider and credentials.')


def masked_owner() -> dict:
    return {'name': '•••••• ••••••', 'address': '••••••, New Delhi', 'contact': '+91 ••••• •••••'}
