#!/usr/bin/env python3
"""
Standalone Database Initialization Script for ABC University Academic Management System.
Creates DuckDB database and tables from sql/schema.sql and seeds initial data from sql/seed.sql.
"""
import sys
import os

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import init_database, get_all_records, TABLES_META

def main():
    print("=" * 60)
    print("ABC UNIVERSITY - DUCKDB INITIALIZATION")
    print("=" * 60)
    
    init_database()
    
    print("\nVerifying tables and record counts:")
    print("-" * 60)
    total_records = 0
    for table_name in TABLES_META:
        records = get_all_records(table_name)
        count = len(records)
        total_records += count
        print(f"  • {table_name:<20}: {count:>3} records")
    print("-" * 60)
    print(f"Total records in database: {total_records}")
    print("Database initialization complete.")

if __name__ == "__main__":
    main()
