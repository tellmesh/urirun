# Author: Tom Sapletta · https://tom.sapletta.com
# Connector-agnostic INPUT primitives any os-level desktop connector can adopt.
# uinput: a pixel-accurate absolute pointer via a raw Linux /dev/uinput device — extracted from
# urirun-connector-kvm so every os-level connector shares the coordinate-exact click that fixed
# the Wayland hot-corner / capture-space≠action-space bug, instead of re-deriving the ABS scaling.
