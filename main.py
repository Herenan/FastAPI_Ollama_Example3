import tkinter as tk
from tkinter import scrolledtext, messagebox
import requests
import json
import os
import threading
from datetime import datetime

import pandas as pd
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

def get_snowflake_connection():
    try:
        return snowflake.connector.connect(
            user=os.getenv("SNOWFLAKE_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
            database=os.getenv("SNOWFLAKE_DATABASE"),
            schema=os.getenv("SNOWFLAKE_SCHEMA")
        )
    except Exception as e:
        print(f"Error connecting to Snowflake: {e}")
        return None

def execute_snowflake_query(sql_query: str):
    conn = get_snowflake_connection()
    if not conn:
        raise ConnectionError("Failed to connect to Snowflake.")
    
    try:
        df = pd.read_sql(sql_query, conn)
        return df
    finally:
        if conn:
            conn.close()

OLLAMA_API_URL = "http://localhost:11434/api/generate"

def ask_ollama_for_sql(user_prompt: str):
    system_prompt = """
    You are an expert Snowflake SQL generator. Your task is to convert the user's natural language request into a single, valid Snowflake SQL query.
    The table you can query is named "BOOKS".
    The "BOOKS" table has the following columns: ID (INT), TITLE (VARCHAR), AUTHOR (VARCHAR), YEAR (INT).
    - Only generate a SELECT statement.
    - Do not generate any other DML (INSERT, UPDATE, DELETE).
    - Do not add any explanations, comments, or any text other than the SQL query itself.
    - If the user's request is not about fetching data from the BOOKS table or is a general chat question, you MUST respond with the exact text: NO_SQL
    """
    
    full_prompt = f"User request: '{user_prompt}'\n\nBased on the instructions, generate the SQL query:"

    payload = {
        "model": "llama3",
        "system": system_prompt,
        "prompt": full_prompt,
        "stream": False
    }
    
    response = requests.post(OLLAMA_API_URL, json=payload)
    response.raise_for_status()
    
    response_text = response.json().get("response", "").strip()
    return response_text

class OllamaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Snowflake AI Assistant")
        self.root.geometry("700x500")

        main_frame = tk.Frame(root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(main_frame, text="ป้อนคำสั่งของคุณ:", font=("Arial", 12)).pack(anchor=tk.W)
        self.prompt_input = tk.Text(main_frame, height=4, font=("Arial", 11))
        self.prompt_input.pack(fill=tk.X, pady=5)

        self.submit_button = tk.Button(main_frame, text="ส่งคำสั่ง", command=self.handle_submit, font=("Arial", 12, "bold"))
        self.submit_button.pack(fill=tk.X, pady=5)

        tk.Label(main_frame, text="สถานะการทำงาน:", font=("Arial", 12)).pack(anchor=tk.W)
        self.console_output = scrolledtext.ScrolledText(main_frame, state='disabled', font=("Courier New", 10))
        self.console_output.pack(fill=tk.BOTH, expand=True)

    def log(self, message):
        self.console_output.config(state='normal')
        self.console_output.insert(tk.END, f"{message}\n")
        self.console_output.see(tk.END)
        self.console_output.config(state='disabled')
        self.root.update_idletasks()

    def handle_submit(self):
        user_prompt = self.prompt_input.get("1.0", tk.END).strip()
        if not user_prompt:
            messagebox.showwarning("Warning", "กรุณาป้อนคำสั่ง")
            return
        
        self.submit_button.config(state='disabled')
        thread = threading.Thread(target=self.process_request, args=(user_prompt,))
        thread.start()

    def process_request(self, user_prompt):
        try:
            self.log("เริ่มต้นประมวลผล...")
            self.log(f"   คำสั่ง: {user_prompt}")
            
            self.log("กำลังส่งคำสั่งไปให้ AI (Ollama) เพื่อสร้าง SQL...")
            sql_query = ask_ollama_for_sql(user_prompt)
            
            if sql_query == "NO_SQL":
                self.log("AI ตีความว่าเป็นคำถามทั่วไป ไม่ใช่คำสั่งดึงข้อมูล")
                self.log("จบการทำงาน")
                return

            self.log(f"SQL ที่ AI สร้าง: {sql_query}")
            
            self.log("กำลังเชื่อมต่อ Snowflake และดึงข้อมูล...")
            data_df = execute_snowflake_query(sql_query)
            self.log(f"   ดึงข้อมูลสำเร็จ! พบ {len(data_df)} แถว")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"snowflake_export_{timestamp}.csv"
            data_df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.log(f"บันทึกข้อมูลเป็นไฟล์ '{filename}' เรียบร้อยแล้ว")
            
            self.log("การทำงานเสร็จสมบูรณ์!")

        except requests.exceptions.RequestException as e:
            self.log(f"เกิดข้อผิดพลาด: ไม่สามารถเชื่อมต่อ Ollama ได้ กรุณาตรวจสอบว่า Ollama server ทำงานอยู่")
        except Exception as e:
            self.log(f"เกิดข้อผิดพลาด: {e}")
        finally:
            self.submit_button.config(state='normal')


if __name__ == "__main__":
    root = tk.Tk()
    app = OllamaApp(root)
    root.mainloop()