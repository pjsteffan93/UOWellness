from openai import OpenAI
import streamlit as st
from openai import OpenAI
from openai.types.beta.assistant_stream_event import ThreadMessageDelta
from openai.types.beta.threads.text_delta_block import TextDeltaBlock 
import os

from fabric import Connection
import tkinter as tk
from tkinter import filedialog
import sys

import pandas as pd

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
ASSISTANT_ID = os.environ["ASSISTANT_ID"]

from typing import Optional, List, Tuple

class PuddlesKnowledgeDF:
    def __init__(self):
        self.df = pd.DataFrame(columns=[
            'knowledge_type', 'base_name', 'file_name', 
            'file_id', 'url', 'text_hash', 'date_accessed'
        ])

    def add_entry(self, knowledge_type: str, base_name: str, file_name: str, file_id: str,
                  url: str, text_hash: str, date_accessed: str):
        new_entry = {
            'knowledge_type': knowledge_type,
            'base_name': base_name,
            'file_name': file_name,
            'file_id': file_id,
            'url': url,
            'text_hash': text_hash,
            'date_accessed': date_accessed
        }
        self.df = self.df.append(new_entry, ignore_index=True)

    def delete_entry(self, file_id: str):
        self.df = self.df[self.df['file_id'] != file_id]

    def search_by_file_id(self, file_id: str) -> Optional[Dict]:
        entry = self.df[self.df['file_id'] == file_id]
        if not entry.empty:
            return entry.iloc[0].to_dict()
        return None

    def search_by_knowledge_type(self, knowledge_type: str) -> List[Dict]:
        entries = self.df[self.df['knowledge_type'] == knowledge_type]
        return entries.to_dict(orient='records')

    def update_entry(self, file_id: str, updates: Dict):
        for key, value in updates.items():
            self.df.loc[self.df['file_id'] == file_id, key] = value

    def to_csv(self, filename: str):
        self.df.to_csv(filename, index=False)

    def from_csv(self, filename: str):
        self.df = pd.read_csv(filename)



def get_tasks(patient_selector, admission_selector):
    query = stitch & ("patient_id = " + patient_selector) & ("admission_id = " + admission_selector)
    return pd.DataFrame(query.fetch(as_dict=True))

def download_file(host, username, password, remote_path, local_path):
    try:
        # Connect to the server
        with Connection(host=host, user=username, connect_kwargs={"password": password}) as conn:

            # Download the file
            conn.get(remote=remote_path, local=local_path)
            st.success(f"File downloaded successfully to {local_path}")
    except Exception as e:
        st.error(f"An error occurred: {e}")


def select_folder():
   root = tk.Tk()
   root.withdraw()
   folder_path = filedialog.askdirectory(master=root)
   root.destroy()
   return folder_path



def main():
    st.title("Stitched File Data Downloader")
    
    #Input Fields for Database Query
    patient_selector = st.text_input("Patient", value="YYY", key="patient_selector")
    admission_selector = st.text_input("Admission", value="1", key="admission_selector")
    fetch_db_button = st.button("Fetch Database")

    if fetch_db_button:
        if 'fetchClicked' in st.session_state:
            st.session_state.tasks = get_tasks(patient_selector, admission_selector)
        else:
            st.session_state.fetchClicked = True
            st.session_state.tasks = get_tasks(patient_selector, admission_selector)
    elif 'fetchClicked' not in st.session_state:
        st.session_state.tasks = pd.DataFrame({'empty': []})
    else:
        st.session_state.tasks = st.session_state.tasks
    st.write(st.session_state.tasks)
    
    
    # Select column to filter by
    st.session_state.filter_column = st.selectbox('Select column to filter by:', options=st.session_state.tasks.columns)
    st.session_state.selected_values = st.multiselect('Select values:', options=st.session_state.tasks[st.session_state.filter_column].unique())
    
    
    # Create subset DataFrame based on selected values
    st.session_state.subset_df = pd.DataFrame(st.session_state.tasks[st.session_state.tasks[st.session_state.filter_column].isin(st.session_state.selected_values)])
    
    
    # Display the subset DataFrame
    st.write('Subset DataFrame:')
    st.write(st.session_state.subset_df) 

    # Button to select local folder
    folder_select_button = st.button("Select Folder")

    if folder_select_button:
        selected_folder_path = select_folder()
        st.session_state.folder_path = selected_folder_path

    # Input fields for server connection
    host = "localhost"
    username = st.text_input("Username", value="username", key = "username")
    password = st.text_input("Password", type="password", value="your_password", key = "password")



    # Button to initiate file download

    if st.button("Download File"):
        pass

if __name__ == "__main__":
    main()