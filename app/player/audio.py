"""AudioPlayer (STUB: frozen interface; Builder D replaces the body)."""


class AudioPlayer:
    def __init__(self, *a, **kw):
        self.shuffle = False
        self.repeat = "off"
        self.on_error = None
        self._queue = []

    def get_state(self):
        return {"track": None, "playing": False, "position": 0.0, "duration": 0.0,
                "volume": 50, "shuffle": self.shuffle, "repeat": self.repeat,
                "queue_index": -1}

    def get_queue(self):
        return list(self._queue)

    def set_queue(self, tracks, start_index=0):
        self._queue = list(tracks)

    def enqueue(self, track):
        self._queue.append(track)

    def play_next(self, track):
        self._queue.insert(0, track)

    def remove_from_queue(self, index):
        pass

    def move_in_queue(self, src, dst):
        pass

    def play(self):
        pass

    def pause(self):
        pass

    def toggle(self):
        pass

    def next(self):
        pass

    def prev(self):
        pass

    def seek(self, fraction):
        pass

    def set_volume(self, volume):
        pass

    def update(self):
        pass

    def cleanup(self):
        pass


class MockAudioPlayer(AudioPlayer):
    pass
