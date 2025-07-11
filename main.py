import time
from api_module import BrewingSystemAPI
from pid_controller import PIDArduino
from temp_sensor import read_temp
from gpio_control import setup_gpio, control_heater
from logging_module import log_temperature
from requests.exceptions import HTTPError
import RPi.GPIO as GPIO
import datetime

# Constants
HEATER_PIN = 17
SAMPLE_TIME = 5
P = 100.0
I = 0.1
D = 1.0
MAX_OUTPUT = 100

base_url = "https://brew-server.onrender.com"
# base_url = "localhost:3000"
communication_interval = 5000
secret_key = "9f70e543-568b-4564-956e-a06d401606c8"
brew_id = "3"
brewery_id = "24"
device_serial_number = "brew_id"
# Initialize API client
api = BrewingSystemAPI(base_url, brew_id, secret_key)

consecutive_401_count = 0  # Initialize the 401 counter


def convert_recipe_to_steps(recipe):
    steps = []

    # Mash step
    mash_temp = recipe.get("mashTempC")
    mash_time = recipe.get("mashTimeMin")
    if mash_temp is not None and mash_time is not None:
        steps.append({
            "temperature_celsius": mash_temp,
            "duration_minutes": mash_time,
            "approval_required": False
        })

    # Boil step
    boil_time = recipe.get("boilTimeMin")
    if boil_time is not None:
        steps.append({
            "temperature_celsius": 95,  # Boiling temp
            "duration_minutes": boil_time,
            "approval_required": False
        })

    return {"step": steps}


def check_and_terminate_brew(report_response):
    """
    Checks the brew status and terminates the brewing process if it has ended.
    """
    if isinstance(report_response, dict):
        brew_status = report_response.get("brew_status")
        if brew_status == "ended":
            print("[INFO] Brew status is 'ended'. Terminating brewing process.")
            setup_gpio(HEATER_PIN)
            control_heater(HEATER_PIN, 0)
            GPIO.cleanup()
            exit(0)


def handle_report_response_status(report_response, device_serial_number, brewing_report, goal_temp_c, pid, step_number):
    global consecutive_401_count  # Ensure we can modify this variable globally

    # Extract status code if report_response is a dictionary, otherwise use the number directly
    if isinstance(report_response, dict):
        status_code = report_response.get('status_code', None)
        error_message = report_response.get('error_message', '')
    else:
        status_code = report_response
        error_message = ''

    if status_code == 401:
        # Increment the 401 counter
        consecutive_401_count += 1
        print(f"[WARNING] Received status 401: Attempt {consecutive_401_count}/5.")

        if error_message:
            print(f"[INFO] Error message: {error_message}")

        # If 401 has been received 5 times in a row, stop the brewing process
        if consecutive_401_count >= 5:
            print("[ERROR] Received status 401 for 5 consecutive times: Stopping the brewing process.")
            raise Exception("Brewing process has been stopped due to receiving 401 status 5 times consecutively.")

    elif status_code == 202:
        # Keep sending reports until a 100 status is received
        print("[INFO] Received status 202: Continue sending reports until receiving status 100.")
        while True:
            try:
                current_temp_c, _ = read_temp()
                pid_output = pid.calc(current_temp_c, goal_temp_c)
                control_heater(HEATER_PIN, pid_output)

                print(f"Maintaining: Current temperature: {current_temp_c}ֲ°C")
                print(f"Heater output: {pid_output}%")

                # Send the brewing report again and get the new response
                new_report_response = api.add_brewing_report(brew_id, brewery_id, current_temp_c)
                check_and_terminate_brew(new_report_response)
                print(f"Waiting for approval step number: {step_number}")
                print(f"New report response: {new_report_response}")

                # Extract status code from the new report response
                if isinstance(new_report_response, dict):
                    new_status_code = new_report_response.get('status_code', None)
                else:
                    new_status_code = new_report_response

                # Break the loop when 100 is received, indicating we can proceed
                if new_status_code == 100:
                    print("[INFO] Received status 100: Proceeding with the brewing process.")
                    break

                # If the new response is 401, handle it
                elif new_status_code == 401:
                    consecutive_401_count += 1
                    print(
                        f"[WARNING] Received status 401 during report resubmission: Attempt {consecutive_401_count}/5.")

                    if error_message:
                        print(f"[INFO] Error message: {error_message}")

                    # If 401 has been received 5 times in a row, stop the brewing process
                    if consecutive_401_count >= 5:
                        print(
                            "[ERROR] Received status 401 for 5 consecutive times during resubmission: Stopping the brewing process.")
                        raise Exception(
                            "Brewing process stopped due to 401 status received 5 times during resubmission.")

            except Exception as e:
                print(f"[ERROR] Error during report resubmission: {e}")
                raise

            # Sleep for a few seconds before resending the report to avoid overwhelming the server
            time.sleep(3)

    elif status_code == 100:
        # Status 100 means everything is fine, continue brewing
        print("[INFO] Received status 100: Continuing brewing process.")

    else:
        # Handle unexpected status codes
        print(f"[WARNING] Unexpected status code received: {status_code}. Proceed with caution.")


def main():
    try:
        # Fetch the recipe
        try:
            recipe_response = api.get_recipe_to_brew()
        except HTTPError as e:
            print(f"[ERROR] Failed to fetch recipe: {e}")
            return

        if recipe_response is None:
            print("[ERROR] Recipe is None. Exiting.")
            return
        else:
            print(f"Recipe received: {recipe_response}")

        original_recipe_id = recipe_response.get("recipe_id")
        original_recipe_snapshot = recipe_response.get("recipe_snapshot")

        if not original_recipe_id or not original_recipe_snapshot:
            print("[ERROR] Missing recipe_id or recipe_snapshot in the response. Exiting.")
            return

        # Convert recipe format for embedded steps
        converted_recipe = convert_recipe_to_steps(original_recipe_snapshot)

        if not converted_recipe["step"]:
            print("[ERROR] Converted recipe has no steps. Exiting.")
            return

        recipe = converted_recipe  # Now use converted_recipe for the rest of the process

        # Ensure that 'step' exists and is a list
        if 'step' not in recipe or not isinstance(recipe['step'], list) or len(recipe['step']) == 0:
            print("[ERROR] No valid steps found in the recipe. Exiting.")
            return

        # Start brewing communication
        try:
            start_brewing_response = api.start_brewing(
                brew_id=brew_id,
                secret_key=secret_key
            )

            print(f"Server start brewing response: {start_brewing_response}")
            print("Running Brewing Module\n")
        except Exception as e:
            print(f"[ERROR] Failed to start brewing process to server: {e}")
            return

        # Setup GPIO for the heater
        try:
            setup_gpio(HEATER_PIN)
            print("Heater GPIO setup is successful.")
        except Exception as e:
            print(f"[ERROR] Failed to setup GPIO: {e}")
            return

        pid = PIDArduino(SAMPLE_TIME, P, I, D, 0, MAX_OUTPUT)

        print("Starting Brewing steps...")
        for step_index, step in enumerate(recipe['step']):
            try:
                # Validate step structure
                if 'temperature_celsius' not in step or 'duration_minutes' not in step:
                    print(f"[ERROR] Step {step_index + 1} is missing required fields.")
                    continue

                goal_temp_c = step['temperature_celsius']
                duration_minutes = step['duration_minutes']
                approval_required = step.get('approval_required', False)
                step_start_time = int(time.time() * 1000)  # Start time in milliseconds

                print(f"Starting heating phase to reach target temperature: {goal_temp_c}ֲ°C")

                step_type = "mash" if step_index == 0 else "boil"
                status_field_prefix = f"{step_type}_status"

                # Heating phase: reach target temperature
                while True:
                    current_temp_c, _ = read_temp()
                    print(f"Current temperature: {current_temp_c}ֲ°C, Target temperature: {goal_temp_c}ֲ°C")

                    if current_temp_c >= goal_temp_c:
                        print("Target temperature reached. Proceeding to maintain temperature.")
                        api.update_step_status(f"{step_type}_status", "started")
                        break

                    pid_output = pid.calc(current_temp_c, goal_temp_c)
                    control_heater(HEATER_PIN, pid_output)
                    print(f"Heater output: {pid_output}% \n")

                    # Call the new function to create the brewing report
                    # brewing_report = create_temperature_report(recipe, current_temp_c)
                    # brewing_report = {brew_id: brew_id, temperature_celsius: current_temp_c}
                    report_response = api.add_brewing_report(brew_id, brewery_id, current_temp_c)
                    check_and_terminate_brew(report_response)
                    # handle_report_response_status(report_response, device_serial_number, brewing_report, goal_temp_c, pid, (step_index + 1))

                    time.sleep(5)

                # Maintaining temperature for the set duration
                print(f"Maintaining temperature at {goal_temp_c}ֲ°C for {duration_minutes} minutes.")
                end_time = time.time() + ((duration_minutes) * 60)

                while time.time() < end_time:
                    current_temp_c, _ = read_temp()
                    pid_output = pid.calc(current_temp_c, goal_temp_c)
                    control_heater(HEATER_PIN, pid_output)

                    # Calculate remaining time
                    remaining_time_sec = end_time - time.time()
                    remaining_minutes = int(remaining_time_sec // 60)
                    remaining_seconds = int(remaining_time_sec % 60)

                    log_temperature(current_temp_c, goal_temp_c)

                    print(f"Maintaining: Current temperature: {current_temp_c}ֲ°C")
                    print(f"Heater output: {pid_output}%")
                    print(f"Time remaining: {remaining_minutes} minutes {remaining_seconds} seconds.\n")

                    # Call the new function to create the brewing report
                    # brewing_report = {brew_id: brew_id, brewery_id: brewery_id, temperature_celsius: current_temp_c}
                    # report_response = api.add_brewing_report(device_serial_number, brewing_report)
                    report_response = api.add_brewing_report(brew_id, brewery_id, current_temp_c)
                    check_and_terminate_brew(report_response)
                    # handle_report_response_status(report_response, device_serial_number, brewing_report, goal_temp_c, pid, (step_index + 1))

                    time.sleep(5)

                # Step is completed, send the appropriate response
                if approval_required:
                    report_status = 205
                    print(f"Approval required for step {step_index + 1}. Sending status 205.")
                else:
                    report_status = 202
                    print(f"No approval required for step {step_index + 1}. Sending status 202.")

                # Call the function to create the final brewing report for the step completion
                # brewing_report = create_brewing_report(recipe, step_index, step, current_temp_c, step_start_time, report_status)
                # report_response = api.add_brewing_report(device_serial_number, brewing_report)
                report_response = api.add_brewing_report(brew_id, brewery_id, current_temp_c)
                check_and_terminate_brew(report_response)
                # print(f"Brewing Report: {brewing_report}")
                print(f"Report Response: {report_response}")
                # handle_report_response_status(report_response, device_serial_number, brewing_report, goal_temp_c, pid, (step_index + 1))

                print(
                    f"Step {step_index + 1} completed. Temperature was maintained at {goal_temp_c}ֲ°C for {duration_minutes} minutes.")
                api.update_step_status(f"{step_type}_status", "ended")
            except Exception as e:
                print(f"[ERROR] Error during brewing step {step_index + 1}: {e}")
                break

        # Mark brewing as finished
        try:
            print("Marking brewing as finished...")
            api.update_step_status("brew_status", "ended")
            api.mark_brewing_as_finished(brew_id)
            print("Brewing process marked as finished.")
        except HTTPError as e:
            print(f"[ERROR] Failed to mark brewing as finished: {e}")

    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")

    finally:
        # Cleanup GPIO to ensure heater is turned off
        try:
            GPIO.setmode(GPIO.BCM)  # Ensure pin mode is set before cleanup
            control_heater(HEATER_PIN, 0)  # Ensure the heater is turned off
            print("[INFO] Heater turned off.")
        except Exception as e:
            print(f"[WARNING] Failed to turn off heater properly: {e}")
        finally:
            setup_gpio(HEATER_PIN)
            GPIO.cleanup()
            print("GPIO cleanup completed.")

        try:
            print("Marking Brew As Complete:")
            complete_response = api.mark_brewing_as_finished(brew_id)
            print(f"Mark response: {complete_response}.")
        except Exception as e:
            print(f"[ERROR] Failed to mark brewing as complete: {e}")


if __name__ == "__main__":
    main()
    # Cleanup GPIO to ensure heater is turned off
    setup_gpio(HEATER_PIN)
    control_heater(HEATER_PIN, 0)  # Ensure the heater is turned off
    GPIO.cleanup()
    print("GPIO cleanup completed, heater turned off.")

