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


class Builder:
    def __init__(self, directory, instructions,VS_name):
        self.client = OpenAI()
        self.directory = directory
        self.txt_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.txt')]
        self.list_of_dicts = self.initialize_list_of_dicts()
        self.file_ids = []
        self.instructions = instructions
        self.vector_store = None
        self.VS_name = VS_name

    def initialize_list_of_dicts(self):
        size = len(self.txt_files)
        keys = ['filename', 'file_id', 'vectorstore_id', 'assistant_id']
        list_of_dicts = [{key: None for key in keys} for _ in range(size)]
        for i, d in enumerate(list_of_dicts):
            d["filename"] = self.txt_files[i]
        return list_of_dicts

    def create_files(self):
        for txt_file in self.txt_files:
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

    def create_vector_store(self):
        try:
            vector_store = self.client.beta.vector_stores.create(name=self.VS_name)
            self.vector_store = vector_store
            batch = self.client.beta.vector_stores.file_batches.create_and_poll(
                vector_store_id=vector_store.id,
                file_ids=self.file_ids
            )
            for d in self.list_of_dicts:
                d["vectorstore_id"] = vector_store.id
        except Exception as e:
            print(f"Error creating vector store: {e}")

    def create_assistant(self):
        try:
            assistant = self.client.beta.assistants.create(
                id = 'asst_faCG9KKu801s5qshDlg5XMcJ',
                instructions=self.instructions,
                model="gpt-4o",
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
        self.create_files()
        self.create_vector_store()
        if self.vector_store is not None:
            self.create_assistant()
            self.save_to_csv(f'{self.directory}/assistant_files.csv') #Need to get rid from the hardcoding
        return self.list_of_dicts[0]['assistant_id']

    def delete_assistant(self):
        try:
            # Delete all files
            list_files = self.client.files.list(purpose='assistants')
            for file in list_files:
                self.client.files.delete(file.id)
                print(f"Deleted file with id: {file.id}")

            # Delete the assistant
            if self.list_of_dicts and self.list_of_dicts[0]['assistant_id']:
                assistant_id = self.list_of_dicts[0]['assistant_id']
                self.client.beta.assistants.delete(assistant_id)
                print(f"Deleted assistant with id: {assistant_id}")

            # Delete the vector store
            if self.list_of_dicts and self.list_of_dicts[0]['vectorstore_id']:
                vectorstore_id = self.list_of_dicts[0]['vectorstore_id']
                self.client.beta.vector_stores.delete(vectorstore_id)
                print(f"Deleted vector store with id: {vectorstore_id}")
        except Exception as e:
            print(f"Error deleting resources: {e}")



class Scraper:
    def __init__(self, URLs, output_dir='/app/Store', max_depth=4,frame=None):
        self.URLs = URLs
        self.max_depth = max_depth
        self.visited_urls = set()
        self.frame = frame
        self.output_dir = output_dir
        self.check_dataframe()

    # Function to generate a hash from text
    def generate_hash(self,text):
        return hashlib.sha256(text.encode()).hexdigest()

    def check_dataframe(self):
        if self.frame is None:
            self.frame = pd.DataFrame(columns=['url', 'text_hash','date_accessed'])
        else:
            self.frame = pd.read_pickle(self.frame)

    def save_dataframe(self):
        self.frame.to_pickle(os.path.join(self.output_dir,'dataframe.pkl'))

    def url_to_filename(self,url):
        filename = re.sub(r'^(http|https)://', '', url)
        filename = filename.replace('/', '_')
        filename = re.sub(r'[^a-zA-Z0-9\-_]', '_', filename)
        max_length = 255
        return filename[:max_length]


    def reset_visited_urls(self):
        self.visited_urls = set()

    def scrape_text_bfs(self,start_url, base_url, max_depth=4):
        self.reset_visited_urls()
        
        queue = deque([(start_url, 0)])  # Queue stores tuples of (url, current_depth)

        while queue and len(self.visited_urls) < 5:
            url, depth = queue.popleft()
            print(f"Scraping {url} at depth {depth}")
            
            # Check if the URL has already been visited or if it exceeds max depth
            if url in self.visited_urls or depth > max_depth:
                continue
            
            mask = self.frame['url'] == url
            entry = self.frame[mask]
            
            try:
                date_accessed = entry['date_accessed'].values[0]
            except:
                date_accessed = None

            # Mark the URL as visited
            self.visited_urls.add(url)

            try:
                response = requests.get(url)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f"Failed to retrieve {url}: {e}")
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            if (mask.sum() == 1 and pd.Timestamp.now()-date_accessed >= pd.Timedelta(weeks=1)) or mask.sum() == 0:
                # Extract and save text
                text = soup.get_text(separator=' ', strip=True)
                text = f"URL:{url}\n{text}"

                try:
                    text_hash = entry['text_hash'].values[0]
                except:
                    text_hash = None

                file_path = os.path.join(self.output_dir, self.url_to_filename(url) + '.txt')

                #See if the stored hash is the same as the hash for current text
                if text_hash == self.generate_hash(text):
                    pass
                elif mask.sum() == 0:
                    
                    with open(file_path, 'w') as f:
                        f.write(text)

                    # Add the URL to the dataframe
                    self.frame = pd.concat([self.frame , pd.DataFrame({'url': [url], 'text_hash': [self.generate_hash(text)],'date_accessed':[datetime.now()],'file_path': [file_path]})], ignore_index=True)
                
                elif mask.sum() == 1:
                    #Delete the corresponding file
                    os.remove(entry['file_path'].values[0])
                    
                    #Delete the entry in the dataframe
                    self.frame = self.frame[~mask]

                    
                    with open(file_path, 'w') as f:
                        f.write(text)

                    # Add the URL to the dataframe
                    self.frame = pd.concat([self.frame , pd.DataFrame({'url': [url], 'text_hash': [self.generate_hash(text)],'date_accessed':[datetime.now()],'file_path': [file_path]})], ignore_index=True)
            
            
            # If the current depth is less than max_depth, find and add links to the queue
            if depth < max_depth:
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    next_url = urljoin(base_url, href)
                    if urlparse(next_url).netloc == urlparse(base_url).netloc and next_url not in self.visited_urls:
                        queue.append((next_url, depth + 1))
                        time.sleep(0.5)  # Sleep for 500ms to avoid hammering the server
        self.save_dataframe()

    def breadth_scrape(self):
        for start_url in tqdm(self.URLs):
            self.scrape_text_bfs(start_url, start_url, max_depth=self.max_depth)

if __name__ == "__main__":
    scrape = Scraper(['https://health.uoregon.edu/'],'/app/Store/',frame='/app/dataframe.pkl')
    scrape.breadth_scrape()
    
    with '/app/puddles_prompt.yml' as f:
        context = yaml.load(f, Loader=yaml.FullLoader)['context']

    builder = Builder('/app/Store/', context,'Puddles_VS')
    builder.delete_assistant()
    builder.initialize_assistant()
