import requests
import time
import datetime

class BrewingSystemAPI:
    def __init__(self, base_url, brew_id, secret_key):
        self.base_url = base_url
        self.brew_id = brew_id
        self.secret_key = secret_key


    def get_recipe_to_brew(self):
        url = f"{self.base_url}/brews/connect"
        payload = {"brew_id": self.brew_id, "secret_key": self.secret_key}
        print(f"Connecting to brew session with brew_id: {self.brew_id}")
        max_retries = 50
        retry_delay = 10  # seconds

        print(f"Preparing to fetch recipe from URL: {url}")
        for attempt in range(max_retries):
            print(f"Attempt {attempt + 1} of {max_retries}...")
            try:
                response = requests.post(url,json=payload)
                print(f"Response received: {response}")
                response.raise_for_status()
                print("Recipe data fetched successfully.")
                return response.json()
            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt + 1} failed with error: {e}")
                if attempt < max_retries - 1:
                    print(f"Next attempt in {retry_delay} seconds...")
                    for remaining in range(retry_delay, 0, -1):
                        print(f"Retrying in {remaining} seconds...", end="\r")
                        time.sleep(1)
                else:
                    print(f"All {max_retries} attempts failed. Raising the exception.")
                    raise

    def start_brewing(self, brew_id, secret_key):
        url = f"{self.base_url}/brews/embedded_start"
        payload = {
            "brew_id": brew_id,
            "secret_key": secret_key,
        }

        max_retries = 10
        print(f"Preparing to start brewing at URL: {url}")
        for attempt in range(max_retries):
            print(f"Attempt {attempt + 1} of {max_retries}...")
            try:
                response = requests.post(url, json=payload)
                print(f"Response received: {response.status_code}")
                response.raise_for_status()
                print("Brewing process started successfully.")
                return response.json()
            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt + 1} failed with error: {e}")
                if attempt < max_retries - 1:
                    print("Retrying in 10 seconds...")
                    time.sleep(10)
                else:
                    print("All attempts to start brewing failed. Raising the exception.")
                    raise


    def mark_brewing_as_finished(self, brew_id):
        url = f"{self.base_url}/brews/end"
        payload = {"brew_id": brew_id}
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload)
                response.raise_for_status()
                print("Brewing marked as finished.")
                return response.json()
            except requests.exceptions.RequestException as e:
                print(f"Error marking brewing as finished: {e}")
                if attempt < max_retries - 1:
                    print("Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    print("Failed to mark brewing as finished after multiple attempts.")
                    raise


    def add_brewing_report(self, brew_id, brewery_id, temperature_celsius):
        url = f"{self.base_url}/brews/temperature"
        payload = {
            "brew_id": brew_id,
            "brewery_id": brewery_id,
            "temperature_celsius": temperature_celsius,
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return {
                "status_code": response.status_code,
                "brew_status": data.get("brew_status"),  # <-- Capture brew_status
                "message": data.get("message")
            }
        except requests.exceptions.HTTPError as http_err:
            print(f"[HTTP ERROR] {http_err}")
            return {
                "status_code": response.status_code,
                "error_message": str(http_err)
            }
        except Exception as err:
            print(f"[ERROR] {err}")
            return {
                "status_code": 500,
                "error_message": str(err)
            }

    def add_fermentation_report(self, device_serial_number, fermentation_report):
        url = f"{self.base_url}/{device_serial_number}/report/fermentation"
        try:
            response = requests.post(url, json=fermentation_report)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f"[HTTP ERROR] {http_err}")
            return {
                "status_code": response.status_code,
                "error_message": str(http_err)
            }
        except Exception as err:
            print(f"[ERROR] {err}")
            return {
                "status_code": 500,
                "error_message": str(err)
            }

    def update_step_status(self, status_field, status_value):
        url = f"{self.base_url}/brews/update_step_status"
        payload = {
            "brew_id": self.brew_id,
            "secret_key": self.secret_key,
            "status_field": status_field,
            "status_value": status_value,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            print(f"Step status update successful: {status_field} = {status_value}")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to update step status: {e}")
            return None



# Helper function

def create_temperature_report(recipe, temperature_celsius):
    """
    Create a minimal temperature report payload for logging.

    Args:
        recipe (dict): Must include 'brew_id', 'brewery_id', and 'user_id'.
        temperature_celsius (float): Current temperature in Celsius.

    Returns:
        dict: Payload for logging temperature.
    """
    return {
        "brew_id": recipe.get("brew_id"),
        "brewery_id": recipe.get("brewery_id"),
        "temperature_celsius": temperature_celsius,
    }


