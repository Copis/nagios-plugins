#!/usr/bin/env python
# Copyright (c) 2018, 2019, 2020 Pure Storage, Inc.
#
# * Overview
#
# This short Nagios/Icinga plugin code shows  how to build a simple plugin to monitor Pure Storage FlashArrays.
# The Pure Storage Python REST Client is used to query the FlashArray alert messages.
#
# * Installation
#
# The script should be copied to the Nagios plugins directory on the machine hosting the Nagios server or the NRPE
# for example the /usr/lib/nagios/plugins folder.
# Change the execution rights of the program to allow the execution to 'all' (usually chmod 0755).
#
# * Dependencies
#
#  nagiosplugin      helper Python class library for Nagios plugins (https://github.com/mpounsett/nagiosplugin)
#  purestorage       Pure Storage Python REST Client (https://github.com/purestorage/rest-client)


"""Pure Storage FlashArray alert messages status
   Nagios plugin to check the general state of a Pure Storage FlashArray from the internal alert messages.
   The plugin has two mandatory arguments:  'endpoint', which specifies the target FA, 'apitoken', which
   specifies the autentication token for the REST call session. The FlashArray is considered unhealty if
   there is any pending message that reports a warning or critical status of one or more components
"""

import argparse
import logging
import logging.handlers
import nagiosplugin
import purestorage

# Disable warnings using urllib3 embedded in requests or directly
try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
except:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class PureFAalert(nagiosplugin.Resource):
    """Pure Storage FlashArray alerts
    Reports the status of all open messages on FlashArray
    """

    def __init__(self, endpoint, apitoken):
        self.endpoint = endpoint
        self.apitoken = apitoken
        self.info = 0
        self.warn = 0
        self.crit = 0
        self.logger = logging.getLogger(self.name)
        handler = logging.handlers.SysLogHandler(address = '/dev/log')
        handler.setLevel(logging.ERROR)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    @property
    def name(self):
        return 'PURE_FA_ALERT'

    def get_alerts(self):
        """Gets active alerts from FlashArray."""
        fainfo = {}
        try:
            fa = purestorage.FlashArray(self.endpoint, api_token=self.apitoken)
            fainfo = fa.list_messages(open = True)
            fa.invalidate_cookie()
        except Exception as e:
            raise nagiosplugin.CheckError(f'FA REST call returned "{e}"')
        
        return(fainfo)

    def probe(self):

        fainfo = self.get_alerts()
        if not fainfo:
            return [nagiosplugin.Metric('critical', 0, min=0),
                    nagiosplugin.Metric('warning', 0, min=0),
                    nagiosplugin.Metric('info', 0, min=0)]
        # Increment each counter for each type of event
        for alert in fainfo:
            if alert['current_severity'] == 'critical':
                self.crit += 1
            elif alert['current_severity'] == 'warning':
                self.warn += 1
            elif alert['current_severity'] == 'info':
                self.info += 1
        return [nagiosplugin.Metric('critical', self.crit, min=0),
                nagiosplugin.Metric('warning', self.warn, min=0),
                nagiosplugin.Metric('info', self.info, min=0)]


def parse_args():
    argp = argparse.ArgumentParser()
    argp.add_argument('endpoint', help="FA hostname or ip address")
    argp.add_argument('apitoken', help="FA api_token")
    argp.add_argument('--warning-crit', metavar='RANGE',
                      help='warning if number of critical messages is outside RANGE')
    argp.add_argument('--critical-crit', metavar='RANGE',
                      help='critical if number of critical messages is outside RANGE')
    argp.add_argument('--warning-warn', metavar='RANGE',
                      help='warning if number of warning messages is outside RANGE')
    argp.add_argument('--critical-warn', metavar='RANGE',
                      help='critical if number of warning messages is outside RANGE')
    argp.add_argument('--warning-info', metavar='RANGE',
                      help='warning if number of info messages is outside RANGE')
    argp.add_argument('--critical-info', metavar='RANGE',
                      help='critical if number of info messages is outside RANGE')
    argp.add_argument('-v', '--verbose', action='count', default=0,
                      help='increase output verbosity (use up to 3 times)')
    argp.add_argument('-t', '--timeout', default=30,
                      help='abort execution after TIMEOUT seconds')
    return argp.parse_args()


@nagiosplugin.guarded
def main():
    args = parse_args()
    check = nagiosplugin.Check(
        PureFAalert(args.endpoint, args.apitoken),
        nagiosplugin.ScalarContext(
            'critical', args.warning_crit, args.critical_crit,
            fmt_metric='{value} critical messages'),
        nagiosplugin.ScalarContext(
            'warning', args.warning_warn, args.critical_warn,
            fmt_metric='{value} warning messages'),
        nagiosplugin.ScalarContext(
            'info', args.warning_info, args.critical_info,
            fmt_metric='{value} info messages'))
    check.main(args.verbose, args.timeout)

if __name__ == '__main__':
    main()
