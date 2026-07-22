FROM python:3.12

ADD [ "https://dev.mysql.com/get/mysql-apt-config_0.8.32-1_all.deb", "/" ]

RUN apt-get -qq update \
	&& export DEBIAN_FRONTEND=noninteractive \
	&& apt-get -qq upgrade -y \
	&& apt-get -qq install -y --no-install-recommends \
		lsb-release \
		locales \
		build-essential \
		zlib1g-dev \
		python3-pycurl \
	# MySQL Tools
	&& dpkg -i /mysql-apt-config_0.8.32-1_all.deb \
	&& apt-get -qq update \
	&& apt-get -qq install -y --no-install-recommends \
		mysql-shell \
		mysql-client \
	# Clean up
	&& apt-get autoremove -y \
	&& apt-get clean -y \
	&& rm -rf /var/lib/apt/lists/* \
	&& rm mysql-apt-config*.deb

# Generate the en_US.UTF-8 locale used by mysqlsh
RUN sed -Ei 's/^# en_US\.UTF-8 UTF-8$/en_US.UTF-8 UTF-8/' /etc/locale.gen && locale-gen

# uv: install the locked dependencies (+ dev group) into the system interpreter,
# derived from pyproject.toml + uv.lock for reproducibility.
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/
COPY ./pyproject.toml ./uv.lock ./
RUN uv export --frozen --no-emit-project -o /tmp/requirements.lock \
	&& uv pip install --system --no-cache-dir -r /tmp/requirements.lock \
	&& uv pip install --system --no-cache-dir pylint \
	&& rm /tmp/requirements.lock

# Create a new user dev (1000 matches the default user in WSL)
ARG USERNAME=rtbdev
ARG UID=1000
ARG GID=1000
RUN groupadd --gid $GID $USERNAME
RUN useradd --create-home --shell /bin/bash --uid $UID --gid $GID $USERNAME

# Run with dev user
USER $USERNAME
