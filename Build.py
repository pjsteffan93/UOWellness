import os
import re
import time
import requests
from urllib.parse import urljoin, urlparse
from collections import deque
from bs4 import BeautifulSoup
from tqdm import tqdm
import pandas as pd
import hashlib
from datetime import datetime
from openai import OpenAI
import yaml
import csv
import validators
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv('/app/.env')


class Builder:
    def __init__(self, directory, instructions,VS_name):
        self.client = OpenAI()
        self.directory = directory
        self.txt_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.txt')]
        self.list_of_dicts = None
        self.file_ids = []
        self.instructions = instructions
        self.vector_store = None
        self.VS_name = VS_name

    def initialize_list_of_dicts_prev(self):
        
        
        if os.path.exists(os.path.join(self.directory,'assistant_files.csv')):
            # Initialize an empty list to store the rows as dictionaries
            self.list_of_dicts = []

            # Open the CSV file for reading
            with open(os.path.join(self.directory,'assistant_files.csv'), mode='r', newline='', encoding='utf-8') as csvfile:
                # Create a DictReader object
                reader = csv.DictReader(csvfile)
                
                # Iterate over the rows in the reader
                for row in reader:
                    # Append each row (as a dictionary) to the data list
                    self.list_of_dicts.append(row)
        else:
            print("Could Not Find Previous file IDs")

    def initialize_list_of_dicts_new(self):
        size = len(self.txt_files)
        keys = ['filename', 'file_id', 'vectorstore_id', 'assistant_id']
        self.list_of_dicts = [{key: None for key in keys} for _ in range(size)]
        for i, d in enumerate(self.list_of_dicts):
            d["filename"] = self.txt_files[i]
    

    def create_files(self):
        for txt_file in tqdm(self.txt_files):
            try:
                with open(txt_file, 'rb') as file:
                    upload_file = self.client.files.create(
                        file=file,
                        purpose='assistants'
                    )
                    self.file_ids.append(upload_file.id)
            except Exception as e:
                print(f"Error uploading file {txt_file}: {e}")

        for i, d in enumerate(self.list_of_dicts):
            d["file_id"] = self.file_ids[i]

    def chunk_files(self, chunk_size):
        for i in range(0,len(self.file_ids),chunk_size):
            yield self.file_ids[i:i+chunk_size]
    
    def create_vector_store(self):
        try:
            vector_store = self.client.beta.vector_stores.create(name=self.VS_name)
            self.vector_store = vector_store

            for file in self.list_of_dicts:
                batch = self.client.beta.vector_stores.file_batches.create_and_poll(
                    vector_store_id=vector_store.id,
                    file_ids=file["file_id"]
                )
            
            for d in self.list_of_dicts:
                d["vectorstore_id"] = vector_store.id
        except Exception as e:
            print(f"Error creating vector store: {e}")

    def create_assistant(self):
        try:
            assistant = self.client.beta.assistants.create(
                name="Puddles_v2",
                instructions=self.instructions,
                model="gpt-4o-mini",
                tools=[{"type": "file_search"}],
                tool_resources={
                    "file_search": {
                        "vector_store_ids": [self.vector_store.id]
                    }
                }
            )
            for d in self.list_of_dicts:
                d["assistant_id"] = assistant.id
            return assistant
        except Exception as e:
            print(f"Error creating assistant: {e}")
            return None

    def save_to_csv(self, filepath):
        try:
            df = pd.DataFrame(self.list_of_dicts)
            df.to_csv(filepath, index=False)
        except Exception as e:
            print(f"Error saving to CSV: {e}")

    def initialize_assistant(self):
        self.initialize_list_of_dicts_new()
        self.create_files()
        self.create_vector_store()
        if self.vector_store is not None:
            self.create_assistant()
            self.save_to_csv(f'{self.directory}/assistant_files.csv') #Need to get rid from the hardcoding
        print("Created New Assistant")
        return self.list_of_dicts[0]['assistant_id']

    def delete_assistant(self):
        self.initialize_list_of_dicts_prev()
        # Delete all files
        list_files = self.client.files.list(purpose='assistants')
        # Key for which you want to retrieve the values
        key = 'file_id'
        # Using a list comprehension to extract values for the specified key
        values = [d[key] for d in self.list_of_dicts if key in d]
        
        files_on_server = []
        for file in list_files:
            file_dict= file.to_dict()
            files_on_server.append(file_dict["id"])


        common_elements = list(set(values) & set(files_on_server))


        for element in common_elements:
            try:
                self.client.files.delete(element)
                print(f"Deleted file with id: {element}")
                time.sleep(0.5)
            except Exception as e:
                print(f"Could not delete file with id: {element} Found {e}")


        # Delete the assistant
        if self.list_of_dicts and self.list_of_dicts[0]['assistant_id'] is not None:
            assistant_id = self.list_of_dicts[0]['assistant_id']
            
            try:
                self.client.beta.assistants.delete(assistant_id)
                print(f"Deleted assistant with id: {assistant_id}")
            except:
                 print(f"Could not deleted assistant with id: {assistant_id}")

        # Delete the vector store
        if self.list_of_dicts and self.list_of_dicts[0]['vectorstore_id'] is not None:
            vectorstore_id = self.list_of_dicts[0]['vectorstore_id']
            
            try:
                self.client.beta.vector_stores.delete(vectorstore_id)
                print(f"Deleted vector store wsith id: {vectorstore_id}")
            except:
                print(f"Could not delete vector story with id {vectorstore_id}")

    def clear_all_files(self):
        response = self.client.files.list(purpose="assistants")
        print(f"The number of files to be deleted is {len(response.data)}")
        for file in tqdm(response.data):
            try:
                self.client.files.delete(file.id)
            except:
                print("Could not delete file")


        


if __name__ == '__main__':

    with open('/app/puddles_prompt.yml') as f:
        context = yaml.load(f, Loader=yaml.FullLoader)['context']

    builder = Builder('/app/Store/', context,'Puddles_VS')
    builder.initialize_assistant()