FROM python:3.8-buster AS build
COPY . /src
RUN pip install --upgrade pip \
    && pip install wheel
RUN cd /src \
    && python setup.py bdist_wheel -d /deps

FROM python:3.8-buster
MAINTAINER scielo-dev@googlegroups.com

ARG USER_ID=1000
ARG GROUP_ID=1000

RUN groupadd -g ${GROUP_ID} prodtools \
    && useradd -u ${USER_ID} -g ${GROUP_ID} prodtools

COPY --from=build /deps/* /deps/
COPY requirements.txt .

RUN mkdir -p /app/markup

RUN apt-get update -qq \
    && apt-get install -qq -y libxml2 libxslt-dev libjpeg-dev tk lib32z1 lib32z1-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-index --find-links=file:///deps -U SciELO_Production_Tools \
    && rm requirements.txt \
    && rm -rf /deps

WORKDIR /app/xml

RUN chown -R ${USER_ID}:${GROUP_ID} /app

USER prodtools

ENV PYTHONUNBUFFERED 1
