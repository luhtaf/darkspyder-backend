#!/usr/bin/env python3
"""
Script untuk mengecek apakah masih ada domain yang panjang setelah cleanup
"""

from es_config import es, index_name

def check_long_domains(min_length=1000, show_examples=5):
    """
    Cek apakah masih ada domain yang panjang
    
    Args:
        min_length (int): Minimum panjang domain yang dianggap 'panjang' (default: 1000)
        show_examples (int): Jumlah contoh yang ditampilkan (default: 5)
    
    Returns:
        dict: Hasil pengecekan dengan statistik dan contoh
    """
    
    print(f"🔍 Checking for domains longer than {min_length} characters...")
    print(f"Index: {index_name}")
    
    # Query sederhana untuk mendapatkan semua dokumen dengan domain
    query = {
        "query": {"exists": {"field": "domain"}},
        "_source": ["domain"],
        "size": 1000
    }
    
    try:
        # Start scroll untuk mendapatkan semua hasil
        response = es.search(index=index_name, scroll='2m', **query)
        scroll_id = response['_scroll_id']
        
        long_domains = []
        processed = 0
        
        print("Scanning documents...")
        
        while True:
            hits = response['hits']['hits']
            if not hits:
                break
                
            for hit in hits:
                processed += 1
                if processed % 10000 == 0:
                    print(f"Processed {processed} documents...")
                
                source = hit['_source']
                if 'domain' in source:
                    domain_str = str(source['domain'])
                    if len(domain_str) > min_length:
                        long_domains.append({
                            'id': hit['_id'],
                            'domain_length': len(domain_str),
                            'domain_preview': domain_str[:200] + "..." if len(domain_str) > 200 else domain_str,
                            'domain_full': domain_str
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
        
        print(f"Scan complete. Processed {processed} documents total.")
        
        # Hasil
        result = {
            'total_long_domains': len(long_domains),
            'min_length_checked': min_length,
            'examples': long_domains[:show_examples] if long_domains else [],
            'all_long_domains': long_domains
        }
        
        # Print hasil
        print(f"\n{'='*50}")
        print(f"📊 HASIL PENGECEKAN DOMAIN PANJANG")
        print(f"{'='*50}")
        print(f"Minimum panjang yang dicek: {min_length} karakter")
        print(f"Total domain panjang ditemukan: {len(long_domains)}")
        
        if long_domains:
            print(f"\n❌ MASIH ADA {len(long_domains)} DOMAIN YANG TERLALU PANJANG!")
            
            if show_examples > 0:
                print(f"\n📋 CONTOH DOMAIN PANJANG (menampilkan {min(show_examples, len(long_domains))} dari {len(long_domains)}):")
                for i, doc in enumerate(long_domains[:show_examples]):
                    print(f"\n{i+1}. Document ID: {doc['id']}")
                    print(f"   Panjang domain: {doc['domain_length']} karakter")
                    print(f"   Preview: {doc['domain_preview']}")
            
            # Statistik tambahan
            lengths = [doc['domain_length'] for doc in long_domains]
            print(f"\n📈 STATISTIK PANJANG DOMAIN:")
            print(f"   - Terpendek: {min(lengths)} karakter")
            print(f"   - Terpanjang: {max(lengths)} karakter")
            print(f"   - Rata-rata: {sum(lengths)/len(lengths):.1f} karakter")
            
            # Kategorisasi berdasarkan panjang
            categories = {
                'Sangat Panjang (>5000)': len([l for l in lengths if l > 5000]),
                'Panjang (2000-5000)': len([l for l in lengths if 2000 <= l <= 5000]),
                'Sedang (1000-2000)': len([l for l in lengths if 1000 <= l < 2000])
            }
            
            print(f"\n📊 KATEGORI BERDASARKAN PANJANG:")
            for category, count in categories.items():
                if count > 0:
                    print(f"   - {category}: {count} domain")
        else:
            print(f"\n✅ BAGUS! TIDAK ADA DOMAIN YANG LEBIH PANJANG DARI {min_length} KARAKTER")
            print("   Semua domain sudah dalam batas normal.")
        
        return result
        
    except Exception as e:
        print(f"❌ Error saat pengecekan: {e}")
        return {
            'error': str(e),
            'total_long_domains': 0,
            'min_length_checked': min_length,
            'examples': [],
            'all_long_domains': []
        }

def check_comma_domains(show_examples=5):
    """
    Cek apakah masih ada domain yang mengandung koma
    
    Args:
        show_examples (int): Jumlah contoh yang ditampilkan (default: 5)
    
    Returns:
        dict: Hasil pengecekan dengan statistik dan contoh
    """
    
    print(f"🔍 Checking for domains containing commas...")
    print(f"Index: {index_name}")
    
    # Query untuk mencari domain dengan koma
    query = {
        "query": {
            "bool": {
                "must": [
                    {"exists": {"field": "domain"}},
                    {"wildcard": {"domain": "*,*"}}
                ]
            }
        },
        "_source": ["domain"],
        "size": 1000
    }
    
    try:
        # Start scroll
        response = es.search(index=index_name, scroll='2m', **query)
        scroll_id = response['_scroll_id']
        
        comma_domains = []
        processed = 0
        
        while True:
            hits = response['hits']['hits']
            if not hits:
                break
                
            for hit in hits:
                processed += 1
                source = hit['_source']
                if 'domain' in source:
                    domain_str = str(source['domain'])
                    if ',' in domain_str:
                        domain_count = len([d.strip() for d in domain_str.split(',') if d.strip()])
                        comma_domains.append({
                            'id': hit['_id'],
                            'domain_count': domain_count,
                            'domain_preview': domain_str[:200] + "..." if len(domain_str) > 200 else domain_str,
                            'domain_full': domain_str
                        })
            
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
        
        # Hasil
        result = {
            'total_comma_domains': len(comma_domains),
            'examples': comma_domains[:show_examples] if comma_domains else [],
            'all_comma_domains': comma_domains
        }
        
        # Print hasil
        print(f"\n{'='*50}")
        print(f"📊 HASIL PENGECEKAN DOMAIN DENGAN KOMA")
        print(f"{'='*50}")
        print(f"Total domain dengan koma ditemukan: {len(comma_domains)}")
        
        if comma_domains:
            print(f"\n❌ MASIH ADA {len(comma_domains)} DOMAIN YANG MENGANDUNG KOMA!")
            
            if show_examples > 0:
                print(f"\n📋 CONTOH DOMAIN DENGAN KOMA (menampilkan {min(show_examples, len(comma_domains))} dari {len(comma_domains)}):")
                for i, doc in enumerate(comma_domains[:show_examples]):
                    print(f"\n{i+1}. Document ID: {doc['id']}")
                    print(f"   Jumlah domain: {doc['domain_count']}")
                    print(f"   Preview: {doc['domain_preview']}")
            
            # Statistik tambahan
            domain_counts = [doc['domain_count'] for doc in comma_domains]
            print(f"\n📈 STATISTIK JUMLAH DOMAIN PER DOKUMEN:")
            print(f"   - Minimum: {min(domain_counts)} domain")
            print(f"   - Maksimum: {max(domain_counts)} domain")
            print(f"   - Rata-rata: {sum(domain_counts)/len(domain_counts):.1f} domain")
        else:
            print(f"\n✅ BAGUS! TIDAK ADA DOMAIN YANG MENGANDUNG KOMA")
            print("   Semua domain sudah bersih dari koma.")
        
        return result
        
    except Exception as e:
        print(f"❌ Error saat pengecekan: {e}")
        return {
            'error': str(e),
            'total_comma_domains': 0,
            'examples': [],
            'all_comma_domains': []
        }

def comprehensive_domain_check(min_length=1000, show_examples=5):
    """
    Pengecekan komprehensif untuk domain bermasalah
    
    Args:
        min_length (int): Minimum panjang domain yang dianggap 'panjang'
        show_examples (int): Jumlah contoh yang ditampilkan
    
    Returns:
        dict: Hasil pengecekan lengkap
    """
    
    print(f"🚀 MEMULAI PENGECEKAN KOMPREHENSIF DOMAIN")
    print(f"{'='*60}")
    
    # Cek domain panjang
    print(f"\n1️⃣ PENGECEKAN DOMAIN PANJANG")
    long_result = check_long_domains(min_length, show_examples)
    
    print(f"\n" + "="*60)
    
    # Cek domain dengan koma
    print(f"\n2️⃣ PENGECEKAN DOMAIN DENGAN KOMA")
    comma_result = check_comma_domains(show_examples)
    
    # Ringkasan
    print(f"\n" + "="*60)
    print(f"📋 RINGKASAN PENGECEKAN")
    print(f"{'='*60}")
    
    total_issues = long_result.get('total_long_domains', 0) + comma_result.get('total_comma_domains', 0)
    
    if total_issues == 0:
        print(f"✅ SELAMAT! TIDAK ADA MASALAH DOMAIN YANG DITEMUKAN")
        print(f"   - Domain panjang (>{min_length} chars): 0")
        print(f"   - Domain dengan koma: 0")
        print(f"   - Total dokumen bermasalah: 0")
    else:
        print(f"❌ DITEMUKAN {total_issues} DOKUMEN DENGAN MASALAH DOMAIN:")
        print(f"   - Domain panjang (>{min_length} chars): {long_result.get('total_long_domains', 0)}")
        print(f"   - Domain dengan koma: {comma_result.get('total_comma_domains', 0)}")
        print(f"   - Total dokumen bermasalah: {total_issues}")
        
        print(f"\n💡 REKOMENDASI:")
        if long_result.get('total_long_domains', 0) > 0:
            print(f"   - Jalankan script cleanup untuk domain panjang")
        if comma_result.get('total_comma_domains', 0) > 0:
            print(f"   - Jalankan script cleanup untuk domain dengan koma")
    
    return {
        'long_domains': long_result,
        'comma_domains': comma_result,
        'total_issues': total_issues,
        'summary': {
            'long_domains_count': long_result.get('total_long_domains', 0),
            'comma_domains_count': comma_result.get('total_comma_domains', 0),
            'total_problematic_docs': total_issues
        }
    }

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'long':
            # Hanya cek domain panjang
            min_len = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
            check_long_domains(min_len)
        elif command == 'comma':
            # Hanya cek domain dengan koma
            check_comma_domains()
        elif command == 'all':
            # Cek semua
            min_len = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
            comprehensive_domain_check(min_len)
        else:
            print("Usage:")
            print("  python check_long_domains.py long [min_length]    - Cek domain panjang")
            print("  python check_long_domains.py comma                - Cek domain dengan koma")
            print("  python check_long_domains.py all [min_length]     - Cek semua masalah")
    else:
        # Default: cek semua
        comprehensive_domain_check()
