#!/usr/bin/python3
#
# Author:       Julian Reith (original inetiu inspiration)
# E-Mail:       julianreith@gmx.de
# Version:      0.1
# Last Updated: 2025-01-01
#
# Description:
# Generic captive-portal login script (BayernWLAN blueprint).
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
PORTAL_FALLBACK_URL = (
    "https://hotspot.vodafone.de/bayern/"
    "?A=B&RequestedURI=http%3A%2F%2Fdetectportal.firefox.com%2Fcanonical.html"
)

# Portal form identification rules.
FORM_ID = "loginForm"
FORM_ACTION_CONTAINS = "/api/v4/login"

# Default fields that are commonly required by BayernWLAN.
DEFAULT_FORM_FIELDS = {
    "loginProfile": "6",
    "accessType": "termsOnly",
    "action": "redirect",
    "portal": "bayern",
}

# Optional query parameters copied from the portal URL when missing in the form.
QUERY_FIELDS_FROM_PORTAL_URL = ["sessionID"]

# Timeouts (seconds).
REQUEST_TIMEOUT = 10

### END OF CONFIGURATION ###


class CaptivePortalFormParser(HTMLParser):
    def __init__(self, form_id: Optional[str], action_contains: Optional[str]) -> None:
        super().__init__()
        self.form_id = form_id
        self.action_contains = action_contains
        self.active_form: Optional[Dict[str, str]] = None
        self.forms: List[Dict[str, str]] = []
        self.inputs: Dict[str, Dict[str, str]] = {}

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attrs_dict = {key: value for key, value in attrs if key}

        if tag == "form":
            if self._matches_form(attrs_dict):
                self.active_form = attrs_dict
                self.forms.append(attrs_dict)
                self.inputs[id(attrs_dict)] = {}
            return

        if tag == "input" and self.active_form is not None:
            name = attrs_dict.get("name")
            value = attrs_dict.get("value", "")
            input_type = attrs_dict.get("type", "").lower()
            if name and input_type != "submit":
                self.inputs[id(self.active_form)][name] = value

    def _matches_form(self, attrs_dict: Dict[str, str]) -> bool:
        if self.form_id and attrs_dict.get("id") == self.form_id:
            return True
        if self.action_contains and self.action_contains in attrs_dict.get("action", ""):
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
    parser = CaptivePortalFormParser(FORM_ID, FORM_ACTION_CONTAINS)
    parser.feed(html)

    if not parser.forms:
        raise RuntimeError("No matching login form found in portal HTML.")

    form_attrs = parser.forms[0]
    form_inputs = parser.inputs.get(id(form_attrs), {})
    return form_attrs, form_inputs


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
    action = form_attrs.get("action", "")
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
