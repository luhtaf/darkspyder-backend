from bs4 import BeautifulSoup
import json
import re

def parse_html_to_json(filename):
    # Read HTML from file
    with open(filename, 'r', encoding='utf-8') as file:
        html_content = file.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    databases = soup.find_all('div', class_='database')

    result = []

    for db in databases:
        # Get title (remove emoji)
        title = db.find('h2').text.strip()
        title = re.sub(r'[^\w\s()-.]', '', title).strip()
    
        # Get description
        description = db.find('p').text.strip()
    
        # Get stats
        stats = {}
        for span in db.find_all('span'):
            text = span.text.strip()
            key_value = re.sub(r'[^\w\s:,]', '', text).strip()
            key, value = key_value.split(':')
            stats[key.strip()] = value.strip().replace(',', '')
    
        db_entry = {
            'title': title,
            'description': description,
            'statistics': stats
        }
    
        result.append(db_entry)
    return result

def save_to_json(data, output_file='databases.json'):
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, ensure_ascii=False, indent=4, fp=f)