import pathlib
import pexpect
import time

base = pathlib.Path(__file__).resolve().parent
args = ['-M', 'romulus-bmc', '-m', '256', '-nographic', '-snapshot',
        '-drive', f'file={base}/image.static.mtd,format=raw,if=mtd',
        '-net', 'nic', '-net', 'user,hostfwd=tcp:127.0.0.1:3222-:22,hostfwd=tcp:127.0.0.1:3443-:443,hostfwd=udp:127.0.0.1:3623-:623']
with (base / 'console.log').open('w') as log:
    child = pexpect.spawn('qemu-system-arm', args, encoding='utf-8', codec_errors='replace', timeout=300)
    child.logfile_read = log
    try:
        child.expect('romulus login:')
        child.sendline('root')
        child.expect('Password:')
        child.sendline('0penBmc')
        child.expect(r'root@romulus:.*#')
        print('LOGIN_OK', flush=True)
        def run(command, timeout=180):
            child.sendline(command + '; printf "\\nCHECK_%s\\n" DONE')
            child.expect(r'CHECK_DONE[\r\n]+', timeout=timeout)
            print(child.before, flush=True)
        run('cat /etc/os-release; command -v obmcutil ip systemctl journalctl; sleep 45; obmcutil state')
        run('obmcutil poweron; echo POWERON_RC=$?; sleep 30; obmcutil state')
        run('systemctl --failed --no-pager; journalctl -b -u avsbus-disable@0.service -u org.openbmc.control.Power@0.service --no-pager -n 60')
        run('obmcutil poweroff; echo POWEROFF_RC=$?; sleep 15; obmcutil state')
        run('journalctl -b -u xyz.openbmc_project.State.BMC.service --no-pager -n 20')
        print('CHECKS_DONE_NETWORK_WINDOW', flush=True)
        time.sleep(90)
    finally:
        child.send('\x01x')
        child.expect(pexpect.EOF, timeout=15)
        child.close(force=True)
