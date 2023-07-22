import os
import shutil

import pbcoin.config as conf


#TODO: just one time generates some keys and in unittest just use them
def pytest_sessionstart(session):
    base_path = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_path, ".key-test")
    os.environ["KEY_PATH"] = path
    if not os.path.exists(path):
        os.mkdir(path)
    test_options = {
        "difficulty": (2 ** 256 - 1) >> (2),
        "logging": False,
        "fetch_db": False  # TODO: Temporarily
    }
    conf.settings.update(test_options)


def pytest_sessionfinish(session, exitstatus):
    path = os.environ["KEY_PATH"]
    shutil.rmtree(path)
