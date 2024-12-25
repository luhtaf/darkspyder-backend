
import requests

def upload_database_file():
    url = 'http://localhost:5001/update-db'
    
    # JWT token
    token = 'YOUR_JWT_TOKEN'
    headers = {
        'Authorization': token
    }
    
    # Prepare the file using database_list2.html
    files = {
        'file': ('database_list2.html', open('./database_list2.html', 'rb'))
    }
    
    # Send PUT request
    response = requests.post(url, headers=headers, files=files)
    
    # Print response
    print(f'Status Code: {response.status_code}')
    print(f'Response: {response.json()}')

if __name__ == '__main__':
    upload_database_file()
