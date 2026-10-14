"""Tests for the blesession-backed BLE notification dispatcher."""

import asyncio

from custom_components.magic_caster_wand.common_ble.notification_dispatcher import NotificationDispatcher


def test_dispatcher_delivers_queued_frames_in_order_and_unsubscribes():
    class Client:
        is_connected = True

        def __init__(self):
            self.callbacks = {}
            self.stopped = []

        async def start_notify(self, characteristic, callback):
            self.callbacks[characteristic] = callback

        async def stop_notify(self, characteristic):
            self.stopped.append(characteristic)

    async def scenario():
        client = Client()
        received = []
        delivered = asyncio.Event()

        def handle(_sender, data):
            received.append(bytes(data))
            if len(received) == 2:
                delivered.set()

        dispatcher = NotificationDispatcher(client, {"notify": handle})
        await dispatcher.start()
        await dispatcher.start()

        client.callbacks["notify"](None, bytearray(b"first"))
        client.callbacks["notify"](None, bytearray(b"second"))
        await asyncio.wait_for(delivered.wait(), timeout=1)
        await dispatcher.stop()

        assert received == [b"first", b"second"]
        assert client.stopped == ["notify"]

    asyncio.run(scenario())


def test_concurrent_start_waits_for_all_subscriptions_to_be_ready():
    class Client:
        is_connected = True

        def __init__(self):
            self.callbacks = {}
            self.first_subscribe_started = asyncio.Event()
            self.allow_subscribe_to_finish = asyncio.Event()
            self.start_calls = []

        async def start_notify(self, characteristic, callback):
            self.start_calls.append(characteristic)
            self.callbacks[characteristic] = callback
            self.first_subscribe_started.set()
            await self.allow_subscribe_to_finish.wait()

        async def stop_notify(self, characteristic):
            pass

    async def scenario():
        client = Client()
        dispatcher = NotificationDispatcher(client, {"notify": lambda *_args: None})
        first_start = asyncio.create_task(dispatcher.start())
        await client.first_subscribe_started.wait()
        second_start = asyncio.create_task(dispatcher.start())
        await asyncio.sleep(0)

        assert not second_start.done()

        client.allow_subscribe_to_finish.set()
        await asyncio.gather(first_start, second_start)
        assert client.start_calls == ["notify"]
        await dispatcher.stop()

    asyncio.run(scenario())


def test_restart_waits_for_previous_subscription_to_stop():
    class Client:
        is_connected = True

        def __init__(self):
            self.start_calls = 0
            self.stop_started = asyncio.Event()
            self.allow_stop_to_finish = asyncio.Event()

        async def start_notify(self, _characteristic, _callback):
            self.start_calls += 1

        async def stop_notify(self, _characteristic):
            self.stop_started.set()
            await self.allow_stop_to_finish.wait()

    async def scenario():
        client = Client()
        dispatcher = NotificationDispatcher(client, {"notify": lambda *_args: None})
        await dispatcher.start()
        stopping = asyncio.create_task(dispatcher.stop())
        await client.stop_started.wait()
        restarting = asyncio.create_task(dispatcher.start())
        await asyncio.sleep(0)

        assert not restarting.done()

        client.allow_stop_to_finish.set()
        await asyncio.gather(stopping, restarting)
        assert client.start_calls == 2
        await dispatcher.stop()

    asyncio.run(scenario())
