# This file is for use as a devcontainer and a runtime container
#
# The devcontainer should use the build target and run as root with podman
# or docker with user namespaces.
#
ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION} as developer

# Add any system dependencies for the developer/build environment here e.g.
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# set up a virtual environment and put it in PATH
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH

# The build stage installs the context into the venv
FROM developer AS build

# copy any required context for the pip install over
COPY . /context
WORKDIR /context

# install python package into /venv
RUN touch dev-requirements.txt && pip install -c dev-requirements.txt .

# The runtime stage copies the built venv into a slim runtime container
FROM python:${PYTHON_VERSION}-slim as runtime

# add apt-get system dependencies for runtime here if needed

# copy the virtual environment from the build stage and put it in PATH
COPY --from=build /venv/ /venv/
ENV PATH=/venv/bin:$PATH

# change this entrypoint if it is not the same as the repo
ENTRYPOINT ["CATio"]
CMD ["--version"]
