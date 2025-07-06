import requests, time
def background_task(token, paymentId):
    total_minutes = 10
    interval_seconds = 60

    for i in range(total_minutes):
        try:
            headers = {"Authorization": token}
            data = {
                "paymentId": paymentId
            }
            response = requests.post("http://127.0.0.1:5000/cek", headers=headers, json=data)
            if response.json().Status!=0:
                break
            print(f"[Background] Called /cek with token, response: {response.status_code}")
        except Exception as e:
            print(f"[Background] Error calling /cek: {e}")

        if i < total_minutes - 1:
            time.sleep(interval_seconds)