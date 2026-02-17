from pymongo import MongoClient
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()

class HackathonDatabase:
    def __init__(self):
        self.client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/"))
        self.db = self.client[os.getenv("MONGODB_DATABASE", "hackathon_db")]
        self.collection = self.db[os.getenv("MONGODB_COLLECTION", "hackathons")]
    
    def get_hackathon_by_id(self, hackathon_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve hackathon data by ID"""
        try:
            hackathon = self.collection.find_one({"_id": hackathon_id})
            return hackathon
        except Exception as e:
            print(f"Error fetching hackathon: {e}")
            return None
    
    def get_hackathon_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Retrieve hackathon data by slug"""
        try:
            hackathon = self.collection.find_one({"slug": slug})
            return hackathon
        except Exception as e:
            print(f"Error fetching hackathon: {e}")
            return None
    
    def insert_hackathon(self, hackathon_data: Dict[str, Any]) -> bool:
        """Insert new hackathon data"""
        try:
            self.collection.insert_one(hackathon_data)
            return True
        except Exception as e:
            print(f"Error inserting hackathon: {e}")
            return False
    
    def update_hackathon(self, hackathon_id: str, update_data: Dict[str, Any]) -> bool:
        """Update existing hackathon data"""
        try:
            result = self.collection.update_one(
                {"_id": hackathon_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Error updating hackathon: {e}")
            return False
    
    def list_all_hackathons(self) -> list:
        """List all hackathons"""
        try:
            return list(self.collection.find({}))
        except Exception as e:
            print(f"Error listing hackathons: {e}")
            return []

# Singleton instance
db = HackathonDatabase()