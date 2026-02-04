from leakcheck import LeakCheckAPI_v2
import sys, json, hashlib
from es_config import update_data_into_es
from trait import ResponseSuccess

def find_data(q, type, limit=1000):
    api = LeakCheckAPI_v2(api_key='018b10e5db3fc3297993fc0ff2b52c3d15d5407f')

    # Perform a lookup
    result = api.lookup(query=q, query_type=type, limit=limit)
    return result

def formatting_data_breach(i):
    return {
        "Data":i,
        "Source":i['source']['name'],
        "type": "breach"
    }

def formatting_data_stealer(data):
    # Set username based on available fields
    if "username" in data:
        username = data["username"]
    elif "email" in data:
        username = data["email"]
    else:
        username = ""
    
    # Convert origin array to comma-separated string
    if "origin" in data and isinstance(data["origin"], list):
        domain = ", ".join(data["origin"])
    elif "origin" in data:
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

def main():
    argumen=sys.argv
    if len(argumen)!=1:
        q=argumen[1]
        type = argumen[2] if len(argumen) > 2 else "auto"
        datajson=find_data(q, type)
        print("Sukses Query into Source, Starting Save Data Into DB")
        for i in datajson:
            if type == "origin":
                # Check if origin is an array and iterate through each domain
                if "origin" in i and isinstance(i["origin"], list):
                    for domain in i["origin"]:
                        # Create a copy of the data with single domain
                        single_domain_data = i.copy()
                        single_domain_data["origin"] = domain
                        newData = formatting_data_stealer(single_domain_data)
                        threat_intel = "stealer3"
                        checksum_input = json.dumps(newData, sort_keys=True)  # Sort keys to ensure consistent hashing
                        newData["Checksum"] = hashlib.sha256(checksum_input.encode()).hexdigest()
                        newData["threatintel"] = threat_intel
                        update_data_into_es(newData)
                else:
                    # Handle single domain or no domain case
                    newData = formatting_data_stealer(i)
                    threat_intel = "stealer3"
                    checksum_input = json.dumps(newData, sort_keys=True)  # Sort keys to ensure consistent hashing
                    newData["Checksum"] = hashlib.sha256(checksum_input.encode()).hexdigest()
                    newData["threatintel"] = threat_intel
                    update_data_into_es(newData)
            else:
                newData = formatting_data_breach(i)
                threat_intel = "breach2"
                checksum_input = json.dumps(newData, sort_keys=True)  # Sort keys to ensure consistent hashing
                newData["Checksum"] = hashlib.sha256(checksum_input.encode()).hexdigest()
                newData["threatintel"] = threat_intel
                update_data_into_es(newData)
    else:
        print("Please Input Argumen")


def search_lcheck_stealer(q, type, limit):
    datajson = find_data(q, type, limit)
    final_data=[]
    for i in datajson:
        if type=="origin":
            source=formatting_data_stealer(i)
        else:
            source=formatting_data_breach(i)
        newData = {"_source":source}
        final_data.append(newData)
    status_code=200
    return ResponseSuccess(final_data, status_code)
    
if __name__ == "__main__":
    main()