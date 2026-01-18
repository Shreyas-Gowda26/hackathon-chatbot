from database import db
import json

print("Starting hackathon data import...")

# Load hackathon JSON data
try:
    with open('hackathon_data.json', 'r') as f:
        hackathon_data = json.load(f)
    print("✅ JSON file loaded successfully")
except FileNotFoundError:
    print("❌ ERROR: hackathon_data.json not found!")
    print("   Please create hackathon_data.json with your hackathon data")
    exit()
except json.JSONDecodeError:
    print("❌ ERROR: Invalid JSON format in hackathon_data.json")
    exit()

# Import to database
print(f"\nImporting: {hackathon_data.get('name', 'Unknown')}")
success = db.insert_hackathon(hackathon_data)

if success:
    print("\n" + "="*50)
    print("✅ SUCCESS! Hackathon data imported to MongoDB")
    print("="*50)
    print(f"   Name: {hackathon_data.get('name')}")
    print(f"   ID: {hackathon_data.get('_id')}")
    print(f"   Organizer: {hackathon_data.get('organizer_name')}")
    print(f"   Themes: {len(hackathon_data.get('themes', []))}")
    print("="*50)
else:
    print("\n❌ FAILED to import data")
    print("   Check if MongoDB is running")