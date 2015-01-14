#!/usr/bin/python
# coding: utf-8

import subprocess, threading

class Command(object):
        def __init__(self, cmd):
            self.cmd = cmd
            self.process = None

        def run(self, timeout):
            def target():
                with open(os.devnull, 'w') as tempf:
                    self.process = subprocess.Popen(self.cmd,
                                            stdout=tempf,
                                            stderr=tempf,
                                            )
                    self.process.communicate()

            thread = threading.Thread(target=target)
            thread.start()
            thread.join(timeout)
            if thread.is_alive():
                self.process.terminate()
                thread.join()
                return self.process.returncode
