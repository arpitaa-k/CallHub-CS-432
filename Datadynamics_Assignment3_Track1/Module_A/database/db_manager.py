
from table import Table

class DatabaseManager:
    def __init__(self):
        # Dictionary to store databases as {db_name: {table_name: Table instance}}
        self.databases = {}

    def create_database(self, db_name):
        """
        Create a new database with the given name.
        Initializes an empty dictionary for tables within this database.
        """
        if db_name in self.databases:
            print(f"Database '{db_name}' already exists.")
            return False
        
        self.databases[db_name] = {}
        print(f"Database '{db_name}' created successfully.")
        return True

    def delete_database(self, db_name):
        """
        Delete an existing database and all its tables.
        """
        if db_name in self.databases:
            del self.databases[db_name]
            print(f"Database '{db_name}' deleted successfully.")
            return True
            
        print(f"Error: Database '{db_name}' does not exist.")
        return False

    def list_databases(self):
        """
        Return a list of all database names currently managed.
        """
        return list(self.databases.keys())

    def create_table(self, db_name, table_name, schema, order=8, search_key=None):
        """
        Create a new table within a specified database.
        - schema: dictionary of column names and data types
        - order: B+ tree order for indexing
        - search_key: field name to use as the key in the B+ Tree
        """
        if db_name not in self.databases:
            print(f"Error: Database '{db_name}' does not exist.")
            return False
            
        if table_name in self.databases[db_name]:
            print(f"Error: Table '{table_name}' already exists in database '{db_name}'.")
            return False

        # If no search_key is provided, default to the first column in the schema
        if search_key is None and schema:
            search_key = list(schema.keys())[0]

        # Initialize the Table (which will spin up its own B+ Tree)
        new_table = Table(table_name, schema, order, search_key)
        self.databases[db_name][table_name] = new_table
        
        print(f"Table '{table_name}' created successfully in '{db_name}'.")
        return True

    def delete_table(self, db_name, table_name):
        """
        Delete a table from the specified database.
        """
        if db_name in self.databases and table_name in self.databases[db_name]:
            del self.databases[db_name][table_name]
            print(f"Table '{table_name}' deleted from '{db_name}'.")
            return True
            
        print(f"Error: Table '{table_name}' not found in database '{db_name}'.")
        return False

    def list_tables(self, db_name):
        """
        List all tables within a given database.
        """
        if db_name in self.databases:
            return list(self.databases[db_name].keys())
            
        print(f"Error: Database '{db_name}' does not exist.")
        return []

    def get_table(self, db_name, table_name):
        """
        Retrieve a Table instance from a given database.
        Useful for performing operations like insert, update, delete on that table.
        """
        if db_name in self.databases and table_name in self.databases[db_name]:
            return self.databases[db_name][table_name]
            
        print(f"Error: Table '{table_name}' not found in '{db_name}'.")
        return None
