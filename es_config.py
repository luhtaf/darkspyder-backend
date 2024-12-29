from elasticsearch import Elasticsearch, helpers
from dotenv import load_dotenv
import os, json, hashlib
from trait import ResponseError
load_dotenv()

elastic_url=os.getenv("ELASTICSEARCH_URL","https://elastic:changeme@localhost:9200")
es = Elasticsearch(elastic_url, verify_certs=False)
index_name='darkspyder'

def update_valid(id,valid):
    try:
        es.update(index=index_name,id=id,body={"doc":{"valid":valid}})
        return {"status":200,"msg":"Success Update Valid"}
    except Exception as e:
        return ResponseError(e,500)

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
            "msg": "Success Bulk Update Valid",
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
    print(valid)
    if valid:
        # set valid to new variable, now it is string of true and false, make new variable is boolean 
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
                    "query": f"{q}",
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
        print(query_body)

        total_count = es.count(index=index_name, body=query_body)['count']

        result = es.search(index=index_name, body=query_body, from_=from_value, size=size)
        
        response = {
                "page": page,
                "size": size,
                "total": total_count, 
                "current_page_data": result['hits']['hits'],
                "status": 200
            }
        return response
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
                    doc_id = search_response['hits']['hits'][0]['_id']
                    update_response = es.update(index=index_name,id=doc_id,body={"doc": newData})
                    print(f"Document updated with new Checksum {newData['Checksum']}: {update_response['_id']}")
            except Exception as inner_e:
                # Handle errors for the current line and continue
                print(f"Error processing line: {line}. Error: {inner_e}")

        print(f"File {filename} processed and deleted successfully.")

    except Exception as e:
        print(f"Error processing file: {e}")
    finally:
        os.remove(filename)