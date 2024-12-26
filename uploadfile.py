
import requests

def upload_database_file():
    url = 'http://localhost:5001/update-db-stealer'
    
    # JWT token
    token = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoidWkya2pzOTAyIiwiZXhwIjoxNzM1MTczMzY3fQ.a9LykqkNz-osu1a0IaiVw0HjevCMRzKuLRPffLsgOFc'
    headers = {
        'Authorization': f"Bearer {token}"
    }
    
    # Prepare the file using database_list2.html
    files = {
        'file': ('dat2.json', open('./dat2.json', 'rb'))
    }
    
    # Send PUT request
    response = requests.post(url, headers=headers, files=files)
    
    # Print response
    print(f'Status Code: {response.status_code}')
    print(f'Response: {response.json()}')

if __name__ == '__main__':
    upload_database_file()
