# Asynchronous Python API for mFi mPower devices

## Notes

This package provides a _direct_ asynchronous API for Ubiquiti mFi mPower devices based on [AsyncSSH](https://asyncssh.readthedocs.io/en/latest/). The mFi product line which are is sadly EOL since 2015 and the latest available mFi firmware is version 2.1.11, which can be found [here](https://www.ui.com/download/mfi/mpower).

**Please note that even with the latest available mFi firmware, Ubiquiti mFi mPower Devices use OpenSSL 1.0.0g (18 Jan 2012) and Dropbear SSH 0.51 (27 Mar 2008).**

To extract information and control the devices via SSH, only the `ssh-rsa` host key algorithm in combination with the `diffie-hellman-group1-sha1` key exchange is supported. The latter is available as [legacy option](http://www.openssh.com/legacy.html). There is also a [known bug](https://github.com/ronf/asyncssh/issues/263) in older Dropbear versions which truncates the list of offered key algorithms. The mFi mPower package therefore limits the offered key algorithms to `ssh-rsa` and the encryption algorithm to `aes128-cbc`. Known host checks will be [disabled](https://github.com/ronf/asyncssh/issues/132) as this would require user interaction.

## Basic example

```python
import asyncio

from mfi_mpower.device import MPowerDevice

async def main():

    data = {
        "host": "name_or_ip",
        "username": "ubnt",
        "password": "ubnt",
    }

    async with MPowerDevice(**data) as device:
        
        # Test LED control
        await device.set_led(MPowerLED.YELLOW)
        await asyncio.sleep(5)
        await device.set_led(MPowerLED.LOCKED_OFF)

        # Create switch for port 1
        switch = await device.create_switch(1)

        # Test lock control
        await switch.lock()
        await asyncio.sleep(5)
        await switch.unlock()

        # Test output control
        await switch.turn_off()
        await asyncio.sleep(5)
        await switch.toggle()

asyncio.run(main())
```

## Better example

```python
import asyncio

from mfi_mpower.device import MPowerDevice

async def query(host: str) -> None:
    """Async query"""

    data = {
        "host": host,
        "username": "ubnt",
        "password": "ubnt",
    }

    async with MPowerDevice(**data) as device:

        # Print device info
        print(device)

        # Print all switches and their state
        switches = await device.create_switches()
        for switch in switches:
            print(switch)

        # Print all sensors and their data
        sensors = await device.create_sensors()
        for sensor in sensors:
            print(sensor)


async def main() -> None:
    """Async main"""

    hosts = [
        "host1", "host2", "host3",
        "host4", "host5", "host6",
    ]

    await asyncio.gather(*[query(host) for host in hosts])

asyncio.run(main())
```
