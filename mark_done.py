import json 
from database_module import VehicleDatabaseManager 
with open('db_config.json') as f: cfg = json.load(f) 
db = VehicleDatabaseManager(**cfg) 
alerts = db.get_alerts(status='NEW', limit=500) 
ids = [str(a.get('alert_id') or a.get('id')) for a in alerts] 
with open('alerted_alert_ids.json', 'w') as f: json.dump(ids, f) 
print(f'Marked {len(ids)} existing alerts as done') 
