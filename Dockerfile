####################################
#
#  Dockerfile for Root the Box
#  v0.1.3 - By Moloch, ElJeffe

FROM python:3.12

RUN apt-get update && apt-get install -y \
build-essential zlib1g-dev rustc \
python3-pycurl sqlite3 libsqlite3-dev

# uv: reproducible dependency management from pyproject.toml + uv.lock
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

WORKDIR /opt/rtb

# Install locked dependencies before copying the source so this layer stays
# cached across code changes. --frozen fails if the lockfile is out of date.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# The app runs as `python3 rootthebox.py`; putting the venv first on PATH makes
# `python3`/`pytest` resolve to the locked environment without needing activate.
ENV PATH="/opt/rtb/.venv/bin:$PATH"

ADD . /opt/rtb

ENV SQL_DIALECT=sqlite

VOLUME ["/opt/rtb/files"]
ENTRYPOINT ["python3", "/opt/rtb/rootthebox.py", "--setup=docker"]
