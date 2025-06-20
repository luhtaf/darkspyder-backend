#!/usr/bin/env python3
"""
Script test untuk mencari data dengan domain yang mengandung koma
"""

from es_config import es, index_name

def test_find_comma_domains():
    """Test berbagai cara mencari data dengan koma di domain"""
    
    print("Testing different search methods for comma-separated domains...")
    print(f"Using index: {index_name}")
    
    # Check total documents first
    print("\n0. Checking total documents in index")
    try:
        query = {"query": {"match_all": {}}, "size": 0}
        response = es.search(index=index_name, **query)
        total_docs = response['hits']['total']['value']
        print(f"Total documents in index: {total_docs}")
    except Exception as e:
        print(f"Error checking total docs: {e}")
    
    # Method 1: Simple match all and filter in Python (larger sample)
    print("\n1. Method 1: Match all and filter in Python (sample 1000 docs)")
    try:
        query = {
            "query": {"match_all": {}},
            "size": 1000,
            "_source": ["domain"]  # Only retrieve domain field
        }
        response = es.search(index=index_name, **query)
        
        print(f"Retrieved {len(response['hits']['hits'])} documents for analysis")
        
        comma_docs = []
        long_domain_docs = []
        
        for hit in response['hits']['hits']:
            source = hit['_source']
            if 'domain' in source:
                domain_str = str(source['domain'])
                if ',' in domain_str:
                    comma_docs.append(hit)
                if len(domain_str) > 1000:  # Check for very long domains
                    long_domain_docs.append(hit)
        
        print(f"Found {len(comma_docs)} documents with comma in domain")
        print(f"Found {len(long_domain_docs)} documents with very long domains (>1000 chars)")
        
        if comma_docs:
            # Show first example
            first_doc = comma_docs[0]
            domain_str = str(first_doc['_source']['domain'])
            print(f"\nExample comma-separated domain document:")
            print(f"Document ID: {first_doc['_id']}")
            print(f"Domain length: {len(domain_str)} characters")
            if len(domain_str) > 200:
                print(f"Domain preview: {domain_str[:200]}...")
            else:
                print(f"Domain: {domain_str}")
            
            # Count domains
            domains = [d.strip() for d in domain_str.split(',') if d.strip()]
            print(f"Number of domains in this record: {len(domains)}")
        
        if long_domain_docs:
            print(f"\nExample of long domain document:")
            long_doc = long_domain_docs[0]
            domain_str = str(long_doc['_source']['domain'])
            print(f"Document ID: {long_doc['_id']}")
            print(f"Domain length: {len(domain_str)} characters")
            print(f"Domain preview: {domain_str[:200]}...")
            domains = [d.strip() for d in domain_str.split(',') if d.strip()]
            print(f"Number of domains in this record: {len(domains)}")
            
    except Exception as e:
        print(f"Error in method 1: {e}")
    
    # Method 2: Term query for comma
    print("\n2. Method 2: Term query for comma")
    try:
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"exists": {"field": "domain"}},
                        {"term": {"domain": ","}}
                    ]
                }
            },
            "size": 10,
            "_source": ["domain"]
        }
        response = es.search(index=index_name, **query)
        print(f"Term query found {response['hits']['total']['value']} documents")
        
    except Exception as e:
        print(f"Error in method 2: {e}")
    
    # Method 3: Match phrase query
    print("\n3. Method 3: Match phrase query")
    try:
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"exists": {"field": "domain"}},
                        {"match_phrase": {"domain": ","}}
                    ]
                }
            },
            "size": 10,
            "_source": ["domain"]
        }
        response = es.search(index=index_name, **query)
        print(f"Match phrase query found {response['hits']['total']['value']} documents")
        
    except Exception as e:
        print(f"Error in method 3: {e}")

if __name__ == "__main__":
    test_find_comma_domains()
