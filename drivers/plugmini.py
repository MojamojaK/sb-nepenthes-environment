# references
# https://qiita.com/hiratarich/items/00be23735ac6001ff74b
# https://github.com/OpenWonderLabs/SwitchBotAPI-BLE/blob/latest/devicetypes/plugmini.md
# https://masahito.hatenablog.com/entry/2021/10/02/095828
# https://bleak.readthedocs.io/en/latest/index.html
# https://github.com/hbldh/bleak/issues/59
# https://qiita.com/pbjpkas/items/d7a2225b9670b759162d

import re
import sys
import logging
import pexpect

logger = logging.getLogger(__name__)

_MAC_RE = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')


def switchbotplugmini(address, operation):
    '''! trigger_device brief.
    turnoff, turnon, toggle, readstate the SwitchBot Plug Mini
    @return : '0000':Error, '0001':Timeout, '0100':Off, '0180':On
    '''
    if not _MAC_RE.match(address):
        raise ValueError(f"Invalid MAC address: {address}")
    logger.debug("Connecting to %s for %s", address, operation)
    con = pexpect.spawn('gatttool -b ' + address + ' -I') # remove "-t random" for Plug Mini
    con.expect(r'\[LE\]>')
    retry = 3
    index = 0
    while retry > 0 and 0 == index:
        con.sendline('connect')
        # To compatible with different Bluez versions
        index = con.expect(
            ['Error', r'\[CON\]', r'Connection successful.*\[LE\]>', pexpect.exceptions.TIMEOUT])
        retry -= 1
    if 0 == index:
        logger.warning("Connection error for %s", address)
        return False, '0000'
    elif 3 == index:
        logger.warning("Connection timeout for %s", address)
        return False, '0001'

    logger.debug("Connection successful to %s", address)
    con.sendline('char-desc')
    con.expect([r'\[CON\]', 'cba20002-224d-11e6-9fb8-0002a5d5c51b'])
    cmd_handle = con.before.decode('utf-8').split('\n')[-1].split()[2].strip(',')
    if operation == 'turnoff':
        con.sendline('char-write-cmd ' + cmd_handle + ' 570f50010100')
    elif operation == 'turnon':
        con.sendline('char-write-cmd ' + cmd_handle + ' 570f50010180')
    elif operation == 'toggle':
        con.sendline('char-write-cmd ' + cmd_handle + ' 570f50010280')
    elif operation == 'readstate':
        con.sendline('char-write-cmd ' + cmd_handle + ' 570f5101')
    else:
        logger.warning("Unsupported command: %s", operation)
        return False, '0000'

    con.expect(r'\[LE\]>')
    con.sendline('char-read-uuid cba20003-224d-11e6-9fb8-0002a5d5c51b')
    index = con.expect(['value:[0-9a-fA-F ]+', 'Error'])
    if index == 0:
        data = con.after.decode('utf-8').split(':')[1].replace(' ', '')
    else:
        data = '0000'
        logger.warning("Read error for %s", address)

    con.expect(r'\[LE\]>')
    con.sendline('quit')
    logger.debug("Completed %s on %s: %s", operation, address, data)
    return True, data

def main():
    if len(sys.argv) != 3:
        print("ERROR, python switchbotplugmini.py <BLE ADDRESS> <turnoff/turnon/toggle/readstate>")
        sys.exit(1)

    result, resp = switchbotplugmini(sys.argv[1], sys.argv[2])
    if result:
        if resp == '0180':
            print(result, resp, "on")
        elif resp == '1000':
            print(result, resp, "off")
        else:
            print(result, resp) 
        sys.exit(0) #result==True, exit(0)
    else:
        print(result, resp)
        sys.exit(1)

if __name__ == "__main__":
    main()

