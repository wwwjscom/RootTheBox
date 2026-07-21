####################################
#
#  Dockerfile for Root the Box
#  v0.1.3 - By Moloch, ElJeffe

FROM python:3.12

RUN apt-get update && apt-get install -y \
build-essential zlib1g-dev rustc \
python3-pycurl sqlite3 libsqlite3-dev

ADD ./setup/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt --upgrade

RUN mkdir /opt/rtb
ADD . /opt/rtb

ENV SQL_DIALECT=sqlite

VOLUME ["/opt/rtb/files"]
ENTRYPOINT ["python3", "/opt/rtb/rootthebox.py", "--setup=docker"]
