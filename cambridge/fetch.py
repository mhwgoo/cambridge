import requests
from fake_user_agent import user_agent

from cambridge.errors import call_on_error
from cambridge.settings import OP
from cambridge.log import logger


def fetch(url, session):
    ua = user_agent()
    headers = {"User-Agent": ua}
    session.headers.update(headers)
    attempt = 0

    while True:
        try:
            logger.debug(f"{OP[0]} {url}")
            r = session.get(url, timeout=9.05)
        except requests.exceptions.HTTPError as e:
            attempt = call_on_error(e, url, attempt, OP[2])
        except requests.exceptions.ConnectTimeout as e:
            attempt = call_on_error(e, url, attempt, OP[2])
        except requests.exceptions.ConnectionError as e:
            attempt = call_on_error(e, url, attempt, OP[2])
        except requests.exceptions.ReadTimeout as e:
            attempt = call_on_error(e, url, attempt, OP[2])
        except Exception as e:
            attempt = call_on_error(e, url, attempt, OP[2])
        else:
            return r
