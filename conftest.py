import os
import shutil


#TODO: just one time generates some keys and in unittest just use them
def pytest_sessionstart(session):
    base_path = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_path, ".key-test")
    os.environ["KEY_PATH"] = path
    if not os.path.exists(path):
        os.mkdir(path)


def pytest_sessionfinish(session, exitstatus):
    path = os.environ["KEY_PATH"]
    shutil.rmtree(path)
