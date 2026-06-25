# Author: Tom Sapletta · https://tom.sapletta.com
# Connector-agnostic CONTROL SURFACES (protocol clients) that any connector can adopt.
# A surface is the generic transport+protocol; the connector layers its own URI contract on top.
# cdp: a stdlib Chrome DevTools Protocol client — extracted from urirun-connector-kvm so kvm's
# find/act, browser-debug/webpage/chrome-plugin connectors, and the Twin window snapshot all
# share ONE CDP client instead of each re-implementing it.
