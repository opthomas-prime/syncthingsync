#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import syncthingsync as sts
import time

try:
    import bottle
    import gunicorn
except ImportError:
    print('missing bottle or gunicorn module')
    sys.exit(1)

sts_conf = None


@bottle.route('/sync/<folder>')
def sync(folder):
    global sts_conf

    conns = []
    for device in sts_conf['general']['devices'].split(','):
        conns.append(sts_conf[device.strip()])

    folder_locs = []
    for conn in conns:
        status, folder_id = sts.check_folder_id(folder, conn['api'], conn['key'])
        if not status:
            return bottle.HTTPResponse(status=500, body='error while looking up folder id on %s\n' % conn['api'])
        if folder_id:
            folder_locs.append((conn, folder_id))

    if len(folder_locs) == 0:
        return bottle.HTTPResponse(status=500, body='folder %s not found\n' % folder)

    for folder_loc in folder_locs:
        if not sts.trigger_scan(folder_loc):
            return bottle.HTTPResponse(status=500, body='error while triggering scan on %s\n' % folder_loc[0]['api'])

    time.sleep(int(sts_conf['general']['s_before_status_check']))

    for folder_loc in folder_locs:
        while True:
            status, in_sync = sts.check_synced(folder_loc)
            if not status:
                return bottle.HTTPResponse(status=500,
                                           body='error while waiting for completion on %s\n' % folder_loc[0]['api'])
            if not in_sync:
                time.sleep(int(sts_conf['general']['s_interval_status_check']))
            else:
                break

    return bottle.HTTPResponse(status=200, body='%s in sync\n' % folder)


def serve(conf):
    global sts_conf
    sts_conf = conf
    sys.argv = sys.argv[:1]
    bottle.run(host='0.0.0.0', port=8080, server='gunicorn', workers=8)
