#!/usr/bin/env python
# Copyright (c) 2018, 2019, 2020 Pure Storage, Inc.
#
# * Overview
#
# This short Nagios/Icinga plugin code shows  how to build a simple plugin to monitor Pure Storage FlashArrays.
# The Pure Storage Python REST Client is used to query the FlashArray occupancy indicators.
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

"""Pure Storage FlashArray occupancy status

   Nagios plugin to retrieve the overall occupancy from a Pure Storage FlashArray or from a single volume.
   Storage occupancy indicators are collected from the target FA using the REST call.
   The plugin has two mandatory arguments:  'endpoint', which specifies the target FA and 'apitoken', which
   specifies the autentication token for the REST call session. A third optional parameter, 'volname' can
   be used to check a specific named value. The optional values for the warning and critical thresholds have
   different meausure units: they must be expressed as percentages in the case of checkig the whole FlashArray
   occupancy, while they must be integer byte units if checking a single volume. You can use the -p flag to
   switch to percentages for per volume checking.

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


class PureFAoccpy(nagiosplugin.Resource):
    """Pure Storage FlashArray  occupancy

    Calculates the overall FA storage occupancy or a single volume capacity.

    """

    def __init__(self, endpoint, apitoken, volname, percentage):
        self.endpoint = endpoint
        self.apitoken = apitoken
        self.volname = volname
        self.percentage = percentage
        self.logger = logging.getLogger(self.name)
        handler = logging.handlers.SysLogHandler(address = '/dev/log')
        handler.setLevel(logging.ERROR)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    @property
    def name(self):
        if (self.volname is None):
            return 'PURE_FA_OCCUPANCY'
        else:
            return 'PURE_FA_VOL_OCCUPANCY'


    def get_space(self):
        """Gets performance counters from flasharray."""
        fainfo = {}
        try:
            fa = purestorage.FlashArray(self.endpoint, api_token=self.apitoken)
            if (self.volname is None):
                fainfo = fa.get(space=True)[0]
            else:
                fainfo = fa.get_volume(self.volname, space=True)
            fa.invalidate_cookie()
        except Exception as e:
            raise nagiosplugin.CheckError(f'FA REST call returned "{e}"')
        return(fainfo)

    def probe(self):

        fainfo = self.get_space()
        if not fainfo:
            return ''
        if (self.volname is None):
            occupancy = round(float(fainfo.get('total'))/float(fainfo.get('capacity')), 2) * 100
            metric = nagiosplugin.Metric('FA occupancy', occupancy, '%', min=0, max=100, context='occupancy')
        elif self.percentage:
            occupancy = round(float(fainfo.get('total'))/float(fainfo.get('size')), 2) * 100
            metric = nagiosplugin.Metric(self.volname + ' occupancy', occupancy, '%', min=0, max=100, context='occupancy')
        else:
            occupancy = int(fainfo.get('volumes'))
            metric = nagiosplugin.Metric(self.volname + ' occupancy', occupancy, 'B', min=0, context='occupancy')
        return metric


def parse_args():
    argp = argparse.ArgumentParser()
    argp.add_argument('endpoint', help="FA hostname or ip address")
    argp.add_argument('apitoken', help="FA api_token")
    argp.add_argument('--vol', help="FA volume name. If omitted the whole FA occupancy is checked")
    
    argp.add_argument('-w', '--warning', metavar='RANGE', default='',
                      help='return warning if occupancy is outside RANGE. Value has to be expressed in percentage for the FA, while in bytes for the single volume')
    argp.add_argument('-c', '--critical', metavar='RANGE', default='',
                      help='return critical if occupancy is outside RANGE. Value has to be expressed in percentage for the FA, while in bytes for the single volume')
    argp.add_argument('-p', '--percentage', action='store_true',
                      help='Set this flag if you want to use percentages instead of bytes for volume space usage. This flag does nothing when checking the whole array')
    argp.add_argument('-v', '--verbose', action='count', default=0,
                      help='increase output verbosity (use up to 3 times)')
    argp.add_argument('-t', '--timeout', default=30,
                      help='abort execution after TIMEOUT seconds')
    return argp.parse_args()


@nagiosplugin.guarded
def main():
    args = parse_args()
    check = nagiosplugin.Check( PureFAoccpy(args.endpoint, args.apitoken, args.vol, args.percentage) )
    check.add(nagiosplugin.ScalarContext('occupancy', args.warning, args.critical))
    check.main(args.verbose, args.timeout)

if __name__ == '__main__':
    main()
