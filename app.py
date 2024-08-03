import tkinter as tk
from tkinter import messagebox, ttk
import RPi.GPIO as GPIO
import json
import uuid
import requests
import cv2
from pyzbar.pyzbar import decode
from PIL import Image
import os
import sys

# Global variables
FLOW_SENSOR_GPIO_1 = 22
FLOW_SENSOR_GPIO_2 = 23
count = 0
flow_rate_factor_1 = 2.25
flow_rate_factor_2 = 2.5
input_data = {
    "inputs": [],
    "batchId": str(uuid.uuid4()),
    "devicecode": "device-123"
}
output_data = {}

def update_display():
    global count
    liters = count * flow_rate_factor_1 / 1000.0
    counter_label.config(text=f"{liters:07.2f}")

def countPulse(channel):
    global count
    count += 1
    update_display()

def scan_qr_code():
    video_capture = cv2.VideoCapture(0)
    wallet_address = None

    while not video_capture.isOpened():
        print("Cannot open camera")
        cv2.waitKey(1000)
        video_capture = cv2.VideoCapture(0)

    while True:
        result, video_frame = video_capture.read()
        if not result:
            print("Failed to grab frame")
            break

        pil_image = Image.fromarray(cv2.cvtColor(video_frame, cv2.COLOR_BGR2RGB))
        barcodes = decode(pil_image)

        for barcode in barcodes:
            (x, y, w, h) = barcode.rect
            cv2.rectangle(video_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

            barcode_data = barcode.data.decode("utf-8")
            wallet_address = barcode_data
            cv2.putText(video_frame, barcode_data, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            print("This is the barcode content: ", barcode_data)
        
        cv2.imshow("USB Camera Test", video_frame)

        if wallet_address or cv2.waitKey(1) & 0xFF == ord("q"):
            break

    video_capture.release()
    cv2.destroyAllWindows()
    return wallet_address

def add_entry():
    global count
    liters = count * flow_rate_factor_1 / 1000.0
    wallet_address = scan_qr_code()
    if wallet_address:
        entry = {"input": liters, "walletAddress": wallet_address}
        input_data["inputs"].append(entry)
        tree.insert("", "end", values=(len(input_data["inputs"]), liters, wallet_address))
        count = 0
        update_display()
    else:
        messagebox.showerror("Error", "QR code scan failed")

def start_counting():
    global count
    count = 0
    GPIO.add_event_detect(FLOW_SENSOR_GPIO_1, GPIO.RISING, callback=countPulse)
    start_button.config(state=tk.DISABLED)
    stop_button.config(state=tk.NORMAL)

def stop_counting():
    GPIO.remove_event_detect(FLOW_SENSOR_GPIO_1)
    start_button.config(state=tk.NORMAL)
    stop_button.config(state=tk.DISABLED)

def save_data():
    with open(f'input_data_{input_data["batchId"]}.json', 'w') as f:
        json.dump(input_data, f)

def confirm_end():
    result = messagebox.askyesno("Confirmation", "Are you sure about the values?")
    if result:
        save_data()
        open_output_screen()
    else:
        messagebox.showinfo("Cancelled", "Operation cancelled")

def open_output_screen():
    global count
    count = 0
    for widget in root.winfo_children():
        widget.destroy()
    
    def update_output_display():
        liters = count * flow_rate_factor_2 / 1000.0
        output_counter_label.config(text=f"{liters:07.2f}")

    def countOutputPulse(channel):
        global count
        count += 1
        update_output_display()

    def start_output_counting():
        global count
        count = 0
        GPIO.add_event_detect(FLOW_SENSOR_GPIO_2, GPIO.RISING, callback=countOutputPulse)
        output_start_button.config(state=tk.DISABLED)

    def send_data():
        try:
            liters = count * flow_rate_factor_2 / 1000.0
            output_data["output"] = liters
            with open(f'input_data_{input_data["batchId"]}.json', 'r') as f:
                data = json.load(f)
            data.update(output_data)
            headers = {
                "api-key": "safeparadise"
            }
            print("data of a json>", data)
            response = requests.post("http://192.168.53.130:8081/api/v1/record/save", json=data, headers=headers)
            if response.status_code == 200:
                messagebox.showinfo("Message", "Data sent successfully!")
            elif response.status_code == 405:
                messagebox.showerror("Error", "405 not allowed")
            else:
                messagebox.showerror("Error", "Something went wrong!")
            with open('final_data.txt', 'w') as f:
                f.write("-------------\n//data\n----------------\n")
                json.dump(data, f, indent=4)
                f.write("\n-------------\n")
            root.quit()
            os.execv(sys.executable, ['python3'] + sys.argv)
        except requests.exceptions.ConnectionError as e:
            messagebox.showerror("Connection Error", f"Failed to connect to the server: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")

    output_counter_label = tk.Label(root, text="000.00", font=("Helvetica", 48))
    output_counter_label.pack(pady=50)

    buttons_frame = tk.Frame(root)
    buttons_frame.pack(pady=20)

    output_start_button = tk.Button(buttons_frame, text="Start", command=start_output_counting)
    output_start_button.grid(row=0, column=0, padx=10)

    send_button = tk.Button(buttons_frame, text="Confirm and Send", command=send_data)
    send_button.grid(row=0, column=1, padx=10)

# Set up GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(FLOW_SENSOR_GPIO_1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(FLOW_SENSOR_GPIO_2, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Set up Tkinter
root = tk.Tk()
root.title("Flowmeter")
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
root.geometry(f"{screen_width}x{screen_height}+0+0")

welcome_label = tk.Label(root, text="Welcome", font=("Helvetica", 48
))
welcome_label.pack(pady=50)

counter_label = tk.Label(root, text="000.00", font=("Helvetica", 48))
counter_label.pack(pady=20)

unit_label = tk.Label(root, text="Liters", font=("Helvetica", 24))
unit_label.pack(pady=10)

buttons_frame = tk.Frame(root)
buttons_frame.pack(pady=20)

add_button = tk.Button(buttons_frame, text="Add", command=add_entry)
add_button.grid(row=0, column=0, padx=10)

start_button = tk.Button(buttons_frame, text="Start", command=start_counting)
start_button.grid(row=0, column=1, padx=10)

stop_button = tk.Button(buttons_frame, text="End", command=confirm_end)
stop_button.grid(row=0, column=2, padx=10)
stop_button.config(state=tk.DISABLED)

tree_frame = tk.Frame(root)
tree_frame.pack(pady=20)

tree = ttk.Treeview(tree_frame, columns=("Entry", "Volume", "Wallet Address"), show="headings")
tree.heading("Entry", text="Entry")
tree.heading("Volume", text="Volume")
tree.heading("Wallet Address", text="Wallet Address")
tree.pack()

root.mainloop()