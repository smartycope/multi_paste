"""
A class that creates a new thread that allows you to paste multiple things in order.
Each time you paste something, it'll set the clipboard to the next thing.
"""

import keyboard, clipboard, os, logging, threading

logger = logging.getLogger(__name__)


class MultiPaste(threading.Thread):
    """ Paste multiple things in order. Each time you paste something, it'll switch to the next thing.
        The first element will be set as the clipboard immediately, and the last element will be the
        text left on the keyboard after all the pastes are consumed.

        If caps_lock is True, it assumes caps lock acts like a control.
        This function will not block execution, and stops functioning after execution is halted.
        If clear, then using this function will override any previous uses of it. For example, if you
        call this function with 5 arguments, and only paste twice, then call this function again, it
        will clear the other 3 pastes. If clear is set to False, then they will be appended to the
        scheduled pastes.
        copy_func lets you specify a custom copy function which takes a string and returns nothing.
        This could be useful for some edge cases where the clipboard module doesn't work, or if you
        want to do something fancy like have a history of pastes or something. By default it just uses
        clipboard.copy.
        Will *not* cast elements to strings, so you can use non-str types with your copy_func if you want.
        timeout is the number of seconds to wait for the next paste before giving up and stopping the paste sequence.
        Default is 5 minutes, so if the user forgets about it, and moves on to something else, they won't suddenly
        start pasting and be confused it's not consistent. None will wait indefinitely.

        self.end_reason will be one of:
        None: the sequence is still running
        'timeout': the timeout was reached before the sequence was completed
        'interrupted': the sequence was interrupted by the user copying something new
        'completed': the sequence was completed successfully

        set_last_if_incomplete will set the clipboard to the last paste if the sequence is interrupted or times out,
        so the last paste is guaranteed to be the last thing in the clipboard.

        clear=False is untested
        Use on Linux is untested
        Use on macOS is untested
        Use with streamlit is tested, and works.

        Known issues:
        On my particular setup, I have caps lock mapped to control via powertoys. This works perfectly with caps lock,
        but ctrl won't do anything until caps lock is pressed at least once. After that, ctrl works fine. I have no idea 
        why this is, but if you have a similar setup, just make sure to press caps lock once before trying to use ctrl.
        using caps_lock=False makes it unusable in this case. 
    """
    _pastes = []

    def __init__(self, *pastes, clear=True, caps_lock=True, copy_func=clipboard.copy, timeout=5*60, set_last_if_incomplete=False):
        # Kill the thread if it's already running, or when the main program ends, so we don't have to worry about it
        super().__init__(daemon=True)
        self.copy_func = copy_func
        self.caps_lock = caps_lock
        self.timeout = timeout
        self.end_reason = None
        self.set_last_if_incomplete = set_last_if_incomplete

        if len(pastes) == 0:
            self.end_reason = 'completed'
            return
        elif len(pastes) == 1:
            copy_func(pastes[0])
            self.end_reason = 'completed'
            return

        if clear:
            MultiPaste._pastes = list(pastes)
        else:
            MultiPaste._pastes += list(pastes)

        is_windows = os.name == 'nt'
        self._hotkey_params = dict(
            suppress=not is_windows,
            trigger_on_release=is_windows,
            timeout=.1 if is_windows else .2
        )

        # Fire and forget. The user can join if they want, otherwise we'll clean up ourselves and kill on parent process exit.
        self.start()

    def run(self):
        unpause = threading.Event()
        interrupted = threading.Event()

        # Set up the hotkey hooks to wait for the paste
        # We don't actually need to recreate these, since they don't actually change at all
        # We need ctrl+v to increment the paste, and ctrl+c to clear pastes, so if the user copies something new, we don't
        # overwrite it
        hooks = [
            # Don't know why lambda is necissary here, but if I just pass pause.set it doesn't work for some reason
            keyboard.add_hotkey('ctrl+v', lambda: logging.debug('ctrl+v') or unpause.set(), **self._hotkey_params),
            keyboard.add_hotkey('ctrl+c', lambda: logging.debug('ctrl+c') or (interrupted.set() and unpause.set()), **self._hotkey_params)
        ]
        if self.caps_lock:
            hooks += [
                keyboard.add_hotkey('caps lock+v', lambda: logging.debug('caps lock+v') or unpause.set(), **self._hotkey_params),
                keyboard.add_hotkey('caps lock+c', lambda: logging.debug('caps lock+c') or (interrupted.set() and unpause.set()), **self._hotkey_params)
            ]

        logger.debug(f'clipboard is now {MultiPaste._pastes[0]}, waiting for next paste...')
        self.copy_func(MultiPaste._pastes.pop(0))

        for copyme in MultiPaste._pastes:
            # Wait for the user to press the paste keys
            if not unpause.wait(self.timeout):
                logger.debug("MultiPaste: Paste timeout reached, stopping paste sequence.")
                self.end_reason = 'timeout'
                break

            if interrupted.is_set():
                self.end_reason = 'interrupted'
                break

            # Clear the lock so we can use it again
            unpause.clear()

            self.copy_func(copyme)
            logger.debug(f'clipboard is now {copyme}, waiting for paste...')

        self.end_reason = self.end_reason or 'completed'

        # Remove the hotkey hooks
        for hook in hooks:
            keyboard.remove_hotkey(hook)

        if self.set_last_if_incomplete and self.end_reason != 'completed' and MultiPaste._pastes:
            self.copy_func(MultiPaste._pastes[-1])

        logger.debug(f'MultiPaste: Paste sequence ended due to {self.end_reason}')

# import streamlit as st
# st.text_area("Testing Area:")

# For manual testing
if __name__ == '__main__':
    # We call .join() just so the program doesn't end immediately
    logger.setLevel(logging.DEBUG)
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')

    # if st.button("Start MultiPaste Test"):
    thread = MultiPaste(*list('abcdefg'), timeout=10, caps_lock=True)
    print(thread.native_id) # so we can kill it if something goes wrong

    # thread.join(20)
    # time.sleep(1000)



"""
Testing Area:
abcdefg
"""
