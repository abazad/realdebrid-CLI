#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
from getopt import GetoptError, gnu_getopt
from getpass import getpass
from hashlib import md5
from json import dump, load
from os import path, makedirs, getcwd, access, W_OK, X_OK
from sys import argv
from RDWorker import RDWorker, UnrestrictionError
from urllib2 import HTTPCookieProcessor, build_opener


def usage(status=0):
    """
    Print rdcli usage information
    """
    print 'Usage: rdcli [OPTIONS] LINK'

    print '\nOPTIONS:'
    print '  -h\tHelp. Display this help.'
    print '  -i\tInit. Force rdcli to ask for your login and password.'
    print '\tUseful if you made a typo or if you changed your login information since you first used rdcli.'
    print '  -l\tList. Write a list of the successfully unrestricted links on STDOUT, without downloading.'
    print '\t-t and -q options have no effect if -l is used.'
    print '  -o\tOutput directory. Download files into a specific directory.'
    print '  -p\tPassword. Provide a password for protected downloads.'
    print '  -q\tQuiet mode. No output will be generated.'
    print '  -t\tTest mode. Perform all operations EXCEPT file downloading.'
    # print '  -T\tTimeout. The maximum number of seconds to wait for a download to start.'

    print '\nLINK can be set of URLs to files you want to download (i.e. http://host.com/myFile.zip) ' \
          'or the path to a file containing them.'

    print '\nExample: rdcli http://host.com/myFile.zip'
    print 'Example: rdcli urls.txt'
    print 'Example: rdcli -t links-to-test.txt'

    print '\nReport rdcli bugs to https://github.com/MrMitch/realdebrid-CLI/issues/new'

    exit(status)


def ask_credentials():
    """
    Ask for user credentials
    """
    username = raw_input('What is your RealDebrid username?\n')
    raw_pass = getpass('What is your RealDebrid password '
                       '(won\'t be displayed and won\'t be stored as plain text)?')
    password = md5(raw_pass).hexdigest()

    return username, password


def save_credentials(conf_file, username, password):
    try:
        with open(conf_file, 'wb') as output:
            dump({'username': username, 'password': password}, output, indent=4)
    except BaseException as e:
        exit('Unable to save login information: %s' % str(e))


def main():
    """
    Main program
    """

    base = path.join(path.expanduser('~'), '.config', 'rdcli-py')
    conf_file = path.join(base, 'conf.json')
    cookie_file = path.join(base, 'cookie.txt')

    list = False
    test = False
    verbose = True
    timeout = 120

    download_password = ''
    output_dir = getcwd()

    def debug(s):
        if verbose:
            print s,

    # make sure the config dir exists
    if not path.exists(base):
        makedirs(base)

    worker = RDWorker(cookie_file)

    # parse command-line arguments
    try:
        opts, args = gnu_getopt(argv[1:], 'hiqtlp:o:T:')
    except GetoptError as e:
        print str(e)
        usage(1)

    for option, argument in opts:
        if option == '-h':
            usage()
        elif option == '-i':
            username, password = ask_credentials()
            save_credentials(conf_file, username, password)
        elif option == '-q':
            if not list:
                verbose = False
        elif option == '-t':
            if not list:
                test = True
        elif option == '-l':
            list = True
            test = False
            verbose = False
        elif option == '-o':
            output_dir = argument
        elif option == '-p':
            download_password = argument
        elif option == '-T':
            timeout = int(argument)

    # stop now if no download and no output wanted
    if test and not verbose:
        exit(0)

    # make sure we have something to process
    if len(args) > 0:
        output_dir = path.abspath(path.expanduser(output_dir))
        # ensure we can write in output directory
        if not output_dir == getcwd() and not path.exists(unicode(output_dir)):
            debug('%s no such directory' % unicode(output_dir))
            exit(1)
        else:
            if not access(output_dir, W_OK | X_OK):
                debug('Output directory not writable')
                exit(1)
            else:
                debug(u'Output directory: %s\n' % output_dir)

        # retrieve login info
        try:
            with open(conf_file, 'r') as conf:
                obj = load(conf)
                username = obj['username']
                password = obj['password']
        except BaseException:
            username, password = ask_credentials()
            save_credentials(conf_file, username, password)

        # login
        try:
            worker.login(username, password)
        except BaseException as e:
            exit('Login failed: %s' % str(e))

        if path.isfile(args[0]):
            with open(args[0], 'r') as f:
                links = f.readlines()
        else:
            links = args[0].splitlines()

        # unrestrict and download
        for link in links:
            link = link.strip()
            debug('\nUnrestricting %s' % link)

            try:
                unrestricted, filename = worker.unrestrict(link, download_password)
                debug(u'→ ' + unrestricted + '\n')

                if list:
                    print unrestricted
                elif not test:
                    fullpath = path.join(output_dir, filename)

                    try:
                        to_mb = lambda b: b / 1048576.
                        opener = build_opener(HTTPCookieProcessor(worker.cookies))
                        stream = opener.open(unrestricted)
                        info = stream.info().getheaders('Content-Length')

                        total_size = 0
                        if len(info):
                            total_size = float(info[0])
                            start = 'Downloading: %s (%.2f MB)\n' % (fullpath, to_mb(total_size))
                        else:
                            start = 'Downloading: %s (unknown size)\n' % fullpath

                        debug(start)

                        downloaded_size = 0
                        percentage = ''
                        with open(fullpath, 'wb') as output:
                            start = datetime.now()
                            while True:

                                try:
                                    content = stream.read(10240)  # 10 KB
                                    end = datetime.now()

                                    if not content:
                                        break

                                    output.write(content)
                                    downloaded_size += len(content)

                                    if total_size:
                                        percentage = ' [%3.2f%%]' % (downloaded_size * 100. / total_size)

                                    status = '\r%.3f MB%s' % (to_mb(downloaded_size), percentage)
                                    debug(status)
                                except KeyboardInterrupt:
                                    break

                            stream.close()

                        speed = to_mb(downloaded_size) / (end - start).total_seconds()
                        debug('\r%.2f MB%s downloaded in %s (≈ %.2f MB/s)\n'
                              % (to_mb(downloaded_size), percentage, str(end - start).split('.')[0], speed))

                    except BaseException as e:
                        debug('\nDownload failed: %s\n' % e)
            except UnrestrictionError as e:
                debug('→ WARNING, unrestriction failed (%s)' % str(e) + '\n')

        debug('End\n')
        return 0
    else:
        usage(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        exit('^C caught, exiting...')
