import threading

from src.core.event_bus import EventBus, EventType


class TestEventBus:
    def test_publish_and_subscribe_single_event(self, event_bus):
        received = []
        event_bus.subscribe(EventType.TIMER_STARTED, lambda payload: received.append(payload))

        event_bus.publish(EventType.TIMER_STARTED, "test_payload")
        event_bus.process_pending()

        assert received == ["test_payload"]

    def test_multiple_subscribers_same_event(self, event_bus):
        received_a = []
        received_b = []
        event_bus.subscribe(EventType.TIMER_TICK, lambda p: received_a.append(p))
        event_bus.subscribe(EventType.TIMER_TICK, lambda p: received_b.append(p))

        event_bus.publish(EventType.TIMER_TICK, 42.0)
        event_bus.process_pending()

        assert received_a == [42.0]
        assert received_b == [42.0]

    def test_unrelated_event_not_delivered(self, event_bus):
        received = []
        event_bus.subscribe(EventType.TIMER_STARTED, lambda p: received.append(p))

        event_bus.publish(EventType.TIMER_STOPPED, "should_not_arrive")
        event_bus.process_pending()

        assert received == []

    def test_process_pending_drains_queue(self, event_bus):
        received = []
        event_bus.subscribe(EventType.TIMER_TICK, lambda p: received.append(p))

        event_bus.publish(EventType.TIMER_TICK, 1.0)
        event_bus.publish(EventType.TIMER_TICK, 2.0)
        event_bus.publish(EventType.TIMER_TICK, 3.0)
        event_bus.process_pending()

        assert received == [1.0, 2.0, 3.0]

        # Second call should not deliver anything new
        received.clear()
        event_bus.process_pending()
        assert received == []

    def test_publish_from_different_thread(self, event_bus):
        received = []
        event_bus.subscribe(EventType.WINDOW_CHANGED, lambda p: received.append(p))

        def publish_from_thread():
            event_bus.publish(EventType.WINDOW_CHANGED, "from_thread")

        t = threading.Thread(target=publish_from_thread)
        t.start()
        t.join()

        event_bus.process_pending()
        assert received == ["from_thread"]

    def test_publish_with_no_subscribers(self, event_bus):
        # Should not raise
        event_bus.publish(EventType.PROJECT_CREATED, {"name": "test"})
        event_bus.process_pending()
