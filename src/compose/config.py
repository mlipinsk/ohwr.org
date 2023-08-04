# SPDX-FileCopyrightText: 2023 CERN (home.cern)
#
# SPDX-License-Identifier: BSD-3-Clause

"""Load, parse and validate configuration."""

import os
import subprocess  # noqa: S404
from datetime import date
from logging import debug, info
from tempfile import TemporaryDirectory
from typing import Literal, Optional, TextIO, Union
from urllib import request
from urllib.error import URLError
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ValidationError
from url import URL


class ConfigError(Exception):
    """Failed to load, parse or validate configuration."""


class LinkConfig(BaseModel):
    """Parses and validates link configuration."""

    name: str
    url: URL


class NewsConfig(BaseModel):
    """Parses and validates news configuration."""

    title: str
    date: date
    image: Optional[URL] = None
    content: Optional[str] = None  # noqa: WPS110


class ProjConfig(BaseModel):
    """Loads, parses and validates project sources configuration."""

    id: str
    url: str
    type: Optional[Literal['featured', 'regular']] = 'regular'
    name: str
    description: str
    website: URL
    licenses: list[str]
    image: Optional[URL] = None
    documentation: Optional[URL] = None
    issues: Optional[URL] = None
    latest_release: Optional[URL] = None
    forum: Optional[URL] = None
    links: Optional[list[LinkConfig]] = None
    gallery: Optional[list[URL]] = None
    categories: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    news: Optional[list[NewsConfig]] = None

    @classmethod
    def from_url(cls, url: str, **kwargs):
        """
        Load project sources configuration from a URL.

        Parameters:
            url: git repository URL.
            kwargs: id and type (optional).

        Returns:
            ProjConfig object.
        """
        if urlparse(url).hostname == 'github.com':
            return cls.from_github(url=url, **kwargs)
        return cls.from_repo(url=url, **kwargs)

    @classmethod
    def from_repo(cls, url: str, **kwargs):
        """
        Load project sources configuration from a git repository.

        Parameters:
            url: git repository URL.
            kwargs: id and type (optional).

        Returns:
            ProjConfig object.

        Raises:
            ConfigError: if loading the configuration fails.
        """
        info('Loading .ohwr.yaml from {0} with git clone...'.format(url))
        tmpdir = TemporaryDirectory().name
        try:
            subprocess.check_output(
                'git clone --depth 1 {0} {1}'.format(url, tmpdir),
                stderr=subprocess.STDOUT,
                shell=True,  # noqa: S602
            )
        except subprocess.CalledProcessError as error:
            msg = 'Failed to clone {0}:\n↳ {1}'
            raise ConfigError(msg.format(url, error))
        try:
            with open(os.path.join(tmpdir, '.ohwr.yaml')) as config_file:
                return cls.from_yaml(config_file, url=url, **kwargs)
        except FileNotFoundError:
            msg = 'No .ohwr.yaml file found in {0}.'
            raise ConfigError(msg.format(url))

    @classmethod
    def from_github(cls, url: str, **kwargs):
        """
        Load project sources configuration from a GitHub repository.

        Parameters:
            url: git repository URL.
            kwargs: id and type (optional).

        Returns:
            ProjConfig object.

        Raises:
            ConfigError: if loading the configuration fails.
        """
        info('Loading .ohwr.yaml from {0} with GitHub API...'.format(url))
        repo = urlparse(url).path.removeprefix('/').removesuffix('.git')
        fmt = 'https://api.github.com/repos/{0}/contents/.ohwr.yaml'
        req = request.Request(
            fmt.format(repo),
            headers={'Accept': 'application/vnd.github.v3.raw'},
        )
        try:
            with request.urlopen(req) as response:  # noqa: S310
                return cls.from_yaml(response, url=url, **kwargs)
        except URLError as error:
            msg = 'Failed to request {0}:\n↳ {1}'
            raise ConfigError(msg.format(req.full_url, error))

    @classmethod
    def from_yaml(cls, config_yaml: Union[str, TextIO], **kwargs):
        """
        Parse and validate project sources YAML configuration.

        Parameters:
            config_yaml: YAML file or string.
            kwargs: id, url and type (optional).

        Returns:
            ProjConfig object.

        Raises:
            ConfigError: if parsing or validating the configuration fails.
        """
        debug('Parsing {0}/.ohwr.yaml...'.format(kwargs['id']))
        try:
            config = yaml.safe_load(config_yaml)
        except yaml.YAMLError as yaml_error:
            msg = 'Failed to load YAML configuration:\n↳ {0}'
            raise ConfigError(msg.format(yaml_error))
        info('Validating {0}/.ohwr.yaml...'.format(kwargs['id']))
        try:
            return cls(**config['project'], **kwargs)
        except (ValidationError, KeyError) as validation_error:
            msg = 'YAML configuration is not valid:\n↳ {0}'
            raise ConfigError(msg.format(validation_error))
