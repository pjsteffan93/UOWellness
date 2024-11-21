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



class Scraper:
    def __init__(self, URLs, output_dir='/app/BFS', max_depth=4,frame=None):
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
        self.frame.to_pickle(os.join(self.output_dir,'dataframe.pkl'))

    def url_to_filename(url):
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
            
            if mask.sum() == 1 and entry['date_accessed'].dt.date == pd.Timestamp.now()-pd.Timedelta(weeks=1):
                # Mark the URL as visited
                self.visited_urls.add(url)

                try:
                    response = requests.get(url)
                    response.raise_for_status()
                except requests.exceptions.RequestException as e:
                    print(f"Failed to retrieve {url}: {e}")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')

                # Extract and save text
                text = soup.get_text(separator=' ', strip=True)
                text = f"URL:{url}\n{text}"


                #See if the stored hash is the same as the hash for current text
                if entry['text_hash'].values[0] == self.generate_hash(text):
                    pass
                else:
                    
                    #Delete the corresponding file
                    os.remove(entry['file_path'].values[0])
                    
                    #Delete the entry in the dataframe
                    self.frame = self.frame[~mask]
                    
                    file_path = os.path.join(self.output_dir, self.url_to_filename(url) + '.txt')
                    
                    with open(file_path, 'w') as f:
                        f.write(text)

                    # Add the URL to the dataframe
                    self.frame = pd.concat([self.frame, pd.DataFrame({'url': [url], 'text_hash': [self.generate_hash(text)],'date_accessed':[datetime.now()],'file_path': [file_path]})], ignore_index=True)

            # If the current depth is less than max_depth, find and add links to the queue
            if depth < max_depth:
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    next_url = urljoin(base_url, href)
                    if urlparse(next_url).netloc == urlparse(base_url).netloc and next_url not in self.visited_urls:
                        queue.append((next_url, depth + 1))
                        time.sleep(0.5)  # Sleep for 500ms to avoid hammering the server
        self.save_dataframe(os.join(self.output_dir,'dataframe.pkl'))

    def breadth_scrape(self):
        for start_url in tqdm(self.URLs):
            self.scrape_text_bfs(start_url, start_url, max_depth=self.max_depth)
