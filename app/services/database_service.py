from typing import Dict, Any, List, Optional
from app.db.supabase_client import supabase
from app.services.base_service import BaseService
from app.core.exceptions import DatabaseError

class DatabaseService(BaseService):
    """
    Service for handling all database operations via Supabase.
    """
    
    def insert_record(self, table_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inserts a record into the specified table.
        """
        try:
            self.log_info(f"Inserting record into {table_name}")
            response = supabase.table(table_name).insert(data).execute()
            if not response.data or len(response.data) == 0:
                raise DatabaseError(f"Failed to insert record into {table_name}")
            return response.data[0]
        except Exception as e:
            self.log_error(f"Database insertion failed for {table_name}", e)
            raise DatabaseError(f"Database error: {str(e)}")

    def update_record(self, table_name: str, record_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates a record in the specified table.
        """
        try:
            self.log_info(f"Updating record {record_id} in {table_name}")
            response = supabase.table(table_name).update(data).eq("id", record_id).execute()
            if not response.data or len(response.data) == 0:
                raise DatabaseError(f"Failed to update record {record_id} in {table_name}")
            return response.data[0]
        except Exception as e:
            self.log_error(f"Database update failed for {table_name}, ID: {record_id}", e)
            raise DatabaseError(f"Database error: {str(e)}")

    def get_record_by_id(self, table_name: str, record_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a record by its ID.
        """
        try:
            response = supabase.table(table_name).select("*").eq("id", record_id).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            self.log_error(f"Failed to retrieve record {record_id} from {table_name}", e)
            return None

    def upload_file(self, bucket_name: str, file_path: str, file_content: bytes, content_type: str = "image/png") -> str:
        """
        Uploads a file to a Supabase bucket and returns its public URL.
        """
        try:
            self.log_info(f"Uploading file to bucket {bucket_name}: {file_path}")
            # Use upsert=True to overwrite if exists
            supabase.storage.from_(bucket_name).upload(
                path=file_path,
                file=file_content,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            
            # Get public URL
            response = supabase.storage.from_(bucket_name).get_public_url(file_path)
            return response
        except Exception as e:
            self.log_error(f"Failed to upload file to {bucket_name}", e)
            raise DatabaseError(f"Storage upload error: {str(e)}")

db_service = DatabaseService()
