#!/usr/bin/python3
#
# Author:       Julian Reith
# E-Mail:       julianreith@gmx.de
# Version:      0.1
# Last Updated: 2025-01-01
#
# Description:
# Generic captive-portal login script (Telekom Hotspot blueprint).
# It checks internet connectivity and, if blocked, requests the portal page,
# extracts the login form, and "presses" the submit button by sending the form
# request. The configuration at the top should be enough to adapt to other
# portals (URL, form selector, and required fields).

from __future__ import annotations

import sys
import urllib.parse
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

import requests

### CONFIGURATION (edit for other portals) ###
# Connectivity check: use a non-HTTPS URL to ensure captive portals can intercept.
PROBE_URL = "http://connectivitycheck.gstatic.com/generate_204"
PROBE_EXPECTED_STATUS = 204

# Fallback portal URL (if the probe did not return a login page).
PORTAL_FALLBACK_URL = "https://hotspot.t-mobile.net/"

# Portal form identification rules.
FORM_ID = None
FORM_ACTION_CONTAINS = "login"

# Button text that should trigger the login request.
BUTTON_TEXT_CONTAINS = "online gehen"

# If this text is shown, Telekom already granted internet access.
ALREADY_ONLINE_TEXT_CONTAINS = "jetzt surfen"

# Default fields that are commonly required by Telekom Hotspot.
DEFAULT_FORM_FIELDS = {}

# Optional query parameters copied from the portal URL when missing in the form.
QUERY_FIELDS_FROM_PORTAL_URL = ["sessionId", "mac", "apMac", "clientMac"]

# Timeouts (seconds).
REQUEST_TIMEOUT = 10

### END OF CONFIGURATION ###


class CaptivePortalFormParser(HTMLParser):
    def __init__(
        self,
        form_id: Optional[str],
        action_contains: Optional[str],
        button_text_contains: Optional[str],
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


def has_internet(session: requests.Session) -> bool:
    try:
        response = session.get(PROBE_URL, timeout=REQUEST_TIMEOUT, allow_redirects=False)
    except requests.RequestException:
        return False
    return response.status_code == PROBE_EXPECTED_STATUS


def fetch_portal_page(session: requests.Session) -> Tuple[str, str]:
    try:
        response = session.get(PROBE_URL, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if response.text and "text/html" in response.headers.get("Content-Type", ""):
            return response.url, response.text
    except requests.RequestException:
        pass

    response = session.get(PORTAL_FALLBACK_URL, timeout=REQUEST_TIMEOUT)
    return response.url, response.text


def parse_login_form(html: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    parser = CaptivePortalFormParser(FORM_ID, FORM_ACTION_CONTAINS, BUTTON_TEXT_CONTAINS)
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
                f"No matching login button found (expected text: {BUTTON_TEXT_CONTAINS!r})."
            )
        selected_index = matching_indices[0]

    form_attrs_raw = parser.forms[selected_index]
    form_attrs: Dict[str, str] = {k: v for k, v in form_attrs_raw.items() if v is not None}
    form_inputs = parser.inputs.get(selected_index, {})
    return form_attrs, form_inputs


def portal_indicates_online(html: str) -> bool:
    marker = ALREADY_ONLINE_TEXT_CONTAINS.strip().lower()
    return bool(marker) and marker in html.lower()


def merge_form_data(
    form_inputs: Dict[str, str],
    portal_url: str,
    extra_fields: Dict[str, str],
) -> Dict[str, str]:
    payload = {key: value for key, value in form_inputs.items() if key}

    parsed_url = urllib.parse.urlparse(portal_url)
    portal_query = urllib.parse.parse_qs(parsed_url.query)
    for field in QUERY_FIELDS_FROM_PORTAL_URL:
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
) -> requests.Response:
    action = form_attrs.get("action", "").rstrip("?")
    method = form_attrs.get("method", "get").lower()

    submit_url = urllib.parse.urljoin(portal_url, action)
    if method == "post":
        return session.post(submit_url, data=payload, timeout=REQUEST_TIMEOUT)
    return session.get(submit_url, params=payload, timeout=REQUEST_TIMEOUT)


def main() -> int:
    session = requests.Session()

    if has_internet(session):
        print("DONE: Internet is reachable. Nothing to do.")
        return 0

    print("Internet not reachable. Attempting captive portal login ...")
    portal_url, portal_html = fetch_portal_page(session)

    if portal_indicates_online(portal_html):
        print(
            "DONE: Portal shows 'Jetzt surfen' page. Treating connection as online/already unlocked."
        )
        return 0

    form_attrs, form_inputs = parse_login_form(portal_html)
    payload = merge_form_data(form_inputs, portal_url, DEFAULT_FORM_FIELDS)

    response = submit_login_form(session, portal_url, form_attrs, payload)
    if response.ok:
        print("DONE: Login request sent. Rechecking internet access ...")
    else:
        print(f"WARNING: Login request returned HTTP {response.status_code}.")

    if has_internet(session):
        print("DONE: You are online!")
        return 0

    print("WARNING: Internet still not reachable. Portal may require extra steps.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
