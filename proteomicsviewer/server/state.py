"""Global application state for ProteomicsViewer."""


class AppState:
    def __init__(self):
        self.data = None       # Parsed protein groups data (dict)
        self.filename = None   # Name of the uploaded file

    def clear(self):
        self.data = None
        self.filename = None


state = AppState()
