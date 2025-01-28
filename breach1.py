import sys, json, hashlib
from es_config import update_data_into_es
from requests import post as token1
from init_crypt import fernet
from trait import ResponseSuccess

#used here
def find_data(q):
    data =  {"token":"763373424:EXnSh7sW", "request":q, "limit": 100, "lang":"en"}
    token = 'gAAAAABnPJw5B5RlAH3ym7MmO7pJpTmkOOoUtwPuwD3Wd8PN1N7x-oNeFuHfUrD2MP8VfCAKGh7bjrRJw26k5uAKPZIMMzVkPo1GPo4Tjy8pWWzqw3xjC7Y='
    new_token = fernet.decrypt(token.encode()).decode()
    response = token1(new_token, json=data)
    return response.json()

def formatting_data(i, datajson):
    return {
        "Data":datajson['List'][i]['Data'],
        "Source":i,
        "Info":datajson['List'][i]['InfoLeak'],
        "type": "breach"
    }

def main():
    argumen=sys.argv
    if len(argumen)!=1:
        q=argumen[1]
        datajson=find_data(q)
        print("Sukses Query into Source, Starting Save Data Into DB")
        for i in datajson['List']:
            try:
                print(f"breach -{datajson['List'][i]}\n")
                newData = formatting_data(i, datajson)
                checksum_input = json.dumps(newData, sort_keys=True)  # Sort keys to ensure consistent hashing
                newData["Checksum"] = hashlib.sha256(checksum_input.encode()).hexdigest()
                newData["threatintel"] = 'breach1'
                update_data_into_es(newData)
            except:
                print(f"error processing data:")
                print(formatting_data(i, datajson))
    else:
        print("Please Input Argumen")

# used in flask
def search_breach1(q):
    datajson = find_data(q)
    final_data=[]
    for i in datajson['List']:
        newData = {"_source":formatting_data(i, datajson)}
        final_data.append(newData)
    status_code=200
    return ResponseSuccess(final_data, status_code)

main()