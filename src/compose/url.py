# SPDX-FileCopyrightText: 2025 CERN (home.cern)
#
# SPDX-License-Identifier: BSD-3-Clause

"""Represent URLs."""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Annotated, Any
from urllib.parse import quote

import requests
from pydantic import Field, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


@dataclass
class Url:
    """Represent a reachable URL."""

    url: str

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, core_schema_handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """
        Define a custom Pydantic core schema for validation.

        Parameters:
            source_type: Pydantic source type.
            core_schema_handler: Pydantic core schema handler.

        Returns:
            A Pydantic CoreSchema instance.
        """
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls._serialize,
            ),
        )

    @classmethod
    def _validate(cls, input_value: Any) -> 'Url':
        """
        Validate input value.

        Parameters:
            input_value: Value to validate.

        Returns:
            A Url instance.

        Raises:
            ValueError: If the provided value is not valid.
        """
        if isinstance(input_value, cls):
            return input_value
        if isinstance(input_value, str):
            cls._head(input_value)
            return cls(input_value)
        raise ValueError("Invalid value: '{0}'".format(input_value))

    @classmethod
    def _serialize(cls, url: 'Url') -> str:
        return url.url

    @classmethod
    def _head(cls, url: str) -> requests.Response:
        try:
            res = requests.head(url, timeout=10, allow_redirects=True)
        except requests.exceptions.RequestException as head_error:
            raise ValueError("HEAD request to '{0}' failed:\n{1}".format(
                url, head_error,
            ))
        try:
            res.raise_for_status()
        except requests.exceptions.RequestException as raise_for_status_error:
            raise ValueError("HEAD request to '{0}' failed:\n{1}".format(
                url, raise_for_status_error,
            ))
        return res

    @classmethod
    def _get(cls, url: str, headers: str = '') -> requests.Response:
        try:
            res = requests.get(url, headers=headers, timeout=10)
        except requests.exceptions.RequestException as get_error:
            raise ValueError("GET request to '{0}' failed:\n{1}".format(
                url, get_error,
            ))
        try:
            res.raise_for_status()
        except requests.exceptions.RequestException as raise_for_status_error:
            raise ValueError("GET request to '{0}' failed:\n{1}".format(
                url, raise_for_status_error,
            ))
        return res


UrlList = Annotated[list[Url], Field(min_length=1)]


@dataclass
class UrlContent(Url, ABC):
    """Abstract class to fetch URL content."""

    text: str

    @classmethod
    @abstractmethod
    def from_url(cls, url: str) -> 'UrlContent':
        """
        Abstract constructor method to fetch content from a URL.

        Parameters:
            url: URL to fetch content from.

        Returns:
            A UrlContent instance.
        """

    @classmethod
    def create(cls, url: str) -> 'UrlContent':
        """
        Return a specific UrlContent instance based on the URL.

        Parameters:
            url: URL to fetch content from.

        Returns:
            A UrlContent instance.
        """
        gitlab = (
            r'^https://(?:gitlab\.com|ohwr\.org|gitlab\.cern\.ch)/.+?/wikis/.+'
        )
        if re.search(gitlab, url):
            return GitLabWikiPage.from_url(url)
        return GenericUrlContent.from_url(url)

    @classmethod
    def _validate(cls, input_value: Any) -> 'UrlContent':
        """
        Validate input value.

        Parameters:
            input_value: Value to validate.

        Returns:
            A UrlContent instance.

        Raises:
            ValueError: If the provided value is not valid.
        """
        if isinstance(input_value, cls):
            return input_value
        if isinstance(input_value, str):
            return cls.create(input_value)
        raise ValueError("Invalid value: '{0}'".format(input_value))


class GitLabWikiPage(UrlContent):
    """GitLab Wiki page."""

    @classmethod
    def from_url(cls, url: str) -> 'GitLabWikiPage':
        """
        Fetch a GitLab Wiki page from a URL.

        Parameters:
            url: Wiki page URL.

        Returns:
            A GitLabWikiPage instance.

        Raises:
            ValueError: If fetching the wiki page fails.
        """
        exp = (
            r'^https://((?:gitlab\.com|ohwr\.org|gitlab\.cern\.ch))/' +
            '(.+?)(?:/-)?/wikis/(.+)'
        )
        match = re.search(exp, url)
        url = 'https://{0}/api/v4/projects/{1}/wikis/{2}'.format(
            match.group(1),
            quote(match.group(2), safe=''),
            quote(match.group(3), safe=''),
        )
        try:
            return cls(url, cls._get(url).json()['content'])
        except (TypeError, json.JSONDecodeError, KeyError) as json_error:
            raise ValueError('Failed to load JSON:\n{0}'.format(json_error))


class GenericUrlContent(UrlContent):
    """Generic URL content."""

    @classmethod
    def from_url(cls, url: str) -> 'GenericUrlContent':
        """
        Fetch content from a URL.

        Parameters:
            url: URL to fetch content from.

        Returns:
            A GenericUrlContent instance.
        """
        return cls(url, cls._get(url).text)
