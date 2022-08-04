import requests
from fake_user_agent import user_agent

from .errors import call_on_error
from .settings import OP


def fetch(url, session):
    ua = user_agent()
    headers = {"User-Agent": ua}
    session.headers.update(headers)
    attempt = 0

    while True:
        try:
            r = session.get(url, timeout=9.05)
        except requests.exceptions.HTTPError as e:
            attempt = call_on_error(e, url, attempt, OP[0])
        except requests.exceptions.ConnectTimeout as e:
            attempt = call_on_error(e, url, attempt, OP[0])
        except requests.exceptions.ConnectionError as e:
            attempt = call_on_error(e, url, attempt, OP[0])
        except requests.exceptions.ReadTimeout as e:
            attempt = call_on_error(e, url, attempt, OP[0])
        except Exception as e:
            attempt = call_on_error(e, url, attempt, OP[0])
        else:
            if r.status_code != 200:  # only a 200 response has a response body
                attempt = call_on_error(r.status_code, url, attempt, OP[0])
            return r
