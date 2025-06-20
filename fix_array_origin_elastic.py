#!/usr/bin/env python3
"""
Script untuk memperbaiki data di Elasticsearch yang memiliki array di field origin.
Script ini akan:
1. Mencari data dengan origin berupa array
2. Membuat record baru untuk setiap domain dalam array
3. Menghapus record lama yang memiliki array origin
"""

import json
import hashlib
from elasticsearch import Elasticsearch
from es_config import es, index_name
import sys

def formatting_data_stealer(data):
    """Format data stealer sesuai dengan fungsi di breach2.py"""
    # Set username based on available fields
    if "username" in data:
        username = data["username"]
    elif "email" in data:
        username = data["email"]
    else:
        username = ""
    
    # Handle single domain (not array)
    if "origin" in data:
        domain = data["origin"]
    else:
        domain = ""
        
    newData = {
        "username": username,
        "password": data.get("password", ""),
        "domain": domain,
        "type": "stealer"
    }
    
    return newData

def find_array_origin_data(search_index=None, size=1000):
    """Mencari data dengan origin berupa array"""
    if search_index is None:
        search_index = index_name
    
    query = {
        "query": {
            "bool": {
                "must": [
                    {"exists": {"field": "origin"}},
                    {"script": {
                        "script": {
                            "source": "doc['origin'].size() > 1",
                            "lang": "painless"
                        }
                    }}
                ]
            }
        },
        "size": size
    }
    
    try:
        response = es.search(index=search_index, body=query)
        return response['hits']['hits']
    except Exception as e:
        print(f"Error searching for array origin data: {e}")
        return []

def create_new_records(original_data, doc_id, index_name):
    """Membuat record baru untuk setiap domain dalam array origin"""
    source_data = original_data['_source']
    
    if 'origin' not in source_data or not isinstance(source_data['origin'], list):
        print(f"Skipping document {doc_id}: origin is not an array")
        return []
    
    new_records = []
    
    for domain in source_data['origin']:
        # Buat copy data dengan single domain
        new_data = source_data.copy()
        new_data['origin'] = domain
        
        # Format sesuai dengan formatting_data_stealer
        formatted_data = formatting_data_stealer(new_data)
        
        # Tambahkan metadata yang diperlukan
        formatted_data['threatintel'] = source_data.get('threatintel', 'stealer3')
        
        # Generate checksum
        checksum_input = json.dumps(formatted_data, sort_keys=True)
        formatted_data['Checksum'] = hashlib.sha256(checksum_input.encode()).hexdigest()
        
        # Simpan ke Elasticsearch
        try:
            response = es.index(index=index_name, body=formatted_data)
            new_records.append({
                'id': response['_id'],
                'domain': domain,
                'data': formatted_data
            })
            print(f"✓ Created new record for domain '{domain}' with ID: {response['_id']}")
        except Exception as e:
            print(f"✗ Error creating record for domain '{domain}': {e}")
    
    return new_records

def delete_old_record(doc_id, index_name):
    """Menghapus record lama yang memiliki array origin"""
    try:
        response = es.delete(index=index_name, id=doc_id)
        print(f"✓ Deleted old record with ID: {doc_id}")
        return True
    except Exception as e:
        print(f"✗ Error deleting record {doc_id}: {e}")
        return False

def process_array_origin_data(dry_run=True):
    """Proses utama untuk memperbaiki data array origin"""
    print("=" * 60)
    print("ELASTICSEARCH ARRAY ORIGIN FIXER")
    print("=" * 60)
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
    else:
        print("⚠️  LIVE MODE - Changes will be applied to Elasticsearch")
    
    print("\n1. Searching for documents with array origin...")
    
    # Cari data dengan array origin
    array_docs = find_array_origin_data()
    
    if not array_docs:
        print("✓ No documents found with array origin. Database is clean!")
        return
    
    print(f"Found {len(array_docs)} documents with array origin")
    
    total_processed = 0
    total_created = 0
    total_deleted = 0
    
    for doc in array_docs:
        doc_id = doc['_id']
        index_name = doc['_index']
        source_data = doc['_source']
        
        print(f"\n--- Processing Document {doc_id} ---")
        print(f"Index: {index_name}")
        print(f"Original origin: {source_data.get('origin', 'N/A')}")
        
        if isinstance(source_data.get('origin'), list):
            origin_count = len(source_data['origin'])
            print(f"Array contains {origin_count} domains: {source_data['origin']}")
            
            if not dry_run:
                # Buat record baru untuk setiap domain
                new_records = create_new_records(doc, doc_id, index_name)
                
                if new_records:
                    total_created += len(new_records)
                    
                    # Hapus record lama
                    if delete_old_record(doc_id, index_name):
                        total_deleted += 1
                        print(f"✓ Successfully processed document {doc_id}")
                    else:
                        print(f"✗ Failed to delete old record {doc_id}")
                        # Rollback: hapus record baru yang sudah dibuat
                        print("Rolling back new records...")
                        for record in new_records:
                            try:
                                es.delete(index=index_name, id=record['id'])
                                print(f"  Rolled back record {record['id']}")
                            except:
                                print(f"  Failed to rollback record {record['id']}")
                else:
                    print(f"✗ Failed to create new records for document {doc_id}")
            else:
                print(f"[DRY RUN] Would create {origin_count} new records and delete original")
                total_created += origin_count
                total_deleted += 1
        
        total_processed += 1
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Documents processed: {total_processed}")
    print(f"New records created: {total_created}")
    print(f"Old records deleted: {total_deleted}")
    
    if dry_run:
        print("\n🔍 This was a DRY RUN. No actual changes were made.")
        print("To apply changes, run the script with --apply flag")
    else:
        print("\n✅ All changes have been applied to Elasticsearch")

def main():
    """Main function"""
    dry_run = True
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--apply":
            dry_run = False
        elif sys.argv[1] == "--help":
            print("Usage:")
            print("  python3 fix_array_origin_elastic.py           # Dry run (preview only)")
            print("  python3 fix_array_origin_elastic.py --apply   # Apply changes")
            print("  python3 fix_array_origin_elastic.py --help    # Show this help")
            return
        else:
            print("Invalid argument. Use --help for usage information.")
            return
    
    try:
        process_array_origin_data(dry_run=dry_run)
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
