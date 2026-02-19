#!/usr/bin/python3
#
# Author:       Julian Reith
# E-Mail:       julianreith@gmx.de
# Version:      0.2
# Last Updated: 2025-01-01
#
# Description:
# Generic captive-portal login script (Telekom Hotspot blueprint).
# It checks internet connectivity and, if blocked, requests the portal page,
# extracts the login form, and "presses" the submit button by sending the form
# request. The configuration at the top should be enough to adapt to other
# portals (URL, form selector, and required fields).

import sys

from captive_portal import CaptivePortalClient

### CONFIGURATION (edit for other portals) ###
PROBE_URL = "http://connectivitycheck.gstatic.com/generate_204"
PROBE_EXPECTED_STATUS = 204

PORTAL_FALLBACK_URL = "https://hotspot.t-mobile.net/"

FORM_ID = None
FORM_ACTION_CONTAINS = "login"

BUTTON_TEXT_CONTAINS = "online gehen"

ALREADY_ONLINE_TEXT_CONTAINS = "jetzt surfen"

DEFAULT_FORM_FIELDS = {}

QUERY_FIELDS_FROM_PORTAL_URL = ["sessionId", "mac", "apMac", "clientMac"]

REQUEST_TIMEOUT = 10


def main() -> int:
    client = CaptivePortalClient(
        probe_url=PROBE_URL,
        probe_expected_status=PROBE_EXPECTED_STATUS,
        portal_fallback_url=PORTAL_FALLBACK_URL,
        form_id=FORM_ID,
        form_action_contains=FORM_ACTION_CONTAINS,
        button_text_contains=BUTTON_TEXT_CONTAINS,
        already_online_marker=ALREADY_ONLINE_TEXT_CONTAINS,
        default_form_fields=DEFAULT_FORM_FIELDS,
        query_fields_from_url=QUERY_FIELDS_FROM_PORTAL_URL,
        request_timeout=REQUEST_TIMEOUT,
    )
    return client.login()


if __name__ == "__main__":
    sys.exit(main())
