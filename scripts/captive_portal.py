#!/usr/bin/python3
"""Shared library for captive portal login scripts."""

from __future__ import annotations

import urllib.parse
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

import requests


class CaptivePortalFormParser(HTMLParser):
    def __init__(
        self,
        form_id: Optional[str],
        action_contains: Optional[str],
        button_text_contains: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.form_id = form_id
        self.action_contains = action_contains
        self.button_text_contains = (button_text_contains or "").lower().strip()
        self.active_form: Optional[Dict[str, Optional[str]]] = None
        self.active_form_index: Optional[int] = None
        self.forms: List[Dict[str, Optional[str]]] = []
        self.inputs: Dict[int, Dict[str, str]] = {}
        self.form_submit_match: Dict[int, bool] = {}
        self.capture_button_text_for_form: Optional[int] = None
        self._form_counter = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attrs_dict: Dict[str, Optional[str]] = {key: value for key, value in attrs if key}

        if tag == "form":
            if self._matches_form(attrs_dict):
                self.active_form = attrs_dict
                self.active_form_index = self._form_counter
                self.forms.append(attrs_dict)
                self.inputs[self._form_counter] = {}
                self.form_submit_match[self._form_counter] = False
                self._form_counter += 1
            return

        if tag == "form" and self.active_form is not None:
            return

        if tag == "button" and self.active_form is not None:
            button_type = (attrs_dict.get("type") or "submit").lower()
            if button_type == "submit":
                self.capture_button_text_for_form = self.active_form_index
            return

        if tag == "input" and self.active_form is not None:
            name = attrs_dict.get("name")
            value = attrs_dict.get("value") or ""
            input_type = (attrs_dict.get("type") or "").lower()
            if input_type in {"submit", "button"}:
                self._mark_submit_match(value)
            if name and input_type != "submit":
                self.inputs[self._form_counter - 1][name] = value

    def handle_endtag(self, tag: str) -> None:
        if tag == "button":
            self.capture_button_text_for_form = None
            return
        if tag == "form":
            self.capture_button_text_for_form = None
            self.active_form = None
            self.active_form_index = None

    def handle_data(self, data: str) -> None:
        if self.capture_button_text_for_form is None:
            return
        self._mark_submit_match(data, self.capture_button_text_for_form)

    def _mark_submit_match(self, text: str, form_index: Optional[int] = None) -> None:
        if not self.button_text_contains:
            return
        if form_index is None:
            form_index = self.active_form_index
        if form_index is None:
            return
        if self.button_text_contains in text.lower():
            self.form_submit_match[form_index] = True

    def _matches_form(self, attrs_dict: Dict[str, Optional[str]]) -> bool:
        if self.form_id and attrs_dict.get("id") == self.form_id:
            return True
        if self.action_contains and self.action_contains in (attrs_dict.get("action") or ""):
            return True
        return False


def has_internet(session: requests.Session, probe_url: str, expected_status: int, timeout: int) -> bool:
    try:
        response = session.get(probe_url, timeout=timeout, allow_redirects=False)
    except requests.RequestException:
        return False
    return response.status_code == expected_status


def fetch_portal_page(session: requests.Session, probe_url: str, fallback_url: str, timeout: int) -> Tuple[str, str]:
    try:
        response = session.get(probe_url, timeout=timeout, allow_redirects=True)
        if response.text and "text/html" in response.headers.get("Content-Type", ""):
            return response.url, response.text
    except requests.RequestException:
        pass

    response = session.get(fallback_url, timeout=timeout)
    return response.url, response.text


def parse_login_form(
    html: str,
    form_id: Optional[str],
    form_action_contains: Optional[str],
    button_text_contains: Optional[str] = None,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    parser = CaptivePortalFormParser(form_id, form_action_contains, button_text_contains)
    parser.feed(html)

    if not parser.forms:
        raise RuntimeError("No matching login form found in portal HTML.")

    selected_index = 0
    if parser.button_text_contains:
        matching_indices = [
            idx for idx, matches in parser.form_submit_match.items() if matches
        ]
        if not matching_indices:
            raise RuntimeError(
                f"No matching login button found (expected text: {button_text_contains!r})."
            )
        selected_index = matching_indices[0]

    form_attrs_raw = parser.forms[selected_index]
    form_attrs: Dict[str, str] = {k: v for k, v in form_attrs_raw.items() if v is not None}
    form_inputs = parser.inputs.get(selected_index, {})
    return form_attrs, form_inputs


def portal_indicates_online(html: str, marker: str) -> bool:
    marker = marker.strip().lower()
    return bool(marker) and marker in html.lower()


def merge_form_data(
    form_inputs: Dict[str, str],
    portal_url: str,
    extra_fields: Dict[str, str],
    query_fields: List[str],
) -> Dict[str, str]:
    payload = {key: value for key, value in form_inputs.items() if key}

    parsed_url = urllib.parse.urlparse(portal_url)
    portal_query = urllib.parse.parse_qs(parsed_url.query)
    for field in query_fields:
        if field not in payload and field in portal_query:
            payload[field] = portal_query[field][0]

    for key, value in extra_fields.items():
        payload.setdefault(key, value)

    return payload


def submit_login_form(
    session: requests.Session,
    portal_url: str,
    form_attrs: Dict[str, str],
    payload: Dict[str, str],
    timeout: int,
) -> requests.Response:
    action = form_attrs.get("action", "").rstrip("?")
    method = form_attrs.get("method", "get").lower()

    submit_url = urllib.parse.urljoin(portal_url, action)
    if method == "post":
        return session.post(submit_url, data=payload, timeout=timeout)
    return session.get(submit_url, params=payload, timeout=timeout)


class CaptivePortalClient:
    def __init__(
        self,
        probe_url: str,
        probe_expected_status: int,
        portal_fallback_url: str,
        form_id: Optional[str],
        form_action_contains: Optional[str],
        button_text_contains: Optional[str] = None,
        already_online_marker: Optional[str] = None,
        default_form_fields: Optional[Dict[str, str]] = None,
        query_fields_from_url: Optional[List[str]] = None,
        request_timeout: int = 10,
    ):
        self.probe_url = probe_url
        self.probe_expected_status = probe_expected_status
        self.portal_fallback_url = portal_fallback_url
        self.form_id = form_id
        self.form_action_contains = form_action_contains
        self.button_text_contains = button_text_contains
        self.already_online_marker = already_online_marker
        self.default_form_fields = default_form_fields or {}
        self.query_fields_from_url = query_fields_from_url or []
        self.request_timeout = request_timeout

    def check_internet(self, session: requests.Session) -> bool:
        return has_internet(session, self.probe_url, self.probe_expected_status, self.request_timeout)

    def fetch_portal(self, session: requests.Session) -> Tuple[str, str]:
        return fetch_portal_page(session, self.probe_url, self.portal_fallback_url, self.request_timeout)

    def parse_form(self, html: str) -> Tuple[Dict[str, str], Dict[str, str]]:
        return parse_login_form(
            html,
            self.form_id,
            self.form_action_contains,
            self.button_text_contains,
        )

    def is_online_page(self, html: str) -> bool:
        if not self.already_online_marker:
            return False
        return portal_indicates_online(html, self.already_online_marker)

    def build_payload(self, form_inputs: Dict[str, str], portal_url: str) -> Dict[str, str]:
        return merge_form_data(
            form_inputs,
            portal_url,
            self.default_form_fields,
            self.query_fields_from_url,
        )

    def submit(self, session: requests.Session, portal_url: str, form_attrs: Dict[str, str], payload: Dict[str, str]) -> requests.Response:
        return submit_login_form(session, portal_url, form_attrs, payload, self.request_timeout)

    def login(self) -> int:
        session = requests.Session()

        if self.check_internet(session):
            print("DONE: Internet is reachable. Nothing to do.")
            return 0

        print("Internet not reachable. Attempting captive portal login ...")
        portal_url, portal_html = self.fetch_portal(session)

        if self.is_online_page(portal_html):
            print("DONE: Portal shows already online page. Treating connection as online.")
            return 0

        form_attrs, form_inputs = self.parse_form(portal_html)
        payload = self.build_payload(form_inputs, portal_url)

        response = self.submit(session, portal_url, form_attrs, payload)
        if response.ok:
            print("DONE: Login request sent. Rechecking internet access ...")
        else:
            print(f"WARNING: Login request returned HTTP {response.status_code}.")

        if self.check_internet(session):
            print("DONE: You are online!")
            return 0

        print("WARNING: Internet still not reachable. Portal may require extra steps.")
        return 1
