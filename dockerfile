FROM python:3.9-slim-buster
#changed to 11.7.1 from 11.7.0 PJS 2024-01-04

ARG PYTHON_VERSION=3.9

WORKDIR /app

COPY requirements.txt .

# Install dependencies and FFmpeg
RUN apt-get update && \
    apt-get install -y libcairo2-dev ffmpeg \
    texlive texlive-latex-extra texlive-fonts-extra \
    texlive-latex-recommended texlive-science \
    tipa libpango1.0-dev

RUN apt-get update && apt-get install -y \
    pkg-config \
    g++


# Update the package list and install the necessary libraries
RUN apt-get update && apt-get install -y \
    libpango1.0-dev \
    libpangocairo-1.0-0 \
    libcairo2-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Continue with the rest of your Dockerfile setup
RUN pip install --trusted-host pypi.python.org -r /app/requirements.txt


RUN apt-get update && apt-get install -y gcc python3-dev

RUN apt-get update && apt-get install -y curl

# Install graphviz
RUN apt-get update && apt-get install -y graphviz

# Add graphviz to the system path for all users
RUN echo 'PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/share/graphviz"' >> /etc/environment

# Install any needed packages specified in requirements.txt
ENV PATH /opt/conda/bin:$PATH 
RUN pip install --upgrade openai
RUN pip install --trusted-host pypi.python.org -r requirements.txt 

ENV DJ_SUPPORT_FILEPATH_MANAGEMENT=TRUE


CMD ["/bin/bash"] 