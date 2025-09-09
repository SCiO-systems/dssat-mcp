FROM python:3.11.11

ARG DSSAT_CODE_REPO_PATH=/app/dssat-csm-os-develop
ARG DSSAT_DATA_REPO_PATH=/app/dssat-csm-data-develop

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y curl
RUN apt-get update && apt-get -y install cmake
RUN apt-get -y install gfortran

# Download DSSAT source code
RUN wget https://github.com/DSSAT/dssat-csm-os/archive/refs/heads/develop.zip 
RUN	unzip develop.zip
RUN rm *zip
RUN wget https://github.com/DSSAT/dssat-csm-data/archive/refs/heads/develop.zip
RUN	unzip develop.zip	
RUN rm *zip

# Install DSSAT
RUN cd ${DSSAT_CODE_REPO_PATH} && \
    mkdir build && \
    cd build
WORKDIR ${DSSAT_CODE_REPO_PATH}/build
RUN cmake .. -DCMAKE_INSTALL_PREFIX=${DSSAT_CODE_REPO_PATH}/build/bin/
RUN make
RUN cp -a ${DSSAT_CODE_REPO_PATH}/Data/. ${DSSAT_CODE_REPO_PATH}/build/bin
RUN cp -a ${DSSAT_DATA_REPO_PATH}/. ${DSSAT_CODE_REPO_PATH}/build/bin

WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn","server:app","--host","0.0.0.0","--port","8000"]