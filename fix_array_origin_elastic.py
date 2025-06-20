#!/usr/bin/env python3
"""
Script untuk memperbaiki data di Elasticsearch yang memiliki multi-domain.
Script ini akan:
1. Iterasi semua data menggunakan scroll API
2. Cek setiap document apakah domain mengandung koma
3. Jika ada koma: buat record baru untuk setiap domain dan hapus record lama
4. Jika tidak ada koma: abaikan dan lanjut ke document berikutnya
"""

import json
import hashlib
from elasticsearch import Elasticsearch
from es_config import es, index_name

def formatting_data_stealer(data):
    """Format data stealer sesuai dengan fungsi di breach2.py"""
    # Set username based on available fields
    if "username" in data:
        username = data["username"]
    elif "email" in data:
        username = data["email"]
    else:
        username = ""
    
    # Handle single domain
    if "domain" in data:
        domain = data["domain"]
    else:
        domain = ""
        
    newData = {
        "username": username,
        "password": data.get("password", ""),
        "domain": domain,
        "type": "stealer"
    }
    
    return newData

def create_new_records(original_data, doc_id, target_index):
    """Membuat record baru untuk setiap domain dalam comma-separated domain"""
    source_data = original_data['_source']
    new_records = []
    
    # Split domain berdasarkan koma dan bersihkan whitespace
    domain_string = str(source_data['domain'])
    domains = [d.strip() for d in domain_string.split(',') if d.strip()]
    
    print(f"Processing {len(domains)} domains for document {doc_id}")
    
    # Limit jumlah domain yang diproses untuk mencegah overload
    max_domains = 500
    if len(domains) > max_domains:
        print(f"⚠️  Warning: Too many domains ({len(domains)}). Processing only first {max_domains} domains.")
        domains = domains[:max_domains]
    
    for i, domain in enumerate(domains):
        # Skip domain kosong atau yang hanya berisi titik
        if not domain or domain.strip() in ['', '.', '...', '....', '.....']:
            continue
            
        # Progress indicator untuk domain yang banyak
        if len(domains) > 50 and i % 50 == 0:
            print(f"  Processing domain {i+1}/{len(domains)}...")
            
        # Buat copy data dengan single domain
        new_data = source_data.copy()
        new_data['domain'] = domain.strip()
        
        # Format sesuai dengan formatting_data_stealer
        formatted_data = formatting_data_stealer(new_data)
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
        except Exception as e:
            print(f"✗ Error creating record for domain '{domain.strip()}': {e}")
    
    print(f"✓ Successfully created {len(new_records)} new records")
    return new_records

def delete_old_record(doc_id, index_name):
    """Menghapus record lama yang memiliki multi-domain"""
    try:
        response = es.delete(index=index_name, id=doc_id)
        print(f"✓ Deleted old record with ID: {doc_id}")
        return True
    except Exception as e:
        print(f"✗ Error deleting record {doc_id}: {e}")
        return False

def process_all_documents():
    """Proses semua document menggunakan scroll API"""
    print("=" * 70)
    print("ELASTICSEARCH MULTI-DOMAIN FIXER")
    print("=" * 70)
    print("🔄 Processing ALL documents using scroll API...")
    
    # Initialize scroll
    scroll_size = 1000
    scroll_timeout = "5m"
    
    # Initial search with scroll
    try:
        response = es.search(
            index=index_name,
            scroll=scroll_timeout,
            size=scroll_size,
            body={"query": {"match_all": {}}}
        )
    except Exception as e:
        print(f"❌ Error initializing scroll: {e}")
        return
    
    scroll_id = response['_scroll_id']
    hits = response['hits']['hits']
    total_docs = response['hits']['total']['value']
    
    print(f"📊 Total documents in index: {total_docs}")
    
    processed_count = 0
    multi_domain_count = 0
    created_records = 0
    deleted_records = 0
    
    # Process documents in batches
    while hits:
        print(f"\n📦 Processing batch of {len(hits)} documents...")
        
        for doc in hits:
            processed_count += 1
            doc_id = doc['_id']
            doc_index = doc['_index']
            source_data = doc['_source']
            
            # Progress indicator
            if processed_count % 1000 == 0:
                print(f"📈 Progress: {processed_count}/{total_docs} documents processed")
            
            # Cek apakah ada domain dengan koma
            if 'domain' in source_data and ',' in str(source_data['domain']):
                multi_domain_count += 1
                print(f"\n🔍 Found multi-domain in document {doc_id}")
                
                # Buat record baru untuk setiap domain
                new_records = create_new_records(doc, doc_id, doc_index)
                
                if new_records:
                    created_records += len(new_records)
                    
                    # Hapus record lama
                    if delete_old_record(doc_id, doc_index):
                        deleted_records += 1
                        print(f"✅ Successfully processed document {doc_id}")
                    else:
                        print(f"❌ Failed to delete old record {doc_id}")
                        # Rollback: hapus record baru yang sudah dibuat
                        print("🔄 Rolling back new records...")
                        for record in new_records:
                            try:
                                es.delete(index=doc_index, id=record['id'])
                                print(f"  ↩️  Rolled back record {record['id']}")
                            except:
                                print(f"  ❌ Failed to rollback record {record['id']}")
                else:
                    print(f"❌ Failed to create new records for document {doc_id}")
        
        # Get next batch
        try:
            response = es.scroll(scroll_id=scroll_id, scroll=scroll_timeout)
            scroll_id = response['_scroll_id']
            hits = response['hits']['hits']
        except Exception as e:
            print(f"❌ Error during scroll: {e}")
            break
    
    # Clear scroll
    try:
        es.clear_scroll(scroll_id=scroll_id)
    except:
        pass
    
    # Summary
    print("\n" + "=" * 70)
    print("📋 SUMMARY")
    print("=" * 70)
    print(f"Total documents processed: {processed_count}")
    print(f"Documents with multi-domain: {multi_domain_count}")
    print(f"New records created: {created_records}")
    print(f"Old records deleted: {deleted_records}")
    print("✅ Processing completed!")

def main():
    """Main function"""
    try:
        process_all_documents()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
