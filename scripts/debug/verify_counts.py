import requests

BASE_URL = "http://127.0.0.1:5000/api"

def check_counts():
    print("Checking counts for poles 1-5...")
    for i in range(1, 6):
        try:
            r = requests.get(f"{BASE_URL}/posts/{i}/service-drops")
            if r.status_code == 200:
                count = r.json().get('count')
                print(f"Pole {i}: count={count}")
            else:
                print(f"Pole {i}: Error {r.status_code}")
        except Exception as e:
            print(f"Pole {i}: Exception {e}")

if __name__ == "__main__":
    check_counts()
