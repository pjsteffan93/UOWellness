from openai import OpenAI
import streamlit as st

import os
import pandas as pd
import time

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
ASSISTANT_ID = os.environ["ASSISTANT_ID"]

def get_asst_by_name(client,name):
    l = client.beta.assistants.list()
    for asst in l:
        asst_dict = asst.to_dict()
        if asst_dict["name"] == name:
            return asst_dict["id"]
        
    return None

def create_merged_df(scrape_path,asst_path):
    df_scrape = pd.read_pickle(scrape_path)
    df_asst = pd.read_csv(asst_path)
    df_asst.rename(columns={'filename': 'file_path'}, inplace=True)

    # Merging on the common column 'key'
    df_merge = pd.merge(df_scrape, df_asst, on='file_path', how='inner')
    return df_merge


def get_name_by_file_id(df_merge,file_id):
    result = df_merge[df_merge["file_id"]==file_id]
    citation_url = result['url'].values[0]
    return citation_url

def modify_citations(df_merge, message):
    # Extract the message content
    message_content = message.content[0].text
    annotations = message_content.annotations
    citations = []

    # Iterate over the annotations and add footnotes
    for index, annotation in enumerate(annotations):
        # Replace the text with a footnote
        message_content.value = message_content.value.replace(annotation.text, f' [{index+1}]')
        
        #Get the File ID for the file in this citation
        file_id = annotation.file_citation.file_id

        #Find the URL or source for the file_id that OpenAI has
        citation = get_name_by_file_id(df_merge,file_id)

        # Add the citation to the list
        citations.append(f'\n \n [{index+1}] {citation}')

    # Add footnotes to the end of the message before displaying to user
    message_content.value += '\n' + '\n' + 'Sources' + '\n' + '\n'.join(citations)
    return message_content.value


def stream_modified_response(response):
    formatted_string = response
    delay = 0.01  # delay in seconds

    for char in formatted_string:
        yield char
        time.sleep(delay)



scrape_path = '/app/appdata/dataframe.pkl'
asst_path = '/app/appdata/assistant_files.csv'

# Initialise the OpenAI client, and retrieve the assistant
client = OpenAI(api_key=OPENAI_API_KEY)
assistant = client.beta.assistants.retrieve(assistant_id=ASSISTANT_ID)

if 'df_merge' not in st.session_state:
    st.session_state.df_merge = create_merged_df(scrape_path,asst_path)

# Initialise session state to store conversation history locally to display on UI
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Title
st.title("Ask Puddles Anything!")
st.subheader("Enter your question below. Please verify the accuracy of the response with the official University of Oregon websites.")

# Display messages in chat history
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Textbox and streaming process
if user_query := st.chat_input("Ask me a question"):

    # Create a new thread if it does not exist
    if "thread_id" not in st.session_state:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id

    # Display the user's query
    with st.chat_message("user"):
        st.markdown(user_query)

    # Store the user's query into the history
    st.session_state.chat_history.append({"role": "user",
                                          "content": user_query})
    
    
    #Send the User's Query to the model
    run = client.beta.threads.create_and_run_poll(
        assistant_id="asst_WvxFY77dyhKaV6ei809wTfye",
        thread={
            "messages": [
            {"role": "user", "content": user_query}
            ]
        },
        tool_choice="required"
    )

    #Pre-process the Assistant's Response
    thread_messages = client.beta.threads.messages.list(run.thread_id)
    id = thread_messages.data[0].id
    # Retrieve the message object
    message = client.beta.threads.messages.retrieve(
    thread_id=run.thread_id,
    message_id=id
    )

    formatted_response = modify_citations(st.session_state.df_merge, message)

    # Stream the assistant's reply
    with st.chat_message("assistant"):
        stream = client.beta.threads.runs.create(
            thread_id=st.session_state.thread_id,
            assistant_id=ASSISTANT_ID,
            stream=True,
            tool_choice='required'
            )
        
        # Empty container to display the assistant's reply
        assistant_reply_box = st.empty()
        
        # A blank string to store the assistant's reply
        assistant_reply = ""

        for event in stream_modified_response(formatted_response):
            assistant_reply_box.empty()
            assistant_reply += event
            assistant_reply_box.markdown(assistant_reply)


        
        # Once the stream is over, update chat history
        st.session_state.chat_history.append({"role": "assistant",
                                              "content": assistant_reply})