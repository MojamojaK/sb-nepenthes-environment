# references
# https://github.com/OpenWonderLabs/python-host/blob/master/switchbot.py

import sys
import logging
import pexpect

logger = logging.getLogger(__name__)

def switchbotbot(address, operation):
    '''! trigger_device brief.
    turnon, turnoff, press, down, up the SwitchBot Plug Mini
    @return : '0000':Error, '0001':Timeout
    '''
    logger.debug("Connecting to %s for %s", address, operation)
    con = pexpect.spawn('gatttool -b ' + address + ' -I -t random')
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
    if operation == 'turnon':
        con.sendline('char-write-cmd ' + cmd_handle + ' 570101')
    elif operation == 'turnoff':
        con.sendline('char-write-cmd ' + cmd_handle + ' 570102')
    elif operation == 'press':
        con.sendline('char-write-cmd ' + cmd_handle + ' 570100')
    elif operation == 'down':
        con.sendline('char-write-cmd ' + cmd_handle + ' 570103')
    elif operation == 'up':
        con.sendline('char-write-cmd ' + cmd_handle + ' 570104')
    else:
        logger.warning("Unsupported command: %s", operation)
        return False, '0000'

    con.expect(r'\[LE\]>')
    con.sendline('quit')
    logger.debug("Completed %s on %s", operation, address)
    return True, ''

def main():
    if len(sys.argv) != 3:
        print("ERROR, python switchbotbot.py <BLE ADDRESS> <turnon/turnoff/press/down/up>")
        sys.exit(1)

    print(sys.argv[1], sys.argv[2])
    result, resp = switchbotbot(sys.argv[1], sys.argv[2])
    if result:
        print(result, resp)
        sys.exit(0) #result==True, exit(0)
    else:
        print(result, resp)
        sys.exit(1)

if __name__ == "__main__":
    main()

