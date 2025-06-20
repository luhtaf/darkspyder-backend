#!/usr/bin/env python3
"""
Script untuk memperbaiki data di Elasticsearch yang memiliki multi-domain.
Script ini akan:
1. Mencari data dengan origin berupa array atau domain berupa comma-separated string
2. Membuat record baru untuk setiap domain
3. Menghapus record lama yang memiliki multi-domain

Contoh data yang akan diperbaiki:
- Array origin: {"origin": ["domain1.com", "domain2.com"]}
- Comma-separated domain: {"domain": "domain1.com, domain2.com, domain3.com"}
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

def find_multi_domain_data(search_index=None, size=1000):
    """Mencari data dengan domain berupa array atau comma-separated string"""
    if search_index is None:
        search_index = index_name
    
    # Query untuk mencari data dengan domain yang mengandung koma (comma-separated)
    # atau origin yang berupa array
    query = {
        "query": {
            "bool": {
                "should": [
                    # Cari domain yang mengandung koma
                    {
                        "bool": {
                            "must": [
                                {"exists": {"field": "domain"}},
                                {"wildcard": {"domain": "*,*"}}
                            ]
                        }
                    },
                    # Cari origin yang berupa array (lebih dari 1 element)
                    {
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
                    }
                ],
                "minimum_should_match": 1
            }
        },
        "size": size
    }
    
    try:
        response = es.search(index=search_index, body=query)
        return response['hits']['hits']
    except Exception as e:
        print(f"Error searching for multi-domain data: {e}")
        return []

def create_new_records(original_data, doc_id, target_index):
    """Membuat record baru untuk setiap domain dalam array origin atau comma-separated domain"""
    source_data = original_data['_source']
    new_records = []
    domains = []
    
    # Cek apakah ada origin array
    if 'origin' in source_data and isinstance(source_data['origin'], list):
        print(f"Processing array origin: {source_data['origin']}")
        domains = source_data['origin']
        source_field = 'origin'
    # Cek apakah ada domain dengan koma
    elif 'domain' in source_data and ',' in str(source_data['domain']):
        print(f"Processing comma-separated domain: {source_data['domain']}")
        # Split domain berdasarkan koma dan bersihkan whitespace
        domains = [d.strip() for d in source_data['domain'].split(',') if d.strip()]
        source_field = 'domain'
    else:
        print(f"Skipping document {doc_id}: no multi-domain data found")
        return []
    
    print(f"Found {len(domains)} domains to process")
    
    for domain in domains:
        # Skip domain kosong atau yang hanya berisi titik
        if not domain or domain.strip() in ['', '.', '...', '....', '.....']:
            continue
            
        # Buat copy data dengan single domain
        new_data = source_data.copy()
        
        # Hapus field origin jika ada (karena akan dikonversi ke domain)
        if 'origin' in new_data:
            del new_data['origin']
        
        # Set domain tunggal
        new_data['domain'] = domain.strip()
        
        # Format sesuai dengan formatting_data_stealer
        formatted_data = formatting_data_stealer(new_data)
        
        # Tambahkan metadata yang diperlukan
        formatted_data['threatintel'] = source_data.get('threatintel', 'stealer3')
        
        # Generate checksum
        checksum_input = json.dumps(formatted_data, sort_keys=True)
        formatted_data['Checksum'] = hashlib.sha256(checksum_input.encode()).hexdigest()
        
        # Simpan ke Elasticsearch
        try:
            response = es.index(index=target_index, body=formatted_data)
            new_records.append({
                'id': response['_id'],
                'domain': domain.strip(),
                'data': formatted_data
            })
            print(f"✓ Created new record for domain '{domain.strip()}' with ID: {response['_id']}")
        except Exception as e:
            print(f"✗ Error creating record for domain '{domain.strip()}': {e}")
    
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

def process_multi_domain_data(dry_run=True):
    """Proses utama untuk memperbaiki data multi-domain (array origin atau comma-separated domain)"""
    print("=" * 70)
    print("ELASTICSEARCH MULTI-DOMAIN FIXER")
    print("=" * 70)
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
    else:
        print("⚠️  LIVE MODE - Changes will be applied to Elasticsearch")
    
    print("\n1. Searching for documents with multi-domain data...")
    
    # Cari data dengan multi-domain (array origin atau comma-separated domain)
    multi_docs = find_multi_domain_data()
    
    if not multi_docs:
        print("✓ No documents found with multi-domain data. Database is clean!")
        return
    
    print(f"Found {len(multi_docs)} documents with multi-domain data")
    
    total_processed = 0
    total_created = 0
    total_deleted = 0
    
    for doc in multi_docs:
        doc_id = doc['_id']
        doc_index = doc['_index']
        source_data = doc['_source']
        
        print(f"\n--- Processing Document {doc_id} ---")
        print(f"Index: {doc_index}")
        
        # Tentukan jenis multi-domain data
        domain_count = 0
        if 'origin' in source_data and isinstance(source_data['origin'], list):
            domain_count = len(source_data['origin'])
            print(f"Array origin contains {domain_count} domains: {source_data['origin']}")
        elif 'domain' in source_data and ',' in str(source_data['domain']):
            domains = [d.strip() for d in source_data['domain'].split(',') if d.strip()]
            domain_count = len(domains)
            print(f"Comma-separated domain contains {domain_count} domains: {source_data['domain']}")
        else:
            print(f"Skipping document {doc_id}: no recognizable multi-domain pattern")
            continue
        
        if not dry_run:
            # Buat record baru untuk setiap domain
            new_records = create_new_records(doc, doc_id, doc_index)
            
            if new_records:
                total_created += len(new_records)
                
                # Hapus record lama
                if delete_old_record(doc_id, doc_index):
                    total_deleted += 1
                    print(f"✓ Successfully processed document {doc_id}")
                else:
                    print(f"✗ Failed to delete old record {doc_id}")
                    # Rollback: hapus record baru yang sudah dibuat
                    print("Rolling back new records...")
                    for record in new_records:
                        try:
                            es.delete(index=doc_index, id=record['id'])
                            print(f"  Rolled back record {record['id']}")
                        except:
                            print(f"  Failed to rollback record {record['id']}")
            else:
                print(f"✗ Failed to create new records for document {doc_id}")
        else:
            print(f"[DRY RUN] Would create {domain_count} new records and delete original")
            total_created += domain_count
            total_deleted += 1
        
        total_processed += 1
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
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
        process_multi_domain_data(dry_run=dry_run)
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
