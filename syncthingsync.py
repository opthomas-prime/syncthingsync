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
WAIT_S_AFTER_SCAN = 1
WAIT_S_RECHECK_STATUS = 2


def get_args():
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('--config', default=DEF_CONF_FILE, help='config file (defaults to %s)' % DEF_CONF_FILE)
    parser.add_argument('folder', help='folder to sync (label)')
    return parser.parse_args()


def load_conf(conf_file):
    from configparser import ConfigParser
    expanded_path = os.path.expanduser(conf_file)
    if not os.path.isfile(expanded_path):
        return None
    conf = ConfigParser()
    conf.read(expanded_path)
    return conf._sections


def find_folders(folder_name, conns):
    folders = []
    for conn in conns:
        print('looking up \'%s\' on %s' % (folder_name, conn['api']))
        headers = {'X-API-Key': conn['key']}
        r = requests.get(conn['api'] + '/system/config', headers=headers)
        if r.status_code != 200:
            return None
        try:
            config = json.loads(r.text)
            for conf_folder in config['folders']:
                if conf_folder['label'] == folder_name:
                    print('found \'%s\'' % conf_folder['id'])
                    folders.append((conn, conf_folder['id']))
        except Exception:
            return None
    return folders


def trigger_scan(folders):
    for folder in folders:
        print('triggering scan on %s / \'%s\'' % (folder[0]['api'], folder[1]))
        headers = {'X-API-Key': folder[0]['key']}
        r = requests.post(folder[0]['api'] + '/db/scan?folder=' + folder[1], headers=headers)
        if r.status_code != 200:
            return False
    return True


def synced(status):
    if status['globalBytes'] == status['localBytes'] and status['globalDeleted'] == status['localDeleted'] \
            and status['globalFiles'] == status['localFiles'] and status['inSyncBytes'] == status['localBytes'] \
            and status['inSyncFiles'] == status['localFiles'] and status['needBytes'] == 0 and status['needFiles'] == 0:
        return True
    return False


def wait_for_completion(folders):
    for folder in folders:
        print('checking status of %s / \'%s\'' % (folder[0]['api'], folder[1]))
        headers = {'X-API-Key': folder[0]['key']}
        while True:
            r = requests.get(folder[0]['api'] + '/db/status?folder=' + folder[1], headers=headers)
            status = None
            if r.status_code != 200:
                return False
            try:
                status = json.loads(r.text)
            except Exception:
                return False
            if not synced(status):
                print('not synced yet, waiting %d seconds' % WAIT_S_RECHECK_STATUS)
                time.sleep(WAIT_S_RECHECK_STATUS)
            else:
                print('synced')
                break
    return True


def main():
    args = get_args()
    conf = load_conf(args.config)
    conns = []
    for device in conf['devices']['devices'].split(','):
        conns.append(conf[device.strip()])

    folders = find_folders(args.folder, conns)
    if not folders:
        print('error while looking up folder ids')
        sys.exit(1)

    result = trigger_scan(folders)
    if not result:
        print('error while triggering scan')
        sys.exit(1)

    print('waiting %d seconds' % WAIT_S_AFTER_SCAN)
    time.sleep(WAIT_S_AFTER_SCAN)

    result = wait_for_completion(folders)
    if not result:
        print('error while waiting for completion')
        sys.exit(1)

    print('%s in sync' % args.folder)


if __name__ == '__main__':
    main()
