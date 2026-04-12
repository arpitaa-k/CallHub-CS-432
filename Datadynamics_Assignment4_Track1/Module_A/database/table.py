

from bplustree import BPlusTree
class Table:
    def __init__(self, name, schema, order=8, search_key=None):
        self.name = name                                     # Name of the table
        self.schema = schema                                 # Table schema: dict of {column_name: data_type}
        self.order = order                                   # Order of the B+ Tree
        self.data = BPlusTree(order=order)                   # Underlying B+ Tree to store the data
        
        # If no search key is provided, default to the first column in the schema
        if search_key is None and schema:
            self.search_key = list(schema.keys())[0]
        else:
            self.search_key = search_key                     # Primary key used for indexing

    def validate_record(self, record):
        """
        Validate that the given record matches the table schema:
        - All required columns are present
        - Data types are correct
        - No extra columns are included
        """
        # 1. Check if all required columns from the schema are in the record
        for col_name, expected_type in self.schema.items():
            if col_name not in record:
                print(f"Validation Error: Missing required column '{col_name}'.")
                return False
            
            # 2. Check if the data type matches
            if not isinstance(record[col_name], expected_type):
                print(f"Validation Error: Column '{col_name}' expects {expected_type.__name__}, got {type(record[col_name]).__name__}.")
                return False

        # 3. Check for any extra unexpected columns in the record
        for col_name in record.keys():
            if col_name not in self.schema:
                print(f"Validation Error: Unknown column '{col_name}' provided.")
                return False
                
        return True

    def insert(self, record):
        """
        Insert a new record into the table.
        The record should be a dictionary matching the schema.
        The key used for insertion should be the value of the `search_key` field.
        """
        if not self.validate_record(record):
            return False
            
        key = record.get(self.search_key)
        
        # Prevent duplicate keys (like duplicate Student IDs)
        if self.data.search(key) is not None:
            print(f"Insert Error: Record with {self.search_key} '{key}' already exists.")
            return False
            
        self.data.insert(key, record)
        return True

    def get(self, record_id):
        """
        Retrieve a single record by its ID (i.e., the value of the `search_key`)
        """
        return self.data.search(record_id)

    def get_all(self):
        """
        Retrieve all records stored in the table in sorted order by search key
        """
        # BPlusTree.get_all() returns a list of (key, value) tuples.
        # We only want to return the actual records (the values).
        kv_pairs = self.data.get_all()
        return [value for key, value in kv_pairs]

    def update(self, record_id, new_record):
        """
        Update a record identified by `record_id` with `new_record` data.
        Usually overwrites the existing entry.
        """
        if not self.validate_record(new_record):
            return False
            
        new_key = new_record.get(self.search_key)
        
        # Check if the record we are trying to update actually exists
        if self.data.search(record_id) is None:
            print(f"Update Error: Record with {self.search_key} '{record_id}' not found.")
            return False

        # If the primary key is changing, we must delete the old one and insert the new one
        if new_key != record_id:
            if self.data.search(new_key) is not None:
                print(f"Update Error: Cannot change ID. A record with {self.search_key} '{new_key}' already exists.")
                return False
            self.data.delete(record_id)
            self.data.insert(new_key, new_record)
        else:
            # Same key, just an in-place update of the data
            self.data.update(record_id, new_record)
            
        return True

    def delete(self, record_id):
        """
        Delete the record from the table by its `record_id`
        """
        if self.data.search(record_id) is None:
            print(f"Delete Error: Record with {self.search_key} '{record_id}' not found.")
            return False
            
        self.data.delete(record_id)
        return True

    def range_query(self, start_value, end_value):
        """
        Perform a range query using the search key.
        Returns records where start_value <= key <= end_value
        """
        # BPlusTree.range_query() returns a list of (key, value) tuples.
        kv_pairs = self.data.range_query(start_value, end_value)
        return [value for key, value in kv_pairs]