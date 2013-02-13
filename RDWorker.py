__author__ = 'MrMitch'

from cookielib import MozillaCookieJar
from getpass import getpass
from hashlib import md5
from HTMLParser import HTMLParser
from json import load
from urllib import unquote, urlencode
from urllib2 import build_opener, HTTPCookieProcessor
from os import path


class UnrestrictionError(Exception):

    UNSUPPORTED = 4
    UPGRADE_NEEDED = 2
    NO_SERVER = 9
    UNAVAILABLE = 11

    def __init__(self, message, code=-1):
        self.message = message
        self.code = code

    def __str__(self):
        return u'[Error %i] %s' % (self.code, self.message)


class RDWorker:
    """
    Worker class to perform RealDebrid related actions:
    - format login info so they can be used by RealDebrid
    - login
    - unrestricting links
    - keeping cookies
    """

    _endpoint = 'http://www.real-debrid.com/ajax/%s'

    def __init__(self, cookie_file, conf_file):
        self._cookie_file = cookie_file
        self._conf_file = conf_file
        self.cookies = MozillaCookieJar(self._cookie_file)

    def ask_login(self):
        username = raw_input('What is your RealDebrid username?\n')
        raw_pass = getpass('What is your RealDebrid password '
                           '(won\'t be displayed and won\'t be stored as plain text)?\n')
        password = md5(raw_pass).hexdigest()

        try:
            with open(self._conf_file, 'w') as file:
                file.write(username + ':' + password)
        except IOError:
            raise

        return {'user': username, 'pass': password}

    def login(self, info):
        if path.isfile(self._cookie_file):
            self.cookies.load(self._cookie_file)

            for cookie in self.cookies:
                if cookie.name == 'auth' and not cookie.is_expired():
                    return  # no need for a new cookie

        # request a new cookie if no valid cookie is found or if it's expired
        opener = build_opener(HTTPCookieProcessor(self.cookies))
        try:
            response = opener.open(self._endpoint % 'login.php?%s' % urlencode(info))
            resp = load(response)
            opener.close()

            if resp['error'] == 0:
                self.cookies.save(self._cookie_file)
            else:
                raise Exception('Login error: %s' % unicode(resp['message']))
        except Exception as e:
            raise Exception('Login failed: %s' % str(e))

    def unrestrict(self, link, password=''):
        opener = build_opener(HTTPCookieProcessor(self.cookies))
        response = opener.open(self._endpoint % 'unrestrict.php?%s' % urlencode({'link': link, 'password': password}))
        resp = load(response)
        opener.close()

        if resp['error'] == 0:
            return resp['main_link']
        else:
            raise UnrestrictionError(resp['message'], resp['error'])

    def get_filename_from_url(self, original):
        parser = HTMLParser()
        filename = parser.unescape(unquote(path.basename(original)))
        return filename.encode('latin-1').decode('utf-8').replace('/', '_')
