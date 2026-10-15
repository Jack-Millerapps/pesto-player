"""PlaylistStore (STUB: frozen interface; Builder D replaces the body)."""


class PlaylistStore:
    def __init__(self, directory=None):
        self.directory = directory

    def list_names(self):
        return []

    def load(self, name):
        return []

    def save(self, name, tracks):
        pass

    def delete(self, name):
        pass

    def add(self, name, track):
        pass
