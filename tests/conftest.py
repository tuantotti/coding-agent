collect_ignore = [
    # Demo/scaffold script (no test_* functions), runs a live Azure OpenAI
    # call at module import time and aborts pytest collection with a 404
    # when the configured deployment doesn't exist. Excluded rather than
    # edited since it's a teammate's file, not part of this scope.
    "test_deep_agents.py",
]
