import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from src.bluetooth_bridge import BluetoothBridge, SERVICES

SERVICE = next(iter(SERVICES))
COMMAND, NOTIFY = SERVICES[SERVICE]


class FakeClient:
    def __init__(self, device, **kwargs):
        self.is_connected = False
        self.services = [SimpleNamespace(uuid=SERVICE)]
        self.writes = []

    async def connect(self):
        self.is_connected = True

    async def disconnect(self):
        self.is_connected = False

    async def start_notify(self, characteristic, callback):
        self.notify = callback

    async def write_gatt_char(self, characteristic, value, response):
        self.writes.append((characteristic, value, response))


class FakeScanner:
    @staticmethod
    async def find_device_by_address(address, **kwargs):
        return SimpleNamespace(address=address, name='GANi4_A23C')

    @staticmethod
    async def discover(**kwargs):
        return {name: (SimpleNamespace(address=address, name=name), SimpleNamespace(local_name=name))
                for name, address in [('GANi4', 'AA:BB:CC:DD:EE:FF'), ('Headphones', '11:22:33:44:55:66')]}


class BluetoothBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.module = patch.dict(sys.modules, {'bleak': SimpleNamespace(BleakClient=FakeClient, BleakScanner=FakeScanner)})
        self.module.start()
        self.addCleanup(self.module.stop)
        known = patch('src.bluetooth_bridge.known_linux_cubes', new_callable=AsyncMock, return_value=[])
        self.known = known.start()
        self.addCleanup(known.stop)
        self.bridge = BluetoothBridge()

    async def asyncTearDown(self):
        await self.bridge.disconnect()

    async def connect(self):
        result = await self.bridge.handle('scan', {})
        self.assertEqual(result['devices'], [{'id': 'AA:BB:CC:DD:EE:FF', 'name': 'GANi4'}])
        return await self.bridge.handle('connect', {'device': result['devices'][0]['id']})

    async def test_connected_nonadvertising_cube_is_selectable(self):
        device = SimpleNamespace(address='0C:3D:5E:BD:A2:3C', name='GANi4_A23C')
        self.known.return_value = [device]
        with patch.object(FakeScanner, 'discover', new_callable=AsyncMock, return_value={}):
            result = await self.bridge.handle('scan', {})
        self.assertEqual(result['devices'], [{'id': device.address, 'name': device.name}])
        connection = await self.bridge.handle('connect', {'device': device.address})
        self.assertEqual(connection['services'], [SERVICE])

    async def test_nonadvertising_paired_cube_can_still_connect(self):
        device = SimpleNamespace(address='0C:3D:5E:BD:A2:3C', name='GANi4_A23C')
        self.bridge.devices[device.address] = device
        with patch.object(FakeScanner, 'find_device_by_address', new_callable=AsyncMock, return_value=None):
            result = await self.bridge.handle('connect', {'device': device.address})
        self.assertEqual(result['services'], [SERVICE])

    async def test_transient_timeout_is_cleaned_up_and_retried(self):
        await self.bridge.handle('scan', {})
        with patch.object(FakeClient, 'connect', new_callable=AsyncMock, side_effect=[TimeoutError(), None]) as connect, \
             patch.object(FakeClient, 'disconnect', new_callable=AsyncMock) as disconnect:
            result = await self.bridge.handle('connect', {'device': 'AA:BB:CC:DD:EE:FF'})
            self.assertEqual(result['services'], [SERVICE])
            self.assertEqual(connect.await_count, 2)
            disconnect.assert_awaited_once()

    async def test_connection_timeout_preserves_error_and_cleans_up(self):
        await self.bridge.handle('scan', {})
        with patch.object(FakeClient, 'connect', new_callable=AsyncMock, side_effect=TimeoutError), \
             patch.object(FakeClient, 'disconnect', new_callable=AsyncMock) as disconnect:
            with self.assertRaisesRegex(ValueError, 'GATT connection did not complete'):
                await self.bridge.handle('connect', {'device': 'AA:BB:CC:DD:EE:FF'})
            self.assertEqual(disconnect.await_count, 2)
        self.assertIsNone(self.bridge.token)

    async def test_notification_and_command_round_trip(self):
        result = await self.connect()
        token = result['token']
        await self.bridge.handle('notify', {'token': token, 'characteristic': NOTIFY})
        self.bridge.client.notify(None, bytearray([1, 2, 255]))
        events = await self.bridge.handle('events', {'token': token, 'cursor': 0})
        self.assertEqual(events['events'][0]['value'], [1, 2, 255])
        self.assertEqual((await self.bridge.handle('events', {'token': token, 'cursor': 1}))['events'], [])
        await self.bridge.handle('write', {'token': token, 'characteristic': COMMAND, 'value': [1, 2]})
        self.assertEqual(self.bridge.client.writes, [(COMMAND, b'\x01\x02', False)])
        await self.bridge.handle('disconnect', {'token': token})
        self.assertIsNone(self.bridge.client)

    async def test_only_selected_cube_and_owner_can_access_gan_characteristics(self):
        with self.assertRaises(ValueError):
            await self.bridge.handle('connect', {'device': 'unselected'})
        result = await self.connect()
        for action, data in [('events', {'token': 'wrong'}),
                             ('write', {'token': result['token'], 'characteristic': 'other', 'value': [1]}),
                             ('write', {'token': result['token'], 'characteristic': COMMAND, 'value': [256]}),
                             ('connect', {'device': 'AA:BB:CC:DD:EE:FF'})]:
            with self.subTest(action=action), self.assertRaises(ValueError):
                await self.bridge.handle(action, data)

    async def test_disconnect_and_notification_overflow_are_reported(self):
        token = (await self.connect())['token']
        await self.bridge.handle('notify', {'token': token, 'characteristic': NOTIFY})
        for _ in range(2050):
            self.bridge.client.notify(None, b'\x00')
        with self.assertRaisesRegex(ValueError, 'missed'):
            await self.bridge.handle('events', {'token': token, 'cursor': 0})
        self.bridge.client.is_connected = False
        self.assertFalse((await self.bridge.handle('events', {'token': token}))['connected'])

class BluetoothHTTPTests(unittest.TestCase):
    def test_hardware_routes_require_this_local_origin(self):
        import json
        import threading
        from http.server import HTTPServer
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen
        from src.server import Handler
        http = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{http.server_port}'
        try:
            with patch('src.bluetooth_bridge.bridge.call', return_value={'devices': []}) as call:
                for origin in (None, 'https://other.example'):
                    headers = {'Content-Type': 'application/json'}
                    if origin:
                        headers['Origin'] = origin
                    with self.assertRaises(HTTPError) as error:
                        urlopen(Request(base+'/api/bluetooth/scan', b'{}', headers), timeout=3)
                    self.assertEqual(error.exception.code, 403)
                    error.exception.close()
                call.assert_not_called()
                with urlopen(Request(base+'/api/bluetooth/scan', b'{}',
                                     {'Content-Type': 'application/json', 'Origin': base}), timeout=3) as response:
                    self.assertEqual(json.load(response), {'devices': []})
                call.assert_called_once_with('scan', {})
        finally:
            http.shutdown()
            http.server_close()
            thread.join()
