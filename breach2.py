from leakcheck import LeakCheckAPI_v2
import sys, json, hashlib
from es_config import update_data_into_es
from trait import ResponseSuccess

def find_data(q, type, limit=1000):
    api = LeakCheckAPI_v2(api_key='018b10e5db3fc3297993fc0ff2b52c3d15d5407f')

    # Perform a lookup
    result = api.lookup(query=q, query_type=type, limit=limit)
    return result

def formatting_data_stealer(i):
    return {
        "Data":i,
        "Source":i['source']['name'],
        "type": "breach"
    }

def main():
    argumen=sys.argv
    if len(argumen)!=1:
        q=argumen[1]
        type = argumen[2] if len(argumen) > 2 else "auto"
        datajson=find_data(q, type)
        print("Sukses Query into Source, Starting Save Data Into DB")
        for i in datajson:
            newData = formatting_data_stealer(i)
            checksum_input = json.dumps(newData, sort_keys=True)  # Sort keys to ensure consistent hashing
            newData["Checksum"] = hashlib.sha256(checksum_input.encode()).hexdigest()
            newData["threatintel"] = 'breach2'
            update_data_into_es(newData)
    else:
        print("Please Input Argumen")


def search_lcheck_stealer(q, type, limit):
    datajson = find_data(q, type, limit)
    final_data=[]
    for i in datajson:
        newData = {"_source":formatting_data_stealer(i)}
        final_data.append(newData)
    status_code=200
    return ResponseSuccess(final_data, status_code)
    
main()