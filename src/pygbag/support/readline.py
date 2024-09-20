#!/usr/bin/env python3
# Incremental readline compatible with micropython/lib/readline.c
# https://docs.python.org/fr/3/library/readline.html
# based on https://github.com/dhylands/mp_readline/

DEBUG = 0
import sys

CTRL_A = b"\x01"
CTRL_C = b"\x03"
CTRL_D = b"\x04"
CTRL_E = b"\x05"
CTRL_U = b"\x15"
TAB = b"\x09"
CR = b"\x0d"
LF = b"\x0a"
ESC = b"\x1b"

DEL = b"\x7f"
BS = b"\x08"

# The following escape sequence is used to query the size of the window:
#
# ESC 7         - Save cursor position
# ESC [r        - Enable scrolling for entire display
# ESC [row;colH - Move to cursor position
# ESC [6n       - Device Status Report - send ESC [row;colR
# ESC 8         - Restore cursor position

REPORT_WINDOW_SIZE_1 = b"\x1b7\x1b[r\x1b[999;999H"
REPORT_WINDOW_SIZE_2 = b"\x1b8"
REPORT_CURSOR_LOCATION = b"\x1b[6n"

# When running the test suite, we're only checking the line buffer, so we
# disable output
FBO = True


def printable(ch):
    """Returns a printable representation of a character."""
    val = ord(ch)
    if val < ord(" ") or val > ord("~"):
        return "."
    return chr(val)


def logger(*argv, **kw):
    if sys.platform in ("emscripten", "wasi"):
        import platform
        import io

        kw["file"] = io.StringIO()
        print(*argv, **kw)
        kw["file"].seek(0)
        platform.window.console.log(kw["file"].read())
        kw["file"].close()


class CmdBase:
    log = logger


class CmdWrite(CmdBase):
    def __init__(self, string, log=None):
        if log:
            self.log = log
        self.string = string

    def is_input(self):
        return False

    def process(self):
        if FBO:
            return
        # self.log("CmdWrite(" + repr(self.string) + ")")
        if isinstance(self.string, str):
            sys.stdout.write(self.string)
            sys.stdout.flush()
        else:
            sys.stdout.buffer.write(self.string)
            sys.stdout.buffer.flush()


class CmdInput(CmdBase):
    def __init__(self, func, log=None):
        if log:
            self.log = log
        self._func = func

    def is_input(self):
        return True

    def process(self):
        # For some reason, the ESC [ 999;999 R sequence doesn't cause
        # select to trigger. So we do a read here.
        # This is what ncurses does as well.
        data = ""
        while True:
            char = sys.stdin.read(1)
            # self.log("CmdInput: got char '%c' 0x%02x" % (printable(char), ord(char)))
            if char == "R":
                break
            data += char
        if data[0] != chr(ord(ESC)) or data[1] != "[":
            # self.log("Invalid cursor position received")
            # self.log("data[0] = " + repr(data[0]))
            # self.log("data[1] = " + repr(data[1]))
            return
        num_str = data[2:].split(";")
        try:
            rows = int(num_str[0])
            cols = int(num_str[1])
        except:
            # self.log("Unknown ESC [ '%s' R" % data[2:])
            # self.log("num_str = " + repr(num_str))
            return
        # self.log("CmdInput: %s rows: %d cols: %d" % (self._func.__name__, rows, cols))
        self._func(rows, cols)


class CmdWriteQueue(object):
    def __init__(self, log=None):
        self.log = logger
        self.queue = []

    def write(self, string):
        self.queue.append(CmdWrite(string, log=self.log))

    def queue_input(self, func):
        self.queue.append(CmdInput(func, log=self.log))

    def wait_for_input(self, func):
        self.queue.append(CmdInput(func, log=self.log))

    def process(self):
        while len(self.queue) > 0:
            cmd = self.queue.pop(0)
            cmd.process()

    def process_input(self, *args, **kwargs):
        assert len(self.queue) > 0
        assert self.queue[0].is_input()
        cmd = self.queue.pop(0)
        cmd.process()
        self.process()


#
#
# """
# Mouse Tracking
# The VT widget can be set to send the mouse position and other information on button presses.
# These modes are typically used by editors and other full-screen applications that want to make use of the mouse.
#
# There are six mutually exclusive modes. One is DEC Locator mode,
# enabled by the DECELR CSI P s ; P s ´z control sequence, and is not described here (control sequences are summarized above).
# The remaining five modes are each enabled (or disabled) by a different parameter in:
#    DECSET CSI ? P m h or DECRST CSI ? P m l control sequence.
#
# Manifest constants for the parameter values are defined in xcharmouse.h as follows:
#
##define SET_X10_MOUSE 9
##define SET_VT200_MOUSE 1000
##define SET_VT200_HIGHLIGHT_MOUSE 1001
##define SET_BTN_EVENT_MOUSE 1002
##define SET_ANY_EVENT_MOUSE 1003
# The motion reporting modes are strictly xterm extensions, and are not part of any standard, though they are analogous to the DEC VT200 DECELR locator reports.
#
# Parameters (such as pointer position and button number) for all mouse tracking escape sequences generated by xterm encode numeric parameters in a single character as value+32. For example, ! specifies the value 1. The upper left character position on the terminal is denoted as 1,1.
#
# X10 compatibility mode sends an escape sequence only on button press, encoding the location and the mouse button pressed. It is enabled by specifying parameter 9 to DECSET. On button press, xterm sends CSI M C b C x C y (6 characters). C b is button−1. C x and C y are the x and y coordinates of the mouse when the button was pressed.
#
# Normal tracking mode sends an escape sequence on both button press and release. Modifier key (shift, ctrl, meta) information is also sent. It is enabled by specifying parameter 1000 to DECSET. On button press or release, xterm sends CSI M C b C x C y . The low two bits of C b encode button information: 0=MB1 pressed, 1=MB2 pressed, 2=MB3 pressed, 3=release. The next three bits encode the modifiers which were down when the button was pressed and are added together: 4=Shift, 8=Meta, 16=Control. Note however that the shift and control bits are normally unavailable because xterm uses the control modifier with mouse for popup menus, and the shift modifier is used in the default translations for button events. The Meta modifier recognized by xterm is the mod1 mask, and is not necessarily the "Meta" key (see xmodmap). C x and C y are the x and y coordinates of the mouse event, encoded as in X10 mode.
#
# Wheel mice may return buttons 4 and 5. Those buttons are represented by the same event codes as buttons 1 and 2 respectively, except that 64 is added to the event code. Release events for the wheel buttons are not reported.
#
# Mouse hilite tracking notifies a program of a button press, receives a range of lines from the program,
# highlights the region covered by the mouse within that range until button release,
# and then sends the program the release coordinates.
# It is enabled by specifying parameter 1001 to DECSET.
#
# Highlighting is performed only for button 1, though other button events can be received.
# Warning: use of this mode requires a cooperating program or it will hang xterm.
# On button press, the same information as for normal tracking is generated;
# xterm then waits for the program to send mouse tracking information.
#
# All X events are ignored until the proper escape sequence is received from the pty: CSI P s ; P s ; P s ; P s ; P s T .
# The parameters are func, startx, starty, firstrow, and lastrow. func is non-zero to initiate hilite tracking and zero to abort. startx and starty give the starting x and y location for the highlighted region. The ending location tracks the mouse, but will never be above row firstrow and will always be above row lastrow. (The top of the screen is row 1.) When the button is released, xterm reports the ending position one of two ways: if the start and end coordinates are valid text locations: CSI t C x C y . If either coordinate is past the end of the line: CSI T C x C y C x C y C x C y . The parameters are startx, starty, endx, endy, mousex, and mousey. startx, starty, endx, and endy give the starting and ending character positions of the region. mousex and mousey give the location of the mouse at button up, which may not be over a character.
#
# Button-event tracking is essentially the same as normal tracking, but xterm also reports button-motion events.
# Motion events are reported only if the mouse pointer has moved to a different character cell.
# It is enabled by specifying parameter 1002 to DECSET.
# On button press or release, xterm sends the same codes used by normal tracking mode.
# On button-motion events, xterm adds 32 to the event code (the third character, C b ).
# The other bits of the event code specify button and modifier keys as in normal mode.
#
# For example,
# motion into cell x,y with button 1 down is reported as:
#    CSI M @ C x C y . ( @ = 32 + 0 (button 1) + 32 (motion indicator) ).
#
# Similarly,
# motion with button 3 down is reported as:
#    CSI M B C x C y . ( B = 32 + 2 (button 3) + 32 (motion indicator) ).
#
# Any-event mode is the same as button-event mode, except that all motion events are reported, even if no mouse button is down.
# It is enabled by specifying 1003 to DECSET.
# """
#


class History(object):
    history = []


class Mouse(History):
    def __init__(self):
        self.CSI_MOUSE = {None: self.csi_mouse_ANY_EVENT}
        self.touch = False

    def csi_mouse(self):
        # stars the mouse sequence
        self.mread = b""

        self.mouse[0] = -1
        self.mouse[1] = -1
        self.mouse[2] = -1

        self.state = self.CSI_MOUSE

    def touch_clear_evt(self):
        rv = self.touch
        self.touch = False
        return rv

    def csi_mouse_ANY_EVENT(self, char):
        l = len(self.mread)
        ch = chr(ord(char))

        if l == 0:  # @AB => button
            self.esc_seq = str(ch)
            self.mouse[0] = ord(char) - 32
        elif l == 1:
            self.mouse[1] = ord(char) - 32
            self.esc_seq = f"{str(self.esc_seq)} {ord(char)}"
        elif l == 2:
            self.esc_seq = f"{str(self.esc_seq)} {ord(char)}"
            self.mouse[2] = ord(char) - 32
            self.state = self.ESEQ_NONE
            self.touch = True

        self.mread += char

    def csi_mouseC(self, char):
        l = len(self.mread)
        ch = chr(ord(char))

        if l == 0:  # @AB => button
            self.esc_seq = f"{str(self.esc_seq)} {ord(char)}"
            self.mouse[0] = ord(char) - 32
        elif l == 1:  # C
            # self.esc_seq = "%s %c" % (self.esc_seq, ch)
            self.esc_seq = f"{str(self.esc_seq)} {ch}"
        elif l == 2:
            self.esc_seq = f"{str(self.esc_seq)} {ord(char)}"
            self.mouse[1] = ord(char) - 32
        elif l == 3:  # C
            # self.esc_seq = "%s %c" % (self.esc_seq, ch)
            self.esc_seq = f"{str(self.esc_seq)} {ch}"
        elif l == 4:
            self.esc_seq = f"{str(self.esc_seq)} {ord(char)}"
            self.mouse[2] = ord(char) - 32
            self.state = self.ESEQ_NONE
        self.mread += char


class readline(Mouse):
    # We arrange the state machine such that the current state is a dictionary
    # which contains the action routines to execute when a particular character
    # is received. The key is the character, and the value is the routine
    # to execute.
    #
    # The None key is used to process any characters which don't otherwise
    # appear in the state dictionary, and it will be passed the received
    # character as an argument.

    def __init__(self, ps1=None, log=None, get_size=False):
        self.ESEQ_NONE = {
            CTRL_A: self.home,
            CTRL_C: self.cancel,
            CTRL_D: self.eof,
            CTRL_E: self.end,
            CTRL_U: self.clear_before_cursor,
            BS: self.backspace,
            CR: self.line_complete,
            ESC: self.esc,
            # DEL: self.delete,
            DEL: self.backspace,
            None: self.typed_char,
        }

        self.ESEQ_ESC = {b"[": self.esc_bracket, b"O": self.esc_O, None: self.esc_typed_char}
        self.ESEQ_CSI = {
            b"A": self.up_arrow,
            b"B": self.down_arrow,
            b"C": self.right_arrow,
            b"D": self.left_arrow,
            b"H": self.home,
            b"F": self.end,
            b"M": self.csi_mouse,
            None: self.csi_typed_char,
        }
        self.ESEQ_CSI_DIGIT = {b"R": self.csi_digit_R, b"~": self.csi_digit_tilde, None: self.csi_digit_typed_char}
        self.ESEQ_ESC_O = {b"H": self.home, b"F": self.end, None: self.esc_O_typed_char}

        Mouse.__init__(self)

        self.state = self.ESEQ_NONE
        self.log = logger
        self.rows = 0
        self.columns = 0
        if ps1 is None:
            ps1 = ""
        self.ps1 = ps1
        self.overwrite = False
        self.write_queue = CmdWriteQueue(log)
        if get_size:
            self.get_window_size()
            # dhylands note: Apparently Windows will raise a value error for the following
            # signal.signal(signal.SIGWINCH, self.handle_sigwinch)
        self.reset(ps1)

        self.mouse = [0, 0, 0]

    def reset(self, line="", ps1=None):
        self.string = ""
        self.line = line
        self.esc_seq = ""
        self.caret = 0  # position within line that data entry will occur
        self.cursor_col = 0  # place that cursor is on the screen
        self.line_start = 0  # index of first character to draw
        self.ps1_width = 0
        self.inval_start = -1
        self.inval_end = -1
        self.input_width = 128
        self.resized = False
        if ps1 is None:
            ps1 = self.ps1
        self.set_ps1(ps1)
        self.write_queue.process()

    def handle_sigwinch(self, signum, frame):
        """Called when the terminal console changes sizes."""
        # It's not safe to do very much during a signal handler, so we just
        # set a flag that indicates that a signal was received and that's it.
        # self.log("SIGWINCH received")
        self.resized = True

    def get_cursor_location(self, func):
        if FBO:
            return
        self.write(REPORT_CURSOR_LOCATION)
        self.write_queue.queue_input(func)

    def get_window_size(self):
        if FBO:
            return
        self.write(REPORT_WINDOW_SIZE_1)
        self.get_cursor_location(self.store_window_size)
        self.write(REPORT_WINDOW_SIZE_2)

    def store_window_size(self, rows, cols):
        self.rows = rows
        self.columns = cols
        if self.resized:
            self.redraw()

    def set_ps1(self, ps1):
        self.ps1 = ps1
        if ps1:
            self.write(ps1)
            self.get_cursor_location(self.store_ps1_width)

    def store_ps1_width(self, rows, cols):
        self.ps1_width = cols

    def cancel(self):
        """Cancels the current line."""
        self.line = ""
        return self.line

    def clear_before_cursor(self):
        old_line_len = len(self.line)
        self.line = self.line[self.caret :]
        self.caret = 0
        self.invalidate(0, old_line_len)

    # ============================================================================

    def backspace(self):
        self.log("backspace")
        if self.caret > 0:
            old_line_len = len(self.line)
            self.line = self.line[: self.caret - 1] + self.line[self.caret :]
            self.caret -= 1
            self.invalidate(self.caret, old_line_len)

    def delete(self):
        self.log("delete")
        if self.caret < len(self.line):
            old_line_len = len(self.line)
            self.line = self.line[: self.caret] + self.line[self.caret + 1 :]
            self.invalidate(self.caret, old_line_len)

    # ============================================================================

    def down_arrow(self):
        self.state = self.ESEQ_NONE

    def end(self):
        """Moves the cursor to the end of the line."""
        self.caret = len(self.line)
        self.state = self.ESEQ_NONE

    def eof(self):
        if len(self.line) == 0:
            self.write("\r\n")
            self.write_queue.process()
            raise EOFError
        # Control-D acts like delete when the line is not empty
        return self.delete()

    def esc(self):
        """Starts an ESC sequence."""
        self.state = self.ESEQ_ESC
        self.esc_seq = ""

    def esc_bracket(self):
        """Starts an ESC [ sequence."""
        self.state = self.ESEQ_CSI

    def csi_digit_R(self):
        """Handle ESC [ 999 ; 999 R."""
        self.state = self.ESEQ_NONE
        num_str = self.esc_seq.split(";")
        try:
            rows = int(num_str[0])
            columns = int(num_str[1])
        except:
            # self.log("Unknown ESC [ '%s' R" % self.esc_seq)
            return
        self.write_queue.process_input(rows, columns)
        self.esc_seq = ""

    def csi_digit_tilde(self):
        """Handle ESC [ 9 ~ (where 9 was a digit)."""
        self.state = self.ESEQ_NONE
        if self.esc_seq == "3":
            return self.delete()
        if self.esc_seq == "2":
            return self.insert()
        if self.esc_seq == "1" or self.esc_seq == "7":
            return self.home()
        if self.esc_seq == "4" or self.esc_seq == "8":
            return self.end()
        # self.log("Unknown ESC [ '%s' ~" % self.esc_seq)

    def csi_digit_typed_char(self, char):
        """We've previously received ESC [ digit."""
        if (char >= b"0" and char <= b"9") or char == b";":
            self.esc_seq += chr(ord(char))
            return
        # self.log("Unknown ESC [ '%s' '%c' 0x%02x" % (self.esc_seq, printable(char), ord(char)))

    def csi_typed_char(self, char):
        """Unrecognized ESC [ sequence."""
        if char[0] >= 0 and char[0] <= 9:
            self.esc_seq = chr(ord(char))
            self.state = self.ESEQ_CSI_DIGIT
        else:
            # self.log("Unknown ESC [ '%c' 0x%02x" % (printable(char), ord(char)))
            self.state = self.ESEQ_NONE

    def esc_typed_char(self, char):
        """Unrecognized ESC sequence."""
        # self.log("Unknown ESC '%c' 0x%02x" % (printable(char), ord(char)))
        self.state = self.ESEQ_NONE

    def esc_O(self):
        self.state = self.ESEQ_ESC_O

    def esc_O_typed_char(self, char):
        """Unrecognized ESC O sequence."""
        # self.log("Unknown ESC O '%c' 0x%02x" % (printable(char), ord(char)))
        self.state = self.ESEQ_NONE

    def home(self):
        """Moves the cursor to the start of the line."""
        self.caret = 0
        self.state = self.ESEQ_NONE

    def insert(self):
        """Toggles between insert and overwrite mode."""
        self.overwrite = not self.overwrite

    def invalidate(self, from_pos, to_pos):
        from_col = from_pos - self.line_start
        to_col = to_pos - self.line_start
        if self.inval_start == -1:
            self.inval_start = from_col
            self.inval_end = to_col
        else:
            self.inval_start = min(from_col, self.inval_start)
            self.inval_end = max(to_col, self.inval_end)
        # self.log("invalidate(%d, %d) inval %d-%d" % (from_pos, to_pos, self.inval_start, self.inval_end))

    def left_arrow(self):
        if self.caret > 0:
            self.caret -= 1
        self.state = self.ESEQ_NONE

    def line_complete(self):
        """Final processing."""
        return self.line

    def right_arrow(self):
        if self.caret < len(self.line):
            self.caret += 1
        self.state = self.ESEQ_NONE

    def typed_char(self, char):
        """Handles regular characters."""
        if self.overwrite:
            self.line = self.line[: self.caret] + chr(char[0]) + self.line[self.caret + 1 :]
        else:
            self.line = self.line[: self.caret] + chr(char[0]) + self.line[self.caret :]
        # self.log("typed_char: len(self.line) = %d" % len(self.line))
        self.invalidate(self.caret, len(self.line))
        self.caret += 1

    def up_arrow(self):
        self.state = self.ESEQ_NONE

    def process_line(self, line):
        """Primarily for FBO. This basically runs a bunch of characters
        through process_char followed by a CR.
        """
        self.process_str(line)
        return self.process_char(CR)

    def process_bstr(self, bstring):
        """Calls process_char for each character in the string."""
        for byte in iter_byte(bstring):
            self.process_char(byte)

    def process_char(self, char):
        """Processes a single character of input."""
        self.prev_line_len = len(self.line)
        if char in self.state:
            action = self.state[char]
            args = tuple()
        else:
            action = self.state[None]
            args = (char,)

        #        if DEBUG:
        #            self.log(
        #                "process_char '%c' 0x%02x - Action %-20s caret = %2d line = %s esc_seq = '%s' (before)"
        #                % (printable(char), ord(char), action.__name__, self.caret, repr(self.line), self.esc_seq)
        #            )
        try:
            result = action(*args)
        except AssertionError as e:
            result = None
        #            self.log(
        #                e,
        #                "process_char '%c' 0x%02x - Action %-20s caret = %2d line = %s esc_seq = '%s' (after)"
        #                % (printable(char), ord(char), action.__name__, self.caret, repr(self.line), self.esc_seq),
        #            )

        if not FBO:
            self.redraw()

        self.string = self.line

        if result is not None:
            self.string += "\n"
            self.write("\r\n")
            self.line = ""
            self.caret = 0
        self.write_queue.process()
        return result

    def redraw(self):
        max_width = self.columns - self.ps1_width
        if max_width < 0:
            max_width = len(self.line)

        # max_width = min(10, max_width)

        # Make sure that the cursor stays in the visible area and scroll the
        # contents to make sure it does

        if self.caret < self.line_start:
            self.line_start = self.caret
            self.invalidate(self.line_start, self.line_start + max_width)
        if self.caret - self.line_start > max_width:
            self.line_start = self.caret - max_width
            self.invalidate(self.line_start, self.line_start + max_width)
        self.inval_end = min(max_width, self.inval_end)

        #        self.log(
        #            "redraw: inval %d-%d cursor: %d line_start: %d caret: %d max_width: %d ps1_width: %d columns: %d"
        #            % (
        #                self.inval_start,
        #                self.inval_end,
        #                self.cursor_col,
        #                self.line_start,
        #                self.caret,
        #                max_width,
        #                self.ps1_width,
        #                self.columns,
        #            )
        #        )

        if self.inval_start < self.inval_end:
            self.move_cursor_to_col(self.inval_start)
            line_end_col = len(self.line) - self.line_start
            write_cols = min(line_end_col - self.inval_start, self.inval_end - self.inval_start)
            start_idx = self.inval_start + self.line_start
            # self.log("redraw: write_cols = %d" % write_cols)
            self.write(self.line[start_idx : start_idx + write_cols])
            self.cursor_col += write_cols
            self.inval_start += write_cols
            if self.inval_start < self.inval_end:
                self.erase_line_from_cursor()
            self.inval_start = -1
            self.inval_end = -1
        # self.log("redraw: self.caret = %d self.line_start = %d" % (self.caret, self.line_start))
        self.move_cursor_to_col(self.caret - self.line_start)

    def erase_line_from_cursor(self):
        self.write("\x1b[K")

    def move_cursor_to_col(self, col):
        # self.log("move_cursor_to_col(%d)" % col)
        if col < self.cursor_col:
            cols = self.cursor_col - col
            #            if cols <= 4:
            #                self.write("\b\b\b\b"[:cols])
            #            else:
            self.write("\x1b[%uD" % cols)
            self.cursor_col -= cols
        elif col > self.cursor_col:
            cols = col - self.cursor_col
            self.write("\x1b[%uC" % cols)
            self.cursor_col += cols

    def write(self, string):
        if FBO:
            return
        # self.log("queued write(" + repr(string) + ")")
        self.write_queue.write(string)


def add_history(line: str):
    readline.history.append(line)


def get_history_item(index: int): ...


def get_current_history_length():
    return len(readline.history)
