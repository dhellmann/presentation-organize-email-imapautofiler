#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
"""

import argparse
import email.parser
import getpass
import imaplib
import logging
import sys

import imapclient

from imapautofiler import actions
from imapautofiler import config
from imapautofiler import rules

LOG = logging.getLogger('imapautofiler')


def get_message(conn, msg_id):
    """Return a Message from the current mailbox.

    Get the body of the message and create a Message object, one line
    at a time (skipping the first line that includes the server
    response).

    """
    email_parser = email.parser.BytesFeedParser()
    response = conn.fetch([msg_id], ['BODY.PEEK[HEADER]'])
    email_parser.feed(response[msg_id][b'BODY[HEADER]'])
    return email_parser.close()


def list_mailboxes(cfg, debug, conn):
    for f in conn.list_folders():
        print(f[-1])


def process_rules(cfg, debug, conn):
    num_messages = 0
    num_processed = 0

    for mailbox in cfg['mailboxes']:      # multiple mailboxes allowed
        mailbox_name = mailbox['name']
        conn.select_folder(mailbox_name)

        mailbox_rules = [                 # convert data to instances
            rules.factory(r, cfg)
            for r in mailbox['rules']
        ]

        msg_ids = conn.search(['ALL'])

        for msg_id in msg_ids:
            num_messages += 1
            message = get_message(conn, msg_id)

            for rule in mailbox_rules:
                if rule.check(message):
                    action = actions.factory(rule.get_action(), cfg)
                    action.invoke(conn, msg_id, message)
                    num_processed += 1
                    break

        # Remove messages that we just moved.
        conn.expunge()


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config-file',
        default='~/.imapautofiler.yml')
    parser.add_argument(
        '--list-mailboxes',
        default=False,
        action='store_true',
        help='instead of processing rules, print a list of mailboxes')
    args = parser.parse_args()

    try:
        cfg = config.get_config(args.config_file)
        conn = imapclient.IMAPClient(
            cfg['server']['hostname'],
            use_uid=True,
            ssl=True,
        )
        username = cfg['server']['username']
        password = cfg['server'].get('password')
        if not password:
            password = getpass.getpass(
                'Password for {}:'.format(username))
        conn.login(username, password)
        try:
            if args.list_mailboxes:
                list_mailboxes(cfg, args.debug, conn)
            else:
                process_rules(cfg, args.debug, conn)
        finally:
            try:
                conn.close()
            except:
                pass
            conn.logout()
    except Exception as err:
        if args.debug:
            raise
        parser.error(err)
    return 0


if __name__ == '__main__':
    sys.exit(main())
