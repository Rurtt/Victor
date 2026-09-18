"""Victor visual tokens: Insta Sunset dark theme with solid colors. Only file with color values."""

BG = "#0C0A12"
SIDEBAR = "#14101D"
SURFACE = "#201A2C"
SURFACE_HI = "#2C2340"
TEXT = "#F7F2FA"
MUTED = "#B8AFC6"
PRIMARY = "#D62976"
PRIMARY_HOVER = "#E1306C"
ON_PRIMARY = "#FFFFFF"
ORANGE = "#F77737"
PURPLE = "#833AB4"
SUCCESS = "#34D399"
SUCCESS_BG = "#0B3326"
WARN = "#FBBF24"
WARN_BG = "#3A2A0A"
DANGER = "#F87171"

FAMILY = "Leelawadee UI"
TITLE, HEADING, BODY, LABEL, HINT = 24, 18, 15, 13, 12

RADIUS_BUTTON = 10
RADIUS_BUBBLE = 16
RADIUS_FIELD = 10

NARROW_WIDTH = 720  # logical px: below this the sidebar collapses into the ☰ menu
TINY_WIDTH = 440    # below this the status pill hides


def font(size=BODY, bold=False):
    # Tuples, not CTkFont objects: no Tk root needed and nothing tied to a destroyed window.
    return (FAMILY, size, "bold") if bold else (FAMILY, size)
