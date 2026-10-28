"""Local GAN-only GATT transport for browsers without Web Bluetooth."""
import asyncio
from collections import deque
import concurrent.futures
import secrets
import sys
import threading
import time

# Supported GAN service -> (command, notification) characteristics.
SERVICES = {
    '6e400001-b5a3-f393-e0a9-e50e24dc4179': (
        '28be4a4a-cd67-11e9-a32f-2a2ae2dbcce4', '28be4cb6-cd67-11e9-a32f-2a2ae2dbcce4'),
    '8653000a-43e6-47b7-9cb0-5fc21d4ae340': (
        '8653000c-43e6-47b7-9cb0-5fc21d4ae340', '8653000b-43e6-47b7-9cb0-5fc21d4ae340'),
    '00000010-0000-fff7-fff6-fff5fff4fff0': (
        '0000fff5-0000-1000-8000-00805f9b34fb', '0000fff6-0000-1000-8000-00805f9b34fb'),
}


async def known_linux_cubes():
    """Read BlueZ's device cache, including connected cubes that no longer advertise."""
    if sys.platform != 'linux':
        return []
    from bleak.backends.device import BLEDevice
    from dbus_fast import BusType, Message, MessageType
    from dbus_fast.aio import MessageBus
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    try:
        reply = await bus.call(Message(destination='org.bluez', path='/',
                                       interface='org.freedesktop.DBus.ObjectManager',
                                       member='GetManagedObjects'))
        if reply.message_type == MessageType.ERROR:
            raise ValueError('Could not read Linux Bluetooth devices: ' + str(reply.body))
        devices = []
        for path, interfaces in reply.body[0].items():
            props = {key: value.value for key, value in interfaces.get('org.bluez.Device1', {}).items()}
            name = props.get('Name') or props.get('Alias') or ''
            if props.get('Address') and name.startswith(('GAN', 'MG', 'AiCube')):
                devices.append(BLEDevice(props['Address'], name, {'path': path, 'props': props}))
        return devices
    finally:
        bus.disconnect()


class BluetoothBridge:
    def __init__(self):
        self.loop = None
        self.thread = None
        self.lock = threading.Lock()
        self.devices = {}
        self.advertising = set()
        self.client = None
        self.token = None
        self.events = deque(maxlen=2048)
        self.serial = 0
        self.subscribed = set()
        self.allowed_commands = set()
        self.allowed_notifications = set()
        self.touched = 0

    def call(self, action, data):
        with self.lock:
            if self.loop is None:
                self.loop = asyncio.new_event_loop()
                self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
                self.thread.start()
        future = asyncio.run_coroutine_threadsafe(self.handle(action, data), self.loop)
        try:
            return future.result(timeout=35)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise ValueError('Bluetooth operation timed out. Wake the cube and try again.') from None

    async def handle(self, action, data):
        try:
            from bleak import BleakClient, BleakScanner
        except ImportError:
            raise ValueError('Local Bluetooth needs Bleak. Install requirements.txt in the Python environment running the app, then restart it.') from None
        if action == 'scan':
            known = await known_linux_cubes()
            found = await BleakScanner.discover(timeout=6, return_adv=True)
            self.devices = {device.address: device for device in known}
            self.advertising = set()
            for device, adv in found.values():
                name = adv.local_name or device.name or ''
                if name.startswith(('GAN', 'MG', 'AiCube')):
                    self.devices[device.address] = device
                    self.advertising.add(device.address)
            return {'devices': [{'id': device.address, 'name': device.name or device.address}
                                for device in self.devices.values()]}
        if action == 'connect':
            if self.client and self.client.is_connected:
                raise ValueError('A local cube is already connected. Disconnect it in the other tab first.')
            device = self.devices.get(data.get('device'))
            if device is None:
                raise ValueError('Select a GAN cube from a fresh scan.')
            # Refresh a cached device when possible, but do not require an
            # advertisement: connected and directed-advertising cubes may be absent.
            connected = bool((getattr(device, 'details', None) or {}).get('props', {}).get('Connected'))
            if device.address not in self.advertising and not connected:
                fresh = await BleakScanner.find_device_by_address(device.address, timeout=2)
                if fresh is not None:
                    device = fresh
                    self.devices[device.address] = fresh
            for attempt in range(2):
                client = BleakClient(device, disconnected_callback=lambda _: None, timeout=10)
                try:
                    await client.connect()
                    services = [service.uuid.lower() for service in client.services if service.uuid.lower() in SERVICES]
                    if not services:
                        raise ValueError('This cube does not expose a supported GAN Gen2/Gen3/Gen4 service.')
                    break
                except BaseException as exc:
                    await self.cleanup_client(client)
                    if isinstance(exc, TimeoutError):
                        if attempt == 0:
                            fresh = await BleakScanner.find_device_by_address(device.address, timeout=2)
                            if fresh is not None:
                                device = fresh
                            continue
                        raise ValueError(f'Linux Bluetooth timed out connecting to {device.name or device.address} after retrying. '
                                         'The cube is paired, but its GATT connection did not complete. '
                                         'Power-cycle the cube in its pod and disconnect it from other devices, then retry.') from exc
                    raise
            self.client = client
            self.allowed_commands = {SERVICES[service][0] for service in services}
            self.allowed_notifications = {SERVICES[service][1] for service in services}
            self.token = secrets.token_urlsafe(32)
            self.events.clear()
            self.subscribed.clear()
            self.serial = 0
            self.touched = time.monotonic()
            asyncio.create_task(self.expire(client, self.token))
            return {'token': self.token, 'services': services}
        token = data.get('token')
        if not self.token or not isinstance(token, str) or not secrets.compare_digest(token, self.token):
            raise ValueError('This Bluetooth connection has expired. Reconnect your cube.')
        self.touched = time.monotonic()
        if action == 'disconnect':
            await self.disconnect()
            return {}
        if not self.client or not self.client.is_connected:
            return {'connected': False, 'events': []} if action == 'events' else self.unavailable()
        if action == 'events':
            cursor = data.get('cursor', 0)
            if not isinstance(cursor, int) or cursor < 0:
                raise ValueError('Invalid Bluetooth event cursor.')
            if self.events and cursor < self.events[0]['serial'] - 1:
                raise ValueError('Bluetooth events were missed. Reconnect to resynchronize the cube.')
            return {'connected': True, 'events': [event for event in self.events if event['serial'] > cursor]}
        characteristic = data.get('characteristic', '')
        if action == 'notify':
            if characteristic not in self.allowed_notifications:
                raise ValueError('Unsupported cube notification characteristic.')
            if characteristic not in self.subscribed:
                def on_value(_, value):
                    self.serial += 1
                    self.events.append({'serial': self.serial, 'characteristic': characteristic, 'value': list(value)})
                await self.client.start_notify(characteristic, on_value)
                self.subscribed.add(characteristic)
            return {}
        if action == 'write':
            if characteristic not in self.allowed_commands:
                raise ValueError('Unsupported cube command characteristic.')
            value = data.get('value')
            if not isinstance(value, list) or not 1 <= len(value) <= 32 or any(type(v) is not int or not 0 <= v <= 255 for v in value):
                raise ValueError('Invalid cube command.')
            await self.client.write_gatt_char(characteristic, bytes(value), response=False)
            return {}
        raise ValueError('Unknown Bluetooth operation.')

    def unavailable(self):
        raise ValueError('Cube disconnected. Reconnect to continue.')

    async def cleanup_client(self, client):
        # A failed BlueZ connect can also stall during cleanup. Bound that wait,
        # preserve the original error, and release partially opened connections.
        task = asyncio.create_task(client.disconnect())
        done, _ = await asyncio.wait({task}, timeout=3)
        if task not in done:
            task.cancel()
        elif not task.cancelled():
            task.exception()

    async def disconnect(self):
        client, self.client = self.client, None
        self.token = None
        self.subscribed.clear()
        if client:
            await self.cleanup_client(client)

    async def expire(self, client, token):
        while self.client is client and self.token == token:
            await asyncio.sleep(10)
            if time.monotonic() - self.touched > 45:
                await self.disconnect()

    def close(self):
        if self.loop is not None:
            try:
                asyncio.run_coroutine_threadsafe(self.disconnect(), self.loop).result(timeout=5)
            except Exception:
                pass
            self.loop.call_soon_threadsafe(self.loop.stop)


bridge = BluetoothBridge()
