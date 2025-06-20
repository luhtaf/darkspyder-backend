#!/usr/bin/env python3
"""
Script untuk mencari SEMUA data dengan domain yang mengandung koma menggunakan scroll
"""

from es_config import es, index_name

def find_all_comma_domains():
    """Scan semua dokumen untuk mencari yang memiliki koma di domain"""
    
    print(f"Scanning ALL documents in index: {index_name}")
    print("This may take a while...")
    
    # Initialize scroll
    query = {
        "query": {"match_all": {}},
        "_source": ["domain"],
        "size": 1000
    }
    
    try:
        # Start scroll
        response = es.search(index=index_name, scroll='2m', **query)
        scroll_id = response['_scroll_id']
        
        total_docs = response['hits']['total']['value']
        print(f"Total documents to scan: {total_docs}")
        
        comma_docs = []
        long_domain_docs = []
        processed = 0
        
        while True:
            hits = response['hits']['hits']
            if not hits:
                break
                
            for hit in hits:
                processed += 1
                if processed % 1000 == 0:
                    print(f"Processed {processed}/{total_docs} documents...")
                
                source = hit['_source']
                if 'domain' in source:
                    domain_str = str(source['domain'])
                    if ',' in domain_str:
                        comma_docs.append({
                            'id': hit['_id'],
                            'domain': domain_str,
                            'domain_count': len([d.strip() for d in domain_str.split(',') if d.strip()])
                        })
                        print(f"Found comma domain! Doc ID: {hit['_id']}, Domain count: {len([d.strip() for d in domain_str.split(',') if d.strip()])}")
                    
                    if len(domain_str) > 1000:
                        long_domain_docs.append({
                            'id': hit['_id'],
                            'domain_length': len(domain_str),
                            'domain_preview': domain_str[:200] + "..."
                        })
                        print(f"Found long domain! Doc ID: {hit['_id']}, Length: {len(domain_str)} chars")
            
            # Get next batch
            try:
                response = es.scroll(scroll_id=scroll_id, scroll='2m')
            except Exception as e:
                print(f"Scroll error: {e}")
                break
        
        # Clear scroll
        try:
            es.clear_scroll(scroll_id=scroll_id)
        except:
            pass
        
        print(f"\n=== SCAN COMPLETE ===")
        print(f"Total documents processed: {processed}")
        print(f"Documents with comma in domain: {len(comma_docs)}")
        print(f"Documents with very long domains (>1000 chars): {len(long_domain_docs)}")
        
        if comma_docs:
            print(f"\n=== COMMA DOMAIN EXAMPLES ===")
            for i, doc in enumerate(comma_docs[:5]):  # Show first 5
                print(f"{i+1}. Document ID: {doc['id']}")
                print(f"   Domain count: {doc['domain_count']}")
                if len(doc['domain']) > 200:
                    print(f"   Domain preview: {doc['domain'][:200]}...")
                else:
                    print(f"   Domain: {doc['domain']}")
                print()
        
        if long_domain_docs:
            print(f"\n=== LONG DOMAIN EXAMPLES ===")
            for i, doc in enumerate(long_domain_docs[:5]):  # Show first 5
                print(f"{i+1}. Document ID: {doc['id']}")
                print(f"   Domain length: {doc['domain_length']} chars")
                print(f"   Domain preview: {doc['domain_preview']}")
                print()
        
        return comma_docs, long_domain_docs
        
    except Exception as e:
        print(f"Error during scan: {e}")
        return [], []

if __name__ == "__main__":
    comma_docs, long_docs = find_all_comma_domains()
    
    if comma_docs:
        print(f"\n✅ Found {len(comma_docs)} documents that need to be fixed!")
    else:
        print(f"\n❌ No documents with comma-separated domains found.")
        print("This might indicate:")
        print("1. The data has already been cleaned")
        print("2. The data is in a different index")
        print("3. The field name is different")
