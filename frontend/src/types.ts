export type Role = 'viewer' | 'officer' | 'admin';
export interface User { username: string; name: string; role: Role; unit: string }
export interface Session { access_token: string; expires_in: number; user: User }
export interface AuthConfig { demo: boolean; has_session: boolean; second_factor_supported: boolean; demo_users: (User & {password: string})[]; units: string[] }
export interface Camera { id: string; name: string; lat: number; lon: number; restricted: boolean }
export interface Road { from: string; to: string; distance_km: number; free_flow_kmh: number }
export interface Corridor extends Road { median_speed_kmh: number | null; congestion_index: number | null; level: 'free'|'moderate'|'heavy'|'congested'|'unknown'; samples: number }
export interface Density { camera_id: string; name: string; lat: number; lon: number; count: number }
export interface Summary { detections: number; plate_detections: number; unidentified_passes: number; unique_vehicles: number; active_cameras: number; network_average_speed_kmh: number | null; open_alerts: number; first_detection: string|null; last_detection: string|null; speed_samples: number }
export interface Minute { camera_id: string; minute: string; count: number }
export interface Analytics { summary: Summary; corridors: Corridor[]; vehicles_per_minute: Minute[] }
export interface OD { origin: string; destination: string; trips: number }
export interface Integrity { valid: boolean; checked: number; head?: string; anchor?: string; broken_at?: number }
export interface Alert { id: number; plate: string; camera_id: string; timestamp: string; kind: string; severity: string; explanation: string; evidence: Record<string, unknown>; status?: 'Open'|'Acknowledged'|'Escalated'|'Verified'|'Dispatched'|'Closed'|'False Positive'; assignee?: string; note?: string }
export interface Watch { plate: string; reason: string; created_at: string }
export interface Audit { id: number; timestamp: string; role: string; action: string; details: string }
export interface Vehicle { id: number; plate: string; vehicle_type: string; confidence: number; valid: number; sightings: number; last_seen: string; match_distance: number }
export interface Hop { detection_id: number; camera_id: string; camera_name: string; timestamp: string; confidence: number; observed_plate: string; leg_distance_km: number; seconds: number|null; speed_kmh: number|null; inferred_cameras: string[]; implausible: boolean }
export interface Trajectory { found: boolean; plate: string; identity_id: number; vehicle_type: string; hops: Hop[]; total_distance_km: number; geojson: {type: 'LineString'; coordinates: [number,number][]} }
export interface PlateRead { text: string; confidence: number; quality: number }
export interface Evidence { id: number; camera_id: string; timestamp: string; plate: string; confidence: number; source: string; reads: PlateRead[]; resolution: {method: string; score: number; canonical_plate: string} }
export interface Owner { name: string; address: string; contact: string }
export interface Challan { number: string; timestamp: string; violation: string; location: string; amount: number; status: string }
export interface Profile { identity: Vehicle; trajectory: Trajectory; evidence: Evidence[]; confidence: number; watchlisted: boolean; integrity: Integrity; alerts: Alert[]; notes: {id: number; username: string; timestamp: string; note: string}[]; registry: {provider: string; demo: boolean; registration: Record<string,string>|null; owner: Owner|null; challans: Challan[]} }
export interface Attribute { id: number|string; identity_id: number|null; plate: string|null; camera_id: string; timestamp: string; vehicle_class: string; colour: string|null; confidence: number|null; attribute_source: string; snapshot: string|null }
export interface Sample { name: string; title: string; license: string; url: string }
