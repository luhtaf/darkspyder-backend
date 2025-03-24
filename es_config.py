from elasticsearch import Elasticsearch, helpers
from dotenv import load_dotenv
import os, json, hashlib, csv
from trait import ResponseError

load_dotenv()

elastic_url=os.getenv("ELASTICSEARCH_URL","https://elastic:changeme@localhost:9200")
es = Elasticsearch(elastic_url, verify_certs=False)
index_name='darkspyder'

def update_valid(id, valid):
    try:
        if valid is None:
            es.update(index=index_name, id=id, body={
                "script": {
                    "source": "ctx._source.remove('valid')"
                }
            })
            return {"status": 200, "message": "Success Delete Valid Field"}
        else:
            es.update(index=index_name, id=id, body={"doc": {"valid": valid}})
            return {"status": 200, "message": "Success Update Valid"}
    except Exception as e:
        return ResponseError(e, 500)
def update_valid_bulk(data):
    try:
        bulk_operations = []
        processed_count = 0
        skipped_count = 0
        
        for id, valid in data.items():
            if isinstance(valid, bool):
                bulk_operations.append({
                    "_op_type": "update",
                    "_index": index_name,
                    "_id": id,
                    "doc": {"valid": valid}
                })
                processed_count += 1
            else:
                skipped_count += 1        
        if bulk_operations:
            helpers.bulk(es, bulk_operations)
            
        return {
            "status": 200, 
            "message": "Success Bulk Update Valid",
            "processed": processed_count,
            "skipped": skipped_count
        }
    except Exception as e:
        return ResponseError(e, 500)

def update_data_into_es(newData):
    search_response = es.search(
            index=index_name,
            body={
                "query": {
                    "term": {"Checksum": newData["Checksum"]}
                }
            }
        )
    if search_response['hits']['total']['value'] == 0:
        response = es.index(index=index_name, body=newData)
        print(f"Document indexed with new Checksum {newData['Checksum']}: {response['_id']}")
    else:
        doc_id = search_response['hits']['hits'][0]['_id']
        update_response = es.update(index=index_name,id=doc_id,body={"doc": newData})
        print(f"Document updated with new Checksum {newData['Checksum']}: {response['_id']}")

def search_elastic(q, type_param, page, size, data, valid):
    from_value = (page - 1) * size
    query_body = {
        "query": {
            "bool": {
                "must": []
            }
        }
    }

    if valid:
        valid_bool = True if valid == 'true' else False
        query_body['query']['bool']['must'].append({
            "term": {
                "valid": valid_bool
            }
        })

    if type_param in ['stealer', 'breach']:
        query_body['query']['bool']['must'].append({
            "term": {
                "type.keyword": type_param
            }
        })

        if q:
            query_body['query']['bool']['must'].append({
                "query_string": {
                    "query": f"*{q}*",
                    "default_operator": "AND"
                }
            })
        else:
            if data['username']:
                query_body['query']["bool"]["must"].append({
                    "query_string": {
                        "query": f"{data['username']}",
                        "default_operator": "AND",
                        "fields": ["username"]
                    }
                })

            if data['domain']:
                query_body['query']["bool"]["must"].append({
                    "query_string": {
                        "query": f"{data['domain']}",
                        "default_operator": "AND",
                        "fields": ["domain"]
                    }
                })

            if data['password']:
                query_body['query']["bool"]["must"].append({
                    "query_string": {
                        "query": f"{data['password']}",
                        "default_operator": "AND",
                        "fields": ["password"]
                    }
                })

        try:
            total_count = es.count(index=index_name, body=query_body)['count']
            
            max_window_size = 10000000
            
            if size == 'all':
                if (isinstance(size, int) and size > max_window_size):
                    return {
                        "status": 400,
                        "message": f"Result size too large. Maximum allowed size is {max_window_size}. Total available results: {total_count}. Please use pagination.",
                        "total_results": total_count
                    }
                
                size = max_window_size
            
            from_value = min((page - 1) * size, max_window_size - size)
            
            query_body['sort'] = [{"valid": {"order": "desc"}}]
            result = es.search(index=index_name, body=query_body, from_=from_value, size=size)

            response = {
                "page": page,
                "size": size,
                "total": total_count,
                "current_page_data": result['hits']['hits'],
                "status": 200,
                "max_allowed_size": max_window_size
            }
            return response
            
        except Exception as e:
            print(f"Error searching documents: {e}")
            return ResponseError(f"Error searching documents: {e}", 500)
    
    

def download_elastic(q, type_param, data, valid):
    query_body = {
        "query": {
            "bool": {
                "must": []
            }
        }        
    }

    if valid:
        valid_bool = True if valid == 'true' else False
        query_body['query']['bool']['must'].append({
            "term": {
                "valid": valid_bool
            }
        })

    if type_param in ['stealer', 'breach']:
        query_body['query']['bool']['must'].append({
            "term": {
                "type.keyword": type_param
            }
        })

        if q:
            query_body['query']['bool']['must'].append({
                "query_string": {
                    "query": f"*{q}*",
                    "default_operator": "AND"
                }
            })
        else:
            if data['username']:
                query_body['query']["bool"]["must"].append({
                    "query_string": {
                        "query": f"{data['username']}",
                        "default_operator": "AND",
                        "fields" : ["username"]
                    }
                })

            if data['domain']:
                query_body['query']["bool"]["must"].append({
                    "query_string": {
                        "query": f"{data['domain']}",
                        "default_operator": "AND",
                        "fields" : ["domain"]
                    }
                })

            if data['password']:
                query_body['query']["bool"]["must"].append({
                    "query_string": {
                        "query": f"{data['password']}",
                        "default_operator": "AND",
                        "fields" : ["password"]
                    }
                })

        total_count = es.count(index=index_name, body=query_body)['count']
        query_body['sort']= [
            {
                "valid": {
                    "order": "desc"
                }
            }
        ]
        

        if type_param == 'stealer':
            result = es.search(index=index_name, body=query_body, size=total_count)
            with open('template-stealer.html', 'r', encoding='utf-8') as template_file:
                html_template = template_file.read()
            
            table_rows = ''
            for hit in result['hits']['hits']:
                source = hit['_source']
                row = f"""<tr>
                    <td>{source.get('username', '')}</td>
                    <td>{source.get('password', '')}</td>
                    <td>{source.get('domain', '')}</td>
                </tr>"""
                table_rows += row
            
            html_content = html_template.replace('{data-stealer}', table_rows)
            
            output_filename = 'stealer_output.html'
            with open(output_filename, 'w', encoding='utf-8') as output_file:
                output_file.write(html_content)
            
            return output_filename

        elif type_param == 'breach':
            result = es.search(index=index_name, body=query_body, size=total_count)
            sorted_hits = sorted(result['hits']['hits'], 
                    key=lambda x: x['_source'].get('Source', '').lower())

            with open('template.html', 'r', encoding='utf-8') as template_file:
                html_template = template_file.read()
            
            sidebar_links = ''
            card_content = ''
            counter = 1
            source_counts = {}
            
            for hit in sorted_hits:
                source = hit['_source']
                title = source.get('Source', 'Unknown Source')
                
                # Track and update source counts
                if title in source_counts:
                    source_counts[title] += 1
                    display_title = f"{title} - {source_counts[title]}"
                else:
                    source_counts[title] = 1
                    display_title = title
                
                # Add sidebar link with numbered title if needed
                sidebar_links += f'<a href="#p{counter}"><b>{display_title}</b></a>\n'
                
                # Start card content with numbered title
                card_content += f'''
                <div id='p{counter}' class='block'>
                    <div class='block-title'><b>{display_title}</b></div>
                    <div class='block-text'><br>'''
                
                if 'Info' in source:
                    card_content += f"{source['Info']}<br><br>"
                
                if 'Data' in source:
                    data = source['Data']
                    if isinstance(data, dict):
                        for field, value in data.items():
                            if isinstance(value, dict):
                                for subfield, subvalue in value.items():
                                    card_content += f"<b>{subfield}: </b> <code>{subvalue}</code><br>"
                            elif isinstance(value, list):
                                card_content += f"<b>{field}: </b> <code>{', '.join(map(str, value))}</code><br>"
                            else:
                                card_content += f"<b>{field}: </b> <code>{value}</code><br>"
                    elif isinstance(data, list):
                        # Handle list data
                        for item in data:
                            if isinstance(item, dict):
                                for field, value in item.items():
                                    card_content += f"<b>{field}: </b> <code>{value}</code><br>"
                            else:
                                card_content += f"<code>{item}</code><br>"
                            card_content += "<br>"  # Add space after each item
                
                card_content += "</div></div>\n"
                counter += 1
            
            # Replace placeholders in template
            html_content = html_template.replace('{breach-side-bar}', sidebar_links)
            html_content = html_content.replace('{breach-card}', card_content)
            
            output_filename = 'breach_output.html'
            with open(output_filename, 'w', encoding='utf-8') as output_file:
                output_file.write(html_content)
            
            return output_filename

    else:
        return ResponseError("Please Specify Type", 400)


def json_to_el_stealer(filename):
    try:
        # Open the file and process it
        with open(filename, "r") as file1:
            terbaca = file1.readlines()

        for line in terbaca:
            try:
                sub_line = line.replace("\n", "").split(":", 1)
                pisah_email = sub_line[1].split("(http", 1)
                url = f"http{pisah_email[1][:-1]}"

                newData = {
                    "username": sub_line[0],
                    "password": pisah_email[0].replace(' ', ''),
                    "domain": url,
                    "type": "stealer"
                }

                # Generate checksum for the new data
                checksum_input = json.dumps(newData, sort_keys=True)  # Sort keys to ensure consistent hashing
                newData["Checksum"] = hashlib.sha256(checksum_input.encode()).hexdigest()
                newData["threatintel"] = 'stealer1'

                # Search for an existing document with the same checksum
                search_response = es.search(
                    index=index_name,
                    body={
                        "query": {
                            "term": {"Checksum": newData["Checksum"]}
                        }
                    }
                )

                # If a document exists with the same checksum, update it
                if search_response['hits']['total']['value'] == 0:
                    response = es.index(index=index_name, body=newData)
                    print(f"Document indexed with new Checksum {newData['Checksum']}: {response['_id']}")
                else:
                    pass
                    # doc_id = search_response['hits']['hits'][0]['_id']
                    # update_response = es.update(index=index_name,id=doc_id,body={"doc": newData})
                    # print(f"Document updated with new Checksum {newData['Checksum']}: {update_response['_id']}")
            except Exception as inner_e:
                # Handle errors for the current line and continue
                print(f"Error processing line: {line}. Error: {inner_e}")

        print(f"File {filename} processed and deleted successfully.")

    except Exception as e:
        print(f"Error processing file: {e}")
    finally:
        os.remove(filename)