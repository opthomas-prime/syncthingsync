#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time

try:
    import requests
except ImportError:
    print('missing requests module')
    sys.exit(1)

DEF_CONF_FILE = '~/.syncthingsync.conf'


def get_args():
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('--config', default=DEF_CONF_FILE, help='config file (defaults to %s)' % DEF_CONF_FILE)
    parser.add_argument('--webservice', help='start as webservice', action='store_true', default=False)
    parser.add_argument('--folder', help='folder to sync (id) - not needed in webservice mode')
    return parser.parse_args()


def load_conf(conf_file):
    from configparser import ConfigParser
    expanded_path = os.path.expanduser(conf_file)
    if not os.path.isfile(expanded_path):
        return None
    conf = ConfigParser()
    conf.read(expanded_path)
    return conf._sections


def check_folder_id(folder_id, api, key):
    headers = {'X-API-Key': key}
    try:
        r = requests.get(api + '/system/config', headers=headers)
        if r.status_code != 200:
            return False, None
        for entry in json.loads(r.text)['folders']:
            if entry['id'] == folder_id:
                return True, entry['id']
        return True, None
    except Exception as e:
        print(e)
        return False, None


def trigger_scan(location):
    headers = {'X-API-Key': location[0]['key']}
    try:
        r = requests.post(location[0]['api'] + '/db/scan?folder=' + location[1], headers=headers)
        if r.status_code != 200:
            return False
    except Exception as e:
        print(e)
        return False
    return True


def synced(status):
    if status['globalBytes'] == status['localBytes'] \
            and status['globalDeleted'] == status['localDeleted'] \
            and status['globalFiles'] == status['localFiles'] \
            and status['inSyncBytes'] == status['localBytes'] \
            and status['inSyncFiles'] == status['localFiles'] \
            and status['needBytes'] == 0 \
            and status['needFiles'] == 0:
        return True
    return False


def check_synced(location):
    headers = {'X-API-Key': location[0]['key']}
    try:
        r = requests.get(location[0]['api'] + '/db/status?folder=' + location[1], headers=headers)
        if r.status_code != 200:
            return False, None
        status = json.loads(r.text)
        if synced(status):
            return True, True
        return True, False
    except Exception as e:
        print(e)
        return False, None


def main():
    args = get_args()
    conf = load_conf(args.config)
    if not conf:
        print('error while reading config file')
        sys.exit(1)

    if args.webservice:
        import syncthingsyncws
        syncthingsyncws.serve(conf)
        sys.exit(0)

    if not args.folder:
        print('no folder specified')
        sys.exit(1)

    conns = []
    for device in conf['general']['devices'].split(','):
        conns.append(conf[device.strip()])
        # e.g. OrderedDict([('api', 'http://a:8384/rest'), ('key', 'SUPERSECRET')])

    folder_locs = []
    for conn in conns:
        print('looking up \'%s\' on %s' % (args.folder, conn['api']))
        status, folder_id = check_folder_id(args.folder, conn['api'], conn['key'])
        if not status:
            print('error while looking up folder id')
            sys.exit(1)
        if not folder_id:
            print('folder not found on this device')
        else:
            print('found \'%s\'' % folder_id)
            folder_locs.append((conn, folder_id))
            # e.g. (OrderedDict([('api', 'http://a:8384/rest'), ('key', 'SUPERSECRET')]), 'abcde-abcde')

    if len(folder_locs) == 0:
        print('folder not found')
        sys.exit(1)

    for folder_loc in folder_locs:
        print('triggering scan on %s / \'%s\'' % (folder_loc[0]['api'], folder_loc[1]))
        if not trigger_scan(folder_loc):
            print('error while triggering scan')
            sys.exit(1)

    print('waiting %d seconds' % int(conf['general']['s_before_status_check']))
    time.sleep(int(conf['general']['s_before_status_check']))

    for folder_loc in folder_locs:
        print('checking status of %s / \'%s\'' % (folder_loc[0]['api'], folder_loc[1]))
        while True:
            status, in_sync = check_synced(folder_loc)
            if not status:
                print('error while waiting for completion')
                sys.exit(1)
            if not in_sync:
                print('not synced yet, waiting %d seconds' % int(conf['general']['s_interval_status_check']))
                time.sleep(int(conf['general']['s_interval_status_check']))
            else:
                print('synced')
                break

    print('%s in sync' % args.folder)


if __name__ == '__main__':
    main()
