import sys, json, hashlib, math
from es_config import update_data_into_es
from requests import get as token1
from init_crypt import fernet
from trait import ResponseSuccess

#used here
def find_data(q, page=1):
    header = {"Authorization": "Bearer ah2u2GZtQk3XxBioW40hSY45BbCZxR7i8XtwoI9SGCZER5eVPkOeZOzw3"}
    token = 'gAAAAABnXrR5ptbnpwn-rK0Qy2oy03eGnkh5IOU35IzkcQ52q5wOmqFhKCbEicZWSbvq2u0V8eh9N_K17t3WV7Ms0rLJro3KNG7ie8PiYeN1j-Ym7GcdlOw='
    new_token = fernet.decrypt(token.encode()).decode()
    new_token = f"{new_token}search/url?keyword={q}&page={page}"
    response = token1(new_token, headers=header)
    return response.json()
def normalized(data):
    for result in data['results']:
        result['username']=result.pop('user')
        result['domain']=result.pop('url')
    return data
def formatting_data(result):
    result['username'] = result.pop('user')
    result['domain'] = result.pop('url')
    result["type"] = "stealer"
    return result

def get_page(hasil):
    total_data = hasil['total_results']
    per_page = hasil['per_page']
    return math.floor(total_data/per_page)

def get_remaining_page(hasil, q):
    last_page = get_page(hasil)
    for i in range(2,last_page):
        datajson = find_data(q, i)
        for i in datajson['results']:
            try:
                print(f"stealer -{datajson['results']}\n")
                newData = formatting_data(i)
                checksum_input = json.dumps(newData, sort_keys=True)  # Sort keys to ensure consistent hashing
                newData["Checksum"] = hashlib.sha256(checksum_input.encode()).hexdigest()
                newData["threatintel"] = 'stealer2'
                update_data_into_es(newData)
            except:
                print(f"error processing data:")

def main():
    argumen=sys.argv
    if len(argumen)!=1:
        q=argumen[1]
        datajson=find_data(q)
        print("Sukses Query into Source, Starting Save Data Into DB")
        for i in datajson['results']:
            try:
                print(f"stealer -{i}\n")
                
                newData = formatting_data(i)
                checksum_input = json.dumps(newData, sort_keys=True)  # Sort keys to ensure consistent hashing
                newData["Checksum"] = hashlib.sha256(checksum_input.encode()).hexdigest()
                update_data_into_es(newData)
            except:
                print(f"error processing data:")
        get_remaining_page(datajson, q)
    else:
        print("Please Input Argumen")

# used in flask
def search_stealer2(q, page):
    datajson = find_data(q, page)
    final_data=[]
    for i in datajson:
        newData = {"_source":formatting_data(i)}
        final_data.append(newData)
    status_code=200
    return ResponseSuccess(final_data, status_code)

main()
